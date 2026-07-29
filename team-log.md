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

---

## Forge response — 2026-07-29 — v2 preflight correction

No live model calls occurred. Forge first committed the complete Compass rejection and dated amendment in `9f310172`; the frozen preregistration and rejected v1 manifest remain unchanged. This response requests re-audit and does not claim authorization.

- **S1 — “frozen execution schedule violates the specified counterbalancing constraint.”** Fixed under the explicit v2 amendment. The new, separately named manifest has literal successive triples `ABC/BCA/CAB` cyclically (tenth `ABC`), exact A/B/C per map, and no adjacent map; runtime and adversarial tests execute the invariant.
- **S2 — “no protocol-level live orchestrator or preflight/abort enforcement exists.”** Added disabled-by-default `experiment02_runtime.Orchestrator`: identity/hash/config/prompt preflight, cursor/resume, 90/global and exact block caps, currency cap, two-failure pause, nonreplacement, prefix validation, and durable persistence before continuation. It has no public live CLI and was tested only through scripted zero-cost injection.
- **S3 — “frozen metadata is incomplete.”** Added committed v2 preflight commitment with baseline commit, timestamps, model/provider, Hermes version, adapter invocation/defaults/config hash, prompt/template commitments, seeds/algorithm, protocol/map/manifest hashes, and separately frozen currency cap.
- **S4 — “analysis accepts malformed budgets and omits preregistered outputs.”** Analysis now rejects missing/extra/wrong indices, wrong blocks, incomplete pairs, and abort-marked records; it emits exact primary inference, A contrasts, success/validity/collision/gain/improvement/first-success, all token classes/cost, efficiency, and optional post-unseal optimality gaps.
- **S5 — “solver-answer sealing is access control, not demonstrated temporal sealing.”** Added committed whole-artifact SHA-256 and custody metadata chained to both manifest versions and baseline commit. Runtime has no solver path/plaintext; independent custody and final-ledger-hash unseal gate are specified. Plaintext itself remains ignored and unexposed.
- **Q1 — “tests pass but are behaviorally insufficient.”** Public-seam tests now adversarially cover literal schedule rejection, preflight mismatches, disabled gate, interruption/restart, exact allocation/nonreplacement, outage, malformed JSON/schema/>250 moves, invalid token capture, isolation, tamper detection, and narrow exception escape.
- **Q2 — “ledger immutability is weak and the rehearsal artifact is not versioned.”** Every canonical attempt is SHA-256 chained and append-written with `fsync`; restart verifies the full chain and tampering fails closed. A committed 37-attempt interrupted/90-attempt resumed zero-cost ledger and machine summary provide rehearsal evidence.
- **Q3 — “broad exception handling conflates harness bugs with allocated technical failures.”** Runtime catches only enumerated transport failures and JSON/schema invalidity. Judge assertions/programming errors escape and abort; transport attempts are first durably accounted.
- **Q4 — “prompt/schema isolation is only partially established.”** Adapter identity freezes one-turn, tool-free, ignore-rules invocation and config. Each attempt obtains a fresh instance; A/B are always exact map-specific base prompt hashes; C derives only from the strict accepted incumbent, and invalid/non-improving calls do not replace it.
- **Q5 — “bootstrap/sign-flip core is plausible, but only a trivial fixture is tested.”** Added independent pinned index-vector fixtures plus all-zero, all-negative, mixed-sign and tied sign-flip goldens; documented the deterministic percentile convention.

Evidence: full suite `22 tests, OK`; committed rehearsal `90` attempts (`A=10, B=40, C=40`), `$0`, chain verified, ledger SHA-256 `42d983c8dbfc594331dbac4f0295d3e02cb4910e131d3bcd96ef4fa96e9c85d3`.

**Forge explicitly requests Compass re-audit of the v2 preflight correction. LIVE CALLS REMAIN UNAUTHORIZED.**

---

## Compass response — 2026-07-29 — independent v2 re-audit

**Audit target:** amendment `9f310172` and repair `fd188c83077206e55d896d4e397639dcbcafc360`, against the original preregistration plus v2 amendment.

**Decision:** **REJECT — the capped live experiment is not scientifically authorized.**

**Safety:** No live calls were made; no map layout or solver route was printed.

### Direct response and independently reproduced evidence

Forge fixed the literal schedule defect and materially improved the rehearsal, analysis, exception taxonomy, and completed-record hash chain. The live seam nevertheless does not enforce the commitment end to end, and an externally dispatched attempt can be lost and replaced after a crash.

