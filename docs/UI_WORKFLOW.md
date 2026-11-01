# Desktop review workflow — product contract

## Screen layout
Target large PC monitor. Persistent filmstrip with lazy-loaded thumbnails and conspicuous review-status markers; clicking any thumb jumps directly to that photo. Full contact sheet/grid for random-access navigation over ~200 photos. Keyboard left/right navigation, quick approve/reject, jump to next unreviewed/rejected. Search and filters (status, subject, multiple tags, city/date, batch). Never demand 50 next-clicks to reach photo 50.

## Main review canvas
Original image left, currently selected edited version right when present; show clear EMPTY/NOT EDITED state otherwise, not fake comparison. Offer selectable attempt/version timeline, zoom/pan synchronized optional, compare slider optional. Presets/colors must not be implicit truth claims.

## Editing panel
- Original filename, dimensions, capture metadata, location, current overall progress.
- Optional primary subject (single), multiple content and condition tags; all AI suggestions editable.
- Eight selectable configurable presets with transparent instructions, numeric AI allowance and semantic-operation warnings. The additional choices cover museum artwork, group photos, night architecture, food, and panoramic scenes.
- Two independent fields: `AI suggested corrections` (pre-populated only after opt-in analysis; editable) and `My additional instructions` (blank initially).
- Compile/preview final prompt as separate editable version. Show stale prompt when upstream field changes and require recompilation/acknowledgment before run.
- Save/saving/error status, auto-save with conflict handling; changes survive navigation/reload.
- Run selected edit, approve or reject current version (only when version exists), rejection note optional, retry options and estimated cost.

## Review speed
Hotkeys and buttons for Previous/Next, Save & Next, Approve & Next, Reject & Next. Bulk apply tag/preset/prompt fragments with preview and undo; no bulk approval by default. Filmstrip should stay at current selection when paging, with scroll-to-current and numeric jump.

## State
Distinguish imported/unanalysed, draft ready, queued/running/failed, completed pending approval, rejected, approved; status indicators must be distinguishable without color alone. Persist selected version and filter state per session when feasible. Responsive fallback for phone is optional, not V1 acceptance criterion.

## Phase 02 visual choices

The implemented desktop default uses a persistent top filmstrip and a fixed side-by-side comparison. This keeps random navigation visible above the image area and leaves room for a clear original/edited distinction. Until editing exists, the right pane says **Not edited yet**. Left/right arrows navigate and `G` opens the contact sheet when focus is outside an editable control. Owner usability review can still revise these choices before Phase 02 approval. A draggable overlay and mask editor remain deferred to the editing phase.

## Phase 03 analysis and prompt flow

Cost preview precedes analysis authorization. The authorization checkbox applies only to the current run and resets afterward. Sanitized suggestions populate editable fields without silently replacing non-empty owner values. The prompt preview shows deterministic assembly from the saved draft, reports conflicts before creating a version, and separates **Save as new version** from **Approve current prompt**. Editing the draft makes an older prompt stale; approval never starts an editing job.

The editing draft shows the selected publication profile and its exact format, maximum long edge, quality, color space, aspect rule, upscale rule, and metadata rule. The compiled prompt snapshots that version. Changing the profile invalidates prompt readiness. Phase 04 will create the derivative and use it as the only generative image input; Phase 03 creates no image artifact.

## Phase 04 run readiness

The Start authorized run button is visibly muted and disabled until the preview is ready, at least one selected photo is eligible, the paid-run budget meets the displayed estimate, and the owner checks current-run authorization. A nearby message states the next missing requirement. Submission locks immediately while the draft save and queue request finish; an unsuccessful attempt clears preview and authorization so the owner inspects the receipt and deliberately previews again before retrying.

## Phase 04 editing and version review

The editing panel defaults to a generative image edit with a 0.10 USD planning budget. The owner may choose a local deterministic correction instead. The owner previews per-photo eligibility, prompt text, and estimated cost, raises the budget when the estimate exceeds 0.10 USD, and explicitly authorizes each run. The budget is an application readiness gate, not an account spending limit. A batch can target the current photo or the first 20 visible photos. A new immutable version appears beside the original with its dimensions and PENDING status. The version list allows selection and downloading; the owner explicitly approves or rejects a pending version. A mask is an optional uploaded transparent PNG tied to one publication input. Masking cannot guarantee unchanged protected pixels. Approved versions are excluded from default new runs. Website export is Phase 06.

## Phase 05 local catalog prefill

Offer an explicit local-analysis action with progress, source/model provenance, suggested subject, tags, conditions, description, and preset. Let the owner accept, adjust, or dismiss each suggestion and review a bounded batch with preview and undo. Mark low-confidence or conflicting results for review; never replace confirmed metadata. The local model may download automatically on first use into an ignored verified cache, with an explanatory progress state; subsequent runs use the cache. The model does not send photo content to an external service.

City and country suggestions come from private EXIF GPS matched server-side to an owner-maintained list of visited cities. The Phase 05 panel shows match distance and ambiguity without exposing raw GPS to the browser. If GPS is absent or no city passes the configured radius, it offers a bounded bulk city/country assignment for visible photos with preview and undo. Recognition requires a current local-run checkbox, shows model-download progress, and lists suggestions with field selection, acceptance, dismissal, and undo. A prepared batch of at most 20 can be accepted after inspecting its summaries and undone. Accepted metadata changes make dependent compiled prompts stale, but no suggestion checks semantic consent, approves a prompt, starts an edit, or approves an image. Editorial location is confirmed by the owner's acceptance or manual entry; publication handling remains Phase 06.

Content and condition tag fields offer case-insensitive prefix matches from existing catalog tags of the same kind. The current comma-separated tag is completed with Tab or Enter; earlier tags are preserved and already entered tags are omitted from suggestions. City and country fields similarly suggest existing editorial values and visited-city names. The owner can type new values in all four fields. Suggestions refresh after a metadata save, and no suggestion is accepted until the owner enters or selects it.
