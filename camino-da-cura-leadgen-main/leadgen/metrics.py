"""Counts distinguish candidate selection, research failure and qualification."""
import json
from .qualification import documented

def quality_metrics(database,campaign,pricing=None):
    all_rows=database.rows(campaign)
    partners=[row for row in all_rows if row.get('pipeline')=='partner']
    rows=[row for row in all_rows if row.get('pipeline') not in {'partner','excluded'}]
    reports=[json.loads(r[0]) for r in database.conn.execute('SELECT report_json FROM discovery_runs WHERE campaign=?',(campaign,))]
    contacts={}
    relevant=0
    for row in rows:
        claims=[c for c in row.get('research_evidence',[]) if documented(c)]
        if any(c['kind']=='organises_retreats' and c.get('value') is True for c in claims) or any(c['kind']=='residential_event' and c.get('occurred') is True for c in claims): relevant+=1
        for c in row.get('professional_contacts',[]):
            identifier=c.get('email') or c.get('phone')
            if identifier: contacts[(row['domain'],identifier)]=c
    contactable=sum(r['qualification_status']!='rejected' and any(c.get('email') and c.get('contact_attribution') in {None,'business_context'} for c in r.get('professional_contacts',[])) and not database.is_suppressed(r) for r in rows)
    attributed=sum(any(c.get('email') and c.get('contact_attribution')=='business_context' for c in r.get('professional_contacts',[])) for r in rows)
    usable=sum(r['qualification_status']=='qualified' and any(c.get('email') and c.get('contact_attribution') in {None,'business_context'} for c in r.get('professional_contacts',[])) and not database.is_suppressed(r) for r in rows)
    attempts=sum(sum(p.get('http_attempts',1) for p in r.get('per_request',[])) or r.get('queries_completed',0) for r in reports)
    price=(pricing or {}).get('search_price_usd_per_1000')
    cost=attempts*price/1000 if price is not None else None
    result = {'discovered_direct_candidates':len(rows),'researched_businesses':sum(bool(r.get('research_metadata',{}).get('pages')) for r in rows),'contactable_businesses':contactable,'businesses_with_explicit_contact_attribution':attributed,'email_coverage':contactable/len(rows) if rows else 0,'usable_leads':usable,'brave_http_attempts':attempts,'estimated_gross_search_cost_usd':cost,'estimated_cost_per_usable_lead_usd':cost/usable if cost is not None and usable else None,'price_source':(pricing or {}).get('search_price_source'),'directory_partners':len(partners),'search_results_retrieved':sum(r.get('search_results_retrieved',0) for r in reports),
      'candidates_after_filtering':len(rows),'relevant_organiser_candidates':relevant,
      'websites_successfully_researched':sum(bool(r.get('research_metadata',{}).get('pages')) for r in rows),
      'websites_inaccessible':sum(not r.get('research_metadata',{}).get('pages') and bool(r.get('research_metadata',{}).get('errors')) for r in rows),
      'contacts_extracted':len(contacts),'business_emails_extracted':sum(bool(c.get('email')) for c in contacts.values()),
      'prospects_qualified':sum(r['qualification_status']=='qualified' for r in rows),
      'prospects_requiring_review':sum(r['qualification_status']=='requires_review' for r in rows),
      'prospects_rejected_for_confirmed_irrelevance':sum(r['qualification_status']=='rejected' for r in rows),
      'filtered_search_results':sum(r.get('filtered_results',0) for r in reports),
      'not_researched':sum(not r.get('research_metadata',{}).get('pages') and not r.get('research_metadata',{}).get('errors') for r in rows),
      'website_evidenced_organisers_per_request':relevant / sum(sum(p.get('http_attempts',1) for p in r.get('per_request',[])) or r.get('queries_completed',0) for r in reports) if sum(r.get('queries_completed',0) for r in reports) else 0,
      'definitions':'Contactable means a published business-associated email, not consent or delivery verification. Usable means qualified plus a published business-associated email. Estimated costs are gross before credits; undefined when no usable leads. Relevant organiser counts require website evidence, not search snippets. Contacts are unique per business. Search counts include repeated requests/runs; candidate count is unique stored businesses.'}

    return result