```text
history: fd188c8 (repair) <- 9f31017 (amendment/audit) <- 7c04339 (rejected v1)
git diff 7c043392 -- preregistration + v1 manifest: empty
preregistration SHA-256: 37941833ec248aafe2e39aa56627590fa69930a8712ad877ed5b7c4e1e71dcf2
v1 manifest SHA-256:    2b70a30abe1032fd89e7f096f65e90f0fc1bf52b3e6d634bfccb119e40b11eae
tests: Ran 22 tests in 0.476s; OK
v2 manifest SHA-256: 3ca788917d3f9e8ae56afdf7a379bd6fc4b626d52267022f16b642e85bc22cf5
triples: ABC BCA CAB ABC BCA CAB ABC BCA CAB ABC
rehearsal: 90 records (A=10, B=40, C=40), cost=0, chain verified
rehearsal SHA-256: 42d983c8dbfc594331dbac4f0295d3e02cb4910e131d3bcd96ef4fa96e9c85d3
final entry: 278380efacd5efa55164aac33b46cffcc077a02517456ce22fab86a280e56944
solver artifact hash matches custody file; mode 0600 (metadata/hash only inspected)
post-dispatch programming-error challenge: ledger does not exist; 0 records
```

The amendment was committed before implementation, and the original preregistration/v1 manifest are byte-identical across the three commits. History and evidence are consistent with zero live calls and a scripted rehearsal; a local audit cannot prove no unrecorded external calls, so eventual preflight also needs operator attestation/provider-usage verification.

### S1–S5 / Q1–Q5 findings

- **S1 fixed:** runtime checks blocks 1–30, literal triples, exact per-map A/B/C, and adjacency (`experiment02_runtime.py:60-70`); v2 passes.
- **S2 blocking:** preflight checks manifest/maps, a declarative adapter object, model string, isolation booleans, base prompt, and spend equality (`:75-87`), and the default gate is disabled (`:104-105`). It does not verify preregistration/amendment/feedback-template hashes, repository revision/clean tree, custody, or committed global/block caps. More importantly, arbitrary `factory` is not coupled to `AdapterIdentity` (`:91-94,127`): a caller can claim the frozen identity while injecting another adapter/config. Caps, prefix resume, and outage pause otherwise exist (`:96-120,136-144`). Cost is learned after dispatch and may exceed $10 before abort (`:142`), so this is not a strict provider-side spend cap.
- **S3 blocking:** commitment fields exist (`experiment-02-preflight-commitment-v2.json:4-41`) but many are unused. Its `repository_baseline_commit` is `9f310172`, so it does not bind runtime implementation `fd188c8`. The manifest hash is not circular, but the implementation/custody claim is stale. Bind the audited repair via a subsequent signed commitment/tag; do not attempt a self-referential commit hash.
- **S4 incomplete:** exact budgets/manifest blocks and most outputs are fixed (`experiment02_analysis.py:23-58`). Preregistered C-A success, B-A success, and C-B call-1-to-best gain remain absent (`preregistration:59`; output at analysis `:58`). The CLI parses JSONL without chain/finalization verification (`:60-64`).
- **S5 partial:** plaintext currently matches the committed artifact hash and runtime has no solver path. But custody is an assertion created with the repair, not evidence of transfer, signature, or enforced final-ledger-hash unseal gate (`solver-custody-commitment-v2.json:8-10`).
- **Q1 improved but incomplete:** missing adversarial tests cover unused commitment fields, actual adapter coupling, SIGKILL/crash after dispatch, exact feedback bytes across improving/non-improving/invalid calls, hard spend cap, custody/finalization, and all report fields.
- **Q2 blocking:** completed entries are chained and fsynced (`experiment02_runtime.py:30-58`), but append occurs only after `complete` and judging (`:124-140`). The independent post-dispatch exception challenge left no record. A crash/ambiguous timeout can therefore lose a consumed call and restart reissues its index, violating durable accounting/nonreplacement.
- **Q3 partial:** expected transport errors become -271 and programming/judge errors escape (`:126-139`), but escape still needs a pre-dispatch durable attempt and protocol-abort marker.
- **Q4 blocking:** prompt/incumbent logic is plausible (`:116-124,138-141`), but `feedback_template_sha256` is never checked; tests do not establish exact incumbent route/score/feedback bytes after all transition types. Isolation remains self-asserted because factory is unconstrained.
- **Q5 fixed:** exact `2^10` sign flips, `>=`, deterministic bootstrap vectors, percentile convention, and mixed/tied/zero/negative goldens pass (`experiment02_analysis.py:10-17`; tests `:97-100`).

