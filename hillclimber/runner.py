"""Bounded accept-only-improvements hill-climbing loop."""

from dataclasses import dataclass
import json
from typing import Any

from hillclimber.judge import InvalidRoute, Puzzle, RouteResult, score_route
from hillclimber.model import RouteModel


@dataclass(frozen=True)
class RoundRecord:
    round: int
    raw_response: str
    route: dict[str, Any] | None
    score: int | None
    accepted: bool
    status: str
    feedback: str


@dataclass(frozen=True)
class RunResult:
    best_route: dict[str, Any]
    best_score: int
    best_result: RouteResult
    rounds: tuple[RoundRecord, ...]
    stop_reason: str
    model_name: str


def build_prompt(puzzle: Puzzle, incumbent: dict[str, Any], result: RouteResult) -> str:
    board = "\n".join(puzzle.rows)
    return (
        "Improve the current route for this deterministic treasure puzzle.\n"
        "Return JSON only, exactly: {\"moves\":[\"U\",\"R\",\"D\",\"L\"]}.\n"
        "Scoring: +30 per unique treasure, -1 per step, -20 and stop on collision, "
        "+50 for reaching E after collecting every treasure. Maximum 250 moves.\n\n"
        f"Map:\n{board}\n\n"
        f"Current route: {json.dumps(incumbent, separators=(',', ':'))}\n"
        f"Current score: {result.score}\n"
        f"Judge feedback: {result.feedback}\n"
        "Propose one complete replacement route that scores higher."
    )


def run_hillclimber(
    puzzle: Puzzle,
    initial_route: dict[str, Any],
    model: RouteModel,
    *,
    max_rounds: int = 8,
    stagnation_limit: int = 3,
) -> RunResult:
    if max_rounds < 0 or stagnation_limit < 1:
        raise ValueError("invalid run limits")
    best_route = initial_route
    best_result = score_route(puzzle, best_route)
    records: list[RoundRecord] = []
    stagnant = 0
    stop_reason = "max_rounds"

    for number in range(1, max_rounds + 1):
        raw = model.complete(build_prompt(puzzle, best_route, best_result))
        try:
            candidate = json.loads(raw)
            candidate_result = score_route(puzzle, candidate)
            accepted = candidate_result.score > best_result.score
            if accepted:
                best_route = candidate
                best_result = candidate_result
                stagnant = 0
            else:
                stagnant += 1
            record = RoundRecord(
                round=number,
                raw_response=raw,
                route=candidate,
                score=candidate_result.score,
                accepted=accepted,
                status="accepted" if accepted else "rejected",
                feedback=candidate_result.feedback,
            )
        except (json.JSONDecodeError, InvalidRoute) as error:
            stagnant += 1
            record = RoundRecord(number, raw, None, None, False, "invalid", str(error))
        records.append(record)
        if stagnant >= stagnation_limit:
            stop_reason = "stagnation"
            break

    return RunResult(
        best_route=best_route,
        best_score=best_result.score,
        best_result=best_result,
        rounds=tuple(records),
        stop_reason=stop_reason,
        model_name=model.name,
    )
