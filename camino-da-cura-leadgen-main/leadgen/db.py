import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from .models import canonical_domain

SCHEMA = """
CREATE TABLE IF NOT EXISTS prospects (
 id INTEGER PRIMARY KEY, domain TEXT UNIQUE NOT NULL, company_name TEXT NOT NULL,
 website TEXT NOT NULL, business_category TEXT, location TEXT, retreat_offering TEXT,
 contact_name TEXT, professional_role TEXT, business_email TEXT,
 email_verification_status TEXT NOT NULL DEFAULT 'not_verified',
 legal_form TEXT NOT NULL DEFAULT 'unknown', jurisdiction TEXT,
 contact_type TEXT NOT NULL DEFAULT 'unknown', lawful_basis_review TEXT NOT NULL DEFAULT 'pending',
 marketing_eligibility TEXT NOT NULL DEFAULT 'requires_review', consent_status TEXT NOT NULL DEFAULT 'unknown',
 compliance_review_status TEXT NOT NULL DEFAULT 'pending',
 lead_score INTEGER CHECK(lead_score BETWEEN 0 AND 100),
 qualification_status TEXT NOT NULL DEFAULT 'discovered' CHECK(qualification_status IN ('discovered','qualified','rejected','requires_review')),
 qualification_explanation TEXT, rejection_reason TEXT,
 missing_information TEXT NOT NULL DEFAULT 'Official website confirmation; business identity; retreat evidence; legal form; contact details',
 date_discovered TEXT NOT NULL, date_last_seen TEXT NOT NULL, date_last_verified TEXT,
 outreach_status TEXT NOT NULL DEFAULT 'not_contacted'
);
CREATE TABLE IF NOT EXISTS campaigns (name TEXT PRIMARY KEY, config_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS campaign_prospects (
 campaign TEXT NOT NULL REFERENCES campaigns(name), prospect_id INTEGER NOT NULL REFERENCES prospects(id),
 PRIMARY KEY(campaign, prospect_id)
);
CREATE TABLE IF NOT EXISTS evidence (
 id INTEGER PRIMARY KEY, prospect_id INTEGER NOT NULL REFERENCES prospects(id),
 source_url TEXT NOT NULL, query TEXT NOT NULL, title TEXT NOT NULL, description TEXT NOT NULL,
 source_type TEXT NOT NULL DEFAULT 'search_result', fact_status TEXT NOT NULL DEFAULT 'unverified',
 retrieved_at TEXT NOT NULL, UNIQUE(prospect_id, source_url, query)
);
CREATE TABLE IF NOT EXISTS suppression (
 kind TEXT NOT NULL CHECK(kind IN ('domain','email')), value TEXT NOT NULL,
 reason TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(kind,value)
);
CREATE TABLE IF NOT EXISTS assessments (
 campaign TEXT NOT NULL REFERENCES campaigns(name), prospect_id INTEGER NOT NULL REFERENCES prospects(id),
 result_json TEXT NOT NULL, config_json TEXT NOT NULL, assessed_at TEXT NOT NULL,
 PRIMARY KEY(campaign,prospect_id)
);
CREATE TABLE IF NOT EXISTS website_research (
 id INTEGER PRIMARY KEY, campaign TEXT NOT NULL REFERENCES campaigns(name),
 prospect_id INTEGER NOT NULL REFERENCES prospects(id), record_json TEXT NOT NULL, retrieved_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS discovery_results (
 id INTEGER PRIMARY KEY, campaign TEXT NOT NULL REFERENCES campaigns(name), query TEXT NOT NULL,
 source_url TEXT NOT NULL, title TEXT NOT NULL, description TEXT NOT NULL,
 selection_reason TEXT NOT NULL, rank INTEGER NOT NULL, retrieved_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS discovery_runs (
 id INTEGER PRIMARY KEY, campaign TEXT NOT NULL REFERENCES campaigns(name), report_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS prospect_routes (
 campaign TEXT NOT NULL REFERENCES campaigns(name), prospect_id INTEGER NOT NULL REFERENCES prospects(id),
 pipeline TEXT NOT NULL, reason TEXT NOT NULL, PRIMARY KEY(campaign,prospect_id)
);
PRAGMA user_version = 2;
"""

def now():
    return datetime.now(timezone.utc).isoformat()

