# Desktop review workflow — product contract

## Screen layout
Target large PC monitor. Persistent filmstrip with lazy-loaded thumbnails and conspicuous review-status markers; clicking any thumb jumps directly to that photo. Full contact sheet/grid for random-access navigation over ~200 photos. Keyboard left/right navigation, quick approve/reject, jump to next unreviewed/rejected. Search and filters (status, subject, multiple tags, city/date, batch). Never demand 50 next-clicks to reach photo 50.

## Main review canvas
Original image above the currently selected edited version in the left comparison column; show clear EMPTY/NOT EDITED state otherwise, not fake comparison. The wider right work area contains the catalog and draft, suggestions, prompt, and editing/version controls as separate tabs. Offer selectable attempt/version timeline, zoom/pan synchronized optional, compare slider optional. Presets/colors must not be implicit truth claims.

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

The desktop default keeps the top filmstrip visible, stacks original and edited images in the left column, and gives most horizontal space to the work area on the right. Until editing exists, the lower image pane says **Not edited yet**. The catalog and draft fields share two columns; the other controls are reached through work area tabs. The page itself fits the viewport, while a work area section can scroll when the window is too short for its contents. Left/right arrows navigate photos outside editable controls and tabs; on a focused tab, they switch work area sections. `G` opens the contact sheet when focus is outside an editable control. A draggable overlay and mask editor remain deferred.

## Phase 03 analysis and prompt flow

Cost preview precedes analysis authorization. The authorization checkbox applies only to the current run and resets afterward. Sanitized suggestions populate editable fields without silently replacing non-empty owner values. The prompt preview shows deterministic assembly from the saved draft, reports conflicts before creating a version, and separates **Save as new version** from **Approve current prompt**. Editing the draft makes an older prompt stale; approval never starts an editing job.

The editing draft shows the selected publication profile and its exact format, maximum long edge, quality, color space, aspect rule, upscale rule, and metadata rule. The compiled prompt snapshots that version. Changing the profile invalidates prompt readiness. Phase 04 will create the derivative and use it as the only generative image input; Phase 03 creates no image artifact.

## Phase 04 run readiness

The Start authorized run button is visibly muted and disabled until the preview is ready, at least one selected photo is eligible, the paid-run budget meets the displayed estimate, and the owner checks current-run authorization. A nearby message states the next missing requirement. Submission locks immediately while the draft save and queue request finish; an unsuccessful attempt clears preview and authorization so the owner inspects the receipt and deliberately previews again before retrying.

## Phase 04 editing and version review

The editing panel offers generative image edits with a 0.10 USD planning budget. The owner previews per-photo eligibility, prompt text, and estimated cost, raises the budget when the estimate exceeds 0.10 USD, and explicitly authorizes each run. The budget is an application readiness gate, not an account spending limit. A batch can target the current photo or the first 20 visible photos. A new immutable version appears beside the original with its dimensions and PENDING status. The version list allows selection and downloading; the owner explicitly approves or rejects a pending version. A mask is an optional uploaded transparent PNG tied to one publication input. Masking cannot guarantee unchanged protected pixels. Approved versions are excluded from default new runs. Website export is Phase 06.

## Phase 05 local catalog prefill

Offer an explicit local-analysis action with progress, source/model provenance, suggested subject, tags, conditions, description, and preset. Let the owner accept, adjust, or dismiss each suggestion and review a bounded batch with preview and undo. Mark low-confidence or conflicting results for review; never replace confirmed metadata. The local model may download automatically on first use into an ignored verified cache, with an explanatory progress state; subsequent runs use the cache. The model does not send photo content to an external service.

City and country suggestions come from private EXIF GPS matched server-side to an owner-maintained list of visited cities. The Phase 05 panel shows match distance and ambiguity without exposing raw GPS to the browser. If GPS is absent or no city passes the configured radius, it offers a bounded bulk city/country assignment for visible photos with preview and undo. Recognition requires a current local-run checkbox, shows model-download progress, and lists suggestions with field selection, acceptance, dismissal, and undo. A prepared batch of at most 20 can be accepted after inspecting its summaries and undone. Accepted metadata changes make dependent compiled prompts stale, but no suggestion checks semantic consent, approves a prompt, starts an edit, or approves an image. Editorial location is confirmed by the owner's acceptance or manual entry; publication handling remains Phase 06.

