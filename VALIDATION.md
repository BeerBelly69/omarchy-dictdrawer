# Release-candidate validation

Checked on 2026-09-08 with Omarchy 4.0.2, Hyprland 0.56.2, Quickshell 0.3.1, and Qt 6.11.2.

## Automated checks

- 54 Python tests: journal recovery, saved-history persistence, literal Unicode highlights, package identity, per-day storage, migration safety, and Handy importing.
- 15 Qt Quick Test results (including setup/cleanup): printable keys, former letter-navigation shortcuts, uppercase, modifiers, arrow navigation, search/copy/Escape, and normal text editing.
- Omarchy plugin validation and QML parse checks.

The storage tests cover concurrent migration/readers, atomic saves, interrupted moves, conflicting files, edited text, exact byte/permission preservation, and symlink rejection. Search reaches every date folder regardless of the recent-excerpt display limit.

Handy tests use authored SQLite fixtures matching upstream's `transcription_history` table. They cover original/post-processed text, delayed completion, same-second entries, retention, manual edits, database byte preservation, committed WAL entries, busy/corrupt/missing databases, older schemas, custom/XDG paths, concurrent monitor imports, interrupted index writes, search highlighting, and independent Voxtype cursors.

Live Handy 0.9.6 validation on 2026-09-08 used a real microphone recording with the Canary 180M Flash Q8_0 model. The CLI recording toggle worked; the app's Ctrl+Space shortcut did not work in this Hyprland session. Handy produced an audio recording and a non-empty transcript. The installed shell initially retained pre-update QML; after `omarchy restart shell`, DictDrawer automatically imported the real transcript with exact text, one archive copy, and no warnings. No test audio or transcript text was added to this repository. AI post-processing was disabled, so live post-processing remains unverified; its adapter behavior is covered by fixtures and the isolated UI test below.

## Layout checks

The opt-in `tests/desktop_check.py` uses the actual QML components on a temporary Hyprland virtual output. It does not change physical-monitor settings. Its throwaway preview disables keyboard capture and cross-monitor dismiss layers, uses only authored sample transcripts, and cleans up the process and output in `finally`.

All 56 combinations passed: four bar sides, 24/72 logical-pixel bar thicknesses, 12/20-pixel base fonts, across these display modes:

| Physical resolution | Output scale |
| --- | --- |
| 1920×1080 | 1×, 1.25×, 1.5×, 2× |
| 1366×768 | 1× |
| 1280×720 | 2× (640×360 logical space) |
| 3840×2160 | 2× |

Assertions check that the card stays on-screen and outside the bar, the footer remains inside the card, the results area is non-negative, and the search field retains usable text width. Additional checks confirm an unchanged drawer height/footer position across typing, multiple matches, no matches, and clearing the query. The test process reported no QML binding-loop/type/reference errors in the successful run.

The same isolated preview also passed a synthetic Handy database through the real background timer and Python helper: import with the drawer closed, a later post-processing update without duplication, an unchanged idle refresh without a model reset or search indicator, and highlighted search after reopening. This verifies the adapter-to-drawer integration, not Handy's recording engine.

Earlier physical-display checks covered 1× and 1.5× monitors, opening/closing animation, outside-click dismissal, and exact clipboard output. Virtual-output checks complement those tests; they do not certify every GPU, theme, input method, or future shell version.

## Install lifecycle

The installed git-managed plugin was updated from the previous review build using `omarchy plugin update dictdrawer --yes`, disabled, removed with the normal Omarchy CLI, and freshly installed with `omarchy plugin add <repository-url> --enable --yes`. The reinstalled package passed validation and loaded under the `dictdrawer` ID after a shell restart.

Before the check, the installed plugin, shell settings, Voxtype config, and saved transcripts were backed up. Afterward, SHA-256 comparisons verified every original transcript file's content was preserved through date-folder migration, removal, and reinstall. Voxtype's config was byte-identical, and widget settings and bar placement were preserved. Both the default 20 and a five-result limit were checked against the full saved history. The Super+Alt+apostrophe binding still targets DictDrawer.

GitHub Actions runs both the Python and offscreen Qt keyboard suites. The release-candidate code passed both jobs; repeat these checks after any final release changes.

## Screenshots

The three repository PNGs were refreshed from the release-candidate components using fictional development-session dictations, with “Release checklist” third. Search highlights that excerpt and retains the same full-height drawer as the normal view. The preview bar reads the active theme's actual bar colors instead of hard-coded colors, and the wider 1000×1020 framing includes the stock Everforest Omarchy-logo wallpaper. The screenshot runner verifies matching bar colors and a loaded wallpaper before capture; `--wallpaper` can select another local image for the isolated preview. No live desktop content or personal dictations is included, and physical desktop theme/background settings are unchanged.
