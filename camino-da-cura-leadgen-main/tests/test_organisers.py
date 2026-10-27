import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from leadgen.config import Campaign
from leadgen.db import Database
from leadgen.discovery import discover
from leadgen.models import SearchResult
from leadgen.pipelines import classify
from leadgen.clean_export import clean_exports,HEADERS
from leadgen.webresearch import extract
from leadgen.qualification import qualify,load_venue,import_research

class OrganiserTests(unittest.TestCase):
    def test_pipeline_classification(self):
        self.assertEqual(classify('Yoga teacher: my retreats in Portugal'),'independent')
        self.assertEqual(classify('Our residential retreat programmes in Spain'),'boutique')
        for text in ['Retreat directory','Travel agency','Retreat booking platform','Venue broker','Find My Venue | Villas For Hire','Yoga Retreats Abroad | Expertly Curated Yoga Holidays','Best Yoga Retreat Venues to Hire in Europe']:
            self.assertEqual(classify(text),'partner')
        self.assertEqual(classify('Our favourite venues for hire'),'excluded')
    def test_named_and_generic_email(self):
        claims=extract('<p>Jane Smith - Pilates instructor</p><p>hello@example.com</p>','https://example.com')['claims']
        self.assertTrue(any(c.get('name')=='Jane Smith' for c in claims))
        self.assertTrue(any(c.get('email_type')=='generic_business' for c in claims))
    def test_contact_absence_does_not_lower_score(self):
        config=load_venue('config/venue.json')
        record=json.loads(Path('fixtures/camino_research.json').read_text())[0]
        with_contact=qualify(record,config)
        record['claims']=[c for c in record['claims'] if c['kind']!='contact']
        absent=qualify(record,config)
        self.assertEqual(absent['lead_score'],with_contact['lead_score'])
        self.assertEqual(absent['qualification_status'],'qualified')
    def test_search_diversity_dedupe_and_partners(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Database(Path(tmp)/'db'); campaign=Campaign.load('campaigns/camino_organisers.json'); campaign.target_prospects=1
            provider=Mock(); provider.search.return_value=[SearchResult('Jane yoga teacher: my retreats','https://teacher.example/retreats','UK based Portugal residential retreats'),SearchResult('Jane teacher','https://www.teacher.example/about','yoga retreats'),SearchResult('Retreat booking platform','https://platform.example','retreat directory')]
            report=discover(campaign,provider,db)
            self.assertEqual(provider.search.call_count,3)
            self.assertEqual(report['candidates_after_filtering'],1)
            self.assertEqual(report['partners_retained'],1)
            self.assertEqual(len(db.rows(campaign.name)),2)
            self.assertEqual(len({r['domain'] for r in db.rows(campaign.name)}),2)
            self.assertIn('http_attempts',report['per_request'][0]);db.close()
    def test_clean_export_headers_blanks_partner_and_suppression(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Database(Path(tmp)/'db');campaign=Campaign.load('campaigns/camino_organisers.json');campaign.max_requests=3
            provider=Mock();provider.search.return_value=[SearchResult('Jane yoga teacher: my retreats','https://teacher.example/retreats','Portugal retreat leader'),SearchResult('Retreat directory','https://directory.example')]
            discover(campaign,provider,db)
            organisers=Path(tmp)/'organisers.csv';partners=Path(tmp)/'partners.csv'
            result=clean_exports(db,campaign.name,organisers,partners)
            self.assertEqual(result,{'organisers':1,'partners':1})
            with organisers.open(encoding='utf-8-sig',newline='') as stream:
                reader=csv.DictReader(stream);self.assertEqual(reader.fieldnames,HEADERS);row=next(reader)
            self.assertEqual(row['Email'],'');self.assertEqual(row['Fit'],'Unassessed')
            self.assertEqual(row['UK location'],'')
            db.suppress('domain','directory.example','Opt out')
            self.assertEqual(clean_exports(db,campaign.name,organisers,partners)['partners'],0);db.close()
    def test_keyword_only_score_limited(self):
        record={'website':'https://example.com','claims':extract('<p>Yoga retreat wellness</p>','https://example.com')['claims']}
        result=qualify(record,load_venue('config/venue.json'))
        self.assertLessEqual(result['lead_score'],15)
        self.assertEqual(result['qualification_status'],'requires_review')
    def test_day_only_not_qualified(self):
        record=json.loads(Path('fixtures/camino_research.json').read_text())[0]
        record['claims']=[c for c in record['claims'] if c['kind']!='residential_event']
        result=qualify(record,load_venue('config/venue.json'))
        self.assertEqual(result['qualification_status'],'requires_review')

    def test_controlled_pilot_with_mocked_network(self):
        from leadgen.cli import main
        with tempfile.TemporaryDirectory() as tmp:
            provider=Mock();provider.search.return_value=[SearchResult(f'Teacher {i} my retreats yoga','https://teacher'+str(i)+'.example','UK based retreat leader Portugal residential') for i in range(5)]+[SearchResult('Retreat directory','https://partner.example')]
            fetcher=Mock();fetcher.fetch.return_value=Path('fixtures/html/home.html').read_text()
            output=Path(tmp)/'organisers.csv'
            with patch('leadgen.cli.BraveSearchProvider',return_value=provider),patch('leadgen.cli.PublicFetcher',return_value=fetcher),patch('leadgen.cli.clean_exports',wraps=clean_exports) as exporter,patch('builtins.print'):
                # Route both clean exports into the test directory.
                exporter.side_effect=lambda db,campaign,organisers: clean_exports(db,campaign,organisers,Path(tmp)/'partners.csv')
                self.assertEqual(main(['--db',str(Path(tmp)/'pilot.db'),'organiser-pilot','--output',str(output)]),0)
            self.assertEqual(provider.search.call_count,3)
            with output.open(encoding='utf-8-sig') as stream:self.assertEqual(len(list(csv.DictReader(stream))),5)
            with (Path(tmp)/'partners.csv').open(encoding='utf-8-sig') as stream:self.assertEqual(len(list(csv.DictReader(stream))),1)