class Database:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(SCHEMA)

    def close(self): self.conn.close()

    def register_campaign(self, campaign):
        from dataclasses import asdict
        with self.conn:
            self.conn.execute("INSERT INTO campaigns VALUES (?,?) ON CONFLICT(name) DO UPDATE SET config_json=excluded.config_json", (campaign.name, json.dumps(asdict(campaign))))

    def upsert(self, campaign, result, query):
        domain, stamp = canonical_domain(result.url), now()
        with self.conn:
            existing = self.conn.execute("SELECT id FROM prospects WHERE domain=?", (domain,)).fetchone()
            self.conn.execute("""INSERT INTO prospects(domain,company_name,website,date_discovered,date_last_seen)
                VALUES (?,?,?,?,?) ON CONFLICT(domain) DO UPDATE SET date_last_seen=excluded.date_last_seen""",
                (domain, result.title or domain, result.url, stamp, stamp))
            pid = self.conn.execute("SELECT id FROM prospects WHERE domain=?", (domain,)).fetchone()[0]
            self.conn.execute("INSERT OR IGNORE INTO campaign_prospects VALUES (?,?)", (campaign, pid))
            self.conn.execute("""INSERT INTO evidence(prospect_id,source_url,query,title,description,retrieved_at)
                VALUES (?,?,?,?,?,?) ON CONFLICT(prospect_id,source_url,query) DO UPDATE SET
                title=excluded.title,description=excluded.description,retrieved_at=excluded.retrieved_at""",
                (pid,result.url,query,result.title,result.description,stamp))
        return existing is None

    def rows(self, campaign=None):
        sql = "SELECT p.* FROM prospects p"
        args = ()
        if campaign:
            sql += " JOIN campaign_prospects c ON c.prospect_id=p.id WHERE c.campaign=?"
            args = (campaign,)
        rows = [dict(row) for row in self.conn.execute(sql + " ORDER BY p.domain", args)]
        for row in rows:
            row['discovery_urls'] = [r[0] for r in self.conn.execute("SELECT DISTINCT source_url FROM evidence WHERE prospect_id=? AND source_type='search_result' AND query!='reviewed research import'",(row['id'],))]
        if campaign:
            for row in rows:
                routing=self.conn.execute('SELECT pipeline,reason FROM prospect_routes WHERE campaign=? AND prospect_id=?',(campaign,row['id'])).fetchone()
                if routing:
                    row['pipeline']=routing[0]; row['pipeline_reason']=routing[1]
                assessment = self.conn.execute('SELECT result_json,assessed_at FROM assessments WHERE campaign=? AND prospect_id=?',(campaign,row['id'])).fetchone()
                if assessment:
                    result = json.loads(assessment['result_json'])
                    row.update({key:result[key] for key in ('lead_score','qualification_status','qualification_explanation','rejection_reason','missing_information','business_category','priority_band','discovery_priority')})
                    row['research_evidence'] = result['claims']
                    row['suitability_notes'] = result.get('suitability_notes','')
                    row['published_business_name'] = result.get('published_business_name')
                    if result.get('pipeline'): row['pipeline']=result['pipeline']
                    row['research_metadata'] = result.get('research_metadata',{})
                    row['official_contact_pages'] = row['research_metadata'].get('contact_pages',[])
                    row['flags'] = result['flags']
                    row['past_destinations'] = result['past_destinations']
                    row['european_experience'] = result['european_experience']
                    row['preferred_destination_experience'] = result['preferred_destination_experience']
                    row['date_assessed'] = assessment['assessed_at']
                    row['research_status'] = 'researched' if row['research_metadata'].get('pages') else ('inaccessible' if row['research_metadata'].get('errors') else 'not_researched')
                    row['commercial_rank'] = result['priority_band'] if row['research_status']=='researched' else 'unassessed'
                    claims = [c for c in result['claims'] if (c.get('reviewed') is True and c.get('fact_status')=='documented') or (c.get('extraction_method')=='explicit_rule_v1' and c.get('fact_status')=='publisher_statement')]
                    bases = [c['value'] for c in claims if c['kind']=='base_country']
                    if bases: row['location'] = '; '.join(sorted(set(bases)))
                    legal = [c for c in claims if c['kind']=='legal_form']
                    if legal:
                        row['legal_form'] = legal[0]['value']
                        row['jurisdiction'] = legal[0].get('jurisdiction')
                    contacts = result['contacts']
                    row['professional_contacts'] = contacts
                    if contacts:
                        previous_email=row.get('business_email'); previous_verification=row.get('email_verification_status')
                        contact = next((c for c in contacts if c.get('email')==previous_email and previous_verification=='verified'),None)
                        contact = contact or next((c for c in contacts if c.get('email') and c.get('name')),None)
                        contact = contact or next((c for c in contacts if c.get('email')), contacts[0])
                        row['business_phones'] = list(dict.fromkeys(c['phone'] for c in contacts if c.get('phone')))
                        row['business_email'] = contact.get('email')
                        row['contact_name'] = contact.get('name')
                        row['professional_role'] = contact.get('role')
                        row['contact_type'] = contact.get('email_type','unknown')
                        row['contact_source'] = contact['source_url']
                        row['contact_retrieved_at'] = contact['retrieved_at']
                        row['email_verification_status'] = 'verified' if previous_verification=='verified' and previous_email==contact.get('email') else 'publicly_listed_not_verified'
        return rows

    def sources(self, pid):
        return [dict(row) for row in self.conn.execute("SELECT source_url,title,description,source_type,fact_status,retrieved_at FROM evidence WHERE prospect_id=? ORDER BY id", (pid,))]

    def suppress(self, kind, value, reason):
        value = canonical_domain("https://" + value) if kind == "domain" else value.strip().lower()
        with self.conn:
            self.conn.execute("INSERT INTO suppression VALUES (?,?,?,?) ON CONFLICT(kind,value) DO UPDATE SET reason=excluded.reason", (kind,value,reason,now()))

    def is_suppressed(self, row):
        emails = {str(row.get('business_email') or '').lower()}
        emails.update(str(c.get('email') or '').lower() for c in row.get('professional_contacts',[]))
        if self.conn.execute("SELECT 1 FROM suppression WHERE kind='domain' AND value=?",(row['domain'],)).fetchone():
            return True
        return any(self.conn.execute("SELECT 1 FROM suppression WHERE kind='email' AND value=?",(email,)).fetchone() for email in emails)

    def summary(self, campaign=None):
        rows = self.rows(campaign)
        return {"total": len(rows), **{state: sum(r['qualification_status'] == state for r in rows) for state in ('discovered','qualified','rejected','requires_review')},
                "compliance_pending": sum(r['compliance_review_status'] == 'pending' for r in rows),
                "suppressed": sum(self.is_suppressed(r) for r in rows),
                "priority_bands": {band:sum(r.get('priority_band')==band for r in rows) for band in ('A','B','C')},
                "details": [{"domain":r['domain'],"score":r['lead_score'],"priority":r.get('priority_band'),"flags":r.get('flags',[]),"rejection_reason":r['rejection_reason'],"missing_information":r['missing_information']} for r in rows]}
