# Phase 01 — Catalog ingestion technical report

- Date: 2026-10-30
- Branch: `dev/v1-phase-01-catalog`
- Reviewed Phase 00 baseline: `1652e3f`
- Implementation commit: `d69fac6`
- Owner/reviewer: project owner; approved and manually committed as `8ee61fb` (`ph1 reviewed`)
- Recommendation: **APPROVED**. The owner reported that thumbnail, metadata, source hash, repeat import, and automated checks pass, then authorized Phase 02.

## Commit policy update (2026-10-30)

The implementation commit listed above is a historical record. For all subsequent work, automatic commits are forbidden: development agents leave changes unstaged and uncommitted, and the owner manually stages and commits after review. This report update is itself left for owner review and manual commit.

## Scope and acceptance

| Check | Status | Evidence |
| --- | --- | --- |
| Backend skeleton and SQLite migration | PASS | `backend/catalog/`; migration `001_catalog.sql`; repeated migration test |
| Safe reference and explicit managed-copy import | PASS | Original SHA-256 before/after tests; managed-copy hash equality |
| EXIF/GPS and orientation-aware thumbnails | PASS | Synthetic EXIF IFD/GPS and orientation tests |
| Duplicates, path conflicts and stable IDs | PASS | Separate duplicate rows; conflict rejection; repeat import and relink tests |
| Indexing and preflight | PASS | Hash/capture indexes and source/managed/thumbnail integrity report |
| JPEG, PNG, TIFF, WebP and corrupt file | PASS | Synthetic multi-format and corrupt-file tests |
| Representative owner photo set and visual thumbnail review | PASS | The owner reported that the thumbnails match the source photos. A fresh reference-only review of the same 20 direct phone JPEGs under ignored `data/phase01-review-direct/` captured hashes before import, imported 20 with 0 errors, found 20 valid GPS records and 20 source/thumbnail preflight results `OK`, repeated as 20 existing/0 imported/0 errors, and matched source hashes after import. All 20 new thumbnail hashes equal those in the visually reviewed catalog. Procedure: [Phase 01 owner photo review](../docs/PHASE_01_REVIEW.md) |
| Owner metadata spot check | PASS | The owner reported that the catalog metadata spot check passed. All 20 catalog rows have capture date, camera and GPS fields; the source EXIF has no lens model, so lens is blank. Private values remain in ignored local evidence. |
| Windows/Linux CI matrix | NOT_RUN | No Windows/Linux run result is documented here; check GitHub Actions after the owner's manual commit/push |
| Owner Phase 01 review | PASS | Owner approved and manually committed the reviewed Phase 01 baseline as `8ee61fb`, then authorized Phase 02 |

## Design and implementation

The default mode references an original without copying it; `--mode copy` writes a separate immutable managed copy. A source path is unique in SQLite. Identical bytes at another path create a separate photo with a duplicate candidate link. A changed file at an existing path is rejected. Relinking a moved source requires the original hash, preserving its UUID. Thumbnail and managed paths are relative to the chosen private data root; source path is retained as observed. No project path is hardcoded.

The migration creates the Phase 01 catalog tables, many-to-many tag structure, and reserved image-version/review-event tables with a one-approved-version index. Review commands and state transitions are not implemented in this phase. The logical schema's analysis, prompt, jobs, masks, batch and export tables await their phases. The CLI provides `init`, `import-photo`, `import-folder`, `list`, `preflight` and `relink`. The read-only `list` command maps filenames to UUID thumbnails and displays captured metadata and GPS parse status without printing precise coordinates. Folder import reports sidecars and known RAW/HEIC file extensions without interpreting them. No API client, paid service, upload, editor, UI or export was added.

Changed files in the initial implementation: `.github/workflows/catalog.yml`, `README.md`, `backend/__init__.py`, `backend/catalog/{__init__.py,__main__.py,database.py,ingestion.py,migrations/001_catalog.sql}`, `requirements.lock`, `scripts/setup_env.py`, `tests/test_catalog.py`, `docs/{DATABASE_SCHEMA.md,DATA_AND_ARTIFACTS.md,DECISIONS.md,REPOSITORY_ARCHITECTURE.md}`, and `reports/PHASE_00_TECHNICAL_REPORT.md`. The uncommitted follow-up adds `docs/PHASE_01_REVIEW.md`, updates the CLI/list test, README, AGENTS instructions, `docs/{DATABASE_SCHEMA.md,DATA_AND_ARTIFACTS.md,DEVELOPMENT_WORKFLOW.md,TESTING_AND_ACCEPTANCE.md}`, and this report. Operational images and SQLite files are ignored by Git. The initial implementation used only temporary synthetic fixtures; the later owner review created a private 20-photo catalog under ignored `data/`.

## Environment and tests

