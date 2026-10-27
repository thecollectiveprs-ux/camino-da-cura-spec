"""Deterministic scoring of explicitly reviewed, documented claims. No LLM or scraping."""
import json
from datetime import date, datetime
from pathlib import Path
from .models import canonical_domain
from .pipelines import classify,suitability

CRITERIA = ('residential_experience','compatible_group','international_experience','relevant_activity','external_venues','recent_activity')
CLAIMS = {'base_country','business_type','organises_retreats','solely_venue','owns_venue','external_venues','residential_event','group_size','activity','contact','legal_form'}

def load_venue(path):
    config = json.loads(Path(path).read_text(encoding='utf-8'))
    weights = config['weights']
    if set(weights) != set(CRITERIA) or any(type(v) is not int or v < 0 for v in weights.values()) or sum(weights.values()) != 100:
        raise ValueError('Scoring weights must cover six criteria and sum to 100')
    if not 0 <= config['thresholds']['B'] < config['thresholds']['A'] <= 100:
        raise ValueError('Invalid priority thresholds')
    if not 1 <= config['ideal_group_size']['min'] <= config['ideal_group_size']['max'] or config['recent_activity_days'] < 1:
        raise ValueError('Invalid capacity or recency settings')
    return config

def documented(claim):
    canonical_domain(claim['source_url'])
    datetime.fromisoformat(claim['retrieved_at'].replace('Z','+00:00'))
    if claim.get('kind') not in CLAIMS or not isinstance(claim.get('excerpt'),str) or not claim['excerpt'].strip():
        raise ValueError('Evidence requires a recognised claim, excerpt, URL and retrieval date')
    human = claim.get('reviewed') is True and claim.get('fact_status') == 'documented'
    automatic = claim.get('extraction_method') == 'explicit_rule_v1' and (claim.get('fact_status') == 'publisher_statement' or (claim.get('fact_status') == 'advertised' and claim['kind']=='activity'))
    return human or automatic

def qualify(record, config, *, today=None):
    today = today or date.today()
    canonical_domain(record['website'])
    claims = record.get('claims', [])
    accepted = [c for c in claims if documented(c)]
    by = lambda kind: [c for c in accepted if c['kind'] == kind]
    values = lambda kind: [c.get('value') for c in by(kind)]
    occurred = [c for c in by('residential_event') if c.get('occurred') is True and c.get('evidence_type') in {'recap','testimonial','attendance_record'} and date.fromisoformat(c['event_date']) <= today]
    size_claims = [c for c in by('group_size') if c.get('basis') == 'total_participants' and type(c.get('value')) is int and c['value'] > 0]
    capacity = config['ideal_group_size']
    compatible = [c for c in size_claims if capacity['min'] <= c['value'] <= capacity['max']]
    relevant_types = set(t for types in config['priorities'].values() for t in types)
    types = set(values('business_type'))
    activity = []
    for c in by('activity'):
        day = date.fromisoformat(c['activity_date'])
        if (c.get('activity_type') == 'upcoming_retreat' and day >= today) or (c.get('activity_type') in {'business_update','retreat_recap'} and 0 <= (today-day).days <= config['recent_activity_days']):
            activity.append(c)
    supporting = {
        'residential_experience': occurred,
        'compatible_group': compatible,
        'international_experience': [c for c in occurred if c.get('country') and c['country'] != config['international_reference_country']],
        'relevant_activity': [c for c in by('business_type') if c.get('value') in relevant_types],
        'external_venues': [c for c in by('external_venues') if c.get('value') is True],
        'recent_activity': activity,
    }
    breakdown = {key:{'points':config['weights'][key] if supporting[key] else 0,'maximum':config['weights'][key],'evidence':supporting[key]} for key in CRITERIA}
    score = sum(v['points'] for v in breakdown.values())
    missing = [key for key in CRITERIA if config['weights'][key]>0 and not supporting[key]]
    flags, reasons = [], []
    base = set(values('base_country'))
    if not base:
        missing.append('verified organiser base country')
    elif len(base) != 1:
        flags.append('conflicting base-country evidence')
    elif not base.intersection(config['allowed_base_countries']):
        reasons.append('Organiser is outside configured base countries')
    if True in values('solely_venue'):
        reasons.append('Solely a competing retreat venue')
    if types.intersection({'consumer','attendee'}):
        reasons.append('Individual consumer or retreat attendee')
    organiser = True in values('organises_retreats') or bool(occurred)
    if not organiser:
        missing.append('confirmed retreat organiser')
    if any(c['value'] > capacity['max'] for c in size_claims):
        flags.append('capacity mismatch: documented larger group')
    if True in values('owns_venue') and not supporting['external_venues']:
        flags.append('owns permanent venue; external venue use unconfirmed')
    if any(c.get('basis') != 'total_participants' for c in by('group_size')):
        flags.append('group size basis unclear; facilitators/total capacity require research')
    metadata = record.get('research_metadata',{})
    contact_flags=[flag for flag in metadata.get('review_flags',[]) if 'contact identity' in flag.lower()]
    flags.extend(metadata.get('review_flags',[]))
    if metadata.get('errors'): missing.append('some website pages inaccessible')
    priority = 'A' if score >= config['thresholds']['A'] else 'B' if score >= config['thresholds']['B'] else 'C'
    discovery_priority = next((int(p) for p, ts in config['priorities'].items() if types.intersection(ts)), None)
    if not relevant_types.intersection(types): missing.append('relevant business activity')
    status = 'rejected' if reasons else ('qualified' if len(base)==1 and base.intersection(config['allowed_base_countries']) and organiser and supporting['relevant_activity'] and priority in {'A','B'} and not flags else 'requires_review')
    if metadata and not metadata.get('pages') and not reasons:
        priority = 'unassessed'
        status = 'requires_review'
    destinations = sorted({c['country'] for c in occurred if c.get('country')})
    contacts = [c for c in by('contact') if c.get('contact_attribution')!='venue']
    if not contacts: missing.append('public professional contact details')
    if not by('legal_form'): missing.append('business legal form')
    missing.append('human marketing compliance review')
    for c in contacts:
        if c.get('email') and ('@' not in c['email'] or c.get('email_type') not in {'generic_business','individual_professional','unknown'}):
            raise ValueError('Contact requires a publicly documented email and email type')
    result = {'lead_score':score,'priority_band':priority,'discovery_priority':discovery_priority,'qualification_status':status,'qualification_explanation':json.dumps(breakdown,ensure_ascii=False),'rejection_reason':'; '.join(reasons) or None,'missing_information':'; '.join(missing),'flags':flags,'past_destinations':destinations,'european_experience':any(c in config['european_destinations'] for c in destinations),'preferred_destination_experience':any(c in config['preferred_destinations'] for c in destinations),'breakdown':breakdown,'contacts':contacts,'claims':claims,'business_category':', '.join(sorted(types)) or None,'research_metadata':record.get('research_metadata',{}),'contact_review_flags':contact_flags}
    result['pipeline_basis']='explicit website organiser statement' if organiser else 'provisional search/text classification; organiser status unconfirmed'
    result['published_business_name']=record.get('published_business_name')
    result['pipeline']=record.get('pipeline') or classify(record.get('company_name','')+' '+ ' '.join(c['excerpt'] for c in accepted),canonical_domain(record['website']))
    evidence_pipeline=classify(' '.join(c['excerpt'] for c in accepted),canonical_domain(record['website']))
    if evidence_pipeline=='partner': result['pipeline']='partner'
    if result['pipeline']=='partner':
        result['qualification_status']='requires_review'
        result['flags'].append('Partner pipeline; not a direct organiser lead')
    residential=bool(occurred) or any(c['kind']=='residential_event' and c.get('fact_status')=='advertised' and 'residential' in c['excerpt'].lower() for c in claims)
    if not residential and result['qualification_status']=='qualified':
        result['qualification_status']='requires_review'
        result['missing_information']+='; documented residential retreat programme'
    result['suitability_notes']=suitability(result)
    advertised_countries=sorted({c['country'] for c in claims if c['kind']=='residential_event' and c.get('occurred') is False and c.get('country')})
    if advertised_countries: result['suitability_notes']+=' Advertised retreats: '+', '.join(advertised_countries)+'; occurrence unconfirmed.'
    return result


