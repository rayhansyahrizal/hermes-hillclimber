# Hermes Hillclimber

[![tests](https://github.com/rayhansyahrizal/hermes-hillclimber/actions/workflows/tests.yml/badge.svg)](https://github.com/rayhansyahrizal/hermes-hillclimber/actions/workflows/tests.yml)

An LLM is dropped into a text maze and asked for a route that collects treasure and reaches the exit.
A deterministic local judge scores every answer and keeps only strictly better ones. The model can
propose; it cannot touch the map, the rules or the judge.

It started as a toy. It became a small lab for one question that matters well beyond mazes:
**when an AI agent retries, does telling it how it did actually help, or would blind retries do just as
well?**

## The game

```
+30  per unique treasure
 -1  per step
-20  and stop, on hitting a wall
+50  for reaching the exit after collecting every treasure
```

The model returns only `{ "moves": [...] }`. Everything else is the judge's job.

## Experiment 01: first live run

The hand-made baseline route scored **24**. The model found a **148**-point route on its first call:
all four treasures, exit reached in 22 steps. Its next three answers were identical, so the judge
rejected them as non-improvements and the stagnation guard stopped the run after four calls.

Interesting result, weak evidence: one map, one run. Hence Experiment 02.

## Experiment 02: does judge feedback help? (preregistered)

Written down and frozen **before** any map was generated or any model was called
([`experiment-02-preregistration.md`](experiment-02-preregistration.md)):

- **10 new 15x15 maps**, 6 treasures each, generated from a fixed seed, each with a unique optimal route
  confirmed by a solver. No human looks at a map before the run.
- **Three conditions per map:** A = one shot; B = four blind retries; C = four retries that see the
  current best route, its score and the judge's failure reason.
- **Primary question:** across maps, is C's best score higher than B's? A only shows what extra calls are worth.
- **Sealed answers:** optimal routes are stored privately; the public manifest holds SHA-256 commitments only.

### Where it stands

**Designed, audited and rehearsed. Not yet run live.** Zero live model calls have been made for Experiment 02.

The harness went through an adversarial review between two roles, a builder ("Forge") and an auditor
("Compass"). The first version was **rejected**, among other findings because its run schedule did not
match the frozen counterbalancing rule. The rejection was kept, the protocol was amended
([v2](experiment-02-protocol-amendment-v2-2026-07-29.md)) before anything was fixed, and the final
preflight was accepted. Why this gate exists and what it caught:
[decision 0001](docs/decisions/0001-an-independent-audit-gates-every-live-experiment.md). The full
exchange, unedited: [`team-log.md`](team-log.md).

Zero-cost rehearsals with a scripted model, in [`experiment-02/evidence/`](experiment-02/evidence/):

| Rehearsal | Checked |
|---|---|
| Full run | 181 hash-chained ledger events, 90 call reservations, finalized |
| Crash mid-call | the crashed call is not silently re-sent |
| Provider outage | the pause is written to disk before resuming; used calls are not replaced |

## Run it

Requires Python 3.10+. No dependencies.

```bash
python3 -m unittest discover -s tests -v              # 26 tests
python3 -m hillclimber.cli score baseline.json        # score the baseline route
python3 -m hillclimber.cli run --dry-run --rounds 8   # full loop, no model calls
```

A live run needs a configured Hermes Agent CLI (`hermes`) on your PATH:

```bash
python3 -m hillclimber.cli run --live --rounds 8 --stagnation 3
```

Live runs are capped at eight one-turn calls, and each writes an auditable record to
`runs/<timestamp>/run.json`.

Experiment 02 materials and a zero-cost rehearsal:

```bash
python3 -m hillclimber.experiment02_cli prepare --root experiment-02
python3 -m hillclimber.experiment02_cli dry-run experiment-02/experiment-02-manifest.json \
  --output runs/experiment-02-dry-run.jsonl
```

The live Experiment 02 entry point, `python3 -m hillclimber.experiment02_live_cli --live`, fails closed:
it refuses to run without an explicit `--live`, a complete operator attestation, a signed source binding
and an empty ledger. The audited source tree is tagged `exp02-audited-source`; a live run must start
from that tag, because any later commit changes the hash the preflight checks.

## Layout

| Path | What it holds |
|---|---|
| `hillclimber/judge.py` | Scoring rules, the only source of truth for a score |
| `hillclimber/runner.py` | Accept-only-improvements loop with a stagnation guard |
| `hillclimber/model.py` | Hermes adapter: one turn, no tools, fixed model |
| `hillclimber/experiment02*.py` | Preregistered harness, runtime, analysis |
| `maps/`, `experiment-02/maps/` | Maze files |
| `experiment-02/evidence/` | Rehearsal ledgers and audit decisions |
| `docs/decisions/` | Decision records |

## License

[MIT](LICENSE).
