import unittest
from pathlib import Path

from hillclimber.judge import InvalidMap, InvalidRoute, parse_map, score_route


MAP = """\
#######
#S.T.E#
#..T..#
#######
"""


class JudgeTests(unittest.TestCase):
    def test_parse_map_finds_required_cells(self):
        puzzle = parse_map(MAP)
        self.assertEqual((1, 1), puzzle.start)
        self.assertEqual((1, 5), puzzle.exit)
        self.assertEqual({(1, 3), (2, 3)}, puzzle.treasures)

    def test_parse_map_requires_one_start_and_exit(self):
        with self.assertRaises(InvalidMap):
            parse_map("###\n#S#\n###")

    def test_valid_route_collects_each_treasure_once_and_gets_exit_bonus(self):
        result = score_route(
            parse_map(MAP),
            {"moves": ["R", "R", "D", "U", "L", "R", "R", "R"]},
        )
        self.assertEqual(102, result.score)
        self.assertEqual(2, result.treasures_collected)
        self.assertTrue(result.reached_exit)
        self.assertEqual(8, result.steps)

    def test_wall_collision_penalizes_and_terminates(self):
        result = score_route(parse_map(MAP), {"moves": ["U", "R"]})
        self.assertEqual(-21, result.score)
        self.assertTrue(result.collided)
        self.assertEqual(1, result.steps)

    def test_out_of_bounds_terminates(self):
        open_map = parse_map("S.E\n...")
        result = score_route(open_map, {"moves": ["U", "R"]})
        self.assertEqual(-21, result.score)
        self.assertTrue(result.collided)

    def test_rejects_bad_contract_and_long_routes(self):
        puzzle = parse_map(MAP)
        bad_routes = [
            [],
            {"moves": ["X"]},
            {"moves": [], "hack": True},
            {"moves": ["R"] * 251},
        ]
        for route in bad_routes:
            with self.subTest(route=route):
                with self.assertRaises(InvalidRoute):
                    score_route(puzzle, route)

    def test_scoring_is_deterministic(self):
        puzzle = parse_map(MAP)
        route = {"moves": ["R", "R", "D", "L"]}
        self.assertEqual(score_route(puzzle, route), score_route(puzzle, route))


if __name__ == "__main__":
    unittest.main()
