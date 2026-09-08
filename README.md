# DictDrawer

Your dictations, a keystroke away.

A searchable Voxtype history drawer for Omarchy. Recover an excerpt, find the words you need, and copy them back into your work.

> Private release candidate — not publicly released or listed in the marketplace. See the [release checklist](RELEASE_CHECKLIST.md) before publishing.

![The dictation drawer, showing sample transcripts](preview.png)

Click the history icon to retrieve words that landed in the wrong window or reuse an earlier excerpt. The panel slides from behind the bar, follows your theme, and keeps its controls in the footer.

## Features

- Recovers existing Voxtype transcripts from the user journal.
- Saves plain-text excerpts in per-day folders and reads them back after journal rotation.
- Searches all saved transcripts, with case-insensitive, multiword matching, highlighted words, and context previews.
- Just start typing to search; arrow-key navigation, expandable excerpts, and clipboard copy with success/failure feedback.
- Top, bottom, left, and right bar layouts, with rounded corners and a subtle shadow.
- No Voxtype configuration changes, additional recording process, model downloads, or network requests.

## Requirements

Tested with Omarchy **4.0.2**, Quickshell **0.3.1**, Qt **6.11.2**, and Voxtype **1.0.1**. This plugin uses Omarchy's shared `qs.Ui` components; older shell versions have not been validated. `RectangularShadow` requires Qt 6.9 or later.

- A running Omarchy Quattro shell on Hyprland/Wayland.
- Voxtype running as the `voxtype.service` **user** service, with INFO-level transcription logs. Quiet logging cannot be recovered.
- Python 3.10+ and `journalctl` (systemd).
- `wl-copy` (`wl-clipboard`) for clipboard access.
- `xdg-open` (`xdg-utils`) and a file manager for the folder button.
- Omarchy's normal Nerd Font for the icons.

Enable Voxtype through Omarchy's Dictation setup if it is not already installed. Leave `state_file = "auto"` in its configuration for immediate archival when a dictation finishes. Opening or refreshing the drawer also imports history.

## Install

During private review, Git must already be authenticated with an account that has access to this repository. This is not yet a public installation URL.

```sh
omarchy plugin add https://github.com/BeerBelly69/omarchy-dictdrawer.git --enable
```

The helper is bundled in the plugin; no separate script installation is needed. To change the bar section:

```sh
omarchy bar move dictdrawer --section center
```

### Optional shortcut

The plugin does not install or replace keybindings. Check whether your preferred chord is free with `omarchy menu keybindings --print`, then add this to `~/.config/hypr/bindings.lua`:

```lua
o.bind("SUPER + ALT + apostrophe", "DictDrawer", "omarchy-shell shell toggle dictdrawer")
```

On a Mac keyboard, Super is the Command key. This shortcut is Cmd+Alt+the apostrophe/quote key, without Shift. Validate changes with `hyprctl reload` followed by `hyprctl configerrors`. The `shell toggle` route chooses the appropriate bar instance on a multi-monitor desktop.

## Use

| Action | Control |
| --- | --- |
| Open or close | History icon, or your optional shortcut |
| Select an excerpt | Up/Down |
| Expand / collapse | Right/Left outside the search field; click the excerpt |
| Copy selection | Enter; copy button on each row |
| Search | Start typing; magnifier, Ctrl+F, or Tab to focus/select the query |
| Refresh from journal | Circular-arrow button |
| Open saved text files | Folder button |
| Close | Escape clears a query first; press again to close, or click outside |

Typing from the excerpt list starts a new search immediately, including letters that used to navigate (j/k/h/l) and punctuation such as `/`. In the search field, Up/Down select results and Enter copies; Left/Right move the caret, and spaces, Backspace, selection, and other normal text editing remain available. Ctrl+F selects the current query. Escape clears the query and returns to the excerpt list; another Escape closes the drawer. Tab returns to list navigation. After copying, paste normally in your destination app.

Search matches every word you enter, regardless of order or case. It searches the full saved archive; the newest matching excerpts are displayed up to the widget's **Dictations shown** limit (5–100, default 20). Narrow the query to reach older matches. The result count shows the total number of matches, including any beyond the display limit.

Matching text is highlighted in yellow. Collapsed results show context around the first match, even deep in a long transcript; expand an excerpt to see all highlighted occurrences. Copy always copies the complete original transcript without formatting.

The drawer stays full-sized while searching, including when there are no matches. Results remain visible until the next search completes, with a small “Searching…” indicator in the field.

![Searching the saved archive](screenshots/search.png)

## Storage and privacy

