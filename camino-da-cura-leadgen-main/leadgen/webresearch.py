"""Bounded public HTML fetching and conservative, source-attributed extraction."""
import ipaddress
import re
import socket
import time
import logging
from .deadlines import bounded_call, DeadlineExceeded
log=logging.getLogger(__name__)
from collections import deque
from datetime import datetime, timezone, date
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urldefrag, unquote
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError
from urllib.robotparser import RobotFileParser
from .models import canonical_domain

AGENT = 'CaminoLeadResearch/0.1'
class ResearchError(RuntimeError):
    def __init__(self,message,category='restricted',status=None):
        super().__init__(message); self.category,self.status=category,status
    def __reduce__(self): return (ResearchError,(str(self),self.category,self.status))

def _fetch_job(fetcher,url):
    fetcher.isolated=False
    result=fetcher.fetch(url)
    return result,fetcher.robots,fetcher.last,fetcher.delays

class PageText(str):
    def __new__(cls,text,url,redirects=None):
        value=super().__new__(cls,text); value.source_url=url; value.redirects=redirects or []; return value
    def __reduce__(self): return (PageText,(str(self),self.source_url,self.redirects))

class PublicFetcher:
    def __init__(self, interval=2, max_bytes=1_000_000, opener=None, sleep=time.sleep, resolver=socket.getaddrinfo, retries=1, max_redirects=5):
        from .transport import public_open
        self.interval,self.max_bytes=interval,max_bytes
        self.isolated=opener is None and sleep is time.sleep and resolver is socket.getaddrinfo
        self.request_budget=30
        self.opener=opener or public_open
        self.sleep,self.resolver=sleep,resolver
        self.retries,self.max_redirects=retries,max_redirects
        self.robots,self.last,self.delays={},{},{}
    def validate(self,url):
        try:
            canonical_domain(url); p=urlsplit(url)
            if p.port not in (None,80,443): raise ResearchError('Nonstandard port blocked','unsafe_destination')
            addresses=self.resolver(p.hostname,p.port or (443 if p.scheme=='https' else 80),type=socket.SOCK_STREAM)
            if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
                raise ResearchError('Non-public network address blocked','unsafe_destination')
        except (ValueError,OSError) as exc:
            raise ResearchError(str(exc),'unsafe_destination' if isinstance(exc,ValueError) else 'temporary_network') from None
    def raw(self,url,html=False,_robots=False):
        initial=url; chain=[]; seen=set()
        for hop in range(self.max_redirects+1):
            if url in seen: raise ResearchError('Redirect loop','redirect')
            seen.add(url); self.validate(url)
            if html: self.allowed(url)
            host=canonical_domain(url)
            redirect=None
            for attempt in range(self.retries+1):
                delay=max(self.interval,self.delays.get(host,0))
                self.sleep(max(0,delay-(time.monotonic()-self.last.get(host,0))))
                self.last[host]=time.monotonic()
                try:
                    with self.opener(Request(url,headers={'User-Agent':AGENT,'Accept':'text/html,text/plain'}),timeout=15) as response:
                        if response.geturl()!=url: raise ResearchError('Unvalidated transport redirect','unsafe_destination')
                        content_type=response.headers.get_content_type()
                        if html and content_type not in {'text/html','application/xhtml+xml'}: raise ResearchError('Non-HTML content skipped','unsupported')
                        if _robots and content_type in {'text/html','application/xhtml+xml'}: raise ResearchError('robots.txt returned HTML instead of rules','robots_invalid')
                        body=response.read(self.max_bytes+1)
                        if len(body)>self.max_bytes: raise ResearchError('Page exceeds size limit','unsupported')
                        text=body.decode(response.headers.get_content_charset() or 'utf-8',errors='replace')
                        if html or not _robots:
                            parser=PageParser(); parser.feed(text)
                            visible=' '.join(parser.lines)
                            # Ignore CAPTCHA scripts/widgets on otherwise public pages.
                            challenge=re.search(r'verify you are human|access denied|sign in to continue|checking your browser|complete the captcha',visible,re.I)
                            policy=re.search(r'automated access (?:is )?prohibited|no automated scraping',visible,re.I)
                            if policy or (challenge and (len(visible)<1500 or re.search(r'access denied|just a moment|verify', ' '.join(parser.title),re.I))):
                                raise ResearchError('Visible access restriction detected: '+visible[:250],'restricted')
                        return PageText(text,url,chain)
                except HTTPError as exc:
                    if exc.code in {301,302,303,307,308}:
                        location=exc.headers.get('Location') if exc.headers else None
                        if not location: raise ResearchError('Redirect missing Location','redirect',exc.code) from None
                        target=urldefrag(urljoin(url,location))[0]
                        self.validate(target)
                        if canonical_domain(target)!=canonical_domain(initial): raise ResearchError('Cross-business redirect requires review','redirect',exc.code)
                        if urlsplit(url).scheme=='https' and urlsplit(target).scheme!='https': raise ResearchError('HTTPS downgrade blocked','redirect',exc.code)
                        chain.append({'from':url,'to':target,'status':exc.code}); redirect=target; break
                    category='restricted' if exc.code in {401,403} else ('temporary_http' if exc.code==429 or exc.code>=500 else 'http_error')
                    if category!='temporary_http' or attempt==self.retries: raise ResearchError('HTTP '+str(exc.code),category,exc.code) from None
                    retry_after=exc.headers.get('Retry-After','2') if exc.headers else '2'
                    try: wait=float(retry_after)
                    except ValueError: wait=2
                    if wait>60: raise ResearchError('Retry-After exceeds local wait limit',category,exc.code)
                    self.sleep(max(2,wait))
                except (OSError,ValueError) as exc:
                    if attempt==self.retries: raise ResearchError(type(exc).__name__+': '+str(exc),'temporary_network') from None
                    self.sleep(2)
            if redirect is None: break
            url=redirect
        raise ResearchError('Redirect hop limit exceeded','redirect')
    def allowed(self,url):
        p=urlsplit(url); origin=p.scheme+'://'+p.netloc
        if origin not in self.robots:
            rules=RobotFileParser()
            try: rules.parse(self.raw(origin+'/robots.txt',_robots=True).splitlines())
            except ResearchError as exc:
                if exc.status in {404,410}: rules.parse([])
                else: raise ResearchError('robots.txt unavailable: '+str(exc),'robots_'+exc.category,exc.status) from None
            self.robots[origin]=rules
            host=canonical_domain(url)
            self.delays[host]=max(self.delays.get(host,0),rules.crawl_delay(AGENT) or rules.crawl_delay('*') or 0)
            rate=rules.request_rate(AGENT) or rules.request_rate('*')
            if rate: self.delays[host]=max(self.delays[host],rate.seconds/rate.requests)
        if not self.robots[origin].can_fetch(AGENT,url): raise ResearchError('robots.txt disallows page','robots_disallowed')
    def fetch(self,url):
        if not self.isolated: return self.raw(url,html=True)
        log.info('Fetching page/robots: %s (%.0fs deadline)',url,self.request_budget)
        try:
            result,self.robots,self.last,self.delays=bounded_call(_fetch_job,(self,url),self.request_budget,url)
            return result
        except (DeadlineExceeded,RuntimeError) as exc:
            log.warning('%s',exc)
            raise ResearchError(str(exc),'request_timeout') from None

