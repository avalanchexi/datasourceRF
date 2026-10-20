# Design QA — 方案 1「阶段指挥中心」

- Final result: `passed`
- Reference: `design-source/option-1.png`
- Implementation capture: `qa/implementation-option-1-final.png`
- Normalized comparison capture: `qa/implementation-option-1-normalized.png`
- Focused comparison: `qa/focus-option-1-source.png` and `qa/focus-option-1-implementation.png`
- Browser state: default 120-day track, all watch items and evidence drawers collapsed, no dialog, report idle

## Viewport and normalization

The reference is 1487 × 1058 px. The in-app browser viewport override was calibrated until the page reported `innerWidth=1487` and `innerHeight=1058`. The host screenshot raster was 1882 × 1339 px and included a scaled 1507 × 1072 rendered content box. For comparison only, that content box was cropped and resized to the reference's exact 1487 × 1058 px. Application code and runtime zoom were not modified by the normalization.

## Full-view comparison

The final implementation matches the reference hierarchy and placement: full-width system strip, 164 px navigation rail, Stage IV command card, seven-cell mechanical mapping, three equal asset cards, two stacked evidence drawers, transition-watch rail, global alert summary, and report action. Panel proportions, glass layers, border brightness, glow emphasis, blue-violet atmosphere, and red/green state semantics remain aligned with the selected direction.

## Focused comparison

The focused crop covers the complete command card, three asset cards, and both evidence drawers. It confirms matching section heights, card gaps, stage emphasis, chart placement, data hierarchy, and evidence-action alignment. The implementation uses deterministic Recharts mock series rather than copying the generated raster's exact line coordinates; this preserves the interaction and information intent without embedding the source image as UI.

## Comparison history

1. Pass 1 — P2: the equity and commodity Y-axis labels were clipped by a negative chart margin. Fixed by restoring chart left margin.
2. Pass 1 — P1: macro and inventory evidence drawers were incorrectly arranged side by side; the reference stacks them as two full-width rows. Fixed and recaptured.
3. Final pass — report action was 16 px too low. Corrected the right-rail bottom padding and recaptured.
4. Final comparison — no remaining P0, P1, or P2 visual defects.

## Interaction and runtime checks

- Asset evidence opens the matching accessible dialog and closes cleanly.
- The public Pring 12-month proxy displays reference Stage III while formal Stage IV remains unchanged.
- Each transition-watch item expands independently.
- Macro and inventory evidence drawers expand independently.
- Report generation enters a queued state.
- Browser console: no warnings or errors.
- Vitest: 5/5 passed.
- Production build: passed.
- Sites packaging tests: 4/4 passed.
