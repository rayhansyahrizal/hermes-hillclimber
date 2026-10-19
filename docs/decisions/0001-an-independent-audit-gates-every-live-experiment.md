# 0001. An independent audit gates every live experiment

Status: accepted, 2026-07-29

## Context

Experiment 02 spends a fixed budget of about 90 model calls. If the harness is wrong, those calls are
spent and the result is unusable, and a preregistered experiment cannot be quietly rerun until it looks
right. So the harness had to be right before the first call, not after.

The builder of a harness is the worst person to judge it. I split the work into two roles with separate
instructions: a builder ("Forge") that writes and fixes the harness, and an auditor ("Compass") that
only reads, reproduces and rules. Compass was not allowed to make live calls, look at the maps, or see
the sealed answers. <!-- Rayhan: confirm these were separately prompted agent sessions and say so plainly. -->

## Decision

No live call runs until the auditor issues ACCEPT against an exact, hashed source tree. A rejection is
kept in the record, not overwritten; a protocol change is written as a dated amendment before the code
that implements it.

## What the audit caught

Four rounds, all recorded verbatim in [`team-log.md`](../../team-log.md):

| Round | Verdict | Main reason |
|---|---|---|
| v1 | REJECT | The run schedule broke the preregistered counterbalancing rule; no orchestrator enforced spend, outage or model limits. |
| v2 | REJECT | Fixes incomplete; ledger and failure handling still too weak to trust. |
| v3 | REVISE | A crash during a second outage skipped the required pause; the source hash included itself, so it could never match; no live entry point existed. |
| final | ACCEPT | All three fixed and independently reproduced; 26 tests; source tree bound to SHA-256 `7dba49d1...`. |

The first finding alone would have invalidated the experiment: the schedule decides which condition
runs first on each map, and getting it wrong confounds the comparison the whole experiment exists to make.

## Consequences

- The accepted source tree is tagged `exp02-audited-source`. A live run must start from that tag. Any
  later commit, including documentation, changes the bound hash and the live preflight will refuse it.
  That is intended.
- The cost is time: one day of audit rounds for an experiment that has still not run.
