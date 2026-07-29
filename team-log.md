# Team Forge ↔ Team Compass audit log — Experiment 02

**Audit target:** Forge commit `7c043392bfcef1c7e553ffb42da97ad21ba44e87` against fixed point `e198874` and frozen `experiment-02-preregistration.md`  
**Auditor:** Team Compass  
**Decision:** **REJECT — live calls are not scientifically authorized.**  
**Safety:** No live model calls were made. Solver routes were neither printed nor used to alter prompts/maps; only sealed-manifest metadata and commitments were checked programmatically.

## Forge claims quoted for audit

> “The frozen harness is separate from the original demo. It deliberately exposes no live-run command.” — `README.md:34-36`

> “Solver routes are stored only in the ignored, mode-0600 `experiment-02/private/experiment-02-solver-manifest.json`; the public manifest contains route commitments (SHA-256) only.” — `README.md:45-48`

> “Run one stateless A/B/C block. A=1 call; B/C=4; failures consume calls.” — `hillclimber/experiment02.py:162-163`

> “public manifest and run ledgers contain hashes, never solver routes.” — `hillclimber/experiment02.py:3-4`

## Compass questions, evidence, and findings

### Spec findings (frozen preregistration)

#### S1 — BLOCKER: frozen execution schedule violates the specified counterbalancing constraint

**Question:** Does the frozen 30-block schedule implement preregistration line 39’s successive triples/rotations rather than merely giving each map an eventual rotation?

**Evidence:** Preregistration `experiment-02-preregistration.md:37-39` requires seeded randomization subject to rotations `ABC`, `BCA`, `CAB` “within each successive set of three maps.” Public manifest blocks 1–3 are `A/A/A` (`experiment-02/experiment-02-manifest.json:78-93`). Independent triple extraction returned:

```text
01-03 AAA
04-06 BBC
07-09 BCC
10-12 AAC
13-15 ACC
16-18 BBB
19-21 BAC
22-24 BAB
25-27 CCB
28-30 ACA
```

Implementation first assigns a per-map rotation, then independently shuffles all ten maps in each condition wave (`hillclimber/experiment02.py:127-136`). The test only checks that each map eventually receives A/B/C and that its occurrences are separated (`tests/test_experiment02.py:20-25`); despite its name, it never asserts the required successive-triple rotation property.

**Finding:** Confirmed protocol deviation. Under the explicit abort rule for “prompt/schedule deviation” (`experiment-02-preregistration.md:49-53`), live execution must not begin.

**Required fix:** Do not silently replace the already-frozen schedule. Record the deviation and regenerate/freeze a schedule using the preregistered seed with an executable, independently tested invariant for each successive three-map set. If correcting after freeze, classify the corrected study appropriately (new preregistration/version or exploratory), and commit the new schedule before any call.

#### S2 — BLOCKER: no protocol-level live orchestrator or preflight/abort enforcement exists

**Question:** Can this harness safely execute the frozen schedule while enforcing model/provider, hashes, 90/global and 4/block call caps, outage pause, spend cap, and immutable incremental raw capture?

**Evidence:** The Experiment 02 CLI exposes only `prepare` and scripted `dry-run` (`hillclimber/experiment02_cli.py:8-22`), consistent with Forge’s no-live-route claim. `run_condition` accepts an arbitrary `model_factory`, has no model/provider identity check, manifest/map/prereg hash preflight, global 90-call guard, cumulative spend guard, two-consecutive-transport-failure pause, or schedule cursor (`hillclimber/experiment02.py:162-181`). It returns records only after a whole block; persistence occurs separately (`hillclimber/experiment02.py:184-186`). Preregistration requires these guards/abort semantics at `experiment-02-preregistration.md:15`, `:35`, and `:49-53`.

**Finding:** “No live route” is safe now, but means live calls cannot be scientifically authorized by this artifact. Calling `run_condition` ad hoc would bypass essential frozen controls.

**Required fix:** Add and behaviorally test a dedicated live orchestrator that validates all commitments before call 1 and before each resumed block, pins/verifies the exact adapter identity/config, enforces schedule and global/per-condition budgets, records a pre-run currency cap, pauses after two consecutive transport failures, never replaces calls, and durably append/commits every attempted call before proceeding. Keep it disabled until re-audit.

