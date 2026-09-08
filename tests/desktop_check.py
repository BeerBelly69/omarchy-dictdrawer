#!/usr/bin/env python3
"""Opt-in Omarchy layout QA on a temporary virtual output; physical monitors are unchanged.

Run from a live Omarchy session: python3 tests/desktop_check.py [--screenshots]
Only authored sample history is exposed to the preview. All test windows,
processes, and the virtual output are removed in finally, even on failure.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import history

OUTPUT = "DICTDRAWER-QA"


def run(*args, env=None):
    result = subprocess.run(args, capture_output=True, text=True, timeout=15, env=env)
    if result.returncode:
        raise RuntimeError(f"{args[0]} failed: {result.stderr or result.stdout}")
    return result.stdout.strip()


def monitor(mode, scale):
    result = run("hyprctl", "eval", f'hl.monitor({{output="{OUTPUT}", mode="{mode}@60", position="8000x0", scale={scale}}})')
    if "error" in result.lower():
        raise RuntimeError(result)
    time.sleep(0.2)


def check(state):
    x, y, width, height = (state[k] for k in ("x", "y", "width", "height"))
    assert state["open"], state
    assert 0 <= x and 0 <= y and x + width <= state["screenW"] + 1 and y + height <= state["screenH"] + 1, state
    side, bar = state["side"], state["bar"]
    if side == "top": assert y >= bar, state
    if side == "bottom": assert y + height <= state["screenH"] - bar + 1, state
    if side == "left": assert x >= bar, state
    if side == "right": assert x + width <= state["screenW"] - bar + 1, state
    assert state["footerBottom"] <= state["innerHeight"] + 1, state
    assert state["resultsHeight"] >= 0, state
    assert state["searchWidth"] >= state["searchPadding"] + 30, state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshots", action="store_true")
    args = parser.parse_args()
    if any(m["name"] == OUTPUT for m in json.loads(run("hyprctl", "monitors", "all", "-j"))):
        raise RuntimeError(f"{OUTPUT} already exists; refusing to reuse or remove someone else's output")
    created, process = False, None
    with tempfile.TemporaryDirectory(prefix="dictdrawer-qa-") as temporary:
        stage = Path(temporary)
        try:
            plugin = stage / "Plugin"
            shutil.copytree(ROOT, plugin, ignore=shutil.ignore_patterns(".git", "__pycache__"))
            for name in ("Commons", "Ui"):
                (stage / name).symlink_to(Path("/usr/share/omarchy/shell") / name, target_is_directory=True)
            shutil.copyfile(ROOT / "tests/fixtures/preview.qml", stage / "shell.qml")
            # Instrument only the throwaway copy. No test IPC is installed.
            panel = plugin / "Panel.qml"
            panel.write_text(panel.read_text().replace('  id: root\n', '''  id: root
  function qaQuery(value) {
    if (value.length) search(value)
    else { searchField.clear(); searchShown = false }
  }
  function qaState() {
    return JSON.stringify({open: opened, query: resultsQuery, rows: rows.length,
      x: panel.cardOrigin.x, y: panel.cardOrigin.y, width: panel.contentWidth, height: panel.contentHeight,
      screenW: panel.screenW, screenH: panel.screenH, side: panel.barPos,
      bar: panel.barPos === "top" || panel.barPos === "bottom" ? panel.barH : panel.barW,
      footerBottom: footer.y + footer.height, innerHeight: panel.contentHeight - panel.verticalContentInset,
      footerY: footer.y, resultsHeight: resultsArea.height, searchWidth: searchField.width,
      searchPadding: searchField.leftPadding + searchField.rightPadding})
  }
''', 1))
            drawer = plugin / "DrawerPanel.qml"
            drawer_source = drawer.read_text().replace('WlrLayershell.keyboardFocus: open\n    ? (focusPrimed ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.Exclusive)\n    : WlrKeyboardFocus.None', 'WlrLayershell.keyboardFocus: WlrKeyboardFocus.None')
            # The production drawer dismisses on clicks on other monitors.
            # Never create those input-catching layers on physical QA outputs.
            drawer_source = drawer_source.replace('model: root.open ? Quickshell.screens : []', 'model: []')
            drawer.write_text(drawer_source)
            samples = [
                "Let’s keep the first release focused: a fast drawer, reliable saved history, and search that finds the words you need.",
                "For the project notes, add a short installation guide and a screenshot with sample dictations. Keep setup simple.",
                "A thought for tomorrow: revisit the project notes and choose the next small improvement after the release.",
                "Pick up coffee, oat milk, and something fresh for dinner on the way home.",
            ]
            data = stage / "data"
            for i, text in enumerate(samples):
                history.save_row(data / "voxtype/history", history.make_row(1788877800000000 - i * 900000000, text))
            (stage / "bin").mkdir()
            journal = stage / "bin/journalctl"
            journal.write_text("#!/bin/sh\nexit 0\n")
            journal.chmod(0o700)
            env = dict(os.environ, XDG_DATA_HOME=str(data), PATH=str(stage / "bin") + os.pathsep + os.environ["PATH"])
            run("hyprctl", "output", "create", "headless", OUTPUT)
            created = True
            monitor("1920x1080", 1)
            with (stage / "preview.log").open("w+") as log:
                process = subprocess.Popen(["quickshell", "-p", str(stage), "--no-color"], env=env, stdout=log, stderr=log)
                def ipc(method, *values):
                    return run("quickshell", "ipc", "-p", str(stage), "call", "preview", method, *map(str, values), env=env)
                def snapshot():
                    return json.loads(ipc("state"))
                time.sleep(1)
                if process.poll() is not None:
                    log.seek(0)
                    raise RuntimeError(log.read())
                cases = 0
                for mode, scale in [("1920x1080", 1), ("1920x1080", 1.25), ("1920x1080", 1.5), ("1920x1080", 2), ("1366x768", 1), ("1280x720", 2), ("3840x2160", 2)]:
                    monitor(mode, scale)
                    for i, side in enumerate(("top", "bottom", "left", "right")):
                        for thickness, font in [(24, 12), (72, 20)]:
                            ipc("setup", side, thickness, font)
                            ipc("query", "release" if i % 2 else "zzzz-no-match")
                            time.sleep(0.35)
                            state = snapshot()
                            check(state)
                            cases += 1
                    print(f"PASS {mode} at {scale}x: four sides, 24/72px bars, 12/20px fonts", flush=True)
                monitor("1920x1080", 1)
                ipc("setup", "top", 38, 14)
                time.sleep(0.4)
                sizes = []
                for query in ("", "r", "re", "release", "zzzz-no-match", ""):
                    ipc("query", query)
                    time.sleep(0.25)
                    state = snapshot()
                    assert state["query"] == query, state
                    sizes.append((state["height"], state["footerY"]))
                assert len(set(sizes)) == 1, sizes
                print(f"PASS {cases} layout cases; search geometry remains stable", flush=True)
                if args.screenshots:
                    def capture(path, bottom=False):
                        screen = next(m for m in json.loads(run("hyprctl", "monitors", "-j")) if m["name"] == OUTPUT)
                        region = f'{screen["x"] + 560},{screen["y"] + (1080 - 690 if bottom else 0)} 800x690'
                        run("grim", "-g", region, str(path))
                    time.sleep(0.3)
                    capture(ROOT / "preview.png")
                    ipc("query", "release")
                    time.sleep(0.35)
                    capture(ROOT / "screenshots/search.png")
                    ipc("query", "")
                    ipc("setup", "bottom", 38, 14)
                    time.sleep(0.45)
                    capture(ROOT / "screenshots/bottom-bar.png", bottom=True)
                    print("Captured three sample-only release screenshots", flush=True)
                ipc("quit")
                process.wait(timeout=5)
                log.seek(0)
                errors = [line for line in log if any(term in line for term in ("ReferenceError", "TypeError", "Binding loop", "Failed to load configuration"))]
                assert not errors, errors
        finally:
            if process and process.poll() is None:
                process.terminate()
                try: process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            if created:
                run("hyprctl", "output", "remove", OUTPUT)
    print("Virtual output and preview process removed", flush=True)


if __name__ == "__main__":
    main()
