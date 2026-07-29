import json
import unittest

from hillclimber.judge import parse_map
from hillclimber.model import ScriptedModel
from hillclimber.runner import run_hillclimber


MAP = "#####\n#STE#\n#####"


class RunnerTests(unittest.TestCase):
    def test_keeps_only_strict_improvements_and_records_every_candidate(self):
        model = ScriptedModel([
            json.dumps({"moves": ["R"]}),       # 29, accepted over 0
            json.dumps({"moves": ["U"]}),       # -21, rejected
            "not json",                          # invalid, rejected
            json.dumps({"moves": ["R", "R"]}), # 78, accepted
        ])
        result = run_hillclimber(
            parse_map(MAP), {"moves": []}, model, max_rounds=4, stagnation_limit=4
        )
        self.assertEqual(78, result.best_score)
        self.assertEqual({"moves": ["R", "R"]}, result.best_route)
        self.assertEqual([True, False, False, True], [r.accepted for r in result.rounds])
        self.assertEqual("invalid", result.rounds[2].status)

    def test_stops_after_consecutive_non_improvements(self):
        model = ScriptedModel([
            json.dumps({"moves": ["U"]}),
            json.dumps({"moves": ["U"]}),
            json.dumps({"moves": ["R", "R"]}),
        ])
        result = run_hillclimber(
            parse_map(MAP), {"moves": []}, model, max_rounds=8, stagnation_limit=2
        )
        self.assertEqual(2, len(result.rounds))
        self.assertEqual("stagnation", result.stop_reason)
        self.assertEqual(2, model.calls)


if __name__ == "__main__":
    unittest.main()