def import_research(database, campaign, records, config):
    from .models import SearchResult
    from .db import now
    prepared = [(record,qualify(record,config)) for record in records]  # validate before writing
    totals = {'imported':0,'qualified':0,'rejected':0,'requires_review':0}
    for record, assessment in prepared:
        existing = database.conn.execute('SELECT a.result_json FROM assessments a JOIN prospects p ON p.id=a.prospect_id WHERE a.campaign=? AND p.domain=?',(campaign,canonical_domain(record['website']))).fetchone()
        if record.get('research_metadata') is not None:
            prospect = database.conn.execute('SELECT id FROM prospects WHERE domain=?',(canonical_domain(record['website']),)).fetchone()
            if prospect:
                with database.conn:
                    database.conn.execute('INSERT INTO website_research(campaign,prospect_id,record_json,retrieved_at) VALUES (?,?,?,?)',(campaign,prospect[0],json.dumps(record),now()))
        if record.get('research_metadata') is not None and existing and not json.loads(existing[0]).get('research_metadata'):
            totals.setdefault('preserved_manual_assessments',0)
            totals['preserved_manual_assessments'] += 1
            continue
        database.upsert(campaign,SearchResult(record['company_name'],record['website']), 'reviewed research import')
        pid = database.conn.execute('SELECT id FROM prospects WHERE domain=?',(canonical_domain(record['website']),)).fetchone()[0]
        with database.conn:
            if record.get('research_metadata') is not None and not prospect:
                database.conn.execute('INSERT INTO website_research(campaign,prospect_id,record_json,retrieved_at) VALUES (?,?,?,?)',(campaign,pid,json.dumps(record),now()))
            database.conn.execute('INSERT INTO assessments(campaign,prospect_id,result_json,config_json,assessed_at) VALUES (?,?,?,?,?) ON CONFLICT(campaign,prospect_id) DO UPDATE SET result_json=excluded.result_json,config_json=excluded.config_json,assessed_at=excluded.assessed_at', (campaign,pid,json.dumps(assessment),json.dumps(config),now()))
        totals['imported'] += 1
        totals[assessment['qualification_status']] += 1
    return totals