class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.links, self.title = [], [], []
        self.anchors=[]; self.current_anchor=None; self.site_name=None
        self.hidden=0; self.in_title=False
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='meta' and attrs.get('property')=='og:site_name': self.site_name=attrs.get('content')
        if tag in {'script','style','noscript'}: self.hidden+=1
        if tag=='title': self.in_title=True
        if not self.hidden and tag=='a' and attrs.get('href'):
            self.links.append(attrs['href']); self.current_anchor={'href':attrs['href'],'text':''}
        if tag in {'p','div','li','br','h1','h2','h3','section','article'}: self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag in {'script','style','noscript'}: self.hidden=max(0,self.hidden-1)
        if tag=='title': self.in_title=False
        if tag=='a' and self.current_anchor:
            self.anchors.append(self.current_anchor); self.current_anchor=None
        if tag in {'p','div','li','h1','h2','h3','section','article'}: self.parts.append('\n')
    def handle_data(self,text):
        if not self.hidden:
            self.parts.append(text)
            if self.current_anchor: self.current_anchor['text'] += text
            if self.in_title: self.title.append(text)
    @property
    def lines(self): return [' '.join(line.split()) for line in ''.join(self.parts).splitlines() if line.strip()]

EMAIL = re.compile(r"(?<![\w.+-])[A-Z0-9.!#$%&'*+/=?^_{}|~-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![\w.-])",re.I)
GENERIC={'info','hello','contact','bookings','booking','enquiries','office','admin','support','team'}

