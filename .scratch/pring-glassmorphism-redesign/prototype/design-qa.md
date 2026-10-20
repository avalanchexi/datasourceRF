# Design QA — 方案 3「证据工作台」

- Final result: `passed`
- Reference: `design-source/option-3.png`
- Implementation capture: `qa/implementation-option-3-final.png`
- Normalized comparison capture: `qa/implementation-option-3-normalized.png`
- Focused comparison: `qa/focus-option-3-source.png` and `qa/focus-option-3-implementation.png`
- Browser state: 1440 × 1024 requested viewport, equity selected, China 120-day track, evidence inspector open

## Normalization

The reference is 1487 × 1058 px. The in-app browser captured a 1424 × 1064 px canvas while rasterizing the 1440 CSS-pixel viewport at 0.8 scale and padding the remainder. For visual comparison only, the 1140 × 851 rendered content box was cropped and resized to 1425 × 1064 px. No application code or runtime zoom was changed by this QA normalization.

## Full-view comparison

The final normalized implementation preserves the reference hierarchy and proportions: system strip, left navigation and Stage IV capsule, three-asset selector, central evidence workbench, six-stage mapping, primary chart, comparison cards, and fixed evidence inspector. Glass depth, blue-violet atmosphere, thin borders, cyan/red state semantics, and panel density are consistent with the selected visual direction.

## Focused comparison

The central workbench crop confirms the asset tabs, metric row, stage map, chart controls, chart annotations, and comparison cards remain readable and aligned at the target state. The implementation uses a smoother deterministic mock series than the generated reference, but preserves the same information hierarchy and interaction intent.

## Comparison history

1. Pass 1 — P2: headings used a serif face and the comparison cards lacked the reference sparklines. Fixed by moving headings to the sans stack, increasing chart height, and adding Recharts mini-series to the two comparison cards.
2. Final pass — no P0, P1, or P2 visual defects found. Minor line-shape differences are intentional mock-data variation and do not change the selected design direction.

## Interaction and runtime checks

- Asset switching updates the core metrics, chart, and inspector.
- The public Pring 12-month proxy exposes an independent reference track while formal Stage IV remains unchanged.
- Evidence inspector closes and reopens.
- Macro and inventory drawers expand independently.
- Report generation enters a queued state.
- Browser console: no warnings or errors.
- Vitest: 5/5 passed.
- Production build: passed.
- Sites packaging tests: 4/4 passed.
