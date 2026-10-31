# Image editing and authenticity policy — initial contract

## Purpose
Preserve documentary fidelity for travel photographs by default. Enhancement must not be confused with historical or physical evidence.

## Operation classes
A. Deterministic: white balance, exposure, lens/perspective correction, crop, rotation, tonal changes and controlled sharpening/denoise. These are default.
B. Local generative: reconstruction/removal/replacement of bounded regions explicitly authorized by the user; requires mask when feasible, with awareness masking is not a pixel-integrity guarantee.
C. Broad semantic modification: invented weather, architecture, objects, facial details or reconstructed scenes; not default and requires explicit per-photo authorization. Must be labeled as generative for publication if representation becomes misleading.

## Allowance 0–10
This is application-level permissiveness only, NOT an OpenAI API fidelity knob or measured error bound.
- 0: deterministic transformations only.
- 1–3: very conservative edits; no semantically new content without explicit instruction.
- 4–6: selectively authorized local generative changes, targeted mask/region, mandatory comparison.
- 7–10: wider creative operations permitted only if user specifically opted in; never inferred from slider alone.
No allowance value overrides explicit preservation constraints, original immutability or review requirements.

## Prompt pipeline
(1) AI sees permitted input image/preview and proposes classification, conditions and editable suggestions with uncertainty. (2) User chooses primary subject, multiple content/condition tags, preset, publication profile and allowance, edits AI suggestion text, and adds independent free-text instructions. (3) Compiler snapshots the complete publication profile and creates a single unambiguous, concise proposed instruction incorporating these fields and safety policy. (4) User may inspect/edit compiled prompt; changes invalidate readiness until saved. (5) The system deterministically creates and validates the publication input. (6) Paid generative editing receives that derivative only and executes only with explicit run authorization. Save source/compiled texts, compiler identity/settings and execution receipts.
If fields conflict (e.g., preserve sky vs replace sky), surface conflict before generating instead of silently choosing. Natural language constraints are not absolute guarantees against generative drift.

## Publication input contract
The original photograph is never the image input to a generative editing call. The initial `website-standard-v1` profile creates a JPEG in sRGB with a maximum 1600-pixel long edge, quality 85, preserved aspect ratio, no enlargement, and private metadata removed. The derivative records its own hash, the original source hash, and the immutable profile version. A changed profile requires a new derivative and a newly compiled prompt. Provider output may be retained in its returned format as a raw attempt, then deterministically normalized and validated as a separate publication version.

## Review contract
Each attempt creates immutable version, begins PENDING. Show original + chosen version side by side, before/after slider optional; APPROVE or REJECT with optional reason. Keep rejected versions. New attempts do not displace approved result without explicit promotion; export defaults to approved versions only.

## Batch safeguards
Default selection: without approved version, not already active, valid source. Preview counts, estimated costs, and per-image prompts before owner authorizes batch. Rejected unchanged settings not silently retried. Budget cap, cancellation, bounded concurrency, logging, resumability, error isolation and failure receipts.

## Privacy
Client-side UI never stores API key; server sends only authorized data. Exif/GPS and person data must not be included in generative requests unless needed and authorized. Sanitized public exports omit private GPS by default.
