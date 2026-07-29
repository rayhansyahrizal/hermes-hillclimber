# Experiment 02 preregistration: does judge feedback help?

**Status:** preregistered before map generation and before any Experiment 02 model calls. This document freezes the confirmatory design; deviations will be logged and treated as exploratory. The experiment is deliberately a small paired pilot, not a benchmark.

## Question and hypotheses

Using only `openai-codex/gpt-5.6-sol`, does a bounded retry loop with the existing deterministic score/failure feedback produce better maze routes than equally many blind retries?

- **Primary estimand:** across maps, the mean paired difference `best_score(C) - best_score(B)` after four calls per condition.
- **Experimental/inference unit:** one map (10 paired maps). Calls and retries are repeated measurements, not independent units.
- **Primary hypothesis:** C has a positive paired mean difference from B. A (one shot) is a reference for the value of additional calls, not the primary causal contrast.

## Frozen materials and maps

Before model calls, record the git commit, model/provider string, Hermes version/config, prompts, generation seed, and SHA-256 hashes of this file and all 10 maps. Do not alter the judge, adapter, score rules, move cap, model, or prompts after this freeze.

Generate exactly 10 previously unused maps locally with UTF-8 seed string **`hermes-hillclimber-exp02-maps-v1`**. No human may inspect, edit, or selectively retain a generated map based on its layout or solution. An offline deterministic solver may reject/regenerate maps only by these mechanical criteria:

- rectangular, 15x15; one `S`, one `E`, exactly 6 treasures; all relevant cells mutually reachable;
- unique optimal all-treasure-to-exit route length from 45 through 100 moves (thus under the 250-move cap);
- at least 8 decision junctions (reachable non-wall cells with at least 3 traversable neighbors) and at least 2 treasure-order choices whose shortest feasible completion lengths differ;
- no direct `S`-to-`E` shortest path may pass every treasure;
- deterministic solver confirms the optimum and map validity.

Generation/rejection counts and criterion failures are logged. Solver routes and optimum scores remain sealed until every model response is committed. If the existing repository cannot generate and verify this exact set without implementation changes, stop and label the study **not run** rather than relaxing criteria or hand-authoring maps.

## Conditions and budgets

Every call is a fresh one-turn, tool-free Hermes invocation with personal rules ignored, temperature/sampling settings left at the single frozen adapter default, and the same map/rules/JSON schema. Maximum response route remains 250 moves.

- **A — one shot:** one base-prompt call; score that response.
- **B — blind retries:** four independent base-prompt calls. A retry receives no prior response, score, judge result, acceptance status, or failure information. Retain the deterministically highest-scoring valid route.
- **C — feedback retries:** four calls through the existing accept-only-improvements loop. Call 1 uses the same substantive base task; calls 2–4 receive the current incumbent route, its deterministic score, and existing `RouteResult.feedback`, and request a higher-scoring replacement. Retain the incumbent.

Use `max_rounds=4` and set `stagnation_limit=4`, so B and C are allocated exactly four attempted calls unless a technical failure invokes the rules below. Do not stop when solved or apparently optimal. A intentionally costs one call; fair causal comparison is C versus B (4 versus 4). Total planned maximum: **90 calls** (10 A, 40 B, 40 C). No reruns, prompt repair, or extra calls based on quality.

## Randomization and masking

Assign map IDs from hashes, not visual order. Before viewing maps or outcomes, use the recorded seed to randomize the 30 map-condition blocks subject to: (i) each map appears once in A/B/C, (ii) no map's conditions are adjacent, and (iii) within each successive set of three maps, condition-order rotations ABC, BCA, and CAB occur once (the last map uses the next rotation). Execute that frozen schedule. Each call is stateless; do not copy information across conditions. Keep solver answers and optimum metrics masked until all 90 attempted calls and raw outputs are immutable.

## Deterministic outcomes and accounting

Score every parseable route only with `score_route`. Invalid JSON/schema is assigned an analysis score of **-271** (worse than the minimum valid 250-move collision score of -270), and remains a failed call. For each map/condition record raw output, parsed route, score, steps, treasures collected, exit reached, collision, validity, call index, acceptance, prompt hash, timestamps, and stop/error status.

Primary endpoint is best analysis score among allocated calls. Deterministic secondary endpoints, reported descriptively: all-treasures-and-exit success (judge bonus condition), validity, collision, best-score gain from call 1, number of strict within-condition improvements, call of first success, and optimality gap `solver_optimum - best_score` after unsealing.

For each invocation record API-reported input, cached-input, output, reasoning, and total tokens plus billed cost when available. If unavailable, record `NA` (never estimate silently). Report calls attempted/completed and tokens/cost by condition; also report C-minus-B score per 1,000 total tokens as exploratory because feedback naturally adds input tokens.

## Technical failures and stopping

The spending guard is 90 attempted calls and 4 per retry condition; reaching either stops further calls. Abort the entire experiment before additional calls on wrong model/provider, map/hash mismatch, judge/test failure, answer leakage, prompt/schedule deviation, or cumulative spend above a separately recorded pre-run currency cap. Preserve partial data but perform no confirmatory test.

Timeout, CLI/provider error, or empty transport response consumes its call and receives -271. A broad provider outage (two consecutive transport failures) pauses execution; resume the frozen next block once, without replacing failed calls. Any accidental extra call is logged and excluded. There is no outcome-based, success-based, futility, or significance stopping.

## Exact analysis

Create one row per map with A, B, and C best scores. The confirmatory estimate is the arithmetic mean of the 10 `C-B` differences, accompanied by all 10 differences, median difference, and the count positive/tied/negative. Test against zero with an **exact paired sign-flip permutation test** over all `2^10` sign assignments, using the mean difference as statistic; report the one-sided p-value `P(T >= observed T)`. Also report a two-sided 95% paired bootstrap percentile interval from 100,000 map resamples using UTF-8 seed string **`hermes-hillclimber-exp02-bootstrap-v1`**. With only 10 maps, emphasize effect sizes and raw pairs; p-values are not a benchmark claim.

Secondary, non-confirmatory contrasts are C-A and B-A on best score and success, plus C-B differences in success, call-1-to-best gain, validity, tokens, and cost. No multiplicity-adjusted claims and no post-hoc map exclusions.

## Interpretation rule

Evidence **supports feedback-driven improvement in this pilot** only if (1) mean `C-B > 0`, (2) more maps favor C than B, and (3) the exact one-sided p-value is below 0.05. The magnitude, interval, token premium, and whether C improves after call 1 must still be shown. This supports the existing feedback-loop package (incumbent selection plus deterministic score/failure feedback), not feedback wording alone or general model learning.

A C advantage over A but not B supports retries/extra compute, **not** feedback. B and C both beating A with C≈B supports retry diversity. C≈B, C<B, improvements confined to call 1, pervasive invalid/transport failures, a protocol abort, or effects driven only by post-hoc exclusions do **not** support feedback-driven improvement. Results apply only to this model, prompt, judge, and mechanically defined map family.
