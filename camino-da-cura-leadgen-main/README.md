Controlled 50-organiser pilot: [UK-based, any retreat destination, separate partner database and capped command](docs/pilot-50.md). 108 offline tests pass; live pilot not run.

Latest six-query audit: [one returned result, no rejected results; query/crawler repairs](docs/latest-organiser-pilot-audit.md). 96 tests pass. No new live requests; original pilot database preserved.

Organiser-first search and clean exports: [five-candidate test and ideal-customer rules](docs/organiser-refinement.md). Default clean outputs: exports/organiser-leads.csv and exports/directory-partners.csv. 87 tests pass; original pilot results preserved.

Progress/timeouts repaired: [resume saved candidates without new Brave searches](docs/pilot-progress.md). 79 tests pass.

First live pilot audited and repaired. See [diagnosis, repairs and the new ten-candidate command](docs/pilot-audit.md). The v2 command uses separate output files. 74 tests pass; no new live run performed. Original first-pilot files are unchanged.

# Automated website research milestone

Website research and a ten-candidate pilot are now implemented. Start with [the beginner live-pilot guide](docs/live-pilot.md). Run `research-web` for existing candidates, or `pilot --limit 10` to discover, research, score and export. Do not run these network commands until you have approved live service usage.

Automated evidence is source-attributed and distinct from human-reviewed evidence; likely/uncertain identity stays under review. All 54 tests pass, including the original 34. The sections below describe the previous milestones; their references to website research as future/manual-only are superseded by the linked guide.

# Camino da Cura Lead Research Agent

Find UK-based businesses that organise residential group retreats and could use Camino da Cura in Portugal. Consumers and attendee leads are excluded. The first live pilot aims to discover 100 prospects, research relevance and report the qualification count; it does not promise 100 qualified leads. No automatic email sending or paid service activation.

## Run in VS Code on Windows

Open this folder in VS Code. Select **Python: Select Interpreter** from the command palette and choose .venv/Scripts/python.exe. Open a PowerShell terminal in the project root. Python 3.11+ is required; the existing environment uses Python 3.12.14. There are no third-party runtime dependencies.

```powershell
# Test everything before live discovery
.\.venv\Scripts\python.exe -m unittest discover -s tests -v

# Existing offline discovery demo (two synthetic search candidates)
.\.venv\Scripts\python.exe -m leadgen discover --dry-run

# Camino scoring demo: six synthetic researched businesses
.\.venv\Scripts\python.exe -m leadgen --db data/camino-demo.sqlite3 research --input fixtures/camino_research.json
.\.venv\Scripts\python.exe -m leadgen --db data/camino-demo.sqlite3 report --campaign camino-uk --output exports/camino-demo-summary.json
.\.venv\Scripts\python.exe -m leadgen --db data/camino-demo.sqlite3 export --campaign camino-uk --status all --output exports/camino-demo-review.csv
.\.venv\Scripts\python.exe -m leadgen --db data/camino-demo.sqlite3 export --campaign camino-uk --output exports/camino-demo-qualified.csv
```

Global --db precedes the command. Always pass --campaign camino-uk to report/export for venue-specific scores. Without a campaign, the original global business view is retained and does not apply venue assessments. Demo CSVs use UTF-8 BOM and formula protection for Excel. .example addresses and fixture claims are fictional; they must not be used as real leads.

On a new machine: install Python 3.11+ and run python -m venv .venv. The module CLI works directly from this folder. Optional pip install -e . installs lead-agent and may download packaging dependencies. .env.example documents the key; .env is not loaded automatically. Real API keys belong in environment variables, never in project files or commits.

## Configuration and requirements

- config/venue.json: venue facts and their provenance, six scoring weights, A/B thresholds, total-participant capacity, recency window, organiser base countries, preferred destinations and activity priorities.
- campaigns/camino_uk.json: UK-based organiser search phrases across all three priorities, 100-prospect target, GB search region, request budget and rate/retry limits. Change locations/search_country and allowed_base_countries together for future European expansion.
- campaigns/yoga_uk.json: original configuration retained for compatibility.
- docs/requirements.md: current business requirements and next development steps.

The venue website confirms five bedrooms, private/shared rooms, ideal groups of 10–15 and listed facilities. Website evidence checked 12 October 2026: https://caminodacura.com/. Exclusive venue hire is owner-provided. Steam room remains owner-reported pending website confirmation. Ideal group size is a targeting preference, not a verified bed allocation; confirm facilitator and guest accommodation before booking.

## Qualification rules

| Criterion | Points |
| --- | ---: |
| Previous residential retreat experience | 25 |
| Documented compatible total group size (10–15) | 25 |
| Previous international retreats | 15 |
| Relevant retreat activity | 15 |
| Documented externally hired venues | 10 |
| Recent business activity or upcoming retreat | 10 |

A = 80–100; B = 60–79; C = below 60. Weights sum to 100 and are configurable. Unknown/unreviewed/inferred evidence earns zero and appears in missing information. Dates use the scoring machine's current date; the unit tests use a fixed date. Recent activity means a business update/retreat recap within 365 days by default, or a documented upcoming retreat.

Qualification is separate from the score band. A/B businesses qualify for venue-fit research when their allowed base country, relevant activity and organiser status are evidenced, with no capacity/ownership/conflicting-geography flags. Unknown group size can therefore produce a B lead with group size explicitly missing; it is not asserted to fit. C leads remain under review. Venue-only businesses, individual consumers/attendees and businesses outside the configured base countries are rejected. Larger documented groups and permanent venue ownership without evidence of external hiring require review, even if the score is high. Portugal/Spain and other European hosting history are reported separately. Budget and booking intentions are never inferred.

