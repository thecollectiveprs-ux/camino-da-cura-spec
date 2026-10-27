import re
from .models import canonical_domain

PARTNER_DOMAINS={'bookretreats.com','bookyogaretreats.com','retreathub.com'}
def classify(text,domain=''):
    lower=text.lower()
    if domain in PARTNER_DOMAINS or re.search(r'booking marketplace|retreat directory|venue broker|travel agency|holiday reseller|compare (?:retreats|prices)|retreat booking platform|find my venue|villas for hire|retreat venues (?:for|to) hire|expertly curated.{0,30}holidays|tailor.made wellness holidays|retreat venues [–—|-]|best yoga retreat venues',lower):
        return 'partner'
    if re.search(r'top \d+|\d+ best|our favourite|venues? for hire|retreat centres? for hire|accommodation listings',lower): return 'excluded'
    if re.search(r'\b(?:i host|my retreats|retreats led by|retreat leader|yoga teacher|pilates instructor|founder|meet your retreat host)\b',lower): return 'independent'
    if re.search(r'retreat|yoga|pilates|wellness|meditation|mindfulness|breathwork|creative',lower): return 'boutique'
    return 'excluded'

def route(database,campaign,pid,pipeline,reason):
    with database.conn:
        database.conn.execute('INSERT INTO prospect_routes VALUES (?,?,?,?) ON CONFLICT(campaign,prospect_id) DO UPDATE SET pipeline=excluded.pipeline,reason=excluded.reason',(campaign,pid,pipeline,reason))

def suitability(result):
    parts=[]
    for key,label in [('residential_experience','past residential retreats'),('compatible_group','documented 10–15-person group fit'),('international_experience','past international retreats'),('external_venues','external venue hire'),('recent_activity','recent or upcoming activity')]:
        if result['breakdown'][key]['points']: parts.append(label)
    text=('Evidence supports '+', '.join(parts)+'.') if parts else 'Insufficient documented retreat evidence to assess venue fit.'
    if result['missing_information']: text+=' Further research: '+result['missing_information']+'.'
    if result['flags']: text+=' Review: '+'; '.join(result['flags'])+'.'
    return text
