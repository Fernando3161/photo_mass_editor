# Phase 07 technical report — public release cleanup

- Branch: dev/v1-phase-07-release-cleanup
- Baseline: 1739ac6, the committed Phase 06 branch head on 2026-11-01
- Working tree: all changes unstaged and uncommitted for owner review; no merge or release performed
- Owner acceptance: pending final diff, example-image/publication-rights review, and completion of the Phase 06 real-export visual gate

## Scope and changes

The README now covers one-command Windows setup and LAN launch, where originals go, Linux setup, every workstation tab and field, authorization, review, export, backup, troubleshooting, privacy, and contact. scripts/start.ps1 creates required ignored directories, updates the one canonical .venv from the locked Python requirements, installs locked frontend packages, imports direct files from data/input, builds the UI, generates a one-run LAN password, prints local/LAN URLs, and runs the server. A manual non-loopback backend launch without a password is rejected. The API now checks Basic authentication, Host, cross-site requests, and cross-origin writes, sets security/cache headers, and bounds mask upload streaming. A synthetic test covers denied and allowed access.

Two downscaled, EXIF-free example JPEGs were made from the owner-approved Budapest Opera photo 15 and are explicitly labeled as a generative alteration. GPLv2 was replaced in the release tree with PolyForm Noncommercial 1.0.0; NOTICE.md separates the photographs' CC BY-NC 4.0 terms. SECURITY.md provides disclosure contact and operating boundaries. CI now targets main and this release branch. Public UI labels no longer refer to development phases. The tracked obsolete design.docx was removed after its Word window closed. The ignored operational data, old review folders, and source photos were not deleted.

The [release audit](RELEASE_AUDIT.md) records the detailed inventory, secret/path scan, dependency checks, network findings, and residual risks. The generic ignore file was shortened to project-specific rules.

## Acceptance checks

| Check | Status | Evidence |
| --- | --- | --- |
| One-command Windows setup and LAN server | PASS in current workspace | scripts/start.ps1 started on port 8765, imported 20 existing photos without new records/errors, rebuilt the UI, and served HTTP. Unauthenticated /api/health returned 401. Server stopped with Ctrl+C. Fresh empty-clone startup was not separately executed. |
| Protected LAN API | PASS in synthetic tests | Missing credentials 401; unknown Host 400; cross-site read and cross-origin write 403; valid password and same-origin write 200. |
| Full backend and frontend checks | PASS locally | 63 backend tests, 15 frontend tests, production build. |
| README example privacy | PASS by artifact inspection | Both files 960 × 720; EXIF/GPS absent; inputs matched stored SHA-256 and edit had APPROVED status. Both previews were visually inspected for the intended before/after pairing; owner must still approve public image rights and presentation. |
| Tracked file and historical secret/path audit | PASS within scan scope | 313 reachable blobs and 105 current files under 2.5 MB scanned; no matched key or user-home path patterns; ignored private paths checked. |
| Dependency advisories | PASS as of audit date | npm audit reported 0; OSV querybatch reported 0 affected among 32 locked Python packages. |
| Obsolete design.docx removal | PASS in unstaged tree | Windows initially refused deletion while read-only Word had it open; removal succeeded after that window closed. The owner must stage the deletion. |
| Real collection visual/privacy acceptance | NOT_RUN | Remains an owner gate from Phase 06. |
| Windows/Linux remote CI and clean-machine setup | NOT_RUN | Workflow configured; no remote execution in this phase. |

## Commands run and results

- .venv\Scripts\python.exe -c "import pathlib,sys; assert pathlib.Path(sys.prefix).resolve()==pathlib.Path('.venv').resolve()" — PASS; canonical interpreter verified before project code.
- .venv\Scripts\python.exe -m unittest discover -s tests -p test_review_api.py -v — PASS, 7 focused tests.
- .venv\Scripts\python.exe -m unittest discover -s tests -q — PASS, 63 tests after final security-header and mask-size refinements.
- npm --prefix frontend test -- --reporter=dot — PASS, 15 tests.
- npm --prefix frontend run build — PASS.
- PowerShell Parser.ParseFile on scripts/start.ps1 — PASS, no syntax errors.
- powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1 -Port 8765 -NoBrowser — setup/build/server PASS; Ctrl+C ended the foreground shell with exit code 1 after a clean Uvicorn shutdown.
- GET http://127.0.0.1:8765/api/health without credentials — 401, as intended.
- npm --prefix frontend audit --json — 0 reported vulnerabilities.
- OSV /v1/querybatch for all 32 pinned Python packages — 0 affected packages.
- Reachable Git blob scan via .venv Python and git rev-list/cat-file — 313 blobs, 0 key/path pattern findings.
- Working-tree scan via .venv Python and git ls-files --cached --others --exclude-standard — 105 files, 0 key/path pattern findings.
- git check-ignore -v on data/input, config/openAI.env, .venv, and frontend/dist — PASS for all four paths.
- git diff --check — PASS; only Windows LF-to-CRLF notices.
- Local Markdown link and preview-image metadata check through .venv Python — PASS for eight current documents and both 960 × 720 JPEGs.
- Canonical catalog preflight plus artifact audit through .venv Python — 20/20 source hashes and thumbnails OK; 59 referenced files, zero missing, changed, source issues, orphans, or invalid reports. The first summary command failed because it treated the preflight list as a dictionary; the corrected command used Counter on its rows and passed. Preflight updates only the catalog's source_missing status, not source photos.
- Remove-Item -LiteralPath design.docx — FAILED twice while Windows reported it open in Word; a guarded graceful-close attempt did nothing because the window had already closed, then the same removal succeeded. The final unstaged tree records the deletion.
- .venv\Scripts\python.exe -m backend.review --host 0.0.0.0 --port 8766 — expected refusal (exit 1): network binding requires PHOTO_EDITOR_ACCESS_PASSWORD. No server started.

No paid provider call, model prefetch, large-batch edit, cloud upload, data-folder deletion, commit, merge, or main-branch change was performed.

## Handoff and risks

The launcher exposes HTTP Basic authentication on the private LAN; credentials and photos are observable to someone who can monitor that network. The manual loopback server remains unauthenticated. A real original served to an authenticated browser can contain EXIF. Owner review of source image content, license rights, real exports, and final staged files remains mandatory. Do not merge until the owner accepts the Phase 06/07 visual and publication checks. Only the owner stages and commits.
