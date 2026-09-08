# DictDrawer release checklist

The owner approved public release on 2026-09-08 after private review and live Handy testing. Marketplace submission is a separate step and requires approval of the completed submission and ownership checklist. Published versions are tracked in [GitHub Releases](https://github.com/BeerBelly69/omarchy-dictdrawer/releases).

## Ready to review

- [x] DictDrawer name and “Your dictations, a keystroke away” tagline.
- [x] Bundled history helper, with no separate helper installation.
- [x] Configurable recent-excerpt count: 20 by default, 5–100 supported.
- [x] Full-history search with highlighted matches and context previews.
- [x] Fixed-height drawer while searching, including no-match states.
- [x] Clipboard, keyboard navigation, and error feedback.
- [x] README, dependency list, storage/privacy notes, MIT license, and changelog.
- [x] Automated history tests and a GitHub Actions workflow.
- [x] Read-only Handy adapter, automatic/custom database path, retention/privacy documentation, and SQLite fixture tests.
- [x] Sample-only screenshots; no personal transcripts or credentials packaged.

## Release readiness

- [x] Review the README, name, screenshots, and current behavior on GitHub.
- [x] Verify a real Handy microphone recording imports automatically with exact text and no duplicate (Handy 0.9.6; shell restart needed to load the updated plugin).
- [x] Per-day storage with full-history search, safe flat-file migration, and concurrent-read/write tests.
- [x] Type-to-search, resolving letter-navigation shortcuts and preserving normal text editing.
- [x] Refresh screenshots for highlighted search and the fixed-height drawer.
- [x] Validate scaling, smaller displays, thick bars, and large fonts; see [validation notes](VALIDATION.md).
- [x] Verify a clean install, update, disable, and removal without disturbing Voxtype configuration or saved transcripts.
- [x] Verify CI passes on the release candidate; rerun after final release changes.
- [x] Obtain owner approval to make the repository public.
- [x] Set version 1.0.0 and prepare release notes in the changelog.
- [ ] Submit the public repository to the Omarchy marketplace for review.

## Follow-up validation

- [ ] Verify live Handy AI post-processing before advertising it as end-to-end tested (fixture and isolated UI tests pass; no live provider configured). This limitation is documented in 1.0.0 and was accepted for release.

## Scope and compatibility

There is no separate Archive/Trash interface or automatic deletion policy in this build. The rolling count controls display, not storage retention. Transcripts are saved in per-day folders; existing flat files are safely reorganized on opening or refreshing.

The plugin ID is `dictdrawer`, matching the DictDrawer name. Omarchy installs it in `~/.config/omarchy/plugins/dictdrawer/`; bar settings and shell commands use the same ID. The transcript storage location is independent of the plugin ID and is unchanged.