Primary subject, content tags, and condition tags offer case-insensitive prefix matches from existing catalog labels of the same kind. The current comma-separated tag is completed with Tab or Enter; earlier tags are preserved and already entered tags are omitted from suggestions. City and country fields similarly suggest existing editorial values and visited-city names. The owner can type new values in all five fields. Suggestions refresh after a metadata save, and no suggestion is accepted until the owner enters or selects it. The Catalog suggestions panel starts collapsed and its heading expands or contracts the local recognition and visited-city controls.

The edit panel's 0.10 USD run budget works for a single eligible photo when `PHOTO_EDIT_PLANNING_COST_USD` is 0.10 in the server configuration. This is a per-image planning estimate: selecting more photos multiplies the displayed estimate. **Preview selected run** saves the current draft, checks each selected photo's approved current prompt, source hash, active/approved job status, retry eligibility, publication input and optional mask references, and reports provider availability, prompt text, and estimated total. It does not call the paid image provider or generate an edit. The owner must then check current-run authorization before starting the job.

## Phase 06 approved collection

The **Export** tab previews every approved website version and validates its file identity, source/profile/job provenance, owner approval event, dimensions and metadata policy. It does not create files. **Export approved collection** requires the owner to tick current-run authorization, then writes a new collection under `data/exports/` for the canonical `data/catalog`. Website images are exact byte copies of the approved JPEGs; small thumbnails, a privacy filtered manifest, and a cost report are separate. The manifest includes city/country only when both editorial fields were entered or accepted by the owner; it omits private GPS and original filenames. The displayed collection path and recent-collection paths open their recorded folders in the local file manager, including after a browser refresh. High-contrast links download the manifest and cost report, and the tab offers a read-only file audit. No cleanup action deletes media.

## V2 Priority 1 local editing workflow

The Editing and versions tab now opens on **Local deterministic correction**. Each photo receives an automatically chosen preset and preloaded conservative levels, exposure, white balance, shadow, and highlight values. **Live preview while adjusting** is enabled by default. Slider, crop, reset, and preset changes feed the latest settings to a throttled reduced-resolution local preview without creating a version. Each input change immediately invalidates older work, even during the throttle interval. The current frame remains visible at full opacity until the latest JPEG has decoded, then the browser swaps it in once; late responses cannot restore an older setting. The server reuses a verified, oriented 960 px working image for the current source identity. **Refresh preview** is a manual fallback, and live preview can be disabled. Straighten, lens correction, perspective, and crop remain zero/identity unless set manually; the UI explains why. **Create local version** saves any current draft, queues a separately hash-checked source-resolution render, and creates a pending website version with a separately downloadable full-resolution PNG master. It requires no prompt approval, budget, or paid-run checkbox. Visual approval is still required for export. Selecting **Generative image edit** exposes the existing prompt, budget, preview, and current-run authorization workflow. Selection-wide recipe application belongs to V2 Priority 2.

For editing, the workspace widens into three visible columns: the original/edited comparison, compact editing controls, and a dedicated local-correction or selected-run preview. Correction parameters and crop use sliders with small value readouts instead of numeric entry fields. The controls and version text use a denser type scale so the preview keeps useful width; the control and preview columns scroll independently when the window is short.

The entire working area uses a compact desktop type scale. Catalog and draft controls, local suggestions, prompt controls and compiled-prompt text, editing controls, and export receipts use smaller fonts and tighter spacing so large monitors show more of the active workflow without extra scrolling. The filmstrip and image-comparison labels retain their existing scale.

When a photo already has an approved version, **Create local version** changes to **Create replacement version** and remains disabled until **Create a replacement for the approved version** is checked. Generative preview/run offers the same explicit replacement mode. The job records the approval it targets. The current approval stays active while the new version is PENDING and also remains active if the candidate is rejected. A replacement candidate shows **Approve and replace current**; after that explicit action, the previous version remains downloadable and is labeled SUPERSEDED, while only the new APPROVED version is eligible for export.
