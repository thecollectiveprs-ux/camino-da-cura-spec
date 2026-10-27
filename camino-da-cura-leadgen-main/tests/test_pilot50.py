import copy
import csv
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock,patch
from leadgen.config import Campaign
from leadgen.db import Database
from leadgen.discovery import discover
from leadgen.models import SearchResult
from leadgen.qualification import qualify,load_venue,import_research
from leadgen.clean_export import clean_exports
from leadgen.metrics import quality_metrics
from leadgen.webresearch import extract,research_website

class Pilot50Tests(unittest.TestCase):
    def setUp(self):
        self.config=load_venue('config/venue_uk_50.json')
        self.record=json.loads(Path('fixtures/camino_research.json').read_text())[0]
    def score(self,record): return qualify(record,self.config,today=date(2026,10,14))
    def test_domestic_and_portugal_score_identically(self):
        uk=copy.deepcopy(self.record)
        for c in uk['claims']:
            if c['kind']=='residential_event': c['country']='United Kingdom'
        self.assertEqual(self.score(uk)['lead_score'],self.score(self.record)['lead_score'])
        self.assertEqual(self.score(uk)['qualification_status'],'qualified')
        self.assertNotIn('international_experience',self.score(uk)['missing_information'])
    def test_any_country_no_portugal_preference(self):
        for country in ['United Kingdom','Portugal','Spain','India','Unknown']:
            record=copy.deepcopy(self.record)
            for c in record['claims']:
                if c['kind']=='residential_event': c['country']=country
            self.assertEqual(self.score(record)['lead_score'],100)
    def test_unknown_group_and_no_contact_retained(self):
        record=copy.deepcopy(self.record);record['claims']=[c for c in record['claims'] if c['kind'] not in {'group_size','contact'}]
        self.assertEqual(self.score(record)['lead_score'],75)
        self.assertEqual(self.score(record)['qualification_status'],'qualified')
    def test_non_uk_base_rejected(self):
        record=copy.deepcopy(self.record);record['claims'][0]['value']='France'
        self.assertEqual(self.score(record)['qualification_status'],'rejected')
    def test_queries_have_no_destination_or_exact_phrase_requirement(self):
        campaign=Campaign.load('campaigns/camino_uk_50.json')
        for query in campaign.queries():
            self.assertNotIn('"',query)
            for term in ['Portugal','Spain','Italy','Europe']:self.assertNotIn(term,query)
    def test_balanced_fifty_and_separate_partner_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Database(Path(tmp)/'direct.db');partners=Database(Path(tmp)/'partners.db')
            campaign=Campaign.load('campaigns/camino_uk_50.json')
            provider=Mock()
            def search(query,count):
                niche=next(i for i,g in enumerate(campaign.query_groups) if query.startswith(g['niche']))
                return [SearchResult(f'Yoga teacher {niche}-{i}: my retreats',f'https://leader{niche}-{i}.example','UK based residential retreats') for i in range(20)]+[SearchResult('Retreat directory','https://directory.example')]
            provider.search.side_effect=search
            report=discover(campaign,provider,db,partners)
            self.assertEqual(len(db.rows(campaign.name)),50)
            self.assertEqual(len(partners.rows(campaign.name)),1)
            self.assertEqual(provider.search.call_count,6)
            self.assertLessEqual(max(report['selected_by_niche'].values())-min(report['selected_by_niche'].values()),1)
            db.close();partners.close()
    def test_contact_source_and_cost_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Database(Path(tmp)/'db');campaign=Campaign.load('campaigns/camino_uk_50.json');db.register_campaign(campaign)
            record=copy.deepcopy(self.record)
            for c in record['claims']:
                if c['kind']=='contact':c['contact_attribution']='business_context'
            import_research(db,campaign.name,[record],self.config)
            out=Path(tmp)/'direct.csv';clean_exports(db,campaign.name,out,Path(tmp)/'partners.csv',include_contact_source=True)
            with out.open(encoding='utf-8-sig') as stream:row=next(csv.DictReader(stream))
            self.assertTrue(row['Contact source'])
            metrics=quality_metrics(db,campaign.name,self.config)
            self.assertEqual(metrics['contactable_businesses'],1)
            self.assertEqual(metrics['usable_leads'],1)
            self.assertEqual(metrics['estimated_gross_search_cost_usd'],0)
            db.close()
    def test_venue_email_not_organiser_email(self):
        claims=extract('<p>Venue contact: hotel@example.com</p><p>Contact us: hello@example.com</p>','https://leader.example/contact')['claims']
        result=qualify({'website':'https://leader.example','claims':claims},self.config)
        self.assertEqual([c['email'] for c in result['contacts']],['hello@example.com'])
    def test_contact_page_upgrades_attribution(self):
        fetcher=Mock()
        fetcher.fetch.side_effect=['<title>Yoga</title><p>hello@example.com</p><a href="/contact">Contact</a>','<p>hello@example.com</p>']
        record=research_website({'company_name':'Yoga','website':'https://leader.example'},fetcher)
        emails=[c for c in record['claims'] if c.get('email')]
        self.assertEqual(len(emails),1)
        self.assertEqual(emails[0]['source_url'],'https://leader.example/contact')
        self.assertEqual(emails[0]['contact_attribution'],'business_context')
        self.assertTrue(emails[0]['alternate_sources'])

    def test_full_fifty_command_mocked_no_live_calls(self):
        from leadgen.cli import main
        with tempfile.TemporaryDirectory() as tmp:
            provider=Mock()
            niches=Campaign.load('campaigns/camino_uk_50.json').query_groups
            def search(query,count):
                category=next(i for i,g in enumerate(niches) if query.startswith(g['niche']))
                return [SearchResult(f'Teacher {category}-{i} my retreats yoga',f'https://leader{category}-{i}.example','UK based residential retreats') for i in range(10)]+[SearchResult('Retreat directory','https://directory.example')]
            provider.search.side_effect=search
            fetcher=Mock();fetcher.fetch.return_value=Path('fixtures/html/home.html').read_text()+'<p>Contact us: hello@leader.example</p>'
            main_db=Path(tmp)/'direct.db';partner_db=Path(tmp)/'partners.db';output=Path(tmp)/'organisers.csv'
            with patch('leadgen.cli.BraveSearchProvider',return_value=provider),patch('leadgen.cli.PublicFetcher',return_value=fetcher),patch('builtins.print'):
                self.assertEqual(main(['--db',str(main_db),'pilot-50','--partners-db',str(partner_db),'--output',str(output),'--partners-output',str(Path(tmp)/'partners.csv'),'--max-requests','6']),0)
            summary=json.loads(Path(str(output)+'.summary.json').read_text())['quality_metrics']
            self.assertEqual(summary['discovered_direct_candidates'],50)
            self.assertEqual(summary['researched_businesses'],50)
            self.assertEqual(summary['partners_in_separate_database'],1)
            self.assertEqual(summary['brave_http_attempts'],6)
            self.assertEqual(summary['prospects_qualified'],0)
            self.assertGreater(summary['contactable_businesses'],0)
            self.assertEqual(provider.search.call_count,6)
            with output.open(encoding='utf-8-sig') as stream:self.assertIn('Contact source',csv.DictReader(stream).fieldnames)
    def test_small_cap_does_not_trigger_more_queries(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Database(Path(tmp)/'db');campaign=Campaign.load('campaigns/camino_uk_50.json');campaign.max_requests=2
            provider=Mock();provider.search.return_value=[]
            discover(campaign,provider,db)
            self.assertEqual(provider.search.call_count,2);db.close()

    def test_generic_yoga_urls_do_not_fill_fifty(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Database(Path(tmp)/'db');campaign=Campaign.load('campaigns/camino_uk_50.json');campaign.max_requests=1
            provider=Mock();provider.search.return_value=[SearchResult('Yoga studio London','https://studio.example','Daily yoga classes')]
            report=discover(campaign,provider,db)
            self.assertEqual(len(db.rows(campaign.name)),0)
            self.assertEqual(report['filtered_results'],1)
            self.assertEqual(db.conn.execute('SELECT selection_reason FROM discovery_results').fetchone()[0],'niche_practitioner_without_retreat_signal')
            db.close()
