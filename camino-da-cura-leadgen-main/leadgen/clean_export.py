import csv
from pathlib import Path
from .export import safe_cell
from .pipelines import classify
HEADERS=['Business','Contact name','Email','Website','Retreat type','UK location','Fit','Evidence URL','Notes']

def clean_exports(database,campaign,organisers='exports/organiser-leads.csv',partners='exports/directory-partners.csv',include_contact_source=False,partner_database=None):
    rows=database.rows(campaign)
    if partner_database: rows=[r for r in rows if r.get('pipeline')!='partner']+partner_database.rows(campaign)
    headers=HEADERS+(['Contact source'] if include_contact_source else [])
    output={'organisers':[],'partners':[]}
    for row in rows:
        if database.is_suppressed(row) or (partner_database and partner_database.is_suppressed(row)): continue
        pipeline=row.get('pipeline') or classify(row['company_name']+' '+ ' '.join(c['excerpt'] for c in row.get('research_evidence',[])),row['domain'])
        if pipeline=='excluded' or row['qualification_status']=='rejected': continue
        contacts=row.get('professional_contacts',[])
        names=[c.get('name') for c in contacts if c.get('name')]
        name=row.get('contact_name') or (names[0] if names else '')
        emails=[c.get('email') for c in contacts if c.get('email')]
        email=row.get('business_email') or (emails[0] if emails else '')
        claims=row.get('research_evidence',[])
        evidence=next((c['source_url'] for c in claims if c['kind'] in {'residential_event','organises_retreats'}),None)
        evidence=evidence or (row.get('discovery_urls') or [''])[0]
        rank=row.get('commercial_rank') or row.get('priority_band')
        fit={'A':'High','B':'Medium','C':'Low'}.get(rank,'Unassessed')
        if not any(c['kind'] in {'organises_retreats','residential_event'} for c in claims): fit='Unassessed'
        notes=row.get('suitability_notes') or 'Discovery candidate; business identity and residential retreat activity need research.'
        if not email: notes+=' Public business email not found yet.'
        if row.get('contact_type')=='unknown' and email: notes+=' Email identity needs review.'
        notes+=' Marketing compliance review required.'
        item=dict(zip(HEADERS,[row.get('published_business_name') or row['company_name'],name,email,row['website'],row.get('business_category') or '',row.get('location') or '',fit,evidence,notes]))
        if include_contact_source: item['Contact source']=row.get('contact_source') or ''
        output['partners' if pipeline=='partner' else 'organisers'].append(item)
    for key,target in [('organisers',organisers),('partners',partners)]:
        Path(target).parent.mkdir(parents=True,exist_ok=True)
        with open(target,'w',encoding='utf-8-sig',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=headers);writer.writeheader()
            writer.writerows({field:safe_cell(value) for field,value in row.items()} for row in output[key])
    return {key:len(values) for key,values in output.items()}
