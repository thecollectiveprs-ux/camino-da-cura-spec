# Ideal customer refinement

The benchmark is an evidenced UK-based residential retreat organiser, not a particular named brand. No Mellulah-specific matching, mandatory named contact, .co.uk rule, LLM or paid enrichment is implemented. No live searches were made during development.

## Search audit and changes

The second pilot also contained venue-finding, curated-holiday and venue-broker titles; these patterns now route to partners rather than direct leads, without hard-coding those businesses. Remaining ambiguous operators stay provisional and may require review. The previous campaign used broad organiser/retreat wording and could fill every slot from its first query. Its venue/editorial exclusion preserved source rows but discarded partners as leads. The new campaigns/camino_organisers.json uses quoted organiser-intent phrases: I host retreats, my retreats, retreats led by, meet your retreat host, retreat leader and 2027 retreats, across yoga, Pilates, wellness/meditation/mindfulness/breathwork and creative categories. UK/location and Portugal/Spain/Italy/Europe terms are discovery hints only, never proof of base or event occurrence. These are hypotheses to test; no live win-rate is claimed.

A five-candidate pilot has six HTTP attempts maximum, zero automatic search retries, and at least three niche-specific queries before an evidence-signal stopping decision. Queries rotate categories. Search results are ranked across those queries; canonical-domain deduplication happens before website research. Five is a direct-organiser candidate target; partners do not consume slots. A search may find fewer than five strong candidates; weaker relevant candidates are retained as provisional records for review rather than invented qualifications. Per-query results and reasons are retained. Reports distinguish provisional organiser-intent yield per HTTP attempt from website-evidenced organiser yield. Budgets reset per run.

## Pipelines

Independent: teachers, instructors, retreat leaders, practitioners and small-team host signals. Boutique: own retreat programme operator signals. Partner: directories, marketplaces, venue brokers and travel/holiday agencies. Pipeline assignments from search are provisional; recorded website partner evidence can override them. Company/team size is not inferred or verified by this classification. Editorial lists and venue-hire listings are excluded from direct leads but remain in diagnostic discovery storage. Existing explicit directory referrals remain available in the legacy pilot; the new organiser pilot retains partner rows separately without spending research slots on them.

New campaign and prospect_routes table preserve all old records. Existing pilot commands/configurations remain available. New assessments include pipeline and a plain-English suitability explanation, with all full evidence, contact provenance, compliance and suppression data retained. Excluded/confirmed irrelevant and suppressed prospects are omitted from clean exports.

## Contacts and suitability

About, team/founder/host, programme, retreat and Contact paths are research targets; Contact/About/team get priority. Explicit published Name – Role statements can produce a named contact even without an email. Displayed and mailto emails remain source-attributed; generic business inboxes are allowed and address guessing is never used. Explicit og:site_name supplies a published business label where available. Published UK/England/Scotland/Wales/Northern Ireland base statements support location; domain endings never do.

Six evidence weights remain configurable. Generic keywords alone earn at most the activity criterion (15), not a high score. Qualification needs documented organiser/base/activity and a residential event/programme, subject to capacity/ownership/identity flags. Past adverts never prove occurrence. Advertised international destinations are noted separately from completed history. No email or named contact is required for commercial qualification. Unknown contact identity can require contact review while score and commercial fit remain unchanged. Public availability still does not confer marketing permission.

Clean Fit maps A/B/C to High/Medium/Low for researched evidence, with Unassessed for missing research or no organiser/event evidence. Notes state remaining uncertainties; Fit is not a booking-intent, budget, legal eligibility or confirmed capacity prediction. Future retreat evidence is advertised, not proof of a completed event. Current conservative English/date rules and inaccessible/JavaScript pages can still miss facts.

## Clean exports

Default paths: exports/organiser-leads.csv and exports/directory-partners.csv. Both use UTF-8 BOM, normal CSV quoting and formula protection for Excel. Exact headers:

Business,Contact name,Email,Website,Retreat type,UK location,Fit,Evidence URL,Notes

Primary and secondary direct pipelines share the organiser export; partners have their own file and do not count as direct leads. Unknown fact fields remain blank. Named contacts and emails can come from separately published blocks; no unproved association is asserted. Evidence URL selects organiser/event evidence if available, otherwise a clearly unverified discovery URL. Suppression applies to all contacts/businesses and both exports. Review artifacts never grant marketing approval.

Preview default files have been generated locally from a SQLite backup of the existing v2 pilot, at data/organiser-export-preview.sqlite3. Old assessments were not rerun or upgraded; their missing information remains missing. Original pilot databases and outputs are unchanged. Use this preview only as a view of earlier evidence, not a new live result.

Optional full audit CSV retains the existing export command:

```powershell
.\.venv\Scripts\python.exe -m leadgen --db data/camino-organisers-5.sqlite3 export --campaign camino-organisers --status all --output exports/organiser-full-audit.csv
```

## Controlled five-candidate live test

With BRAVE_SEARCH_API_KEY set and service usage approved:

```powershell
.\.venv\Scripts\python.exe -u -m leadgen --db data/camino-organisers-5.sqlite3 organiser-pilot --limit 5 --max-requests 6
```

This discovers up to five direct candidates across multiple niches, researches them with existing rate limits/deadlines, and writes the two default clean exports plus exports/organiser-leads.csv.summary.json. It uses a separate database and does not modify either earlier pilot. Future repetitions overwrite the new clean default files, not the historic pilot CSVs. Partners remain in the database/export without direct research or qualification claims. No messages are sent.

To regenerate clean exports without network calls:

```powershell
.\.venv\Scripts\python.exe -m leadgen --db data/camino-organisers-5.sqlite3 export-clean
```

87 automated tests pass, including previous 79, pipeline classification, named/generic contact extraction, contact-free scoring, clean headers/blanks/suppression, diversified budget allocation, deduplication, retained partners, keyword-only scoring, day-only review and the mock five-candidate command. No live Brave/AI calls or LLM integration during this development task.