#### S3 — BLOCKER: frozen metadata is incomplete

**Evidence:** Preregistration `:13-15` requires git commit, model/provider, Hermes version/config, prompts, generation seed, and hashes before calls. The public manifest records protocol, model, map seed, preregistration hash, generation log, map commitments, and schedule (`experiment-02/experiment-02-manifest.json:1-15,78-230`), but not the git commit, Hermes version/config, adapter default/sampling settings, substantive base/feedback prompt text or commitments, schedule seed, creation timestamp, or separately recorded spend cap. `BASE_PROMPT` is only source code (`hillclimber/experiment02.py:23-27`), and the feedback wording is only code (`:158-159`).

**Required fix:** Add a committed, sealed-before-call preflight manifest containing all required metadata and SHA-256 commitments, including exact prompt bytes, adapter invocation/config, schedule seed/algorithm/version, repository commit, Hermes version, and currency cap. Verify them at runtime.

#### S4 — MAJOR: analysis accepts malformed budgets and omits preregistered outputs

**Evidence:** `analyze` checks only ten maps and presence of A/B/C (`hillclimber/experiment02_analysis.py:9-14`), then takes maxima over however many records exist (`:16-19`). It therefore accepts missing retry calls, duplicate/extra calls, wrong call indices, and records after an abort, contrary to exact allocation and exclusion rules (`experiment-02-preregistration.md:35,43,51-53`). Output includes primary score summaries and condition total tokens/cost (`experiment02_analysis.py:20-30`) but omits most frozen secondary endpoints, input/cached/output/reasoning token totals, C-minus-B per 1,000 tokens, success/validity/collision/improvement/first-success metrics, optimality gaps after unsealing, and C-A/B-A contrasts required by preregistration `:43-47,57-59`.

**Required fix:** Validate the exact manifest schedule and exact call-index sets (A={1}, B/C={1..4}), reject/flag extras and protocol aborts for confirmatory inference, distinguish attempted transport calls from parse validity, and implement every frozen primary/secondary/accounting output.

#### S5 — MAJOR: solver-answer sealing is access control, not demonstrated temporal sealing

**Evidence:** Independent metadata-only inspection found mode `0600`, `sealed=true`, 10 entries, and all 10 public route commitments match sealed routes. However, the sealed file is ignored (`.gitignore:5`; verified by `git check-ignore`) and its only top-level keys are `entries` and `sealed`; there is no creation timestamp, repository commit, manifest hash, signature, or external/committed ciphertext commitment proving it remained unchanged until unsealing. Preregistration requires answers remain sealed until raw outputs are immutable (`:25,39`).

**Required fix:** Commit a pre-call cryptographic commitment to the complete sealed artifact (or encrypted artifact) plus creation metadata and chain it to commit/public manifest. Use an independent custody/unsealing procedure; do not expose plaintext to the live-run process.

### Standards/code-quality findings

#### Q1 — MAJOR: tests pass but are behaviorally insufficient

**Evidence:** `python3 -m unittest discover -s tests -v` returned **18 tests, OK**. Experiment 02 has only five compact tests (`tests/test_experiment02.py:15-44`). Missing adversarial coverage includes: literal successive-triple schedule invariant; manifest/hash/model preflight; global cap/spend/outage/resume; empty/timeout/provider failures consuming indices; malformed schema varieties and >250 moves in this harness; token fields on invalid responses; no cross-condition prompt leakage; exact feedback incumbent after improvement/non-improvement; durable partial writes; extra/missing call rejection; bootstrap seed/index fixtures; sign-flip ties/negative/mixed vectors; and all required report fields.

**Required fix:** Add black-box tests for every protocol invariant and failure transition, not only helper happy paths. A test named “rotated” must assert the literal frozen rotation constraint.

#### Q2 — MAJOR: ledger immutability is weak and the rehearsal artifact is not versioned

