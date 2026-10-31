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
