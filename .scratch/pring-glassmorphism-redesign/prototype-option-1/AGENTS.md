# Prototype Instructions

Run the local server yourself and open the preview in the browser available to this environment. Do not give the user server-start instructions when you can run it.

Before making substantial visual changes, use the Product Design plugin's `get-context` skill when the visual source is unclear or no longer matches the current goal. When the user gives durable prototype-specific design feedback, preferences, or decisions, record them in `AGENTS.md`.

When implementing from a selected generated mock, treat that image as the source of truth for layout, component anatomy, density, spacing, color, typography, visible content, and hierarchy.

Build app UI in `src/`. Keep `.openai/hosting.json`, `worker/index.js`, `scripts/prepare-sites-build.mjs`, and `tests/sites-worker.test.mjs` intact so the same local prototype can be handed to Sites. Before a Sites handoff, run `npm run build` and `npm run test:sites`; the build must leave `dist/client/index.html`, `dist/server/index.js`, and `dist/.openai/hosting.json`.

## Selected direction

- Build option 1, the glassmorphism "阶段指挥中心", in this directory.
- Treat `design-source/option-1.png` as the only visual source of truth. Do not introduce outside design references.
- Preserve the formal Pring hierarchy: Stage IV is determined only by the three certified core asset states (债− / 股+ / 商+). Macro and inventory evidence may confirm the narrative but must not mutate the formal stage.
- Keep the three asset cards, six-stage mechanical map, transition-watch rail, global alert summary, and report action visible in the primary desktop state.
