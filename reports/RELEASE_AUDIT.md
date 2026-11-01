# Public-release repository and security audit

Date: 2026-11-01. Branch: dev/v1-phase-07-release-cleanup. Baseline: 1739ac6. This is a source and local-launch audit, not a penetration test of every host or network.

## Inventory and cleanup

The tracked baseline contained application source, migrations, pinned Python/npm dependencies, tests, governing documentation, historical phase reports, one obsolete design.docx, and no operational data/ files. The 1.5 MB design.docx was a temporary UI sketch already incorporated in the frontend; it has been removed from the unstaged working tree. Historical reports and migration/recovery scripts are retained because they document provenance and support existing catalogs. The generic 5 KB ignore template was replaced with project-specific private-data and build rules. The stale README was rewritten, and public-facing “Phase” labels were removed from the UI.

The two intentionally public README previews are 960 × 720 JPEGs (about 172 KB and 205 KB). They were generated from the checked source hash and the owner's approved photo-15 version, with fresh RGB encoding and no EXIF/GPS. The full-size source and edit remain ignored under data/. The README explicitly labels the generative scene alteration.

Deleting design.docx from the next commit reduces the release checkout, but its blob remains in existing Git history and can still contribute to a full clone. History was not rewritten because this branch is for owner review and the file contained no detected credential or private path. A future history rewrite would require separate owner coordination with every clone.

## Sensitive material review

- A read-only scan of 313 reachable Git blobs and 105 current working-tree files under 2.5 MB checked for OpenAI, GitHub, AWS, and PEM private-key patterns and Windows/macOS/Linux user-home path patterns. It reported zero matches. The scan does not cover unreachable objects, arbitrary encodings, or secrets that do not match those patterns.
- Current tracked paths contain no data/ operational files, real config/openAI.env, .venv/, or frontend build output. git check-ignore confirmed those paths are excluded. The sample provider config has only a placeholder key.
- Git commit metadata already contains a contributor's work email address. Git history is not rewritten by this phase. The public contact in the README is a personal address found in another repository by the same author.
- The original-image browser endpoint serves original bytes, including embedded EXIF, to an authenticated browser. Photo-detail JSON omits precise GPS and internal paths. The local Export panel intentionally shows the absolute collection directory to the authenticated user; that path is not in the public manifest. Website exports copy metadata-free approved JPEGs and omit private paths and coordinates from manifests. A user must still review image content and editorial place names before publication.
- Real provider credentials remain server-side in ignored config/openAI.env or the process environment. Paid execution still requires current-run authorization and a planning estimate. That estimate is not a provider billing cap.

## Network and application findings

| Finding | Severity | Resolution or remaining limit |
| --- | --- | --- |
| Previous server had no authentication when bound to a LAN address | High | Manual non-loopback binding now refuses to start without PHOTO_EDITOR_ACCESS_PASSWORD. The Windows launcher creates a random per-run password. Middleware protects all routes, validates Host, blocks cross-site browser requests, and requires a matching Origin for writes. It adds no-store/no-sniff/frame/resource-policy headers. |
| LAN HTTP is unencrypted | Medium | Documented as trusted-private-LAN only. Basic credentials and photos can be intercepted by someone able to observe that network. Do not use public Wi-Fi, internet forwarding, or a public tunnel. HTTPS/remote deployment is outside this local tool's scope. |
| Original media can contain private EXIF | Medium | Access requires the run password on LAN. Public exports strip metadata. Owners should not treat the review URL as a publication URL. |
| Large mask upload could consume memory before the existing 4 MB check | Medium | The request is now streamed and rejected at 4 MB before image decoding. |
| Loopback-only manual launch has no authentication | Low | Intended single-user local mode. Other local processes and users with access to the host may still reach it. |
| Local model/package downloads require supplier trust | Medium | Locked package versions and a hashed model manifest support reproducibility and model integrity. The first setup/model download still relies on package registries and TLS. No offline supply-chain proof is claimed. |

No SQL string interpolation, arbitrary browser-supplied export path, or client-side API credential was found in the reviewed API boundaries. Database inputs use parameters; recorded export paths are constrained beneath the export directory. This review does not establish that every parser, dependency, or operating system is free of vulnerabilities.

## Dependency and license review

npm audit --json reported 0 vulnerabilities across the frontend dependency tree. OSV querybatch reported 0 affected packages among the 32 pinned Python dependencies. These are database results as of the audit date, not guarantees about future disclosures. No ad-hoc dependency installation was made.

The former LICENSE was GPLv2, inconsistent with the owner's requested noncommercial redistribution rule. The release tree now contains the unmodified [PolyForm Noncommercial 1.0.0 text](https://polyformproject.org/licenses/noncommercial/1.0.0), which permits noncommercial use, modification, and distribution. [NOTICE.md](../NOTICE.md) carries the required copyright notice and separately identifies CC BY-NC 4.0 terms for the two example photos. Earlier GPLv2 grants remain in prior history. The owner should verify copyright ownership and the intended commercial boundary before merging; this audit is not legal advice.

## Release gates

Backend/frontend suites, build, launcher smoke test, code diff, documentation links, license text, example images, and owner visual/publication review must be recorded in [the Phase 07 report](PHASE_07_TECHNICAL_REPORT.md). No merge, public release, real paid call, bulk generation, or deletion of private data is part of this audit.