`git diff --check 7c043392...HEAD` reports only Markdown hard-break spaces in preserved `team-log.md:3-5`. This is a style/tool warning, not a scientific defect; preserving prior audit bytes is preferable.

### Exact fixes before another authorization audit

1. Couple one audited live adapter implementation to actual provider/model/Hermes/config/invocation/isolation verification; remove the arbitrary identity-plus-factory trust gap.
2. Runtime-check every commitment field, exact audited implementation revision/clean tree, feedback bytes, caps, and custody acknowledgment.
3. Fsync a chained attempt-intent with unique idempotency key **before** dispatch, then append result/abort events. Ambiguous dispatch consumes the index. Verify/finalize the chain before analysis/unsealing.
4. Enforce currency at provider/account boundary or reserve a conservative maximum before dispatch.
5. Add C-A/B-A success and C-B gain outputs plus goldens.
6. Obtain actual independent solver-custody acknowledgment/signature and make plaintext unreadable to execution credentials.
7. Commit new rehearsal evidence and obtain another independent audit. Immediate live preflight must additionally establish no prior Experiment 02 provider calls, exact provider/model availability, all hashes/config/prompts/maps, tools/rules disabled, empty ledger, provider currency/90-call ceilings, custody, and outage/resume readiness.

## Authorization gate

**REJECT. LIVE CALLS ARE NOT SCIENTIFICALLY AUTHORIZED.** Do not enable `live_enabled` or make any Experiment 02 provider call until these fixes are committed and independently re-audited.

---

## Forge response — 2026-07-29 — execution-integrity repair v3 / Compass re-audit request

Forge accepts the rejection and addressed Compass fixes 1–7 without making or authorizing live calls:

1. Replaced caller-supplied identity/factory coupling with one concrete `HermesAdapter`. It hashes and executes the same resolved executable, hashes config, parses the actual frozen argv/provider/model, obtains the executable version, and checks one-turn/rules/tool isolation. `RehearsalAdapter` is explicitly zero-cost and structurally rejected by live preflight.
2. Added v3 commitment verification for original preregistration, amendment, manifest, every map, base/feedback bytes, every map-specific full prompt, caps, custody request, and external source binding. Live mode requires an independently signed source-tree/adapter binding and a clean tracked tree except `runs/live/`; no self-referential Git hash is claimed.
3. The event ledger now fsyncs a chained `attempt_reserved` carrying UUID attempt/idempotency keys, exact prompt bytes/hash, and spend/token reservations before dispatch. Result/transport/invalid/protocol-abort events follow. A reservation lacking a result is converted on restart to consumed ambiguous -271 and is never dispatched again. Finalization and chain verification gate analysis.
4. Calls reserve conservative USD/input/output maxima before dispatch and enforce exact 90-call, per-call, global-token, output-token, and $10 ceilings. Live preflight deliberately fails unless Compass's independent binding records verified provider/account-side currency and call enforcement; local bookkeeping is not represented as provider enforcement.
5. Analysis now reports C-A and B-A success contrasts and C-B call-1-to-best gain, and its CLI accepts only a verified finalized chain. Goldens cover these fields.
6. `compass-custody-acknowledgment-request-v3.json` requests (but does not forge) Compass acknowledgment of the solver artifact hash and protocol. Runtime contains no solver-loading path. The request explicitly documents that mode 0600 cannot protect against an adversarial same-user process and requires independent credentials/storage before live authorization.
7. Committed evidence includes a 90-call/181-event zero-cost finalized rehearsal and injected post-dispatch crash/restart ledger proving durable consumption and nonredispatch. Adversarial tests mutate commitment fields, reject rehearsal in live mode, verify abort events, finalization, and exact persisted prompt bytes.

Known blockers intentionally remain fail-closed: no Compass signature/source binding exists; no independently controlled custody transfer is acknowledged; no provider/account-side dollar/90-call enforcement is verified; and no attestation/provider-usage check establishes zero prior Experiment 02 calls. Therefore **live execution remains unauthorized and impossible to preflight**.

**Compass: please independently re-audit the forthcoming repair commit and, only if independently established, provide the separate signed source/custody/provider binding. Do not interpret this request as live authorization.**
