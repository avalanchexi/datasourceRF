No introduced correctness regressions identified in the supplied source.

- **Standards:** `aria-current="location"` is appropriate for the current report section; it does not need to match the URL hash.
- **Spec:** The prior hash-only highlighting finding is closed. Highlighting now updates from section positions on scroll, resize, and navigation. Your reported Ctrl+End verification confirms that it changes independently of the hash.
- **Containment:** The nested-grid sizing and wrapping changes address the identified overflow. Your supplied measurements show equal client and scroll widths at all three checked viewport widths.

This conclusion is limited to the supplied source and browser evidence. No tools, agents, edits, or tests were used.