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
- [ ] Finish the proposed date-folder storage: keep all saved transcripts in local-date folders, while limiting only the default drawer view. Preserve existing text and search across days; test migration and concurrent writes before reorganizing live files.
- [ ] Confirm and implement type-to-search if desired, resolving letter-navigation shortcuts and normal text-editing behavior.
- [ ] Refresh screenshots for highlighted search and the fixed-height drawer.
- [ ] Verify a clean install, update, disable, and removal without disturbing Voxtype configuration or saved transcripts.
- [ ] Verify CI passes on the final release commit.
- [ ] Obtain owner approval to make the repository public.
- [ ] Set the final version, tag the approved commit, and publish release notes.
- [ ] Submit the public repository to the Omarchy marketplace for review.

## Scope and compatibility

There is no separate Archive/Trash interface or automatic deletion policy in this build. The rolling count controls display, not storage retention. Files currently remain in the existing flat history directory; day-based folders are not implemented yet.

The plugin ID remains `mbelli.dictation` to preserve existing bar settings and keybindings. DictDrawer is the display name; users do not need to rename their installed plugin directory.
