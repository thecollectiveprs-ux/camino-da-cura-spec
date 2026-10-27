# Controlled 50-organiser pilot

Implemented and tested offline on 14 October 2026. No live Brave requests, prospect website visits, paid AI calls, LLM or outreach sending during this development task. Previous pilot databases and exports are preserved. 108 tests pass, including the original 96 and a fully mocked 50-business command.

## Run once you are ready for live usage

From the project folder in VS Code PowerShell, with BRAVE_SEARCH_API_KEY configured:

```powershell
.\.venv\Scripts\python.exe -u -m leadgen --db data/camino-organisers-50.sqlite3 pilot-50 --limit 50 --max-requests 40
```

--max-requests is the explicit configurable search cap; this campaign disables automatic search retries. The run stops at an adequate plausible shortlist or the cap. Fifty is a target, not a guarantee. It can return fewer than 50 suitable candidates or fewer qualified businesses. Budgets reset if you run discovery again. The command above has not been executed live.

Outputs:

- data/camino-organisers-50.sqlite3: direct businesses, full evidence, compliance, suppression and discovery diagnostics.
- data/camino-partners-50.sqlite3: separately stored partner business records.
- exports/organiser-leads-50.csv: clean direct organiser review list.
- exports/directory-partners-50.csv: clean partner list, never counted toward 50 organisers.
- exports/organiser-leads-50.csv.summary.json: discovery, research, contacts, qualification and estimated costs.
- logs/pilot.log: immediate request/stage/business/page progress and failure details.

Optional --partners-db, --output and --partners-output change the new paths. Partner and direct database paths must differ. Initial partner results are recorded only as business prospects in the partner database; their raw discovery results still remain in the main diagnostic table. A candidate later shown by website evidence to be a partner is also copied to the partner database, with its original main record retained as an excluded audit trace. It does not count as a direct lead. No previous pilot records are deleted.

## Targeting and query audit

Previous templates required Portugal/Spain/Italy/Europe and sometimes exact phrases. The new campaigns/camino_uk_50.json requires neither destination terms nor exact wording. It rotates residential/weekend/overnight/organiser/leader behaviours across yoga, Pilates, wellness, meditation/mindfulness, breathwork and creative niches, with UK/England/Scotland search location signals. Up to 20 results per query, six niche categories before early stopping under the default cap, then category-balanced ranking and canonical-domain deduplication before research. Where a niche yields fewer candidates, spare slots fill from other relevant niches. Initial category assignment is a search provenance label, not proof of business size or retreat type.

Niche-only class/studio URLs without any retreat/residential/overnight signal cannot fill the target. Clear unrelated/editorial/venue-only listings are excluded, explicit directories/brokers/marketplaces retained as partners, and uncertain plausible organisers remain review candidates. Every saved search result retains its exact URL, snippet and screening reason. Search-result statements do not establish UK business base or earn qualification points. Unverified base is flagged; documented non-UK businesses are rejected by qualification.

## Domestic-inclusive qualification

config/venue_uk_50.json is a new scoring profile; original venue.json and earlier campaign configurations remain available unchanged. Residential experience now receives 40 points, compatible group 25, relevant activity 15, external venue use 10 and recent activity 10. International history receives zero points and is not a missing criterion. Any past destination, including UK domestic retreats, scores identically when the other evidence is identical. No Portugal preference is applied. Destination history is still retained as factual/adverted information for future research.

Unknown total group size earns zero group-fit points and is flagged, but can leave a strong organiser at 75/B and qualified. Missing contact also does not change the commercial score. Qualification still requires documented UK base, organiser activity and residential evidence, adequate score and resolution of material identity/capacity/ownership flags. Day-only offers do not qualify as residential retreats; old adverts never establish an event occurred. An unknown group or unavailable email does not cause rejection.

## Contacts and clean export

Exact clean headers for this pilot:

Business,Contact name,Email,Website,Retreat type,UK location,Fit,Evidence URL,Notes,Contact source

Earlier nine-column clean exports remain unchanged. The new tenth column is public contact provenance, not legal/diagnostic clutter. Facts unknown remain blank. Full detailed audit export remains available through the existing export command.

Explicitly labelled hotel/venue/accommodation contacts are retained in raw claim evidence but not selected as organiser emails. Stronger Contact-page attribution can replace an earlier ambiguous occurrence of the same email while retaining alternate sources. An existing verified email record is preferred when the same published email is found; otherwise verification stays publicly_listed_not_verified. No email is generated, guessed, newly verified or linked to a named person merely by a name pattern. An official-looking page or contextual association is evidence, not independent proof of ownership or delivery. Review uncertain attribution before use. Suppression in either store applies to both clean exports.

## Counts and estimated costs

Summary/logs report separately: plausible direct candidates discovered; businesses successfully researched; website-evidenced organiser candidates; contactable businesses; explicit source-context contact attribution; email coverage; qualified/review/rejected counts; partners in the separate database; query results, HTTP attempts and reasons for exclusions. Contactable means a published business-associated email, not marketing permission or deliverability verification. Usable is conservatively defined for the cost report as qualified plus a published business-associated email and not suppressed. The application does not claim every contact is correctly attributed beyond its documented evidence; uncertain contacts need human review.

Brave Search price checked from https://brave.com/search/api/ on 14 October 2026: $5/1,000 requests. Forty requests have an estimated gross search cost of $0.20, before monthly credits. Price/date/source are configurable in venue_uk_50.json. Estimate is not an invoice, excludes other costs and treats failed attempts conservatively where exact billing is unknown. Cost per usable lead is null if there are no usable leads. No fixed qualified-lead or cost-per-lead promise.

Network safety, robots policy, 30-second page elapsed-time deadlines and approximately 90-second website research budgets remain. A 50-business run can take substantial time (roughly 75 minutes of website budget if every site exhausts it, plus search time); progress/timeout logs stay visible and each completed business is saved. Ctrl+C preserves completed work. Limited English/date extraction and genuinely blocked or JavaScript-only pages can still leave fields missing.

## Validation

108 tests passed. Added UK-only versus Portugal/other-country score equality, unknown-size/no-contact retention, non-UK rejection, destination-free queries, balanced 50-domain discovery, separate partner storage/export, contact source/cost metrics, venue-contact isolation, duplicate email attribution improvement, the full mocked 50-business command, strict request cap and rejection of arbitrary niche-only URLs. No earlier pilot was used as live research input or modified during this test run.
