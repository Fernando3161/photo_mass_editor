# V2 Priority 4 owner review — cost provenance, signed copies and launch

Use the committed Phase 03 catalog only after backing up `data/catalog/` together with its media, `data/input/` and `data/exports/`. These paths are ignored and private. The checks below do not make a paid provider call. Do not copy a new photo batch over the sources recorded in an existing catalog.

## Windows PowerShell from a fresh repository-root shell

```powershell
New-Item -ItemType Directory -Force -Path 'data/input','data/catalog','data/exports','data/backups','data/evidence','data/models','frontend/dist' | Out-Null
if (-not (Test-Path -LiteralPath 'requirements.lock' -PathType Leaf) -or -not (Test-Path -LiteralPath 'frontend/package-lock.json' -PathType Leaf)) { throw 'Missing dependency lockfile.' }
python scripts/setup_env.py
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath '.venv/Scripts/python.exe' -PathType Leaf)) { throw 'Canonical environment setup failed.' }
& .\.venv\Scripts\python.exe -c "import pathlib,sys; assert pathlib.Path(sys.prefix).resolve()==pathlib.Path('.venv').resolve()"
if ($LASTEXITCODE -ne 0) { throw 'Wrong Python interpreter.' }
& .\.venv\Scripts\python.exe -m unittest discover -s tests -q
if ($LASTEXITCODE -ne 0) { throw 'Backend tests failed.' }
npm --prefix frontend test
if ($LASTEXITCODE -ne 0) { throw 'Frontend tests failed.' }
& .\.venv\Scripts\python.exe scripts/frontend_bundle.py
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath 'frontend/dist/index.html' -PathType Leaf)) { throw 'Frontend build failed.' }
powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1 -Check -NoBrowser
if ($LASTEXITCODE -ne 0) { throw 'Launcher check failed.' }
```

`-Check` validates the catalog and imports any new supported files from `data/input/`; it does not start the browser or make an AI call. Record original SHA-256 values before and after if the input folder contains owner photographs. Test the actual browser separately with `powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1 -NoBrowser`; confirm only `127.0.0.1` is printed. Stop it, then use `-Lan -NoBrowser` only on a trusted private network. Confirm unauthenticated LAN requests fail, the run password works, and a false Host header fails.

## Linux from a fresh repository-root shell

```bash
mkdir -p data/input data/catalog data/exports data/backups data/evidence data/models frontend/dist
test -f requirements.lock && test -f frontend/package-lock.json || { echo 'Missing dependency lockfile' >&2; exit 1; }
python3 scripts/setup_env.py || exit 1
test -x .venv/bin/python || { echo 'Canonical environment missing' >&2; exit 1; }
.venv/bin/python -c "import pathlib,sys; assert pathlib.Path(sys.prefix).resolve()==pathlib.Path('.venv').resolve()" || exit 1
.venv/bin/python -m unittest discover -s tests -q || exit 1
npm --prefix frontend test || exit 1
.venv/bin/python scripts/frontend_bundle.py || exit 1
test -f frontend/dist/index.html || { echo 'Frontend bundle missing' >&2; exit 1; }
bash -n scripts/start.sh || exit 1
bash scripts/start.sh --check || exit 1
```

Run `bash scripts/start.sh` for a real loopback browser smoke test. Use `--lan-host YOUR_LAN_IPV4` only on a trusted network and verify Basic authentication and Host restrictions. For an offline restart, stop the server, retain the verified `.venv`, `frontend/node_modules`, `frontend/dist` and `data/models` cache, then run the launcher with package indexes unavailable; verify that it reuses the installed dependencies and current bundle. A fresh install still requires package access or a separately prepared wheel/npm cache. Never force a private model download in CI.

## Cost report and optional owner billing reconciliation

Preview or create an approved collection using the normal UI. Inspect `cost_report.json`: editing, analysis and refinement have separate planning, calculated and reconciled USD fields, dated price versions, and unknown counts. Missing token details must remain unknown. Rates can differ by provider tier, region or billing date. A planning amount is not an account spending limit.

An owner-supplied billing CSV has columns `operation,receipt_id,provider_request_id,billed_usd` and one itemized row per request. Keep it under ignored `data/evidence/`. The receipt ID and provider request ID must match the private SQLite receipt. Do not guess or distribute invoice data. To import it on Windows, first create `data/evidence/` and verify both the CSV and `data/catalog/catalog.sqlite` exist, then run `.venv\Scripts\python.exe -m backend.review.export_cli reconcile-billing --csv data/evidence/billing.csv`; on Linux use `.venv/bin/python` in the same command. A new export report will show the reconciliation while retaining the earlier immutable export report. Duplicate or mismatched rows fail as one transaction.

## Optional C2PA signed publication copies

Decide certificate issuer, trust list and private-key custody before enabling public signed export. The SDK test certificate is never a production identity. Store the certificate chain and private key under ignored private storage with restrictive permissions. The CLI signs separate copies; default UI exports remain unsigned.

From a fresh Windows PowerShell shell at the repository root:

```powershell
New-Item -ItemType Directory -Force -Path 'data/catalog','data/exports','data/evidence/signing' | Out-Null
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe' -PathType Leaf)) { throw 'Run canonical setup first.' }
if (-not (Test-Path -LiteralPath 'data/catalog/catalog.sqlite' -PathType Leaf)) { throw 'Catalog is missing.' }
if (-not (Test-Path -LiteralPath 'data/evidence/signing/cert.pem' -PathType Leaf) -or -not (Test-Path -LiteralPath 'data/evidence/signing/key.pem' -PathType Leaf)) { throw 'Owner signing credential is missing.' }
& .\.venv\Scripts\python.exe -m backend.review.export_cli preview
if ($LASTEXITCODE -ne 0) { throw 'Review the export preview before signing.' }
& .\.venv\Scripts\python.exe -m backend.review.export_cli export --authorized --c2pa-cert data/evidence/signing/cert.pem --c2pa-key data/evidence/signing/key.pem
if ($LASTEXITCODE -ne 0) { throw 'Signed export failed.' }
& .\.venv\Scripts\python.exe -m backend.review.export_cli audit
```

On Linux, create the same directories with `mkdir -p`, check each file with `test -f`, verify `.venv/bin/python` belongs to the repository, and replace the interpreter in the three CLI commands above with `.venv/bin/python`. Compare each `images/` hash to the approved version and each distinct `signed/` hash to the manifest and SQLite receipt. Inspect embedded C2PA ingredients, operations and signer. Confirm no source path, private GPS or hidden prompt text appears. Public validators will only recognize the signer if its chain meets the chosen trust policy. Owner inspection of actual photographs and publishing rights remains separate from software verification.
