import json
import tempfile
import unittest
from pathlib import Path

from hillclimber.cli import run_dry


class CliTests(unittest.TestCase):
    def test_dry_run_writes_auditable_artifact_without_api_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            result, artifact = run_dry(Path(directory), rounds=8, stagnation=3)
            self.assertGreater(result.best_score, 24)
            self.assertTrue(artifact.exists())
            data = json.loads(artifact.read_text())
            self.assertEqual("scripted-local", data["model"])
            self.assertEqual(result.best_score, data["bestScore"])
            self.assertEqual(len(result.rounds), len(data["rounds"]))
            self.assertTrue(all("raw_response" in item for item in data["rounds"]))


if __name__ == "__main__":
    unittest.main()
