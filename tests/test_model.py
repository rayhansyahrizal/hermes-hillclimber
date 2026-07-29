import subprocess
import unittest
from unittest.mock import patch

from hillclimber.model import HermesModel


class HermesModelTests(unittest.TestCase):
    @patch("hillclimber.model.subprocess.run")
    def test_uses_one_turn_quiet_isolated_query(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, '{"moves":["R"]}\n', "")
        model = HermesModel(model="gpt-5.6-sol", provider="openai-codex")
        response = model.complete("puzzle prompt")
        self.assertEqual('{"moves":["R"]}', response)
        command = run.call_args.args[0]
        self.assertIn("--max-turns", command)
        self.assertIn("1", command)
        self.assertIn("--ignore-rules", command)
        self.assertIn("--quiet", command)
        self.assertIn("gpt-5.6-sol", command)
        self.assertEqual(1, model.calls)

    @patch("hillclimber.model.subprocess.run")
    def test_surfaces_cli_failure(self, run):
        run.return_value = subprocess.CompletedProcess([], 2, "", "provider failed")
        model = HermesModel(model="gpt-5.6-sol", provider="openai-codex")
        with self.assertRaisesRegex(RuntimeError, "provider failed"):
            model.complete("puzzle prompt")


if __name__ == "__main__":
    unittest.main()
