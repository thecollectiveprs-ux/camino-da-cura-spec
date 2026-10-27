"""Optional bounded directory use: explicit external official-site links only."""
import re
from urllib.parse import urljoin
from .webresearch import PageParser, ResearchError, DIRECTORIES
from .models import SearchResult, canonical_domain
from .selection import candidate_quality

def expand_directory_sources(database,campaign,fetcher,limit):
    sources=database.conn.execute("SELECT DISTINCT source_url FROM discovery_results WHERE campaign=? AND selection_reason='directory_or_editorial_source' ORDER BY id",(campaign,)).fetchall()
    report={'sources_attempted':0,'external_candidates_added':0,'errors':[]}
    for row in sources[:2]:
        if len(database.rows(campaign))>=limit: break
        url=row[0]; domain=canonical_domain(url)
        if domain in {'timeout.com','facebook.com','instagram.com','linkedin.com'}: continue
        report['sources_attempted']+=1
        try:
            content=fetcher.fetch(url); parser=PageParser(); parser.feed(content)
            source=getattr(content,'source_url',url)
            for anchor in parser.anchors:
                if len(database.rows(campaign))>=limit: break
                if not re.search(r'official website|organis(?:er|ator) website|visit (?:the )?(?:organiser|organizer)',anchor['text'],re.I): continue
                target=urljoin(source,anchor['href'])
                try:
                    if canonical_domain(target)==domain: continue
                    result=SearchResult(anchor['text'],target,'Directory supplied external retreat organiser link; identity unverified')
                    rank,reason=candidate_quality(result)
                    if not rank: continue
                    if database.upsert(campaign,result,'directory referral from '+source): report['external_candidates_added']+=1
                except ValueError: continue
        except ResearchError as exc: report['errors'].append({'url':url,'reason':str(exc),'category':exc.category})
    return report
