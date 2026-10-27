import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError, URLError
from unittest.mock import Mock
from leadgen.config import Campaign
from leadgen.models import SearchResult, canonical_domain
from leadgen.providers import BraveSearchProvider, MockSearchProvider, SearchError
from leadgen.db import Database
from leadgen.discovery import discover
from leadgen.export import export_csv, safe_cell
from leadgen.cli import main

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp.name) / 'test.sqlite3')
        self.campaign = Campaign()
    def tearDown(self):
        self.db.close()
        self.temp.cleanup()
    def test_repeat_runs_preserve_identity_and_review(self):
        discover(self.campaign, MockSearchProvider(), self.db)
        self.db.conn.execute("UPDATE prospects SET company_name='Reviewed name',legal_form='limited_company'")
        self.db.conn.commit()
        discover(self.campaign, MockSearchProvider(), self.db)
        self.assertEqual(len(self.db.rows()), 2)
        self.assertEqual(self.db.rows()[0]['company_name'], 'Reviewed name')
        self.assertIsNone(self.db.rows()[0]['date_last_verified'])
        self.assertEqual(self.db.conn.execute('SELECT count(*) FROM evidence').fetchone()[0], 6)
    def test_default_qualified_export_empty(self):
        discover(self.campaign, MockSearchProvider(), self.db)
        output = Path(self.temp.name) / 'leads.csv'
        self.assertEqual(export_csv(self.db, output), 0)
        self.assertIn('business_email', output.read_text(encoding='utf-8-sig'))
    def test_review_export_sources_and_suppression(self):
        discover(self.campaign, MockSearchProvider(), self.db)
        self.db.suppress('domain', 'www.demo-studio.example', 'Opt out')
        output = Path(self.temp.name) / 'review.csv'
        self.assertEqual(export_csv(self.db, output, status='all'), 1)
        with output.open(encoding='utf-8-sig', newline='') as stream:
            row = next(csv.DictReader(stream))
        self.assertTrue(json.loads(row['evidence']))
        self.assertEqual(row['marketing_eligibility'], 'requires_review')
    def test_outreach_approval_and_compliance(self):
        discover(self.campaign, MockSearchProvider(), self.db)
        output = Path(self.temp.name) / 'outreach.csv'
        with self.assertRaises(ValueError): export_csv(self.db, output, purpose='outreach')
        self.assertEqual(export_csv(self.db, output, purpose='outreach', approved_by='Reviewer'), 0)
    def test_campaign_scope(self):
        discover(self.campaign, MockSearchProvider(), self.db)
        self.assertEqual(self.db.rows('another-campaign'), [])
        self.assertEqual(self.db.summary()['discovered'], 2)
    def test_invalid_url_skipped(self):
        provider = Mock()
        provider.search.return_value = [SearchResult('Invalid', 'file:///secret')]
        result = discover(self.campaign, provider, self.db)
        self.assertEqual(result['invalid_urls'], 2)
    def test_failure_reported(self):
        provider = Mock()
        provider.search.side_effect = SearchError('Unavailable')
        self.assertEqual(discover(self.campaign, provider, self.db)['errors'], ['Unavailable'])

class ProviderTests(unittest.TestCase):
    def response(self, data):
        return io.StringIO(json.dumps(data))
    def test_api_mapping(self):
        opener = Mock(return_value=self.response({'web':{'results':[{'title':'Retreat','url':'https://retreat.example','description':'Evidence'}]}}))
        provider = BraveSearchProvider('test-secret', opener=opener)
        self.assertEqual(provider.search('yoga', 20)[0].description, 'Evidence')
        self.assertIn('country=GB', opener.call_args.args[0].full_url)
    def test_retry_and_budget(self):
        sleep = Mock()
        opener = Mock(side_effect=[HTTPError('https://api.example',429,'limited',{'Retry-After':'3'},None),self.response({})])
        provider = BraveSearchProvider('test',opener=opener,sleep=sleep,max_requests=2)
        self.assertEqual(provider.search('yoga',20), [])
        sleep.assert_any_call(3.0)
        with self.assertRaises(SearchError): provider.search('again',20)
        self.assertEqual(opener.call_count, 2)
    def test_auth_error_no_retry(self):
        opener = Mock(side_effect=HTTPError('https://api.example',401,'auth',{},None))
        with self.assertRaises(SearchError): BraveSearchProvider('test',opener=opener).search('yoga',20)
        self.assertEqual(opener.call_count,1)
    def test_malformed_response(self):
        with self.assertRaises(SearchError): BraveSearchProvider('test',opener=Mock(return_value=io.StringIO('invalid'))).search('yoga',20)
    def test_network_retry_exhausted(self):
        opener = Mock(side_effect=URLError('offline'))
        with self.assertRaises(SearchError): BraveSearchProvider('test',opener=opener,sleep=Mock(),retries=1).search('yoga',20)
        self.assertEqual(opener.call_count,2)

class ValidationTests(unittest.TestCase):
    def test_domain(self):
        self.assertEqual(canonical_domain('https://WWW.Example.CO.UK/path?x=1'), 'example.co.uk')
        for url in ['file:///tmp', 'https://localhost', 'https://127.0.0.1', 'https://user:pass@example.com']:
            with self.assertRaises(ValueError): canonical_domain(url)
    def test_config(self):
        for config in [{'max_requests':0},{'retries':9},{'interval_seconds':0},{'locations':[]}]:
            with self.assertRaises(ValueError): Campaign(**config)
    def test_csv_injection(self):
        for value in ['=SUM(A1)', ' +CMD', '@cmd', '\tcommand']:
            self.assertTrue(safe_cell(value).startswith("'"))
        self.assertEqual(safe_cell('Yoga'), 'Yoga')

if __name__ == '__main__': unittest.main()
