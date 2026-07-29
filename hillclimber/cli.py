"""Command-line interface for local and live hill-climbing runs."""

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Sequence

from hillclimber.baseline import BASELINE_ROUTE
from hillclimber.judge import parse_map, score_route
from hillclimber.model import HermesModel, ScriptedModel
from hillclimber.render import render_result
from hillclimber.runner import RunResult, run_hillclimber


ROOT = Path(__file__).resolve().parents[1]
LIVE_MODEL = "gpt-5.6-sol"
LIVE_PROVIDER = "openai-codex"
DRY_RESPONSES = [
    '{"moves":["D","D","D","D","R","R","R"]}',
    '{"moves":["D","D","D","D","R","R"]}',
    'not json',
    '{"moves":["D","D","D","D","R","R","R","R","R","R","U","U","L","R","R","R","D","D","U","U","U","U"]}',
    '{"moves":["D"]}',
    '{"moves":["U"]}',
    '{"moves":[]}',
    '{"moves":["R"]}',
]


def load_puzzle():
    return parse_map((ROOT / "maps" / "level-01.txt").read_text())


def _write_artifact(result: RunResult, output_root: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = output_root / stamp
    suffix = 1
    while run_dir.exists():
        run_dir = output_root / f"{stamp}-{suffix}"
        suffix += 1
    run_dir.mkdir(parents=True)
    payload = {
        "model": result.model_name,
        "bestScore": result.best_score,
        "bestRoute": result.best_route,
        "stopReason": result.stop_reason,
        "rounds": [asdict(item) for item in result.rounds],
    }
    artifact = run_dir / "run.json"
    artifact.write_text(json.dumps(payload, indent=2) + "\n")
    return artifact


def run_dry(output_root: Path, *, rounds: int = 8, stagnation: int = 3):
    puzzle = load_puzzle()
    model = ScriptedModel(DRY_RESPONSES[:rounds])
    result = run_hillclimber(
        puzzle,
        BASELINE_ROUTE,
        model,
        max_rounds=min(rounds, len(DRY_RESPONSES)),
        stagnation_limit=stagnation,
    )
    return result, _write_artifact(result, output_root)


def run_live(output_root: Path, *, rounds: int = 8, stagnation: int = 3):
    if rounds < 1 or rounds > 8:
        raise ValueError("live runs require between 1 and 8 rounds")
    puzzle = load_puzzle()
    model = HermesModel(model=LIVE_MODEL, provider=LIVE_PROVIDER)
    result = run_hillclimber(
        puzzle,
        BASELINE_ROUTE,
        model,
        max_rounds=rounds,
        stagnation_limit=stagnation,
    )
    return result, _write_artifact(result, output_root)


def print_progress(result: RunResult) -> None:
    baseline = score_route(load_puzzle(), BASELINE_ROUTE)
    print(
        f"Round 0  score={baseline.score}  treasures={baseline.treasures_collected}  "
        f"steps={baseline.steps}  BASELINE"
    )
    for item in result.rounds:
        score = "invalid" if item.score is None else str(item.score)
        print(f"Round {item.round}  score={score}  {item.status.upper()}")
    print(f"Final score={result.best_score}  stop={result.stop_reason}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hermes-hillclimber")
    sub = parser.add_subparsers(dest="command", required=True)
    score_parser = sub.add_parser("score")
    score_parser.add_argument("route", type=Path)
    run_parser = sub.add_parser("run")
    mode = run_parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--live", action="store_true")
    run_parser.add_argument("--rounds", type=int, default=8)
    run_parser.add_argument("--stagnation", type=int, default=3)

    args = parser.parse_args(argv)
    puzzle = load_puzzle()
    if args.command == "score":
        route = json.loads(args.route.read_text())
        print(render_result(puzzle, score_route(puzzle, route)))
        return 0
    if args.live:
        result, artifact = run_live(
            ROOT / "runs", rounds=args.rounds, stagnation=args.stagnation
        )
    else:
        result, artifact = run_dry(
            ROOT / "runs", rounds=args.rounds, stagnation=args.stagnation
        )
    print_progress(result)
    print(f"Artifact: {artifact}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
