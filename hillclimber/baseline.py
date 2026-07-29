"""A deliberately valid but weak starting route."""

import json
from pathlib import Path

from hillclimber.judge import parse_map, score_route
from hillclimber.render import render_result


BASELINE_ROUTE = {"moves": ["D", "D", "D", "D", "R", "R"]}


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    puzzle = parse_map((root / "maps" / "level-01.txt").read_text())
    result = score_route(puzzle, BASELINE_ROUTE)
    print(json.dumps(BASELINE_ROUTE))
    print(render_result(puzzle, result))


if __name__ == "__main__":
    main()
