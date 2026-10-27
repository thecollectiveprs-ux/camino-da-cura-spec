import copy
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from leadgen.qualification import qualify, load_venue, import_research
from leadgen.config import Campaign
from leadgen.db import Database
from leadgen.export import export_csv
from leadgen.discovery import discover
from leadgen.providers import MockSearchProvider

class CaminoTests(unittest.TestCase):
    def setUp(self):
        self.config = load_venue('config/venue.json')
        self.records = json.loads(Path('fixtures/camino_research.json').read_text())
    def score(self, record):
        return qualify(record,self.config,today=date(2026,10,12))
    def test_complete_documented_score(self):
        result=self.score(self.records[0])
        self.assertEqual(result['lead_score'],100)
        self.assertEqual(result['priority_band'],'A')
        self.assertEqual(result['qualification_status'],'qualified')
        self.assertTrue(result['preferred_destination_experience'])
    def test_unknown_group_zero_and_flagged(self):
        result=self.score(self.records[1])
        self.assertEqual(result['lead_score'],75)
        self.assertEqual(result['priority_band'],'B')
        self.assertIn('compatible_group', result['missing_information'])
    def test_venue_rejected(self):
        self.assertEqual(self.score(self.records[2])['qualification_status'],'rejected')
    def test_large_group_requires_review(self):
        result=self.score(self.records[3])
        self.assertEqual(result['qualification_status'],'requires_review')
        self.assertIn('capacity mismatch', result['flags'][0])
        self.assertEqual(result['breakdown']['compatible_group']['points'],0)
    def test_studio_priority_three(self):
        result=self.score(self.records[4])
        self.assertEqual(result['discovery_priority'],3)
        self.assertEqual(result['priority_band'],'C')
    def test_advert_not_occurrence(self):
        result=self.score(self.records[5])
        self.assertEqual(result['breakdown']['residential_experience']['points'],0)
        self.assertEqual(result['breakdown']['international_experience']['points'],0)
    def test_unreviewed_and_inferences_zero(self):
        record=copy.deepcopy(self.records[0])
        for c in record['claims']: c['fact_status']='inference'
        self.assertEqual(self.score(record)['lead_score'],0)
    def test_non_uk_rejected(self):
        record=copy.deepcopy(self.records[0]); record['claims'][0]['value']='France'
        self.assertEqual(self.score(record)['qualification_status'],'rejected')
    def test_missing_base_cannot_qualify(self):
        record=copy.deepcopy(self.records[0]); record['claims']=record['claims'][1:]
        self.assertEqual(self.score(record)['qualification_status'],'requires_review')
    def test_owns_venue_flag(self):
        record=copy.deepcopy(self.records[0])
        record['claims']=[c for c in record['claims'] if c['kind']!='external_venues']
        record['claims'].append({**record['claims'][0],'kind':'owns_venue','value':True})
        self.assertEqual(self.score(record)['qualification_status'],'requires_review')
    def test_capacity_boundaries_and_unclear_basis(self):
        for size in (10,15):
            record=copy.deepcopy(self.records[0]); record['claims'][4]['value']=size
            self.assertEqual(self.score(record)['lead_score'],100)
        record['claims'][4]['basis']='guests_only'
        self.assertEqual(self.score(record)['breakdown']['compatible_group']['points'],0)
    def test_recent_and_future_past_event(self):
        record=copy.deepcopy(self.records[0]); record['claims'][6].update(activity_type='business_update',activity_date='2020-01-01')
        record['claims'][3]['event_date']='2027-01-01'
        result=self.score(record)
        self.assertEqual(result['breakdown']['recent_activity']['points'],0)
        self.assertEqual(result['breakdown']['residential_experience']['points'],0)
    def test_missing_provenance_fails(self):
        record=copy.deepcopy(self.records[0]); del record['claims'][0]['source_url']
        with self.assertRaises((ValueError,KeyError)): self.score(record)
    def test_weight_configuration_changes_score(self):
        self.config['weights']['compatible_group']=20
        self.config['weights']['recent_activity']=15
        self.assertEqual(self.score(self.records[1])['lead_score'],80)
    def test_import_repeat_campaign_scope_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Database(Path(tmp)/'leads.db')
            campaign=Campaign.load('campaigns/camino_uk.json')
            db.register_campaign(campaign)
            report=import_research(db,campaign.name,self.records,self.config)
            self.assertEqual(report,{'imported':6,'qualified':2,'rejected':1,'requires_review':3})
            import_research(db,campaign.name,self.records,self.config)
            self.assertEqual(len(db.rows(campaign.name)),6)
            self.assertEqual(db.rows()[0]['qualification_status'],'discovered')
            self.assertEqual(db.summary(campaign.name)['priority_bands'],{'A':1,'B':2,'C':3})
            out=Path(tmp)/'qualified.csv'
            self.assertEqual(export_csv(db,out,campaign=campaign.name),2)
            self.assertTrue(out.read_bytes().startswith(b'\xef\xbb\xbf'))
            row=next(r for r in db.rows(campaign.name) if r['domain']=='mock-yoga.example')
            self.assertEqual(row['email_verification_status'],'publicly_listed_not_verified')
            self.assertEqual(row['compliance_review_status'],'pending')
            db.close()
    def test_prospect_target_stops_discovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Database(Path(tmp)/'leads.db')
            report=discover(Campaign(target_prospects=2),MockSearchProvider(),db)
            self.assertEqual(report['queries_completed'],1)
            db.close()
    def test_reopen_preserves_legacy_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/'leads.db'; db=Database(file)
            discover(Campaign(),MockSearchProvider(),db); db.close()
            db=Database(file)
            self.assertEqual(len(db.rows()),2)
            self.assertEqual(db.conn.execute('PRAGMA user_version').fetchone()[0],2)
            db.close()

class MoreSafetyTests(unittest.TestCase):
    def test_secondary_contact_suppression(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Database(Path(tmp)/'leads.db')
            db.suppress('email','second@example.com','Opt out')
            self.assertTrue(db.is_suppressed({'domain':'example.com','business_email':'first@example.com','professional_contacts':[{'email':'second@example.com'}]}))
            db.close()
    def test_invalid_weights_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            config=load_venue('config/venue.json'); config['weights']['recent_activity']=11
            file=Path(tmp)/'venue.json'; file.write_text(json.dumps(config))
            with self.assertRaises(ValueError): load_venue(file)
