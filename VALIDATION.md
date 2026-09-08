# Release-candidate validation

Checked on 2026-09-08 with Omarchy 4.0.2, Hyprland 0.56.2, Quickshell 0.3.1, and Qt 6.11.2.

## Automated checks

- 32 Python tests: journal recovery, saved-history persistence, literal Unicode highlights, package identity, per-day storage, and migration safety.
- 15 Qt Quick Test results (including setup/cleanup): printable keys, former letter-navigation shortcuts, uppercase, modifiers, arrow navigation, search/copy/Escape, and normal text editing.
- Omarchy plugin validation and QML parse checks.

The storage tests cover concurrent migration/readers, atomic saves, interrupted moves, conflicting files, edited text, exact byte/permission preservation, and symlink rejection. Search reaches every date folder regardless of the recent-excerpt display limit.

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

Earlier physical-display checks covered 1× and 1.5× monitors, opening/closing animation, outside-click dismissal, and exact clipboard output. Virtual-output checks complement those tests; they do not certify every GPU, theme, input method, or future shell version.

## Install lifecycle

Final update, disable, remove, and reinstall checks are pending on the release-candidate build. Saved transcripts and Voxtype configuration are backed up before the check; byte comparisons will verify preservation afterward.

## Screenshots

The three repository PNGs were refreshed from the release-candidate components using authored sample transcripts. Search shows highlighted matches and the same full-height drawer as the normal view. No live desktop content or personal dictations is included.