Past residential experience requires a dated, past event backed by reviewed recap, testimonial or attendance evidence. An old advertisement is not occurrence evidence, even if an import incorrectly marks occurred=true. Future adverts can support upcoming activity only. Group-size points require an explicit total_participants basis; guest-only counts do not establish total capacity.

## Reviewed evidence input

The research command currently imports human-reviewed JSON; it does not fetch prospect websites or call an LLM. Use fixtures/camino_research.json as a structural example only. Each business has company_name, website and claims. Every claim requires kind, source_url, retrieved_at (ISO date/time), excerpt, reviewed and fact_status. Only reviewed=true and fact_status=documented claims score. A reviewer must check that the source actually supports the structured values; this validator cannot independently verify their truth. Keep summaries/inferences unreviewed or marked inference.

Claim kinds: base_country, business_type, organises_retreats, solely_venue, owns_venue, external_venues, residential_event, group_size, activity, contact, legal_form. Value meanings and event/activity fields are illustrated in the fixture. business_type values and priority groups are in venue config. Contact claims require the publicly listed email and generic_business or individual_professional email_type; optional name/role and official contact-page URLs are retained. No email construction or guessing. Public listings are marked publicly_listed_not_verified, never verified. Legal form can include jurisdiction. All marketing reviews remain pending.

Scores and full claim evidence are stored in a campaign-specific assessments table with configuration snapshot and assessment date. Reimports update existing domain/campaign records. Legacy records and tests remain intact. date_last_seen means search/import observation; date_last_verified is deliberately not changed by a research import. Assessment time does not claim a fresh website retrieval. Per-criterion evidence and points are in qualification_explanation; all source URLs/dates are in CSV evidence.

## Live pilot (not run)

After selecting an approved search service and setting BRAVE_SEARCH_API_KEY in the process environment:

```powershell
.\.venv\Scripts\python.exe -m leadgen discover --campaign campaigns/camino_uk.json
.\.venv\Scripts\python.exe -m leadgen report --campaign camino-uk
# Once actual evidence has been reviewed into a separate JSON file:
.\.venv\Scripts\python.exe -m leadgen research --input reviewed-research.json
.\.venv\Scripts\python.exe -m leadgen export --campaign camino-uk --status all --output exports/camino-review.csv
```

Brave uses its official JSON API. Request budget includes retries and resets each run. HTTP timeout is 20 seconds; 429/5xx/network errors use bounded retries, with numeric Retry-After support. Auth and malformed responses stop. A failed discovery preserves earlier results and exits 1. Bad configuration/input exits 2. Search region and UK query words do not prove UK business location. Search snippets/titles are unverified; no points are awarded automatically. The target is a stopping threshold checked between result batches, so there can be a small overshoot. Existing campaign candidates count toward the threshold. Official-site confirmation and relevance checking remain research work; 100 raw search candidates do not mean 100 relevant businesses. Search currently uses first-page results only; budget or coverage may yield fewer than 100.

Domain deduplication normalises case/www/path/query; other subdomains remain separate. Cross-domain business identity resolution is still pending verified identifiers. Directory pages and irrelevant results remain candidates until researched. These limitations will be addressed before a reliable 100-relevant-prospect pilot is claimed.

## Suppression and compliance

```powershell
.\.venv\Scripts\python.exe -m leadgen suppress --kind domain --value example.com --reason "Opt out"
.\.venv\Scripts\python.exe -m leadgen suppress --kind email --value contact@example.com --reason "Opt out"
```

Suppressed domains/emails, including secondary professional contacts, are excluded from exports. Compliance fields retain legal form, jurisdiction, contact type, lawful-basis review, eligibility and consent. Sole traders, unknown forms and personal professional contacts require human review. Public email availability does not grant marketing permission. Review CSVs are research artifacts. Existing local outreach CSV gating requires explicit --approved-by and approved compliance/lawful-basis, eligible marketing status and verified email; current research imports cannot grant any of those approvals. The reviewer name is a local attestation, not authenticated access control. There is no outbound sender or outreach-platform integration.

## Modules, storage and costs

config.py handles campaigns; providers.py contains interchangeable search adapters; discovery.py orchestrates discovery; qualification.py handles documented evidence scoring; db.py manages SQLite, campaign assessments and suppression; export.py handles Excel CSVs; cli.py exposes commands. SQLite migration adds assessments without deleting original records. Data, CSVs, .env, caches and virtual environment are Git-ignored. Restrict access to real contact data and define retention before live research.

Standard library, SQLite and mock tests are free. Brave pricing should be checked before activation: https://brave.com/search/api/. No paid services were requested. A future LLM provider will interpret research, while this deterministic scorer remains auditable and interchangeable input providers can be added. Permitted website research with robots/restriction checks, contact extraction, licensed verification and Companies House integration remain future modules.

## Validation

Original 15 tests preserved. Expanded suite checks scoring, boundaries, adverts versus occurrence, unknowns/inferences, geography, venue ownership, large groups, recency, campaign isolation, repeated imports, SQLite reopen, Excel encoding and suppression. The six-record scoring demo yields 2 qualified, 1 rejected, 3 requiring review, with 1 A / 2 B / 3 C. All six remain pending marketing compliance review. No live discovery or prospect-page fetching has been performed.