**Evidence:** `write_immutable_ledger` refuses an existing path and chmods it `0444` (`hillclimber/experiment02.py:184-186`); test coverage only checks same-path overwrite refusal (`tests/test_experiment02.py:33-36`). The dry-run ledger is ignored by `runs/` (`.gitignore:4`) and absent from commit `7c043392`. Independent check found 90 records and mode `0444`, but owner permissions can be restored, the file can be replaced by renaming in its writable directory, and records are written only after the complete run.

**Required fix:** Use append-only/durable per-call writes with hash chaining and fsync, finalize with a committed content hash/signature/WORM or independently controlled store, and version the dry-run evidence (or at minimum its hash and machine-verifiable summary). Test interruption/restart and tampering detection.

#### Q3 — MAJOR: broad exception handling conflates harness bugs with allocated technical failures

**Evidence:** `run_condition` catches every `Exception` around model construction, completion, JSON parse, and judge execution and assigns -271 (`hillclimber/experiment02.py:170-177`). Thus programming errors or judge regressions can silently become model failures rather than triggering the preregistered judge/test abort (`experiment-02-preregistration.md:51`).

**Required fix:** Catch and classify only expected transport/CLI/timeout/JSON/schema exceptions. Let invariant/judge/programming exceptions abort the protocol, while still atomically logging an attempted call where appropriate.

#### Q4 — MAJOR: prompt/schema isolation is only partially established

**Evidence:** Fresh factory creation per retry is present (`hillclimber/experiment02.py:172`); B always receives the base prompt and C receives incumbent route/score/feedback only after a valid incumbent (`:168-179`). The test confirms B lacks `Current route:` and C’s second prompt has feedback (`tests/test_experiment02.py:26-32`). But an arbitrary factory can share state, there is no test that A/B/C base prompts are byte-identical for the same map, no adapter-level assertion of personal-rules ignored/tool-free/fresh one-turn behavior in this harness, and no prompt commitment/preflight.

**Required fix:** Integrate the pinned adapter behind a narrow fresh-call interface; assert exact prompt hashes, no prior material in A/B, no information across conditions/maps, no tools/personal rules, and C’s exact incumbent semantics across invalid and non-improving calls.

#### Q5 — MINOR: bootstrap/sign-flip core is plausible, but only a trivial fixture is tested

**Evidence:** Exact sign flips enumerate all `2^10` assignments and use `>= observed` (`hillclimber/experiment02_analysis.py:20-22`), matching preregistration `:55-57`. Bootstrap uses SHA-256-derived UTF-8 seed and 100,000 resamples (`:23-24`), selecting zero-based indices 2499/97499 (`:30`), a defensible nearest-rank convention. The sole test uses ten identical +1 differences and checks only mean/p (`tests/test_experiment02.py:37-44`); it does not independently pin resample indices/CI or mixed/tied sign-flip behavior.

**Required fix:** Add independent golden fixtures for mixed signs, ties, all-zero and negative observations, exact `>=` handling, deterministic first bootstrap index vectors, and explicitly document/freeze the percentile convention.

## Independently reproduced checks (no live calls)

```text
$ python3 -m unittest discover -s tests -v
Ran 18 tests in 0.737s
OK

prereg_hash_match True
map_hash_matches 10 / 10
route_hash_matches 10 / 10
sealed_mode 0o600 sealed_flag True entries 10
ledger_mode 0o444 records 90
calls_by_condition Counter({'B': 40, 'C': 40, 'A': 10})
calls_per_block_ok True
adjacent_same_map []
blocks_1_3 AAA
```

Map layouts and solver routes are intentionally omitted from this log.

## Decision and authorization gate

**REJECT. LIVE CALLS ARE NOT SCIENTIFICALLY AUTHORIZED.** The confirmed schedule deviation alone activates the frozen abort rule. Independently, there is no live orchestrator capable of enforcing model/hash/spend/outage/global-budget controls, required freeze metadata is absent, and durable immutable per-call capture is not established.

Re-audit is required after S1–S5 and Q1–Q4 are fixed. Existing materials must not be silently rewritten as though still preregistered; preserve this audit and explicitly version/log any protocol correction before any model call.
