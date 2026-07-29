# Experiment 02 protocol amendment v2 — 2026-07-29

**Status:** preflight correction after Compass rejection; no Experiment 02 live model calls occurred. This amendment does not overwrite or retroactively repair the frozen v1 preregistration or its rejected manifest. The original preregistration, manifest, audit, and commit `7c043392bfcef1c7e553ffb42da97ad21ba44e87` remain the audit trail. Any eventual execution under this amendment is a separately versioned corrected pilot and remains unauthorized until Compass re-audits it.

## Defect and classification

The v1 schedule generator assigned a rotation per map and then independently shuffled waves. Consequently, successive schedule triples did not literally implement the counterbalancing sentence in preregistration line 39 (the first triple was `AAA`). This is a schedule implementation defect and triggers v1's prompt/schedule-deviation abort rule. Since there were no live calls, v2 corrects preflight materials rather than excluding or modifying observations. It is not represented as the untouched original preregistration.

## Clarified executable schedule invariant

Using UTF-8 seed `hermes-hillclimber-exp02-maps-v1`, sort map IDs, then use the repository's SHA-256-seeded PRNG to construct a deterministic 30-block schedule satisfying all of the following:

1. Every map ID occurs exactly once with each condition A, B, and C.
2. No two adjacent blocks use the same map ID.
3. Partition blocks into ten consecutive triples. Their literal condition strings are, in order, `ABC`, `BCA`, `CAB`, repeated cyclically; the tenth triple uses the next rotation, `ABC`.
4. The generator must fail closed if it cannot establish these properties. Runtime preflight independently rechecks the literal properties against the committed corrected manifest.

This is the sole scientific-design clarification. Map bytes, map IDs, scoring, budgets, prompts, model target, analysis seed, and all other frozen v1 rules remain unchanged. The corrected schedule is stored in a new v2 manifest; the rejected v1 manifest is retained byte-for-byte.

## Additional preflight controls (implementation hardening, not outcome-dependent changes)

Before any future call, v2 requires a committed commitment/preflight manifest; exact prompt/config/map/protocol hashes; a disabled-by-default pinned fresh one-turn adapter; global/per-block/spend caps; resumable schedule cursor; nonreplacement; outage pause; append-only hash-chained fsync persistence per attempt; exact-ledger validation; and sealed-solver-artifact custody metadata/commitment without plaintext routes. Solver plaintext is never available to the run process. These controls may be exercised only with zero-cost scripted adapters until re-audit.

## Authorization

This amendment does **not** authorize live calls. Forge must request Compass re-audit after implementation and rehearsal evidence is committed.
