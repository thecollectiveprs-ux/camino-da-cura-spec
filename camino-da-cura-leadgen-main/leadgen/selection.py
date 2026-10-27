import re
from .models import canonical_domain
from .webresearch import DIRECTORIES

def candidate_quality(result):
    domain=canonical_domain(result.url)
    text=(result.title+' '+result.description).lower()
    if any(domain==d or domain.endswith('.'+d) for d in DIRECTORIES): return 0,'directory_or_editorial_source'
    if re.search(r'(?:top \d+|\d+ best|our favourite|best yoga venues|venues? for hire|retreat centres? for hire|retreat centers? for hire|hotel directory|accommodation listings)',result.title,re.I): return 0,'editorial_or_venue_listing'
    if not re.search(r'retreat|yoga|pilates|meditation|wellness|mindfulness|breathwork',text): return 0,'insufficient_niche_signal'
    score=10
    if re.search(r'organis|instructor|teacher|facilitator|we (?:run|lead)|retreat specialist',text): score+=20
    if re.search(r'portugal|spain|ibiza|europe|international|abroad',text): score+=15
    if re.search(r'uk.based|based in|united kingdom|london|dorset',text): score+=5
    return score,'organiser_candidate_unverified'


def initial_screen(result):
    """Search snippets supply intent, not qualification. Keep ambiguous niche results."""
    from .pipelines import classify
    domain=canonical_domain(result.url)
    text=result.title+' '+result.description
    pipeline=classify(text,domain)
    rank,reason=candidate_quality(result)
    if pipeline=='partner': return 0,'partner_discovery_source',pipeline
    intent=bool(re.search(r'\b(?:i (?:host|lead|organise|organize)|my retreats|we (?:host|run|organise|organize)|retreats led by)\b',result.description,re.I))
    if reason=='editorial_or_venue_listing' and intent:
        return max(rank,30),'ambiguous_listing_with_organiser_intent','unconfirmed'
    if reason=='insufficient_niche_signal': return 0,reason,'excluded'
    if rank and pipeline!='excluded': return rank,reason,pipeline
    if rank and intent: return rank,'uncertain_organiser_candidate','unconfirmed'
    return rank,reason,pipeline
