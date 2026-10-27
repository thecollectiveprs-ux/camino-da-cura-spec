import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from email.message import Message
from urllib.error import HTTPError
from leadgen.webresearch import extract, research_website, ResearchError, PublicFetcher
from leadgen.qualification import qualify, load_venue, import_research
from leadgen.db import Database
from leadgen.config import Campaign
from leadgen.models import SearchResult
from leadgen.export import export_csv

ROOT=Path('fixtures/html')
def html(name): return (ROOT/name).read_text()
class FixtureFetcher:
    def fetch(self,url):
        name={'https://clear.example':'home.html','https://clear.example/retreats':'retreats.html','https://clear.example/contact':'contact.html'}
        if url not in name: raise ResearchError('HTTP 404')
        return html(name[url])
class WebsiteTests(unittest.TestCase):
    def setUp(self): self.config=load_venue('config/venue.json')
    def record(self): return research_website({'company_name':'Clear Yoga Retreats','website':'https://clear.example'},FixtureFetcher())
    def test_extraction_and_attribution(self):
        data=extract(html('home.html'),'https://clear.example','2026-10-13')
        self.assertTrue(any(c['kind']=='base_country' for c in data['claims']))
        for c in data['claims']:
            self.assertEqual(c['source_url'],'https://clear.example')
            self.assertEqual(c['retrieved_at'],'2026-10-13')
            self.assertFalse(c['reviewed'])
    def test_emails_named_generic_unknown(self):
        claims=extract(html('contact.html'),'https://clear.example/contact')['claims']
        emails={c['email']:c for c in claims if c.get('email')}
        self.assertEqual(len(emails),3)
        self.assertEqual(emails['hello@clear.example']['email_type'],'generic_business')
        self.assertEqual(emails['jane@clear.example']['name'],'Jane Smith')
        self.assertEqual(emails['jane@clear.example']['role'],'Yoga teacher')
        self.assertEqual(emails['other@clear.example']['email_type'],'unknown')
        self.assertTrue(any(c.get('phone') for c in claims))
    def test_script_email_not_extracted(self):
        self.assertNotIn('secret@example.com',str(extract(html('home.html'),'https://clear.example')['claims']))
    def test_duplicate_contacts(self):
        record=self.record(); emails=[c['email'] for c in record['claims'] if c.get('email')]
        self.assertEqual(len(emails),len(set(emails)))
    def test_advert_not_occurrence(self):
        claims=extract('<p>Residential yoga retreat in Spain on 2020-05-01.</p>','https://clear.example')['claims']
        result=qualify({'website':'https://clear.example','claims':claims},self.config)
        self.assertEqual(result['breakdown']['residential_experience']['points'],0)
        self.assertEqual(result['breakdown']['international_experience']['points'],0)
    def test_venue_vs_organiser(self):
        result=qualify({'website':'https://venue.example','claims':extract(html('venue.html'),'https://venue.example')['claims']},self.config)
        self.assertEqual(result['qualification_status'],'rejected')
        self.assertTrue(any(c['kind']=='organises_retreats' for c in self.record()['claims']))
    def test_inaccessible_and_missing(self):
        fetcher=Mock(); fetcher.fetch.side_effect=ResearchError('blocked')
        record=research_website({'company_name':'Unknown','website':'https://unknown.example'},fetcher)
        result=qualify(record,self.config)
        self.assertEqual(result['lead_score'],0)
        self.assertEqual(result['qualification_status'],'requires_review')
        self.assertTrue(record['research_metadata']['errors'])
    def test_capacity_mismatch(self):
        claims=extract('<p>Our retreat has a total group size: 40 participants.</p>','https://clear.example')['claims']
        result=qualify({'website':'https://clear.example','claims':claims},self.config)
        self.assertIn('capacity mismatch',result['flags'][0])
    def test_directory_not_fetched(self):
        fetcher=Mock()
        record=research_website({'company_name':'Directory','website':'https://bookretreats.com'},fetcher)
        fetcher.fetch.assert_not_called()
        self.assertTrue(record['research_metadata']['review_flags'])
    def test_end_to_end_database_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Database(Path(tmp)/'leads.db'); db.register_campaign(Campaign(name='web'))
            result=import_research(db,'web',[self.record()],self.config)
            self.assertEqual(result['requires_review'],1)
            row=db.rows('web')[0]
            self.assertEqual(row['lead_score'],100)
            self.assertEqual(row['compliance_review_status'],'pending')
            self.assertIn('https://clear.example/contact',row['official_contact_pages'])
            out=Path(tmp)/'out.csv'; self.assertEqual(export_csv(db,out,campaign='web',status='all'),1)
            self.assertIn('publisher_statement',out.read_text(encoding='utf-8-sig'))
            db.close()
    def test_manual_assessment_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Database(Path(tmp)/'db'); db.register_campaign(Campaign(name='web'))
            record=self.record(); record.pop('research_metadata')
            import_research(db,'web',[record],self.config)
            result=import_research(db,'web',[self.record()],self.config)
            self.assertEqual(result['preserved_manual_assessments'],1); db.close()

