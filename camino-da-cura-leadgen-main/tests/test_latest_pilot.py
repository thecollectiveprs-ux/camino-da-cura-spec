import html
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from leadgen.config import Campaign
from leadgen.models import SearchResult
from leadgen.selection import initial_screen
from leadgen.webresearch import research_website,PageText,extract
from leadgen.qualification import qualify,load_venue
from leadgen.discovery import discover
from leadgen.db import Database

SNAPSHOT=json.loads(Path('fixtures/organiser-pilot-audit.json').read_text())
class LatestPilotTests(unittest.TestCase):
    def test_saved_six_queries_had_one_result_and_no_rejections(self):
        run=json.loads(SNAPSHOT['discovery_runs'][0]['report_json'])
        self.assertEqual(run['queries_completed'],6)
        self.assertEqual(run['search_results_retrieved'],1)
        self.assertEqual(run['filtered_results'],0)
        self.assertEqual(len(SNAPSHOT['discovery_results']),1)
        self.assertEqual(SNAPSHOT['discovery_results'][0]['selection_reason'],'organiser_candidate_unverified')
    def test_saved_candidate_remains_relevant_not_qualified_by_snippet(self):
        row=SNAPSHOT['discovery_results'][0]
        rank,reason,pipeline=initial_screen(SearchResult(row['title'],row['source_url'],row['description']))
        self.assertGreater(rank,0);self.assertEqual(pipeline,'independent')
        original=json.loads(SNAPSHOT['assessments'][0]['result_json'])
        self.assertEqual(original['qualification_status'],'requires_review')
        self.assertEqual(original['lead_score'],15)
    def test_new_queries_have_no_exact_phrase_bottleneck(self):
        queries=Campaign.load('campaigns/camino_organisers.json').queries()[:6]
        self.assertEqual(len(queries),6)
        self.assertTrue(all('"' not in q for q in queries))
        self.assertTrue(any('yoga teacher' in q for q in queries))
        self.assertTrue(any('Pilates instructor' in q for q in queries))
        self.assertFalse(any('wellness meditation mindfulness breathwork' in q for q in queries))
    def test_listing_with_explicit_host_signal_kept_for_research(self):
        result=SearchResult('Our favourite retreats in Spain','https://teacher.example','I host residential yoga retreats for my students.')
        rank,reason,pipeline=initial_screen(result)
        self.assertGreater(rank,0);self.assertEqual(pipeline,'unconfirmed')
        self.assertEqual(reason,'ambiguous_listing_with_organiser_intent')
    def test_directory_never_becomes_direct_candidate(self):
        result=SearchResult('Yoga teacher retreats','https://bookretreats.com','My retreats directory listings')
        rank,reason,pipeline=initial_screen(result)
        self.assertEqual(rank,0);self.assertEqual(pipeline,'partner')
    def test_duplicate_queue_does_not_emit_duplicate_progress(self):
        fetcher=Mock();fetcher.fetch.return_value='<title>Yoga</title>'+''.join('<a href="/about">About</a><a href="/contact">Contact</a><a href="/retreats">Retreats</a>' for _ in range(8))
        with self.assertLogs('leadgen.webresearch',level='INFO') as logs:
            research_website({'company_name':'Yoga','website':'https://example.com'},fetcher)
        pages=[message for message in logs.output if 'Research page ' in message]
        self.assertEqual(len(pages),fetcher.fetch.call_count)
        self.assertEqual(len(pages),4)
        self.assertEqual(len({message.split(': ')[-1] for message in pages}),4)
    def test_redirect_alias_not_researched_again(self):
        def fetch(url):
            if url.endswith('/about'):
                return PageText('<title>Yoga</title><a href="/our-story">Story</a>','https://example.com/our-story')
            return '<title>Yoga</title><a href="/about">About</a>'
        fetcher=Mock();fetcher.fetch.side_effect=fetch
        research_website({'company_name':'Yoga','website':'https://example.com'},fetcher)
        self.assertEqual(fetcher.fetch.call_count,2)
    def test_saved_founder_and_programme_narrative_are_extracted(self):
        original=json.loads(SNAPSHOT['assessments'][0]['result_json'])
        excerpts=list(dict.fromkeys(c['excerpt'] for c in original['claims']))
        fixture=''.join('<p>'+html.escape(text)+'</p>' for text in excerpts)
        claims=extract(fixture,'https://fixture.example')['claims']
        self.assertTrue(any(c.get('name')=='Nicole Windle' and c.get('role')=='Founder' for c in claims))
        self.assertTrue(any(c['kind']=='organises_retreats' for c in claims))
        result=qualify({'company_name':'Fixture Retreat Company','website':'https://fixture.example','claims':claims},load_venue('config/venue.json'))
        self.assertEqual(result['breakdown']['residential_experience']['points'],0)
        self.assertEqual(result['qualification_status'],'requires_review')
    def test_budget_retains_uncertain_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Database(Path(tmp)/'db');campaign=Campaign.load('campaigns/camino_organisers.json');campaign.max_requests=3;campaign.target_prospects=5
            provider=Mock();provider.search.return_value=[SearchResult('Our favourite retreats','https://teacher.example','I host yoga retreats for students in Spain.')]
            result=discover(campaign,provider,db)
            self.assertEqual(provider.search.call_count,3)
            self.assertEqual(len(db.rows(campaign.name)),1)
            self.assertEqual(db.rows(campaign.name)[0]['pipeline'],'unconfirmed')
            self.assertEqual(result['per_request'][0]['results_returned'],1)
            db.close()
