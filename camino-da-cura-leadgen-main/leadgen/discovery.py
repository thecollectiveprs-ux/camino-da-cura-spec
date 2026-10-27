import logging
from .providers import SearchError
from .selection import candidate_quality,initial_screen
from .pipelines import classify,route
from .models import canonical_domain
from .db import now
import json
import re

log = logging.getLogger(__name__)

def discover(campaign, provider, database, partner_database=None):
    if campaign.organiser_mode: return discover_organisers(campaign,provider,database,partner_database)
    database.register_campaign(campaign)
    report = {"new": 0, "existing_results": 0, "invalid_urls": 0, "queries_completed": 0, "errors": [], "search_results_retrieved":0, "candidates_after_filtering":0, "filtered_results":0}
    for query in campaign.queries()[:campaign.max_requests]:
        if campaign.target_prospects and len(database.rows(campaign.name)) >= campaign.target_prospects:
            break
        try:
            log.info('Search query: %s',query)
            results = provider.search(query, campaign.results_per_query)
            log.info('Search returned %s results',len(results))
        except SearchError as exc:
            report['errors'].append(str(exc))
            log.error("Discovery stopped: %s", exc)
            break
        report['search_results_retrieved'] += len(results)
        ranked=[]
        for result in results:
            try:
                rank,reason=candidate_quality(result) if campaign.filter_candidates else (10,'legacy_unfiltered')
            except ValueError:
                rank,reason=0,'invalid_url'
            with database.conn:
                database.conn.execute('INSERT INTO discovery_results(campaign,query,source_url,title,description,selection_reason,rank,retrieved_at) VALUES (?,?,?,?,?,?,?,?)',(campaign.name,query,result.url,result.title,result.description,reason,rank,now()))
            if rank: ranked.append((rank,result))
            else: report['filtered_results'] += 1
        report['candidates_after_filtering'] += len(ranked)
        for rank,result in sorted(ranked,key=lambda pair:pair[0],reverse=True):
            if campaign.target_prospects and len(database.rows(campaign.name)) >= campaign.target_prospects:
                break
            try:
                created = database.upsert(campaign.name, result, query)
                report['new' if created else 'existing_results'] += 1
            except ValueError:
                report['invalid_urls'] += 1
        report['queries_completed'] += 1
        if campaign.target_prospects and len(database.rows(campaign.name)) >= campaign.target_prospects:
            break
    with database.conn:
        database.conn.execute('INSERT INTO discovery_runs(campaign,report_json,created_at) VALUES (?,?,?)',(campaign.name,json.dumps(report),now()))
    return report


def discover_organisers(campaign,provider,database,partner_database=None):
    database.register_campaign(campaign)
    report={'new':0,'existing_results':0,'invalid_urls':0,'queries_completed':0,'errors':[],'search_results_retrieved':0,'filtered_results':0,'candidates_after_filtering':0,'per_request':[]}
    pool={};partners={}
    if partner_database: partner_database.register_campaign(campaign)
    candidate_categories={}
    for index,query in enumerate(campaign.queries()[:campaign.max_requests]):
        log.info('Organiser search category %s: %s',index%len(campaign.query_groups)+1,query)
        before=getattr(provider,'attempts',0)
        if not isinstance(before,int): before=0
        try: results=provider.search(query,campaign.results_per_query)
        except SearchError as exc:
            report['errors'].append(str(exc))
            report['per_request'].append({'query':query,'http_attempts':1,'results_returned':0,'error':str(exc),'attempt_count_basis':'Conservative failed-call estimate; billing unknown'})
            log.error('Search stopped: %s',exc)
            break
        report['queries_completed']+=1; report['search_results_retrieved']+=len(results)
        signals=set()
        for result in results:
            try:
                domain=canonical_domain(result.url)
                rank,reason,pipeline=initial_screen(result)
                if campaign.require_retreat_signal and pipeline!='partner' and not re.search(r'retreat|residential|overnight',result.title+' '+result.description,re.I):
                    rank=0;reason='niche_practitioner_without_retreat_signal'
            except ValueError:
                report['invalid_urls']+=1;continue
            with database.conn:
                database.conn.execute('INSERT INTO discovery_results(campaign,query,source_url,title,description,selection_reason,rank,retrieved_at) VALUES (?,?,?,?,?,?,?,?)',(campaign.name,query,result.url,result.title,result.description,reason,rank,now()))
            log.info('Screened %s: %s (rank %s, pipeline %s)',result.url,reason,rank,pipeline)
            if pipeline=='partner': partners.setdefault(domain,[]).append((result,query,pipeline));continue
            if pipeline=='excluded' or not rank: report['filtered_results']+=1;continue
            pool.setdefault(domain,[]).append((rank,result,query,pipeline))
            candidate_categories.setdefault(domain,index%len(campaign.query_groups))
            if rank>=30: signals.add(domain)
        after=getattr(provider,'attempts',before+1)
        requests=max(1,after-before) if isinstance(after,int) else 1
        report['per_request'].append({'query':query,'http_attempts':requests,'results_returned':len(results),'organiser_intent_results':len(signals),'unique_direct_candidates_so_far':len(pool)})
        strong=sum(max(item[0] for item in values)>=30 for values in pool.values())
        if report['queries_completed']>=campaign.minimum_queries and strong>=(campaign.target_prospects or 100):break
    buckets={category:[] for category in range(len(campaign.query_groups))}
    for domain,values in pool.items(): buckets[candidate_categories[domain]].append(values)
    for values in buckets.values(): values.sort(key=lambda entries:max(item[0] for item in entries),reverse=True)
    selected=[]
    while any(buckets.values()) and len(selected)<(campaign.target_prospects or 100):
        for category,values in buckets.items():
            if values and len(selected)<(campaign.target_prospects or 100): selected.append(values.pop(0))
    for values in selected:
        for rank,result,query,pipeline in sorted(values,key=lambda item:item[0],reverse=True):
            created=database.upsert(campaign.name,result,query)
            report['new' if created else 'existing_results']+=1
        pid=database.conn.execute('SELECT id FROM prospects WHERE domain=?',(canonical_domain(values[0][1].url),)).fetchone()[0]
        best=max(values,key=lambda item:item[0])
        route(database,campaign.name,pid,best[3],'Provisional search signal; website evidence required')
    partner_store=partner_database or database
    for values in partners.values():
        for result,query,pipeline in values: partner_store.upsert(campaign.name,result,query)
        pid=partner_store.conn.execute('SELECT id FROM prospects WHERE domain=?',(canonical_domain(values[0][0].url),)).fetchone()[0]
        route(partner_store,campaign.name,pid,'partner','Directory/marketplace/agency; not a direct organiser')
    report['selected_by_niche']={campaign.query_groups[i]['niche']:sum(candidate_categories[canonical_domain(v[0][1].url)]==i for v in selected) for i in range(len(campaign.query_groups))}
    report['candidates_after_filtering']=len(selected); report['partners_retained']=len(partners)
    attempts=sum(r['http_attempts'] for r in report['per_request'])
    report['unique_organiser_candidates_per_request']=len(selected)/attempts if attempts else 0
    report['yield_definition']='Provisional organiser-intent candidates per HTTP attempt; not website-verified organisers.'
    with database.conn: database.conn.execute('INSERT INTO discovery_runs(campaign,report_json,created_at) VALUES (?,?,?)',(campaign.name,json.dumps(report),now()))
    return report
