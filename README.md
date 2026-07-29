# Hermes Hillclimber

A tiny experiment where one Hermes model repeatedly tries to improve a route through a treasure maze. A deterministic local judge accepts only strictly better solutions.

## Rules

- `+30` per unique treasure
- `-1` per movement step
- `-20` and stop on collision
- `+50` for reaching the exit after collecting every treasure

The model returns only `{ "moves": [...] }`. It cannot modify the map or judge.

## Run locally for free

```bash
python3 -m unittest discover -s tests -v
python3 -m hillclimber.cli score baseline.json
python3 -m hillclimber.cli run --dry-run --rounds 8
```

## Run with the configured Hermes model

```bash
python3 -m hillclimber.cli run --live --rounds 8 --stagnation 3
```

Live runs are hard-capped at eight one-turn calls. The current adapter pins `openai-codex/gpt-5.6-sol`, ignores personal rules, allows only one turn per call, and stops after three consecutive non-improvements.

Each run writes an auditable JSON record under `runs/<timestamp>/run.json`.

## Experiment 02 (preregistered)

The frozen harness is separate from the original demo. It deliberately exposes no live-run command.

After Compass rejected v1, `experiment-02-protocol-amendment-v2-2026-07-29.md` was committed before any schedule correction. The rejected manifest remains at its original path; corrected preflight materials use explicit `-v2` names. `hillclimber.experiment02_runtime.Orchestrator` is a dedicated resumable protocol seam, but it fails closed unless explicitly enabled and is **not an authorization or public live command**. Only the injected scripted adapter has been exercised. See the committed hash-chained rehearsal and summary under `experiment-02/evidence/`.

The legacy CLI can still prepare materials and run a zero-cost rehearsal; it does not expose the v2 live orchestrator:

```bash
python3 -m hillclimber.experiment02_cli prepare --root experiment-02
python3 -m hillclimber.experiment02_cli dry-run experiment-02/experiment-02-manifest.json \
  --output runs/experiment-02-dry-run.jsonl
python3 -m hillclimber.experiment02_analysis <immutable-live-ledger.jsonl>
```

Solver routes are stored only in the ignored, mode-0600
`experiment-02/private/experiment-02-solver-manifest.json`; the public manifest
contains route commitments (SHA-256) only. Do not unseal it until all live raw
responses have been committed.

## First live result

The baseline scored `24`. The model found a `148`-point route on its first attempt, collecting all four treasures and reaching the exit in 22 steps. Three identical optimal attempts were rejected, then the stagnation guard stopped the run after four calls.
