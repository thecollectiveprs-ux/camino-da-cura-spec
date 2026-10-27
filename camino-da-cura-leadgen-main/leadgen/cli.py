import argparse
import json
import logging
import os
import sqlite3
from .config import Campaign
from .db import Database
from .discovery import discover
from .export import export_csv
from .clean_export import clean_exports
from pathlib import Path
from .qualification import load_venue, import_research
from .directory_sources import expand_directory_sources
from .metrics import quality_metrics
from .webresearch import PublicFetcher, research_website
from .providers import BraveSearchProvider, MockSearchProvider


def main(argv=None):
    parser = argparse.ArgumentParser(description='Evidence-first B2B prospect discovery (milestone 1)')
    parser.add_argument('--db', default='data/leads.sqlite3')
    commands = parser.add_subparsers(dest='command', required=True)
    search = commands.add_parser('discover')
    search.add_argument('--campaign', default='campaigns/camino_uk.json')
    search.add_argument('--dry-run', action='store_true', help='Persist synthetic fixtures to an isolated demo database by default')
    search.add_argument('--provider', choices=['brave'], default='brave')
    research = commands.add_parser('research')
    research.add_argument('--input', required=True, help='Reviewed evidence JSON; no automatic web fetch')
    research.add_argument('--campaign', default='campaigns/camino_uk.json')
    research.add_argument('--venue', default='config/venue.json')
    auto = commands.add_parser('research-web')
    auto.add_argument('--campaign',default='campaigns/camino_uk.json')
    auto.add_argument('--venue',default='config/venue.json')
    auto.add_argument('--limit',type=int,default=10)
    auto.add_argument('--max-pages',type=int,default=6)
    pilot = commands.add_parser('pilot')
    pilot.add_argument('--campaign',default='campaigns/camino_uk.json')
    pilot.add_argument('--venue',default='config/venue.json')
    pilot.add_argument('--limit',type=int,default=10)
    pilot.add_argument('--max-requests',type=int,default=10)
    pilot.add_argument('--output',default='exports/camino-pilot-10.csv')
    organiser_pilot=commands.add_parser('organiser-pilot')
    organiser_pilot.add_argument('--campaign',default='campaigns/camino_organisers.json')
    organiser_pilot.add_argument('--venue',default='config/venue.json')
    organiser_pilot.add_argument('--output',default='exports/organiser-leads.csv')
    organiser_pilot.add_argument('--partners-output',help='Optional separate partner CSV path')
    organiser_pilot.add_argument('--limit',type=int,default=5)
    organiser_pilot.add_argument('--max-requests',type=int,default=6)
    pilot50=commands.add_parser('pilot-50')
    pilot50.add_argument('--campaign',default='campaigns/camino_uk_50.json')
    pilot50.add_argument('--venue',default='config/venue_uk_50.json')
    pilot50.add_argument('--limit',type=int,default=50)
    pilot50.add_argument('--max-requests',type=int,default=40)
    pilot50.add_argument('--output',default='exports/organiser-leads-50.csv')
    pilot50.add_argument('--partners-output',default='exports/directory-partners-50.csv')
    pilot50.add_argument('--partners-db',default='data/camino-partners-50.sqlite3')
    clean=commands.add_parser('export-clean')
    clean.add_argument('--campaign',default='camino-organisers')
    clean.add_argument('--organisers',default='exports/organiser-leads.csv')
    clean.add_argument('--partners',default='exports/directory-partners.csv')
    report = commands.add_parser('report')
    report.add_argument('--campaign')
    report.add_argument('--output', help='Optional JSON summary file')
    export = commands.add_parser('export')
    export.add_argument('--output', default='exports/leads.csv')
    export.add_argument('--campaign')
    export.add_argument('--status', choices=['all','qualified','discovered','rejected','requires_review'], default='qualified')
    export.add_argument('--purpose', choices=['review','outreach'], default='review')
    export.add_argument('--approved-by')
    suppression = commands.add_parser('suppress')
    suppression.add_argument('--kind', choices=['domain','email'], required=True)
    suppression.add_argument('--value', required=True)
    suppression.add_argument('--reason', required=True)
    args = parser.parse_args(argv)
    Path('logs').mkdir(exist_ok=True)
    handler=logging.FileHandler('logs/pilot.log',encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logger=logging.getLogger('leadgen')
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    logger.info('Starting %s; database=%s; no interactive prompts',args.command,args.db)
    database = None
    partner_database=None
    try:
        if args.command == 'discover':
            campaign = Campaign.load(args.campaign)
            provider = MockSearchProvider() if args.dry_run else BraveSearchProvider(os.environ.get('BRAVE_SEARCH_API_KEY'),country=campaign.search_country,max_requests=campaign.max_requests,interval_seconds=campaign.interval_seconds,retries=campaign.retries)
            if args.dry_run and args.db == 'data/leads.sqlite3':
                args.db = 'data/demo.sqlite3'
        database = Database(args.db)
        if args.command == 'discover':
            result = discover(campaign, provider, database)
            print(json.dumps(result, indent=2))
            return 1 if result['errors'] else 0
        if args.command in {'research-web','pilot','organiser-pilot','pilot-50'}:
            if not 1<=args.limit<=100 or not 1<=getattr(args,'max_pages',6)<=20:
                raise ValueError('Business limit must be 1–100 and max pages 1–20')
            campaign=Campaign.load(args.campaign)
            config=load_venue(args.venue)
            database.register_campaign(campaign)
            if args.command in {'pilot','organiser-pilot','pilot-50'}:
                if not 1<=args.max_requests<=100: raise ValueError('Request budget must be 1–100')
                campaign.target_prospects=args.limit
                campaign.results_per_query=20 if campaign.organiser_mode else min(args.limit,20)
                campaign.max_requests=args.max_requests
                campaign.minimum_queries=min(campaign.minimum_queries,args.max_requests)
                provider=BraveSearchProvider(os.environ.get('BRAVE_SEARCH_API_KEY'),country=campaign.search_country,max_requests=campaign.max_requests,interval_seconds=campaign.interval_seconds,retries=campaign.retries)
                logger.info('Stage: discovery (up to %s requests)',args.max_requests)
                if args.command=='pilot-50':
                    if Path(args.db).resolve()==Path(args.partners_db).resolve(): raise ValueError('Partner database must be separate')
                    partner_database=Database(args.partners_db)
                    partner_database.register_campaign(campaign)
                    discovery_result=discover(campaign,provider,database,partner_database)
                else:
                    discovery_result=discover(campaign,provider,database)
                logger.info('Discovery complete: %s candidates',len(database.rows(campaign.name)))
            fetcher=PublicFetcher()
            if args.command=='pilot':
                discovery_result['directory_sources']=expand_directory_sources(database,campaign.name,fetcher,args.limit)
            rows=[row for row in database.rows(campaign.name) if row.get('pipeline') not in {'partner','excluded'} and not database.is_suppressed(row)][:args.limit]
            logger.info('Stage: website research; %s businesses; 90s per business',len(rows))
            for index,row in enumerate(rows,1):
                logger.info('Business %s/%s: %s',index,len(rows),row['website'])
                record=research_website(row,fetcher,max_pages=getattr(args,'max_pages',6))
                outcome=import_research(database,campaign.name,[record],config)
                if partner_database and database.rows(campaign.name) and record.get('pipeline')=='partner':
                    import_research(partner_database,campaign.name,[record],config)
                elif partner_database:
                    assessed=next((r for r in database.rows(campaign.name) if r['domain']==row['domain']),None)
                    if assessed and assessed.get('pipeline')=='partner':
                        record['pipeline']='partner'
                        import_research(partner_database,campaign.name,[record],config)
                logger.info('Saved business %s/%s: %s',index,len(rows),outcome)
                if args.command=='pilot-50':
                    logger.info('Coverage: %s',quality_metrics(database,campaign.name,config))
            print(json.dumps(database.summary(campaign.name),indent=2),flush=True)
            if args.command in {'pilot','organiser-pilot','pilot-50'}:
                logger.info('Stage: exporting CSV to %s',args.output)
                if args.command=='pilot-50':
                    clean_exports(database,campaign.name,args.output,args.partners_output,include_contact_source=True,partner_database=partner_database)
                elif args.command=='organiser-pilot':
                    if args.partners_output:
                        clean_exports(database,campaign.name,organisers=args.output,partners=args.partners_output)
                    else:
                        clean_exports(database,campaign.name,organisers=args.output)
                else:
                    export_csv(database,args.output,campaign=campaign.name,status='all')
                report_payload={**database.summary(campaign.name),'quality_metrics':quality_metrics(database,campaign.name,config),'discovery_run':discovery_result}
                if partner_database: report_payload['quality_metrics']['partners_in_separate_database']=len(partner_database.rows(campaign.name))
                Path(args.output+'.summary.json').write_text(json.dumps(report_payload,indent=2),encoding='utf-8')
                print('CSV saved: '+args.output)
                if args.command=='pilot-50':
                    summary_metrics=quality_metrics(database,campaign.name,config)
                    summary_metrics['partners_in_separate_database']=len(partner_database.rows(campaign.name))
                    logger.info('Final pilot counts: %s',summary_metrics)
                    print(json.dumps(summary_metrics,indent=2),flush=True)
                if discovery_result['errors']: return 1
        elif args.command == 'research':
            campaign = Campaign.load(args.campaign)
            records = json.loads(Path(args.input).read_text(encoding='utf-8'))
            config = load_venue(args.venue)
            database.register_campaign(campaign)
            print(json.dumps(import_research(database,campaign.name,records,config),indent=2))
        elif args.command == 'report':
            summary = json.dumps({**database.summary(args.campaign), **({'quality_metrics':quality_metrics(database,args.campaign)} if args.campaign else {})}, indent=2)
            print(summary)
            if args.output:
                Path(args.output).parent.mkdir(parents=True,exist_ok=True)
                Path(args.output).write_text(summary,encoding='utf-8')
        elif args.command == 'export-clean':
            print(json.dumps(clean_exports(database,args.campaign,args.organisers,args.partners)))
        elif args.command == 'export':
            print(json.dumps({'exported':export_csv(database,args.output,campaign=args.campaign,status=args.status,purpose=args.purpose,approved_by=args.approved_by),'path':args.output}))
        elif args.command == 'suppress':
            database.suppress(args.kind,args.value,args.reason)
            print('Suppression recorded')
        return 0
    except (ValueError, TypeError, KeyError, OSError, sqlite3.Error) as exc:
        parser.exit(2, f'Error: {exc}\n')
    except KeyboardInterrupt:
        logger.warning("Interrupted; completed businesses remain saved. Resume with research-web to avoid search charges.")
        return 130
    finally:
        logger.removeHandler(handler)
        handler.close()
        if database: database.close()
        if partner_database: partner_database.close()
