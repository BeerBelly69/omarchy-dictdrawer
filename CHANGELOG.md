# Changelog

## 1.0.0 — 2026-09-08

- Read-only Handy support with automatic/custom database discovery, background imports, post-processing updates, and preservation of edited or retained excerpts.
- DictDrawer branding with the matching `dictdrawer` plugin ID and install directory.
- Sliding drawer that emerges from behind any bar edge.
- Persistent local Voxtype transcript recovery and legacy archive support.
- Full-archive search with highlighted matches and context previews, keyboard navigation, and expandable excerpts.
- Verified clipboard copy, refresh, folder access, and actionable error states.
- Compact keycap legend, theme-aware colors, and sample-only release previews.
- Steady full-height search results, including loading and no-match states.
- Type-to-search with normal text editing; Enter copies and Escape clears before closing.
- Per-day local transcript folders, with interruption-safe migration and conflict preservation.
- Automated keyboard tests and an opt-in virtual-display layout/screenshot check.

### Validation and limitations

- 54 Python tests, 15 Qt keyboard test results, and 56 virtual-display layout cases pass.
- Real Voxtype use and a Handy 0.9.6 microphone recording were verified. Handy imported automatically with exact text and no duplicate.
- Handy AI post-processing updates pass fixture and isolated UI tests; a real AI provider has not been tested.
- Existing users may need `omarchy restart shell` after updating if Omarchy retains cached plugin code.
- The default 20-excerpt limit controls the view, not retention. Saved text is kept until you remove it; Handy's own deletions do not remove DictDrawer copies.
