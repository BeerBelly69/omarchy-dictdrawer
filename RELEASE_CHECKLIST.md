# DictDrawer release review

This repository is private for review. Do not change its visibility, create a public release, or submit a marketplace listing until the owner approves publication.

## Ready to review

- [x] DictDrawer name and “Your dictations, a keystroke away” tagline.
- [x] Bundled history helper, with no separate helper installation.
- [x] Configurable recent-excerpt count: 20 by default, 5–100 supported.
- [x] Full-history search with highlighted matches and context previews.
- [x] Fixed-height drawer while searching, including no-match states.
- [x] Clipboard, keyboard navigation, and error feedback.
- [x] README, dependency list, storage/privacy notes, MIT license, and changelog.
- [x] Automated history tests and a GitHub Actions workflow.
- [x] Sample-only screenshots; no personal transcripts or credentials packaged.

## Before public release

- [ ] Review the README, name, screenshots, and current behavior on GitHub.
- [x] Per-day storage with full-history search, safe flat-file migration, and concurrent-read/write tests.
- [x] Type-to-search, resolving letter-navigation shortcuts and preserving normal text editing.
- [x] Refresh screenshots for highlighted search and the fixed-height drawer.
- [x] Validate scaling, smaller displays, thick bars, and large fonts; see [validation notes](VALIDATION.md).
- [x] Verify a clean install, update, disable, and removal without disturbing Voxtype configuration or saved transcripts.
- [x] Verify CI passes on the release candidate; rerun after final release changes.
- [ ] Obtain owner approval to make the repository public.
- [ ] Set the final version, tag the approved commit, and publish release notes.
- [ ] Submit the public repository to the Omarchy marketplace for review.

## Scope and compatibility

There is no separate Archive/Trash interface or automatic deletion policy in this build. The rolling count controls display, not storage retention. Transcripts are saved in per-day folders; existing flat files are safely reorganized on opening or refreshing.

The plugin ID is `dictdrawer`, matching the DictDrawer name. Omarchy installs it in `~/.config/omarchy/plugins/dictdrawer/`; bar settings and shell commands use the same ID. The transcript storage location is independent of the plugin ID and is unchanged.