def extract(html,url,retrieved_at=None):
    retrieved_at=retrieved_at or datetime.now(timezone.utc).isoformat()
    parser=PageParser(); parser.feed(html)
    claims=[]; contacts={}; pages=[]
    def claim(kind,line,**fields):
        claims.append({'kind':kind,'source_url':url,'retrieved_at':retrieved_at,'excerpt':line,'reviewed':False,'fact_status':'publisher_statement','extraction_method':'explicit_rule_v1',**fields})
    for line in parser.lines:
        low=line.lower()
        if re.search(r'\b(?:we are|our (?:business|team) is|[A-Z][\w &]+ is) (?:based|headquartered) in (?:the )?(?:UK|United Kingdom|England|Scotland|Wales|Northern Ireland)\b',line,re.I):
            claim('base_country',line,value='United Kingdom',published_location=line)
        if re.search(r'\b(?:we|i) (?:organise|organize|run|lead|host) (?:\w+ ){0,3}(?:retreats|residential retreats)\b',low): claim('organises_retreats',line,value=True)
        if re.search(r'\bretreat company[, ]+(?:now )?hosting\b',low): claim('organises_retreats',line,value=True)
        for category in ('yoga','wellness','meditation','mindfulness','pilates','breathwork','holistic','creative','leadership','corporate'):
            if re.search(r'\b'+category+r'\b',low) and re.search(r'\b(retreats?|teacher|facilitator|studio)\b',low): claim('business_type',line,value=category)
        if re.search(r'(?:venue hire only|solely a retreat venue|we do not (?:organise|organize|run) retreats)',low): claim('solely_venue',line,value=True)
        if re.search(r'\b(?:we own|our own) (?:permanent )?retreat (?:venue|centre|center)\b',low): claim('owns_venue',line,value=True)
        if re.search(r'\bwe (?:hire|rent) (?:external |independent )?(?:venues|retreat venues)\b',low): claim('external_venues',line,value=True)
        size=re.search(r'\b(?:total (?:group size|participants)|total of)\s*:?\s*(\d{1,3})\s*(?:participants|people|persons)?',low)
        if size and re.search(r'retreat',low): claim('group_size',line,value=int(size[1]),basis='total_participants')
        day=re.search(r'\b(20\d{2}-\d{2}-\d{2})\b',line)
        if day and 'retreat' in low:
            try: parsed=date.fromisoformat(day[1])
            except ValueError: parsed=None
            country=next((c for c in ('Portugal','Spain','France','Italy','Greece','Croatia','United Kingdom') if c.lower() in low),None)
            recap=bool(re.search(r'\b(?:we hosted|we held|we led|we returned from|our retreat took place)\b',low))
            residential=bool(re.search(r'\b(?:residential|overnight|[2-9][ -](?:night|day))\b',low))
            if parsed and recap and residential and parsed<=date.today():
                claim('residential_event',line,occurred=True,event_date=day[1],country=country,evidence_type='recap')
                claim('activity',line,activity_date=day[1],activity_type='retreat_recap')
            elif parsed:
                claim('residential_event',line,occurred=False,event_date=day[1],country=country,evidence_type='advertisement',fact_status='advertised')
                if parsed>=date.today(): claim('activity',line,activity_date=day[1],activity_type='upcoming_retreat',fact_status='advertised')
        for email in EMAIL.findall(line): contacts.setdefault(email.lower(),(line,None,None))
        person=re.search(r'\b([A-Z][a-z]+ [A-Z][a-z]+)\s*[-–:]\s*(Yoga teacher|Yoga instructor|Pilates instructor|Retreat organiser|Retreat leader|Founder|Director|Facilitator)\b',line)
        founder=re.search(r'\bfounder\s+([A-Z][a-z]+(?:[- ][A-Z][a-z]+)+)',line)
        if founder: claim('contact',line,name=founder[1],role='Founder',email_type='unknown')
        if person and not EMAIL.findall(line): claim('contact',line,name=person[1],role=person[2],email_type='unknown')
        if person:
            for email in EMAIL.findall(line): contacts[email.lower()]=(line,person[1],person[2])
        phone=re.search(r'(?:phone|telephone|tel)\s*:?\s*(\+?[\d ()-]{8,25})',line,re.I)
        if phone: claim('contact',line,phone=phone[1].strip(),email_type='unknown')
    for link in parser.links:
        if link.lower().startswith('mailto:'):
            email=unquote(link[7:].split('?')[0])
            if EMAIL.fullmatch(email): contacts.setdefault(email.lower(),('Published mailto:'+email,None,None))
        elif link.lower().startswith('tel:'):
            claim('contact','Published tel:'+link[4:],phone=unquote(link[4:]),email_type='unknown')
        elif re.search(r'contact',link,re.I): pages.append(urljoin(url,link))
    for email,(excerpt,name,role) in contacts.items():
        local=email.split('@')[0]
        email_type='generic_business' if local in GENERIC else ('individual_professional' if name else 'unknown')
        venue_contact=bool(re.search(r'(?:venue|hotel|accommodation) (?:contact|email|reception)',excerpt,re.I))
        associated=bool(name or re.search(r'/contact|/about|/team',urlsplit(url).path,re.I) or re.search(r'email us|contact us|our email|business email',excerpt,re.I))
        claim('contact',excerpt,email=email,email_type=email_type,name=name,role=role,contact_attribution='venue' if venue_contact else ('business_context' if associated else 'uncertain'),contact_identity_uncertain=email_type=='unknown')
    return {'claims':claims,'links':parser.links,'title':' '.join(parser.title).strip(),'contact_pages':pages,'business_name':parser.site_name}

