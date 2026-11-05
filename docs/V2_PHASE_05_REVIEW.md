# V2 Priority 5 owner review — ontology prefill

This review uses the existing private 20-photo catalog. Back up `data/catalog/` and its source media before interactive catalog acceptance. The read-only pilot below does not change SQLite or source photos. Do not reimport or replace photographs for this review.

## Windows PowerShell, fresh repository-root shell

```powershell
New-Item -ItemType Directory -Force -Path 'data/evidence' | Out-Null
if (-not (Test-Path -LiteralPath 'requirements.lock' -PathType Leaf) -or -not (Test-Path -LiteralPath 'frontend/package-lock.json' -PathType Leaf)) { throw 'Dependency lockfile missing.' }
python scripts/setup_env.py
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath '.venv/Scripts/python.exe' -PathType Leaf)) { throw 'Canonical environment setup failed.' }
& .\.venv\Scripts\python.exe -c "import pathlib,sys; assert pathlib.Path(sys.prefix).resolve()==pathlib.Path('.venv').resolve()"
if ($LASTEXITCODE -ne 0) { throw 'Wrong Python interpreter.' }
& .\.venv\Scripts\python.exe -m unittest discover -s tests -q
if ($LASTEXITCODE -ne 0) { throw 'Backend tests failed.' }
npm --prefix frontend test
if ($LASTEXITCODE -ne 0) { throw 'Frontend tests failed.' }
npm --prefix frontend run build
if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
if (-not (Test-Path -LiteralPath 'data/catalog/catalog.sqlite' -PathType Leaf)) { throw 'Private pilot catalog missing.' }
if (-not (Test-Path -LiteralPath 'data/models/clip-vit-base-patch32-d15189d7/onnx/model_quantized.onnx' -PathType Leaf)) { throw 'Verified local model cache missing; prepare it with the documented setup prefetch.' }
& .\.venv\Scripts\python.exe scripts/evaluate_ontology_pilot.py
if ($LASTEXITCODE -ne 0) { throw 'Pilot evaluation failed.' }
```

## Linux, fresh repository-root shell

```bash
mkdir -p data/evidence
test -f requirements.lock && test -f frontend/package-lock.json || { echo 'Dependency lockfile missing' >&2; exit 1; }
python3 scripts/setup_env.py || exit 1
test -x .venv/bin/python || { echo 'Canonical environment missing' >&2; exit 1; }
.venv/bin/python -c "import pathlib,sys; assert pathlib.Path(sys.prefix).resolve()==pathlib.Path('.venv').resolve()" || exit 1
.venv/bin/python -m unittest discover -s tests -q || exit 1
npm --prefix frontend test || exit 1
npm --prefix frontend run build || exit 1
test -f data/catalog/catalog.sqlite || { echo 'Private pilot catalog missing' >&2; exit 1; }
test -f data/models/clip-vit-base-patch32-d15189d7/onnx/model_quantized.onnx || { echo 'Verified model cache missing' >&2; exit 1; }
.venv/bin/python scripts/evaluate_ontology_pilot.py || exit 1
```

The script verifies the cached model and every thumbnail hash. Inspect ignored `data/evidence/ontology-pilot.png` and `ontology-pilot.json`. For each photograph, record owner judgment of subject, every content/condition tag, draft preset and local recipe; calculate subject accuracy, content precision/recall, condition accuracy, preset agreement and useful tags per photo. Record false positives, missing tags, clicks and correction time. The report's coverage counts are not accuracy.

In the browser, authorize **Suggest current photo** on a photo with empty catalog fields. Verify proposals appear in the catalog form as provisional, edit one tag and preset, and confirm no catalog value or prompt history changes before **Accept & prepare**. Check the prompt preview updates and displays a conflict if owner instructions contradict approved constraints. Accept, then save one unapproved prompt version; repeat preview and compilation and verify no duplicate version. Undo a separate acceptance. Confirm a nonempty owner subject/preset remains unchanged, and a local correction preview works without compiling a prompt. For a selection of at most 20, inspect the compact table, bulk accept correct rows, correct exceptions individually, and undo a batch. No image edit or paid API call is needed.

Owner visual and workflow acceptance remains open. The owner alone stages and commits accepted changes or starts another phase.
