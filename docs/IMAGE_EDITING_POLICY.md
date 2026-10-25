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
(1) AI sees permitted input image/preview and proposes classification, conditions and editable suggestions with uncertainty. (2) User chooses primary subject, multiple content/condition tags, preset and allowance, edits AI suggestion text, adds independent free-text instructions. (3) Compiler creates a single unambiguous, concise proposed instruction incorporating these fields and safety policy. (4) User may inspect/edit compiled prompt; changes invalidate readiness until saved. (5) Paid edit executes only with explicit run authorization. Save source/compiled texts, compiler identity/settings and execution receipts.
If fields conflict (e.g., preserve sky vs replace sky), surface conflict before generating instead of silently choosing. Natural language constraints are not absolute guarantees against generative drift.

## Review contract
Each attempt creates immutable version, begins PENDING. Show original + chosen version side by side, before/after slider optional; APPROVE or REJECT with optional reason. Keep rejected versions. New attempts do not displace approved result without explicit promotion; export defaults to approved versions only.

## Batch safeguards
Default selection: without approved version, not already active, valid source. Preview counts, estimated costs, and per-image prompts before owner authorizes batch. Rejected unchanged settings not silently retried. Budget cap, cancellation, bounded concurrency, logging, resumability, error isolation and failure receipts.

## Privacy
Client-side UI never stores API key; server sends only authorized data. Exif/GPS and person data must not be included in generative requests unless needed and authorized. Sanitized public exports omit private GPS by default.
