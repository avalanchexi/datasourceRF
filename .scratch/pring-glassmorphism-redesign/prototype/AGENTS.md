# Prototype Instructions

Run the local server yourself and open the preview in the browser available to this environment. Do not give the user server-start instructions when you can run it.

Before making substantial visual changes, use the Product Design plugin's `get-context` skill when the visual source is unclear or no longer matches the current goal. When the user gives durable prototype-specific design feedback, preferences, or decisions, record them in `AGENTS.md`.

When implementing from a selected generated mock, treat that image as the source of truth for layout, component anatomy, density, spacing, color, typography, visible content, and hierarchy.

Build app UI in `src/`. Keep `.openai/hosting.json`, `worker/index.js`, `scripts/prepare-sites-build.mjs`, and `tests/sites-worker.test.mjs` intact so the same local prototype can be handed to Sites. Before a Sites handoff, run `npm run build` and `npm run test:sites`; the build must leave `dist/client/index.html`, `dist/server/index.js`, and `dist/.openai/hosting.json`.

## Selected design direction

- Treat `../../pring-cycle-v1-wayfinding/prototypes/pring-cycle-dashboard-prototype.html` as the source of truth for information architecture, page structure, navigation, card composition, evidence drawer, report workspace, responsive behavior, and the current dark presentation.
- Preserve its overview-first dashboard and eight-page navigation. Fine-tune the existing composition instead of rebuilding it as an asset-first workbench or a persistent-inspector layout.
- Keep `design-source/option-3.png` and this React prototype as exploration history, not implementation references.
- Limit fine-tuning to domain terminology, the global projection envelope, report and degradation states, state-color clarity, accessibility, spacing, density, and small visual polish unless the user explicitly approves a structural change.
- Use the existing light palette as the default theme and remember explicit theme changes; retain the dark theme as a supported secondary presentation.
- Keep readable UI text at 12 px or above: metadata at 12 px, compact labels at 13 px, secondary information at 14 px, and body or key explanations at 16 px. Headings may be larger.
- Use Chinese-market state colors: red for rising/bullish/supporting states and green for falling/bearish/contradicting states. Keep asset-category accents separate from state colors.
- Treat desktop as the design target. Preserve narrow-window anti-breakage behavior without adding mobile design or mobile acceptance work.
- Preserve the domain hierarchy in every refinement: 正式阶段 first, 转折观察 second, 宏观事后确认 third.
