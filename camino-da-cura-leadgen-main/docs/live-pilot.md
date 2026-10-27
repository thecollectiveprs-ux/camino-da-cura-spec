Updated after the first pilot: read [the audit and repair report](pilot-audit.md). It supersedes the old redirect/forced-review policy below. Use the separate v2 pilot command in that report.

# Activate a small live pilot

The automated pipeline is ready for a controlled pilot, but no live Brave searches or prospect website visits have been run by the agent. Local fixtures and mocked network responses are used in all tests.

## 1. Open the project

In VS Code open this folder, choose Python: Select Interpreter, select .venv/Scripts/python.exe, then open a PowerShell terminal. First verify tests:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## 2. Obtain a Brave Search key

Open https://api-dashboard.search.brave.com/ and create/sign into your account. Review the Search plan, any payment requirements and current terms before subscribing: https://brave.com/search/api/. In the dashboard activate the appropriate Search plan and generate/copy an API key. Set a spending limit in your Brave account if available. The application uses the Web Search endpoint, not Answers. Do not paste the key into this chat or commit it.

The exact environment variable is BRAVE_SEARCH_API_KEY. The app passes it as the X-Subscription-Token request header, as documented by Brave: https://api-dashboard.search.brave.com/app/documentation/web-search/get-started.

## 3. Set the key in your current terminal

Use a hidden prompt so the key is not typed into PowerShell history:

```powershell
$braveSecret = Read-Host "Paste your Brave Search API key" -AsSecureString
$bravePointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($braveSecret)
try {
    $env:BRAVE_SEARCH_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bravePointer)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bravePointer)
}
Remove-Variable braveSecret, bravePointer
```

This applies to the current terminal only. Set it again after opening a new terminal. .env.example documents the name, but .env files are not automatically loaded. Running the next command initiates real API requests and public website visits; only do so once you approve the provider's account terms and potential costs.

## 4. Run up to ten real business candidates

```powershell
.\.venv\Scripts\python.exe -m leadgen --db data/camino-pilot-10.sqlite3 pilot --limit 10 --max-requests 10 --output exports/camino-pilot-10.csv
```

CSV: exports/camino-pilot-10.csv inside this project folder. Summary: exports/camino-pilot-10.csv.summary.json. Database: data/camino-pilot-10.sqlite3. The CSV includes all candidate outcomes, scores, evidence, missing information, contacts and review flags. It is UTF-8 with a BOM for Excel. Fewer than ten may be found if search requests fail or the budget is exhausted; ten candidates do not promise ten relevant/qualified organisers. The request budget includes retries. No 100-lead search is started. Reusing this database preserves records and avoids fresh search if its target is already reached; website research is refreshed.

## 5. Inspect the report

```powershell
.\.venv\Scripts\python.exe -m leadgen --db data/camino-pilot-10.sqlite3 report --campaign camino-uk
```

To research existing candidates without search API calls:

```powershell
.\.venv\Scripts\python.exe -m leadgen --db data/camino-pilot-10.sqlite3 research-web --limit 10 --max-pages 6
```

This last command still visits real public websites. It respects suppression. Manual reviewed-evidence import remains available via research --input; an existing manual assessment is preserved when automated research runs. Website evidence is retained separately in SQLite's website_research table, even when that manual assessment is preserved.

## What research does

It starts from search candidates, checks robots.txt and visits up to six relevant HTML pages per business, following same-domain retreat, About, Contact, team, past and upcoming links. It uses a two-second minimum interval per host, honours robots crawl-delay/request-rate and records fetch errors. Missing robots.txt (404) permits access; other robots failures stop visits. Redirects require review rather than being automatically followed. Non-public resolved addresses, nonstandard ports, huge pages, non-HTML responses and detected access restrictions are rejected. No login/CAPTCHA bypass, search-result scraping or JavaScript browser execution.

Explicit text rules extract business base, organiser/category statements, total group size, external venue use, permanent ownership, venue-only declarations, dated residential recaps and upcoming adverts. It extracts displayed/mailto emails and displayed/tel phone numbers; name and role are linked only when explicitly published with an email in the same text block. Duplicates collapse per business. Generic inbox labels use a fixed vocabulary; a person's address is labelled individual only with a published name; other email identities remain unknown and require review. Contact pages and all original evidence URLs/retrieval dates are saved.

Publisher statements are not independently verified truth. Automated claims use reviewed=false and retain their extraction method. Only explicit source statements, plus advertised upcoming activity, feed the existing scorer. Old adverts never earn occurrence points. Inferences remain unscored. Official-site identity is only likely/uncertain, so automated assessments require human confirmation before being treated as qualified. Large-group and ownership warnings remain active. No contacts receive marketing approval.

Extraction is intentionally conservative: it currently recognises dates in YYYY-MM-DD format and specific English phrases. Other date formats, JavaScript pages, PDFs, complicated layouts and vague statements may leave fields missing; they earn zero rather than guessed values. Limited country vocabulary in the extractor may leave other European destinations unknown. A UK domain or UK retreat destination is not proof of UK business base. UK means UK-based organisers, whatever their retreat destinations.

## Test result

54 tests pass, including all 34 previous tests. Added local HTML fixtures and mocked fetch/search tests cover extraction, attribution, missing information, blocked sites, duplicates, venue versus organiser, private-network/redirect/robots restrictions, manual preservation and the ten-candidate pilot command. No live credentials are used in tests. No email sender exists.
