import time
import unittest
from unittest.mock import Mock,patch
from leadgen.deadlines import bounded_call,DeadlineExceeded
from leadgen.webresearch import PublicFetcher,ResearchError,PageText,research_website

def stalled(): time.sleep(10)
def completed(): return PageText('local HTML','https://clear.example',[])
def failed(): raise ResearchError('Timed out','request_timeout')

class DeadlineTests(unittest.TestCase):
    def test_stalled_worker_is_terminated(self):
        started=time.monotonic()
        with self.assertRaises(DeadlineExceeded): bounded_call(stalled,(),0.3,'fixture')
        self.assertLess(time.monotonic()-started,4)
    def test_successful_worker_serializes_source(self):
        result=bounded_call(completed,(),5,'fixture')
        self.assertEqual(result.source_url,'https://clear.example')
    def test_worker_error_preserves_category(self):
        with self.assertRaises(ResearchError) as error: bounded_call(failed,(),5,'fixture')
        self.assertEqual(error.exception.category,'request_timeout')
    def test_request_deadline_becomes_reviewable_failure(self):
        fetcher=PublicFetcher()
        with patch('leadgen.webresearch.bounded_call',side_effect=DeadlineExceeded('fixture timeout')):
            record=research_website({'company_name':'Yoga','website':'https://clear.example'},fetcher)
        self.assertEqual(record['research_metadata']['errors'][0]['category'],'request_timeout')
    def test_website_budget_stops_before_network(self):
        fetcher=Mock()
        record=research_website({'company_name':'Yoga','website':'https://clear.example'},fetcher,website_seconds=0)
        fetcher.fetch.assert_not_called()
        self.assertEqual(record['research_metadata']['errors'][0]['category'],'website_timeout')