Python 3.13.5 on Windows was used. The repository-local `.venv` was created with `python -m venv .venv`. The cross-platform `python scripts/setup_env.py` now creates `.venv` when absent, installs the pinned `Pillow==13.0.0` dependency from `requirements.lock`, verifies versions and `pip check`, and prints the `.venv` interpreter. Pillow has no required transitive Python dependencies. The same setup script is in the Windows/Linux CI workflow. Dependency rationale is in ADR-008. The package version was checked against [the Pillow release on PyPI](https://pypi.org/project/pillow/13.0.0/).

| Command | Result |
| --- | --- |
| `python scripts/setup_env.py` | PASS; Pillow 13.0.0, no broken requirements, `.venv/Scripts/python.exe` |
| `.venv\Scripts\python.exe -m unittest discover -s tests -v` | PASS; 13 tests, 1.029 s on the final run |
| `git diff --cached --check` | PASS before implementation commit |
| `.venv\Scripts\python.exe -m unittest discover -s tests -v` (review-guide follow-up) | PASS; 13 tests, 1.169 s, including read-only CLI listing |
| `.venv\Scripts\python.exe -m unittest discover -s tests -v` (GPS diagnostic follow-up) | PASS; 14 tests, 1.251 s, including invalid GPS reference handling |
| `.venv\Scripts\python.exe -m unittest discover -s tests -v` (owner review follow-up) | PASS; 14 tests, 1.313 s |

The initial test run failed because the synthetic JPEG helper passed `exif=None` to Pillow. The helper was corrected; later runs passed, including the current 14-test run. Automated tests used no owner photographs, external APIs, or full-resolution outputs. Test success checks data integrity and behavior, not visual correctness of real photographs. The owner separately reported that the current thumbnails match their sources. Linux execution, remote CI, RAW/HEIC compatibility, backup/restore and concurrent import stress were **NOT_RUN**. These are not claimed as passed.

The first owner attempt to capture the manual-review hash baseline failed because the guide used PowerShell's special `$input` variable as a path variable. The guide now uses `$reviewInput` and guards against an empty or overwritten baseline. The earlier review set had 18 JPEGs with numeric GPS components but NUL N/S and E/W references and 2 without a GPS IFD. The owner replaced that set with files copied directly from the phone and imported the current 20 JPEGs. A read-only inspection found valid GPS direction fields in all 20 current source files, populated private coordinates in all 20 catalog rows, matching source hashes for all 20, and matching thumbnail hashes for all 20. No managed copies exist in reference mode. The previous hash manifest and earlier source copies are no longer available locally, so this does not prove which transfer step changed the earlier files. In the first review of the direct phone copies, a new 20-entry `data/phase01-review/before.sha256.txt` was captured **after** the initial import. That run showed 20 `VALID` GPS statuses, 20 sources and thumbnails `OK`, 20 `existing` on repeat import, and unchanged hashes. Its owner-reviewed thumbnails matched their sources.

To obtain a true before-import baseline, a separate reference-only catalog was created at ignored `data/phase01-review-direct/catalog/`, pointing to the same 20 phone-copy sources without duplicating or modifying them. `data/phase01-review-direct/before.sha256.txt` was captured before catalog initialization/import. First import reported 20 `imported`, 0 `existing`, 0 `errors`; listing reported 20 `VALID` GPS statuses; preflight reported 20 sources and 20 thumbnails `OK`; repeat import reported 20 `existing`, 0 `imported`, 0 `errors`; and the after-import manifest matched the before-import manifest. All 20 source hashes and all 20 thumbnail hashes match the owner-reviewed prior catalog, so the fresh review presents the same thumbnail bytes. Private JSON and hash evidence remains under ignored `data/`. The owner subsequently reported that the metadata check passed.

## Owner review procedure corrections

The private `data/phase01-review/` input directory was absent in the fresh checkout because `data/` is ignored by Git. The first instructions did not make folder creation sufficiently prominent before the import and hash commands. The owner confirmed that explicit PowerShell variables `$reviewRoot`, `$reviewInput`, `$reviewCatalog` and `New-Item -ItemType Directory -Force -Path $reviewInput` worked, followed by `python scripts/setup_env.py` and `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`, `import-folder`, `list`, and `preflight`. The earlier `Get-ChildItem -LiteralPath $input` failed because `$input` is a PowerShell automatic variable and was empty; the guide now consistently uses `$reviewInput`. The initial successful commands printed results but did not save every evidence file, so the separate fresh review captured complete import, list, preflight, repeat-import, and before/after hash evidence.

The review guide now creates the review root, input, and catalog directories in its runnable commands, checks for input files, uses the confirmed `.\.venv\Scripts\python.exe` invocation, explains UUID thumbnail names and catalog fields, and documents clean reruns and the GPS-source discrepancy. Development instructions now require every runnable procedure to create its generated directories and verify inputs. These are documentation changes; no catalog behavior or dependency changed.

## Privacy, safety and unresolved risks

- **Low, owner/Phase 01 review:** the owner reported that thumbnail and metadata checks pass; branch/documentation review and explicit phase approval remain. Private GPS stays in the ignored SQLite database; no public export exists.
- **Low, earlier source metadata discrepancy:** the earlier review copies had 18 invalid GPS references and 2 absent GPS IFDs; all current direct phone copies have valid references. The previous copies are unavailable for a direct byte comparison, so Google Drive is a plausible but unverified cause. Preserve the current phone copies and hash manifest for the rest of this review.
- **Medium, future recovery work:** a process crash between artifact creation and SQLite commit could leave an orphan thumbnail or managed copy. Preflight detects missing or altered referenced media; orphan scanning and backup/restore automation remain future work. No automatic deletion occurs.
- **Medium, format decision:** RAW, HEIC/HEIF and sidecar interpretation are deferred. Those files are reported instead of imported.
- **Low, operational:** reference mode depends on external source paths remaining available. Preflight flags missing/changed files, and hash-verified relink repairs a move.
- **Low, later review phase:** reserved review tables constrain duplicate approvals, but explicit review event transactions and state transition APIs must be added and tested in Phase 04.

## Reproduction and handoff

Follow [the Phase 01 owner photo review](../docs/PHASE_01_REVIEW.md) from the repository root to reproduce the private catalog check. It specifies folders, Windows/Linux commands, hash capture, import, listing, preflight, visual inspection, and repeat import. The default mode is reference-only. Keep `data/` private and backed up.

## Owner approval update (2026-10-30)

The owner completed the manual review, reported it passed, and manually committed the accepted Phase 01 baseline as `8ee61fb` with message `ph1 reviewed`. The owner then explicitly authorized Phase 02. Earlier pending language above is retained only where it describes the state at the time of an earlier run; this update is the current phase status.
