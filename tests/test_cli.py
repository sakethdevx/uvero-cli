from __future__ import annotations

import unittest
from unittest.mock import patch

from typer.testing import CliRunner

from uvero.cli import app


class UveroCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()
        self.base_env = {
            "UVERO_AUTO_UPGRADE": "0",
            "UVERO_UPDATE_CHECK": "0",
        }

    def invoke(self, args: list[str], **kwargs):
        env = dict(self.base_env)
        env.update(kwargs.pop("env", {}))
        return self.runner.invoke(app, args, env=env, **kwargs)

    def test_send_clipboard_keyword_uses_readable_source(self) -> None:
        def fake_read_text_source(source, value, *, interactive_prompt):
            self.assertEqual(source, "clipboard")
            self.assertIsNone(value)
            self.assertIn("Paste or type your text", interactive_prompt)
            return "hello from clipboard"

        with patch("uvero.cli.read_text_source", side_effect=fake_read_text_source), patch(
            "uvero.cli.call_api",
            return_value={"success": True, "data": {"code": "4832"}},
        ), patch("uvero.cli.write_clipboard") as mock_write_clipboard:
            result = self.invoke(["send", "clipboard"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("4832", result.output)
        mock_write_clipboard.assert_called_once_with("4832")

    def test_send_file_keyword_supports_beginner_friendly_syntax(self) -> None:
        def fake_read_text_source(source, value, *, interactive_prompt):
            self.assertEqual(source, "file")
            self.assertEqual(value, "notes.txt")
            return "file contents"

        with patch("uvero.cli.read_text_source", side_effect=fake_read_text_source), patch(
            "uvero.cli.call_api",
            return_value={"success": True, "data": {"code": "5921"}},
        ), patch("uvero.cli.write_clipboard"):
            result = self.invoke(["send", "file", "notes.txt"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("5921", result.output)

    def test_get_clipboard_keyword_writes_to_clipboard(self) -> None:
        with patch(
            "uvero.cli.call_api",
            return_value={"success": True, "data": {"content": "saved text"}},
        ), patch("uvero.utils.write_clipboard") as mock_write_clipboard:
            result = self.invoke(["get", "1234", "clipboard"])

        self.assertEqual(result.exit_code, 0, result.output)
        mock_write_clipboard.assert_called_once_with("saved text")
        self.assertIn("clipboard", result.output.lower())

    def test_help_does_not_trigger_update_check(self) -> None:
        with patch(
            "uvero.cli.notify_if_update_available",
            side_effect=AssertionError("update check should not run for help"),
        ):
            result = self.runner.invoke(app, ["--help"], env={})
            subcommand_result = self.runner.invoke(app, ["send", "--help"], env={})

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Usage:", result.output)
        self.assertEqual(subcommand_result.exit_code, 0, subcommand_result.output)
        self.assertIn("Usage:", subcommand_result.output)

    def test_board_send_rejects_empty_content(self) -> None:
        with patch("uvero.boards.read_text_source", return_value=""):
            result = self.invoke(["board", "send", "abcd-def"])

        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn("Nothing to send", result.output)

    def test_legacy_get_dash_still_maps_to_clipboard(self) -> None:
        with patch(
            "uvero.cli.call_api",
            return_value={"success": True, "data": {"content": "legacy text"}},
        ), patch("uvero.utils.write_clipboard") as mock_write_clipboard:
            result = self.invoke(["get", "1234", "-"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("deprecated", result.output.lower())
        mock_write_clipboard.assert_called_once_with("legacy text")

    def test_board_get_accepts_password_option(self) -> None:
        with patch(
            "uvero.boards.call_api",
            return_value={"success": True, "data": {"content": "protected board text"}},
        ) as mock_call_api:
            result = self.invoke(["board", "get", "secure-1", "stdout", "--password", "secret123"])

        self.assertEqual(result.exit_code, 0, result.output)
        _, args, kwargs = mock_call_api.mock_calls[0]
        self.assertEqual(args[1], "secure-1")
        self.assertEqual(kwargs["password"], "secret123")


if __name__ == "__main__":
    unittest.main()
