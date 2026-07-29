"""Fail-closed Experiment 02 live entrypoint. Disabled unless --live is explicit."""
from __future__ import annotations
import argparse, json
from datetime import datetime, timezone
from pathlib import Path
from .experiment02_runtime import HashChainLedger, HermesAdapter, Orchestrator, OutagePause, ProtocolAbort, preflight

ROOT=Path(__file__).resolve().parents[1]
COMMITMENT=ROOT/"experiment-02/experiment-02-preflight-commitment-v3.json"
LEDGER=ROOT/"runs/live/experiment-02-v3.jsonl"
ATTESTATION=ROOT/"runs/live/experiment-02-operator-attestation.json"
EXECUTABLE=Path.home()/".hermes/hermes-agent/venv/bin/hermes"
CONFIG=Path.home()/".hermes/config.yaml"
INVOCATION=("hermes","chat","--quiet","--ignore-rules","--max-turns","1","--source","tool","--provider","openai-codex","--model","gpt-5.6-sol")

def parser():
    p=argparse.ArgumentParser(description="Exact disabled-by-default Experiment 02 live runner")
    p.add_argument("--live",action="store_true",help="required live authorization gate")
    p.add_argument("--resume-after-outage",action="store_true",help="consume the one frozen outage resume")
    p.add_argument("--preflight-only",action="store_true",help="perform all checks and make zero model calls")
    return p

def _attest():
    if not ATTESTATION.is_file(): raise ProtocolAbort(f"operator attestation required at {ATTESTATION}")
    a=json.loads(ATTESTATION.read_text())
    required=("no_metered_or_extra_usage_fallback","no_prior_experiment_02_live_calls","no_solver_inspection_or_unseal","operator_attested")
    if any(a.get(k) is not True for k in required): raise ProtocolAbort("operator attestation incomplete or false")

def main(argv=None):
    args=parser().parse_args(argv)
    if not args.live: raise ProtocolAbort("live execution disabled: explicit --live required")
    _attest()
    adapter=HermesAdapter(EXECUTABLE,CONFIG,INVOCATION)
    preflight(ROOT,COMMITMENT,adapter,live=True)
    if args.resume_after_outage:
        if not LEDGER.is_file() or LEDGER.stat().st_size==0: raise ProtocolAbort("resume requires existing nonempty ledger")
        rows=HashChainLedger.verify(LEDGER)
        pauses=[r for r in rows if r.get("event")=="outage_paused"]
        if not pauses or any(r.get("event")=="outage_resumed" for r in rows): raise ProtocolAbort("no unconsumed one-time outage resume")
    elif LEDGER.exists() and LEDGER.stat().st_size:
        raise ProtocolAbort("initial live run requires an empty/new fixed ledger; use explicit resume only for outage")
    if args.preflight_only:
        return 0
    clock=lambda:datetime.now(timezone.utc).isoformat()
    Orchestrator(ROOT,COMMITMENT,LEDGER,adapter,mode="live",clock=clock).run(resume_outage=args.resume_after_outage)
    return 0

if __name__=="__main__": raise SystemExit(main())
