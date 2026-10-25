# Desktop review workflow — product contract

## Screen layout
Target large PC monitor. Persistent filmstrip with lazy-loaded thumbnails and conspicuous review-status markers; clicking any thumb jumps directly to that photo. Full contact sheet/grid for random-access navigation over ~200 photos. Keyboard left/right navigation, quick approve/reject, jump to next unreviewed/rejected. Search and filters (status, subject, multiple tags, city/date, batch). Never demand 50 next-clicks to reach photo 50.

## Main review canvas
Original image left, currently selected edited version right when present; show clear EMPTY/NOT EDITED state otherwise, not fake comparison. Offer selectable attempt/version timeline, zoom/pan synchronized optional, compare slider optional. Presets/colors must not be implicit truth claims.

## Editing panel
- Original filename, dimensions, capture metadata, location, current overall progress.
- Optional primary subject (single), multiple content and condition tags; all AI suggestions editable.
- Three selectable configurable presets with transparent instructions, numeric AI allowance and semantic-operation warnings.
- Two independent fields: `AI suggested corrections` (pre-populated only after opt-in analysis; editable) and `My additional instructions` (blank initially).
- Compile/preview final prompt as separate editable version. Show stale prompt when upstream field changes and require recompilation/acknowledgment before run.
- Save/saving/error status, auto-save with conflict handling; changes survive navigation/reload.
- Run selected edit, approve or reject current version (only when version exists), rejection note optional, retry options and estimated cost.

## Review speed
Hotkeys and buttons for Previous/Next, Save & Next, Approve & Next, Reject & Next. Bulk apply tag/preset/prompt fragments with preview and undo; no bulk approval by default. Filmstrip should stay at current selection when paging, with scroll-to-current and numeric jump.

## State
Distinguish imported/unanalysed, draft ready, queued/running/failed, completed pending approval, rejected, approved; status indicators must be distinguishable without color alone. Persist selected version and filter state per session when feasible. Responsive fallback for phone is optional, not V1 acceptance criterion.

## Unresolved visual choices
Filmstrip top vs bottom; split vs draggable overlay comparison default; keyboard mapping and mask editor tooling. Resolve by usability testing in Phase 02, not by prematurely committing to an inflexible UI.
