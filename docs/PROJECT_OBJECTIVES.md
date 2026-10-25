# Project objectives

## Mission and user
A single-user, PC-oriented, local-first tool for cataloging, evaluating and selectively editing an initial ~200 manually curated photos, followed by human approval and website-ready exports. Photographic authenticity and controlled human decisions take precedence over automated visual impressiveness.

## Outcomes
1. Import selected originals, retain immutable files and captured EXIF/GPS, generate thumbnails, fingerprint duplicates.
2. Search/review via large-monitor dual image viewer, persistent horizontal filmstrip, contact sheet, keyboard navigation and filters.
3. Allow optional primary subject plus multiple tags and observed photographic conditions; user can override AI prepopulation.
4. Maintain editable AI recommendation and distinct optional user instructions, then produce a versioned editable final prompt after reviewing the metadata/preset/policy.
5. Run deterministic edits when possible and optional masked generative edits only when authorized; capture costs, models, masks, prompts and parameters.
6. Keep every attempt, compare original with selected edited version, approve/reject explicitly; rerun only non-approved photos by default.
7. Export only approved versions by default with captions, geographic data (privacy filtered) and web-friendly derivatives; support data interchange to a separate travel website.

## Quality priorities
Original preservation > traceable provenance and authenticity > user review speed > correctness/reproducibility > cost control > aesthetics > throughput.

## Scope / non-goals for V1
In scope: local single-user installation, SQLite catalog, folder import, EXIF data, editable analysis suggestions, three configurable presets, preview/generation and approvals, batch retries, reporting, exports.
Not in scope initially: public-facing SaaS, multi-user accounts, cloud synchronization, Adobe-hosted integration, raw nondestructive development parity with Lightroom, autonomous AI decisions, payment/customer commerce, or a complete travel website. References to Adobe assets or future commercialization remain requirements to clarify, not committed V1 architecture.

## Decisions pending evidence
Exact three preset wordings, masking editor ergonomics, image model choice and prices, image-format coverage (RAW/HEIC), location privacy defaults, desired export targets, whether importing copies or referencing originals is preferable. Resolve during relevant milestone with decision record; do not invent requirements.

## Success
A user can import a dataset, quickly annotate every photo without repetitive navigation, execute approved transformations, reject and retry individually, see full attempt history and publish only approved images without losing originals or metadata.
