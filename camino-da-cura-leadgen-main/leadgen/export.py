import csv
import json
from pathlib import Path

FIELDS = ['company_name','website','domain','business_category','location','retreat_offering','evidence','contact_name','professional_role','business_email','email_verification_status','legal_form','jurisdiction','contact_type','lawful_basis_review','marketing_eligibility','consent_status','compliance_review_status','lead_score','qualification_status','qualification_explanation','rejection_reason','missing_information','date_discovered','date_last_seen','date_last_verified','outreach_status','priority_band','discovery_priority','flags','past_destinations','european_experience','preferred_destination_experience','contact_source','contact_retrieved_at','professional_contacts','date_assessed','official_contact_pages','research_metadata','business_phones','research_status','commercial_rank']

def safe_cell(value):
    if value is None: return ''
    value = str(value)
    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) or value.startswith(('\t','\r','\n')) else value

def export_csv(database, path, *, campaign=None, status='qualified', purpose='review', approved_by=None):
    if purpose not in {'review', 'outreach'}:
        raise ValueError('Invalid export purpose')
    if purpose == 'outreach' and (not approved_by or not approved_by.strip()):
        raise ValueError('Outreach export requires explicit human approval via --approved-by')
    if purpose == 'outreach' and status != 'qualified':
        raise ValueError('Outreach export must select qualified leads')
    rows = [r for r in database.rows(campaign) if (status == 'all' or r['qualification_status'] == status) and not database.is_suppressed(r)]
    if purpose == 'outreach':
        rows = [r for r in rows if r['compliance_review_status'] == 'approved' and r['lawful_basis_review'] == 'approved' and r['marketing_eligibility'] == 'eligible' and r['business_email'] and r['email_verification_status'] == 'verified']
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            row['evidence'] = json.dumps(database.sources(row['id']) + row.get('research_evidence',[]), ensure_ascii=False)
            writer.writerow({key:safe_cell(json.dumps(row.get(key), ensure_ascii=False) if isinstance(row.get(key),(list,dict)) else row.get(key)) for key in FIELDS})
    if purpose == 'outreach':
        Path(str(path) + '.approval.json').write_text(json.dumps({'approved_by':approved_by,'purpose':purpose,'count':len(rows),'domains':[r['domain'] for r in rows]}, indent=2), encoding='utf-8')
    return len(rows)
