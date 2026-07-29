"""Deterministic map parser and route judge."""

from dataclasses import dataclass
from typing import Any


class InvalidMap(ValueError):
    pass


class InvalidRoute(ValueError):
    pass


@dataclass(frozen=True)
class Puzzle:
    rows: tuple[str, ...]
    start: tuple[int, int]
    exit: tuple[int, int]
    treasures: frozenset[tuple[int, int]]


@dataclass(frozen=True)
class RouteResult:
    score: int
    steps: int
    treasures_collected: int
    reached_exit: bool
    collided: bool
    final_position: tuple[int, int]
    visited: tuple[tuple[int, int], ...]
    collected: frozenset[tuple[int, int]]
    feedback: str


def parse_map(text: str) -> Puzzle:
    rows = tuple(text.splitlines())
    if not rows or not any(rows):
        raise InvalidMap("map is empty")
    width = len(rows[0])
    if width == 0 or any(len(row) != width for row in rows):
        raise InvalidMap("map must be rectangular")
    allowed = set("#S.E.T")
    if any(char not in allowed for row in rows for char in row):
        raise InvalidMap("map contains unsupported cells")
    starts = [(r, c) for r, row in enumerate(rows) for c, char in enumerate(row) if char == "S"]
    exits = [(r, c) for r, row in enumerate(rows) for c, char in enumerate(row) if char == "E"]
    if len(starts) != 1 or len(exits) != 1:
        raise InvalidMap("map requires exactly one start and one exit")
    treasures = frozenset(
        (r, c) for r, row in enumerate(rows) for c, char in enumerate(row) if char == "T"
    )
    return Puzzle(rows, starts[0], exits[0], treasures)


def _validate_route(route: Any) -> list[str]:
    if not isinstance(route, dict) or set(route) != {"moves"}:
        raise InvalidRoute("route must be an object containing only 'moves'")
    moves = route["moves"]
    if not isinstance(moves, list) or len(moves) > 250:
        raise InvalidRoute("moves must be a list of at most 250 directions")
    if any(not isinstance(move, str) or move not in {"U", "R", "D", "L"} for move in moves):
        raise InvalidRoute("directions must be U, R, D, or L")
    return moves


def score_route(puzzle: Puzzle, route: Any) -> RouteResult:
    moves = _validate_route(route)
    deltas = {"U": (-1, 0), "R": (0, 1), "D": (1, 0), "L": (0, -1)}
    position = puzzle.start
    visited = [position]
    collected: set[tuple[int, int]] = set()
    score = 0
    collided = False

    for move in moves:
        dr, dc = deltas[move]
        candidate = (position[0] + dr, position[1] + dc)
        score -= 1
        if (
            candidate[0] < 0
            or candidate[0] >= len(puzzle.rows)
            or candidate[1] < 0
            or candidate[1] >= len(puzzle.rows[0])
            or puzzle.rows[candidate[0]][candidate[1]] == "#"
        ):
            score -= 20
            collided = True
            break
        position = candidate
        visited.append(position)
        if position in puzzle.treasures and position not in collected:
            collected.add(position)
            score += 30

    reached_exit = position == puzzle.exit
    if reached_exit and collected == set(puzzle.treasures):
        score += 50

    feedback_parts = [f"collected {len(collected)}/{len(puzzle.treasures)} treasures", f"used {len(visited) - 1 + int(collided)} steps"]
    if collided:
        feedback_parts.append("route terminated on a collision")
    elif position != puzzle.exit:
        feedback_parts.append("route did not finish at the exit")
    elif collected != set(puzzle.treasures):
        feedback_parts.append("exit reached before all treasures were collected")
    else:
        feedback_parts.append("all treasures collected and exit reached")

    return RouteResult(
        score=score,
        steps=len(visited) - 1 + int(collided),
        treasures_collected=len(collected),
        reached_exit=reached_exit,
        collided=collided,
        final_position=position,
        visited=tuple(visited),
        collected=frozenset(collected),
        feedback="; ".join(feedback_parts),
    )
