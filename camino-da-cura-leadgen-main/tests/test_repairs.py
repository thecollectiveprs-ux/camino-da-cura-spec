import io
import json
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from urllib.error import HTTPError
from unittest.mock import Mock, patch
from leadgen.webresearch import PublicFetcher,ResearchError,research_website
from leadgen.selection import candidate_quality
from leadgen.models import SearchResult
from leadgen.config import Campaign
from leadgen.db import Database
from leadgen.discovery import discover
from leadgen.metrics import quality_metrics
from leadgen.qualification import qualify,load_venue,import_research

PILOT=json.loads(Path('fixtures/previous_pilot.json').read_text())
class RepairsTests(unittest.TestCase):
    def response(self,text,url,kind='text/html'):
        r=io.BytesIO(text.encode()); r.headers=Message(); r.headers['Content-Type']=kind; r.geturl=lambda:url; return r
    def fetcher(self,opener):
        return PublicFetcher(opener=opener,sleep=Mock(),resolver=lambda *a,**k:[(2,1,6,'',('93.184.216.34',443))])
    def test_actual_pilot_rejection_split(self):
        results=[SearchResult(r['title'],r['source_url'],r['description']) for r in PILOT['evidence']]
        rejected=[r for r in results if candidate_quality(r)[0]==0]
        self.assertEqual(len(rejected),5)
        self.assertEqual(len(results)-len(rejected),5)
    def test_prior_pilot_had_only_directory_success(self):
        successful=[r for r in PILOT['records'] if r['pages']]
        self.assertEqual([r['domain'] for r in successful],['retreathub.com'])
        self.assertEqual(sum(bool(r['errors']) for r in PILOT['records']),7)
    def test_ananda_301_www_redirect(self):
        url='https://anandayogaretreats.com'; final='https://www.anandayogaretreats.com/'
        def opener(request,timeout):
            u=request.full_url
            if u.endswith('/robots.txt'): return self.response('User-agent: *\nAllow: /',u,'text/plain')
            if u==url: raise HTTPError(u,301,'',{'Location':final},None)
            return self.response('<p>Email: hello@example.com</p>',u)
        fetched=self.fetcher(opener).fetch(url)
        self.assertEqual(fetched.source_url,final)
        self.assertEqual(fetched.redirects[0]['status'],301)
    def test_robots_www_redirect(self):
        opener=Mock(side_effect=[HTTPError('',301,'',{'Location':'https://www.ourretreat.co.uk/robots.txt'},None),self.response('User-agent: *\nAllow: /','https://www.ourretreat.co.uk/robots.txt','text/plain'),self.response('public','https://ourretreat.co.uk')])
        self.assertEqual(self.fetcher(opener).fetch('https://ourretreat.co.uk'),'public')
    def test_captcha_widget_not_access_restriction(self):
        url='https://adventureyogi.com/yoga-retreats/'
        body='<html><title>Yoga Retreats</title><script src="https://google.com/recaptcha/api.js"></script><p>Contact hello@example.com</p></html>'
        result=self.fetcher(Mock(return_value=self.response(body,url))).raw(url,html=False)
        self.assertIn('hello@example.com',result)
    def test_visible_challenge_still_blocked(self):
        url='https://forestretreats.co.uk'
        with self.assertRaises(ResearchError) as error:
            self.fetcher(Mock(return_value=self.response('<title>Access denied</title><p>Verify you are human</p>',url))).raw(url)
        self.assertEqual(error.exception.category,'restricted')
    def test_temporary_network_retry(self):
        opener=Mock(side_effect=[TimeoutError('timeout'),self.response('public','https://clear.example')])
        self.assertEqual(self.fetcher(opener).raw('https://clear.example'),'public')
        self.assertEqual(opener.call_count,2)
    def test_403_never_retried(self):
        opener=Mock(side_effect=HTTPError('',403,'',{},None))
        with self.assertRaises(ResearchError) as error:self.fetcher(opener).raw('https://clear.example')
        self.assertEqual(opener.call_count,1); self.assertEqual(error.exception.category,'restricted')
    def test_503_diagnostics(self):
        opener=Mock(side_effect=HTTPError('',503,'',{},None))
        with self.assertRaises(ResearchError) as error:self.fetcher(opener).fetch('https://clear.example')
        self.assertEqual(error.exception.category,'robots_temporary_http')
        self.assertEqual(error.exception.status,503)
    def test_html_robots_conservative_stop(self):
        opener=Mock(return_value=self.response('<html>Not found</html>','https://clear.example/robots.txt'))
        with self.assertRaises(ResearchError) as error:self.fetcher(opener).fetch('https://clear.example')
        self.assertIn('robots_invalid',error.exception.category)
    def test_cross_business_redirect_not_followed(self):
        opener=Mock(side_effect=HTTPError('',302,'',{'Location':'https://other.example'},None))
        with self.assertRaises(ResearchError): self.fetcher(opener).raw('https://clear.example')
        self.assertEqual(opener.call_count,1)
    def test_redirect_loop(self):
        opener=Mock(side_effect=HTTPError('',301,'',{'Location':'https://clear.example'},None))
        with self.assertRaises(ResearchError) as error:self.fetcher(opener).raw('https://clear.example')
        self.assertEqual(error.exception.category,'redirect')
    def test_redirect_destination_robots_checked(self):
        def opener(request,timeout):
            u=request.full_url
            if u=='https://clear.example/robots.txt': return self.response('User-agent: *\nAllow: /',u,'text/plain')
            if u=='https://clear.example': raise HTTPError(u,301,'',{'Location':'https://www.clear.example/'},None)
            if u.endswith('robots.txt'): return self.response('User-agent: *\nDisallow: /',u,'text/plain')
            self.fail('Disallowed destination requested')
        with self.assertRaises(ResearchError):self.fetcher(opener).fetch('https://clear.example')
    def test_original_retreat_urls_used(self):
        fetcher=Mock(); fetcher.fetch.return_value='<p>hello@example.com</p>'
        candidate={'company_name':'AdventureYogi','website':'https://adventureyogi.com','discovery_urls':['https://adventureyogi.com/yoga-retreats/']}
        result=research_website(candidate,fetcher,max_pages=1)
        fetcher.fetch.assert_called_once_with(candidate['discovery_urls'][0])
        self.assertEqual(result['claims'][0]['source_url'],candidate['discovery_urls'][0])
    def test_failed_research_unassessed(self):
        f=Mock();f.fetch.side_effect=ResearchError('timeout','temporary_network')
        result=qualify(research_website({'company_name':'Yoga','website':'https://yoga.example'},f),load_venue('config/venue.json'))
        self.assertEqual(result['priority_band'],'unassessed');self.assertIsNone(result['rejection_reason'])
    def test_metrics_and_snippets_not_scored(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Database(Path(tmp)/'db'); campaign=Campaign(name='repair',filter_candidates=True,target_prospects=10)
            p=Mock();p.search.return_value=[SearchResult(r['title'],r['source_url'],r['description']) for r in PILOT['evidence']]
            discover(campaign,p,db)
            self.assertEqual(len(db.rows('repair')),5)
            metrics=quality_metrics(db,'repair')
            self.assertEqual(metrics['relevant_organiser_candidates'],0)
            self.assertEqual(metrics['search_results_retrieved'],20)
            self.assertEqual(metrics['contacts_extracted'],0)
            self.assertTrue(any('/yoga-retreats/' in r['website'] for r in db.rows('repair')))
            db.close()
    def test_transport_never_connects_private(self):
        from leadgen.transport import public_open
        from urllib.request import Request
        with patch('leadgen.transport.socket.getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',443))]),patch('leadgen.transport.socket.create_connection') as connect:
            with self.assertRaises(OSError):public_open(Request('https://clear.example'))
            connect.assert_not_called()

    def test_directory_only_explicit_official_link_used(self):
        from leadgen.directory_sources import expand_directory_sources
        with tempfile.TemporaryDirectory() as tmp:
            db=Database(Path(tmp)/'db'); campaign=Campaign(name='sources',filter_candidates=True)
            provider=Mock();provider.search.return_value=[SearchResult('Directory','https://bookretreats.com/source')]
            discover(campaign,provider,db)
            fetcher=Mock();fetcher.fetch.return_value='<a href="https://organiser.example/retreats">Jane Yoga official website</a><a href="https://ads.example">Advertisement</a>'
            result=expand_directory_sources(db,'sources',fetcher,10)
            self.assertEqual(result['external_candidates_added'],1)
            self.assertEqual(len(db.rows('sources')),1)
            self.assertEqual(db.rows('sources')[0]['domain'],'organiser.example')
            db.close()
    def test_good_identity_no_forced_review(self):
        from leadgen.webresearch import extract
        claims=extract(Path('fixtures/html/home.html').read_text() + Path('fixtures/html/retreats.html').read_text(),'https://clear.example')['claims']
        result=qualify({'website':'https://clear.example','claims':claims,'research_metadata':{'pages':[{'url':'https://clear.example'}],'review_flags':[]}},load_venue('config/venue.json'))
        self.assertEqual(result['lead_score'],100)
        self.assertEqual(result['qualification_status'],'qualified')
    def test_https_downgrade_not_followed(self):
        opener=Mock(side_effect=HTTPError('',301,'',{'Location':'http://clear.example'},None))
        with self.assertRaises(ResearchError):self.fetcher(opener).raw('https://clear.example')
        self.assertEqual(opener.call_count,1)