DIRECTORIES={'retreathub.com','timeout.com','facebook.com','instagram.com','linkedin.com','tripadvisor.com','bookretreats.com','bookyogaretreats.com','eventbrite.com'}

def research_website(candidate,fetcher,*,max_pages=6,website_seconds=90):
    started=time.monotonic()
    url=candidate['website']; domain=canonical_domain(url)
    result={'company_name':candidate['company_name'],'website':url,'claims':[],'research_metadata':{'pages':[],'errors':[],'contact_pages':[],'identity_status':'uncertain','review_flags':[]}}
    if candidate.get('pipeline'): result['pipeline']=candidate['pipeline']
    meta=result['research_metadata']
    if any(domain==d or domain.endswith('.'+d) for d in DIRECTORIES):
        meta['review_flags'].append('Directory/social platform; official website required'); return result
    seeds=[u for u in candidate.get('discovery_urls',[]) if canonical_domain(u)==domain]
    queue=deque(list(dict.fromkeys(seeds+[url]))); queued=set(queue); seen=set(); attempted=0; seen_claims=set(); seen_contacts={}
    while queue and attempted<max_pages:
        remaining=website_seconds-(time.monotonic()-started)
        if remaining<=0:
            meta['errors'].append({'url':url,'reason':'Website research deadline reached','category':'website_timeout'})
            log.warning('Website deadline reached: %s',url)
            break
        if isinstance(fetcher,PublicFetcher): fetcher.request_budget=min(30,remaining)
        page=urldefrag(queue.popleft())[0]
        queued.discard(page)
        if page in seen: continue
        seen.add(page); attempted+=1
        log.info('Research page %s/%s: %s',attempted,max_pages,page)
        try:
            html=fetcher.fetch(page)
            stamp=datetime.now(timezone.utc).isoformat()
            source=getattr(html,'source_url',page)
            seen.add(source)
            data=extract(html,source,stamp)
        except (ResearchError,OSError,ValueError) as exc:
            log.warning('Page failed: %s: %s',page,exc)
            meta['errors'].append({'url':page,'reason':str(exc),'category':getattr(exc,'category','temporary_network'),'http_status':getattr(exc,'status',None)}); continue
        if data.get('business_name'):
            result['published_business_name']=data['business_name']
            meta['business_name_source']={'url':source,'retrieved_at':stamp,'value':data['business_name']}
        meta['pages'].append({'url':source,'requested_url':page,'retrieved_at':stamp,'title':data['title'],'redirects':getattr(html,'redirects',[])})
        if data['title'] and any(token in data['title'].lower() for token in candidate['company_name'].lower().split() if len(token)>3): meta['identity_status']='likely_official'
        for c in data['claims']:
            key=(c['kind'],c['excerpt'],c['source_url'])
            if c['kind']=='contact':
                contact_key=c.get('email') or c.get('phone') or (c.get('name'),c.get('role'))
                if contact_key in seen_contacts:
                    previous=result['claims'][seen_contacts[contact_key]]
                    confidence=lambda item: (2 if item.get('contact_attribution')=='business_context' else 0)+(1 if item.get('name') else 0)
                    if confidence(c)>confidence(previous):
                        c['alternate_sources']=previous.get('alternate_sources',[])+[{'source_url':previous['source_url'],'retrieved_at':previous['retrieved_at'],'excerpt':previous['excerpt']}]
                        result['claims'][seen_contacts[contact_key]]=c
                    continue
                seen_contacts[contact_key]=len(result['claims'])
            if key not in seen_claims: result['claims'].append(c); seen_claims.add(key)
        for link in data['links']:
            target=urldefrag(urljoin(source,link))[0]
            try: same=canonical_domain(target)==domain
            except ValueError: continue
            if same and not urlsplit(target).query and re.search(r'retreat|about|contact|team|founder|host|programme|program|story|past|upcoming',urlsplit(target).path,re.I) and target not in seen and target not in queued:
                queued.add(target)
                (queue.appendleft(target) if re.search(r'contact|about|team|founder',urlsplit(target).path,re.I) else queue.append(target))
                if 'contact' in target.lower() and target not in meta['contact_pages']: meta['contact_pages'].append(target)
    if meta['identity_status']=='likely_official' and not (any(c['kind']=='base_country' for c in result['claims']) and any(c['kind']=='organises_retreats' for c in result['claims'])): meta['review_flags'].append('Likely official website; identity requires human confirmation')
    if meta['identity_status']=='uncertain': meta['review_flags'].append('Business identity/official website uncertain')
    if any(c.get('contact_identity_uncertain') for c in result['claims']): meta['review_flags'].append('Published contact identity requires review')
    if not meta['pages']: meta['review_flags'].append('Website inaccessible or restricted')
    return result
