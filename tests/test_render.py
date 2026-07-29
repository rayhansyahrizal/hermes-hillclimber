import unittest

from hillclimber.judge import parse_map, score_route
from hillclimber.render import render_result


class RenderTests(unittest.TestCase):
    def test_replay_shows_path_and_score_breakdown(self):
        puzzle = parse_map("#####\n#STE#\n#####")
        result = score_route(puzzle, {"moves": ["R", "R"]})
        output = render_result(puzzle, result)
        self.assertIn("**@", output)
        self.assertIn("score=78", output)
        self.assertIn("treasures=1/1", output)
        self.assertIn("steps=2", output)


if __name__ == "__main__":
    unittest.main()
