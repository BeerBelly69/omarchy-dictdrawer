"""Keep the install identity consistent across the packaged app and docs."""

import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PackageTests(unittest.TestCase):
    def test_install_identity_matches_app_name(self):
        manifest = json.loads((ROOT / "manifest.json").read_text())
        self.assertEqual(manifest["id"], "dictdrawer")
        self.assertEqual(manifest["name"], "DictDrawer")
        self.assertEqual(manifest["barWidget"]["displayName"], "DictDrawer")
        panel = (ROOT / "Panel.qml").read_text()
        self.assertEqual(re.search(r'moduleName:\s*"([^"]+)"', panel)[1], manifest["id"])

    def test_documented_commands_target_installed_plugin(self):
        readme = (ROOT / "README.md").read_text()
        for command in ("omarchy bar move dictdrawer", "omarchy-shell shell toggle dictdrawer",
                        "omarchy plugin disable dictdrawer", "omarchy plugin remove dictdrawer"):
            self.assertIn(command, readme)
        self.assertIn("omarchy-dictdrawer.git", readme)


if __name__ == "__main__":
    unittest.main()
