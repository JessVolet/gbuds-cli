"""Tests for the GitHub release update checker."""

import unittest
import json
import sys
from hashlib import sha256
from contextlib import redirect_stdout
from io import BytesIO, StringIO
from pathlib import Path
from unittest.mock import patch

from gbuds.cli import main
from gbuds.updates import ReleaseInfo, UpdateCheck, UpdateError, install_release, parse_version, select_release


class TestUpdates(unittest.TestCase):
    def test_semantic_version_order_includes_prerelease_stages(self):
        self.assertLess(parse_version("v0.2.0a1"), parse_version("0.2.0b1"))
        self.assertLess(parse_version("0.2.0b2"), parse_version("0.2.0rc1"))
        self.assertLess(parse_version("0.2.0rc1"), parse_version("0.2.0"))
        self.assertLess(parse_version("0.1.9"), parse_version("0.2.0b1"))
        self.assertIsNone(parse_version("not-a-version"))

    def test_release_selection_ignores_drafts_and_respects_prerelease_option(self):
        releases = [
            {"tag_name": "v0.1.0b1", "draft": False, "prerelease": True, "html_url": "https://github.com/JessVolet/gbuds-cli/releases/tag/v0.1.0b1", "assets": []},
            {"tag_name": "v0.1.0b2", "draft": False, "prerelease": True, "html_url": "https://github.com/JessVolet/gbuds-cli/releases/tag/v0.1.0b2", "assets": []},
            {"tag_name": "v9.0.0", "draft": True, "prerelease": False, "html_url": "https://github.com/JessVolet/gbuds-cli/releases/tag/v9.0.0", "assets": []},
        ]

        self.assertIsNone(select_release(releases, include_prerelease=False))
        latest = select_release(releases, include_prerelease=True)
        self.assertEqual(latest.version, "0.1.0b2")

    def test_release_selection_requires_an_official_github_wheel_asset(self):
        release = {
            "tag_name": "v0.2.0",
            "draft": False,
            "prerelease": False,
            "html_url": "https://github.com/JessVolet/gbuds-cli/releases/tag/v0.2.0",
            "assets": [{
                "name": "gbuds-0.2.0-py3-none-any.whl",
                "browser_download_url": "https://example.com/gbuds-0.2.0-py3-none-any.whl",
                "digest": "sha256:" + "a" * 64,
            }],
        }

        selected = select_release([release], include_prerelease=False)
        self.assertEqual(selected.version, "0.2.0")
        self.assertIsNone(selected.wheel_url)
        self.assertIsNone(selected.wheel_sha256)

    def test_install_verifies_asset_digest_before_invoking_pip(self):
        wheel_data = b"verified wheel bytes"
        release = ReleaseInfo(
            "0.2.0", "v0.2.0", "https://github.com/JessVolet/gbuds-cli/releases/tag/v0.2.0",
            "https://github.com/JessVolet/gbuds-cli/releases/download/v0.2.0/gbuds-0.2.0-py3-none-any.whl",
            sha256(wheel_data).hexdigest(),
        )

        def inspect_installer(command, check):
            self.assertEqual(Path(command[-1]).read_bytes(), wheel_data)
            self.assertFalse(check)
            return type("Result", (), {"returncode": 0})()

        with patch("gbuds.updates.sys.prefix", "/venv"), \
             patch("gbuds.updates.sys.base_prefix", "/usr"), \
             patch("gbuds.updates.urlopen", return_value=BytesIO(wheel_data)), \
             patch("gbuds.updates.subprocess.run", side_effect=inspect_installer) as installer:
            install_release(release)

        installer.assert_called_once()

    def test_install_rejects_digest_mismatch_and_system_python(self):
        release = ReleaseInfo(
            "0.2.0", "v0.2.0", "https://github.com/JessVolet/gbuds-cli/releases/tag/v0.2.0",
            "https://github.com/JessVolet/gbuds-cli/releases/download/v0.2.0/gbuds-0.2.0-py3-none-any.whl",
            "a" * 64,
        )
        with patch("gbuds.updates.sys.prefix", "/venv"), \
             patch("gbuds.updates.sys.base_prefix", "/usr"), \
             patch("gbuds.updates.urlopen", return_value=BytesIO(b"different wheel")), \
             patch("gbuds.updates.subprocess.run") as installer:
            with self.assertRaisesRegex(UpdateError, "SHA-256 digest does not match"):
                install_release(release)
        installer.assert_not_called()

        with patch("gbuds.updates.sys.prefix", "/usr"), \
             patch("gbuds.updates.sys.base_prefix", "/usr"):
            with self.assertRaisesRegex(UpdateError, "Refusing to modify a system Python"):
                install_release(release)


class TestUpdateCommand(unittest.TestCase):
    def test_update_check_emits_json_and_does_not_touch_bluetooth(self):
        release = ReleaseInfo("0.1.0b1", "v0.1.0b1", "https://github.com/JessVolet/gbuds-cli/releases/tag/v0.1.0b1", None, None)
        check = UpdateCheck("0.1.0b1", release, False)
        output = StringIO()
        with patch.object(sys, "argv", ["gbuds", "--json", "update"]), \
             patch("gbuds.cli.check_for_updates", return_value=check), \
             patch("gbuds.cli.auto_detect_buds_mac") as detect, \
             redirect_stdout(output):
            main()

        payload = json.loads(output.getvalue())
        self.assertTrue(payload["success"])
        self.assertFalse(payload["update_available"])
        self.assertEqual(payload["latest_version"], "0.1.0b1")
        detect.assert_not_called()

    def test_update_install_uses_selected_release_only_when_requested(self):
        release = ReleaseInfo("0.1.0b2", "v0.1.0b2", "https://github.com/JessVolet/gbuds-cli/releases/tag/v0.1.0b2", "https://github.com/JessVolet/gbuds-cli/releases/download/v0.1.0b2/gbuds-0.1.0b2-py3-none-any.whl", "a" * 64)
        check = UpdateCheck("0.1.0b1", release, True)
        output = StringIO()
        with patch.object(sys, "argv", ["gbuds", "update", "--install", "--prerelease"]), \
             patch("gbuds.cli.check_for_updates", return_value=check) as check_fn, \
             patch("gbuds.cli.install_release") as install_fn, \
             redirect_stdout(output):
            main()

        check_fn.assert_called_once_with(include_prerelease=True)
        install_fn.assert_called_once_with(release)
        self.assertIn("Updated Gbuds to 0.1.0b2", output.getvalue())


if __name__ == "__main__":
    unittest.main()
