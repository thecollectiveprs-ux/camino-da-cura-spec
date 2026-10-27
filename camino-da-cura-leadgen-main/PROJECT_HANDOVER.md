# Camino da Cura project handover

Updated 21 October 2026. This document contains no credentials or private leads.

## Purpose and current implementation

Python lead research tool for UK-based residential retreat organisers who might hire Camino da Cura. The current 50-organiser campaign accepts previous retreats in any country, including UK-only experience, with no Portugal preference. Yoga, Pilates, wellness, meditation, breathwork and creative organisers are included. Unknown group size or a missing email does not automatically reject a relevant organiser. Partner directories and marketplaces are kept separately; venue-only businesses are excluded.

Discovery uses Brave Search; website research, rule-based qualification, SQLite storage and CSV export are implemented. No LLM assessment or outbound email sender is implemented. Public email availability does not establish marketing permission or delivery verification. Do not describe discovered candidates as qualified without evidence.

Primary files: campaigns/camino_uk_50.json, config/venue_uk_50.json, leadgen/, tests/, docs/pilot-50.md. Earlier configurations remain for compatibility. README contains historical milestone descriptions; prefer the current pilot guide for the latest behaviour. Historical statements that a pilot was not run describe development sessions, not the current presence of local pilot results.

## Windows and VS Code

Open the existing project folder in VS Code. Use Python: Select Interpreter to select .venv\Scripts\python.exe. Git is separate from the GitHub connector; VS Code has built-in Git support and no additional GitHub extension is required for basic version control.

Python 3.11+ is required; runtime uses only the standard library. On a new machine create an environment with `py -3 -m venv .venv`. From the project root, run offline unit tests with:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests use mocks and synthetic examples, but two historical regression fixtures contain real pilot research: fixtures/previous_pilot.json and fixtures/organiser-pilot-audit.json. They are intentionally ignored by Git. A fresh clone needs those files transferred securely by an authorised company owner before the full historical suite can pass. Do not publish them to fix a missing-fixture failure. Synthetic replacements can be developed later.

## Credentials and private data

.env.example lists BRAVE_SEARCH_API_KEY with no value. The application reads the process environment and does not automatically load .env. No OpenAI key is currently used by this code. Provision company credentials later through the company's approved process; never paste them into code, chat, documentation or commits.

.gitignore excludes environment files, credential files, virtual environments, SQLite databases and sidecars, CSV/Excel exports, logs, data/exports/private-lead folders and historical pilot audit artifacts. Ignoring files does not protect files already committed: inspect the Git index before each publication. Private databases and exports require a separate secure backup and transfer; Git will not carry them to a new machine.

## GitHub repository and first commit

The current private repository is https://github.com/charcoalmyne-eng/camino-da-cura-leadgen, owned by the personal account charcoalmyne-eng. The company organisation has not been created. The user chose to start with a personal private repository; a later company ownership transfer or separate copy needs explicit approval.

The local main branch is connected through the origin remote. Source files are being prepared for the first commit. Confirm the intended Git commit name and email before creating it; set them locally for this repository only. Review staged file names and contents before publication. No push is authorised yet.

Offline verification on 21 October 2026: all 108 tests passed with network connections blocked and API credentials cleared for the test process. Private historical fixtures are required for the full local suite, as described above. The corresponding private audit reports are also excluded; historical links to those reports will not resolve in a source-only clone.

Git carries committed source and history. It does not transfer chat history, secrets, virtual environments or ignored research data. Transfer private research through a separately approved secure channel. No account switching, paid API calls or outreach are authorised by this handover.

## Working copy and next steps

The existing working copy is in OneDrive. It has not been moved or deleted. If a separate company working copy is desired, agree its local destination first; do not treat Google Drive or OneDrive sync as Git hosting. Recreate .venv on a new machine rather than copying it.

Before any live pilot, inspect output paths and use new database/export names to preserve earlier research. Live discovery and website research require separate approval. Request caps are per run. Existing lead totals and quality have not been re-audited in this Git setup task. The next product milestone is a separately approved lead assessment workflow; no paid API or account switch is needed for local Git preparation.