The plugin reads only the `voxtype.service` user journal and its transcript directory. It never records audio or uploads transcripts. Enabling the widget enables local archival; there is no separate capture hook or config rewrite.

History lives in `$XDG_DATA_HOME/voxtype/history`, or `~/.local/share/voxtype/history` when XDG_DATA_HOME is unset. Each transcript is saved under its recording's local date, for example `history/2026-09-08/1788877800000000-<hash>.txt`. New transcripts are private (`0600`) text files with microsecond timestamps and content hashes in their names. New archive and date directories are created with mode `0700`. Existing directories and legacy files retain their permissions.

On opening or refreshing, existing flat transcript files—including older `YYYY-MM-DD_HHMMSS.txt` files—are reorganized into date folders without changing their filenames, bytes, or permissions. Both layouts remain readable. Interrupted moves can resume safely; conflicting copies are kept with a warning, never overwritten. Unrelated files and symlinks are left alone. A private `.dictdrawer.lock` coordinates reorganization and reads between monitor instances. New transcript writes are atomic, and manually edited archive text is preserved.

Dates use the system's local timezone when a file is first saved or organized. Changing timezone does not relocate already-organized files. The rolling 20 (or your chosen display limit) never deletes older transcripts; search covers all date folders.

On first use, at most the newest **50,000 journal records** are imported. Subsequent imports resume from the newest saved timestamp with a one-second overlap. A warning appears if the import cap is reached or history is unavailable. Journal entries already removed by rotation cannot be recovered unless a saved transcript exists. The archive has no automatic retention limit in this release.

To stop archival, disable the widget:

```sh
omarchy plugin disable dictdrawer
```

To remove saved excerpts, use the folder button and your file manager. **Re-enabling or refreshing can recover deleted excerpts again while their source journal entries still exist.** The plugin does not erase system journals. Saving and deleting history are local operations, not a guarantee that every other copy has been erased.

## Remove

```sh
omarchy plugin remove dictdrawer
```

Remove the optional binding you added to `bindings.lua` and reload Hyprland. Saved transcripts remain in the history directory; remove them separately only if you want to discard them. There is no Voxtype hook to uninstall, and no service needs to be restarted.

## Troubleshooting

- **No transcripts:** check `systemctl --user status voxtype.service` and `journalctl --user -u voxtype.service`. This release recognizes Voxtype's `INFO Transcribed:` message format. Other services, custom state paths, and future log-format changes may need adaptation.
- **Copy fails:** confirm `wl-copy` is available and the shell is running in your Wayland session.
- **Archive warning:** check the history directory's permissions and available disk space. Saved history remains readable when the journal fails.
- **An edit does not appear:** try `omarchy-shell shell rescanPlugins`. Some shell versions retain cached QML; `omarchy restart shell` loads the new components.

## Development and validation

```sh
python3 -m unittest discover -s tests -v
QT_QPA_PLATFORM=offscreen /usr/lib/qt6/bin/qmltestrunner -input tests/qml -o -,txt
omarchy plugin validate .
```

The automated tests use temporary files and mocked journals. They cover recovery after rotation, concurrent saves and migration, date folders, interrupted/conflicting moves, timestamp collisions, legacy archives, literal Unicode search, edited files, unreadable files, missing/failed journal commands, package identity, and type-to-search keyboard behavior. They do not require private transcripts or a running desktop. The keyboard tests require Qt Quick Test (`qmltestrunner`); these development tools are not needed to run DictDrawer.

Manual checks on Omarchy 4.0.2 covered top/bottom/left/right bar layouts, 1× and 1.5× physical monitors, search and no-match states, exact clipboard content, Escape dismissal, and rapid close/reopen. For reproducible layout checks, `python3 tests/desktop_check.py` creates a temporary virtual output in a running Hyprland session, exercises additional resolutions/scales/bar sizes/font sizes, and removes the output and test process afterward. Physical monitor settings are unchanged. Add `--screenshots` to refresh the three repository previews using only authored sample transcripts. See [validation notes](VALIDATION.md) for tested coverage.

![The drawer above a bottom bar](screenshots/bottom-bar.png)

## Related plugin

[Dictation (Voxtype) History](https://github.com/okurmustafa/omarchy-plugin-voxtype-history) is another history plugin with post-process capture, pinning, and deletion. This project focuses on a sliding drawer and recovery of existing journal history without adding a Voxtype hook.

## License

MIT. The drawer's focus and popup coordination are adapted from Omarchy's `Ui/KeyboardPanel.qml`; its copyright notice is retained in [LICENSE](LICENSE). The screenshots and sample dictations were created for this project.
