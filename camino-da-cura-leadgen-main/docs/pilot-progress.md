# Pilot appeared to hang: investigation and repair

At inspection on 13 October 2026 no Python pilot process was running. Windows process inspection was initially permission-denied; approved process inspection subsequently returned no Python processes. Therefore no current socket, blocked thread or input wait could be attached to or identified. The existing v2 database contains 8 candidates, 3 completed discovery runs and zero website_research/assessment records. The last recorded discovery completed 10 queries without API errors. No historical progress log existed; logs/pilot.log is newly added, and initial entries are from mock tests, not live work.

Confirmed code issues: the website stage had no progress output and collected the entire batch before saving any research. Socket timeouts were 15 seconds for website operations and 20 seconds for Brave, but DNS resolution and continuously trickling reads had no elapsed-time deadline. Rate-limit waits, robots requests, redirects and retries added further silent delays. There is no interactive input prompt in the pilot. The specific historical request that delayed or stopped the process cannot be established from the saved evidence.

Repairs: immediate stage/business/page logging, 5-second waiting messages, timeout warnings, file log at logs/pilot.log, per-business database checkpoints and Ctrl+C guidance. Production page fetching runs in a killable worker with a 30-second wall-clock deadline including robots/DNS/redirects/retries; website research has a 90-second budget with short worker cleanup overhead. Brave searches have a 45-second elapsed-time deadline; an uncertain/failed request stops discovery rather than automatically spending further credits. Mock/custom fetchers remain directly injectable for tests. Windows multiprocessing entry is guarded to prevent child processes restarting the CLI. Existing access restrictions, IP validation and suppression remain in place.

79 tests passed, including existing 74, worker termination, successful source serialization, error-category preservation, request timeout metadata and website-budget exhaustion. No new paid API calls or live website visits were made during debugging. Existing live results were only read.

## Resume the 8 saved candidates without search charges

From the project folder in VS Code PowerShell:

```powershell
.\.venv\Scripts\python.exe -u -m leadgen --db data/camino-pilot-10-v2.sqlite3 research-web --limit 10
.\.venv\Scripts\python.exe -m leadgen --db data/camino-pilot-10-v2.sqlite3 export --campaign camino-uk --status all --output exports/camino-pilot-10-v2-resumed.csv
```

This visits business websites, but never calls Brave. It researches up to the available eight saved candidates, preserving existing records and manual assessments. The new CSV path preserves any earlier v2 export. A complete ten-business research stage can take several minutes, but now shows progress and continues after individual network failures.

To view progress from another terminal:

```powershell
Get-Content logs/pilot.log -Tail 20 -Wait
```

If another terminal is still running an old version, stop it with Ctrl+C before restarting; already saved discovery candidates remain. No process was stopped by this repair.

## Restart discovery only when further API usage is approved

```powershell
.\.venv\Scripts\python.exe -u -m leadgen --db data/camino-pilot-10-v2.sqlite3 pilot --limit 10 --max-requests 10 --output exports/camino-pilot-10-v2-resumed.csv
```

Unlike research-web, pilot can make paid Brave requests because the current database has fewer than ten candidates. This command was not executed during debugging. Run only after deciding to spend additional search credits.