class FetcherTests(unittest.TestCase):
    def response(self,text,content='text/html',url='https://clear.example'):
        response=io.BytesIO(text.encode()); headers=Message(); headers['Content-Type']=content
        response.headers=headers; response.geturl=lambda:url
        return response
    def fetcher(self,opener):
        return PublicFetcher(opener=opener,sleep=Mock(),resolver=lambda *a,**k:[(2,1,6,'',('93.184.216.34',443))])
    def test_robots_disallow(self):
        opener=Mock(return_value=self.response('User-agent: *\nDisallow: /', 'text/plain','https://clear.example/robots.txt'))
        with self.assertRaises(ResearchError): self.fetcher(opener).fetch('https://clear.example')
        self.assertEqual(opener.call_count,1)
    def test_missing_robots_allowed(self):
        opener=Mock(side_effect=[HTTPError('',404,'',{},None),self.response('<p>Public</p>')])
        self.assertIn('Public',self.fetcher(opener).fetch('https://clear.example'))
    def test_robots_unavailable_stops(self):
        opener=Mock(side_effect=HTTPError('',403,'',{},None))
        with self.assertRaises(ResearchError): self.fetcher(opener).fetch('https://clear.example')
        self.assertEqual(opener.call_count,1)
    def test_private_network_blocked(self):
        fetcher=PublicFetcher(resolver=lambda *a,**k:[(2,1,6,'',('127.0.0.1',443))])
        with self.assertRaises(ResearchError): fetcher.validate('https://clear.example')
    def test_access_control_stops(self):
        opener=Mock(return_value=self.response('Verify you are human'))
        with self.assertRaises(ResearchError): self.fetcher(opener).raw('https://clear.example')
    def test_redirect_not_followed(self):
        opener=Mock(side_effect=HTTPError('',302,'',{'Location':'http://localhost'},None))
        with self.assertRaises(ResearchError): self.fetcher(opener).raw('https://clear.example')
    def test_max_page_budget(self):
        fetcher=FixtureFetcher(); record=research_website({'company_name':'Clear Yoga','website':'https://clear.example'},fetcher,max_pages=1)
        self.assertEqual(len(record['research_metadata']['pages']),1)

class PilotTests(unittest.TestCase):
    def test_ten_candidate_cli_without_network(self):
        from unittest.mock import patch
        from leadgen.cli import main
        with tempfile.TemporaryDirectory() as tmp:
            dbfile=Path(tmp)/'pilot.db'; csvfile=Path(tmp)/'pilot.csv'
            provider=Mock(); provider.search.return_value=[SearchResult('Clear Yoga',f'https://business{i}.example') for i in range(12)]
            fetcher=Mock(); fetcher.fetch.return_value=html('home.html')
            with patch('leadgen.cli.BraveSearchProvider',return_value=provider), patch('leadgen.cli.PublicFetcher',return_value=fetcher), patch('builtins.print'):
                self.assertEqual(main(['--db',str(dbfile),'pilot','--limit','10','--output',str(csvfile)]),0)
            db=Database(dbfile)
            self.assertEqual(len(db.rows('camino-uk')),10)
            self.assertEqual(db.conn.execute('SELECT count(*) FROM website_research').fetchone()[0],10)
            self.assertTrue(csvfile.exists()); self.assertTrue(Path(str(csvfile)+'.summary.json').exists())
            provider.search.assert_called_once(); db.close()
    def test_manual_preservation_still_stores_website_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Database(Path(tmp)/'db'); db.register_campaign(Campaign(name='web'))
            record=research_website({'company_name':'Clear Yoga','website':'https://clear.example'},FixtureFetcher())
            manual=dict(record); manual.pop('research_metadata')
            config=load_venue('config/venue.json')
            import_research(db,'web',[manual],config); import_research(db,'web',[record],config)
            self.assertEqual(db.conn.execute('SELECT count(*) FROM website_research').fetchone()[0],1)
            db.close()
