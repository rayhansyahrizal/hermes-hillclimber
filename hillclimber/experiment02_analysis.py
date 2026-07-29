"""Fail-closed preregistered analysis for Experiment 02 v2."""
from __future__ import annotations
import argparse, hashlib, itertools, json, random, statistics
from pathlib import Path

BOOTSTRAP_SEED="hermes-hillclimber-exp02-bootstrap-v1"
EXPECTED={"A":1,"B":4,"C":4}
TOKEN_FIELDS=("input_tokens","cached_input_tokens","output_tokens","reasoning_tokens","total_tokens")

def sign_flip(diffs):
    observed=statistics.mean(diffs)
    values=[statistics.mean(d*s for d,s in zip(diffs,signs)) for signs in itertools.product((-1,1),repeat=len(diffs))]
    return observed,sum(x>=observed for x in values)/len(values)

def bootstrap_index_vectors(n, count, seed=BOOTSTRAP_SEED):
    rng=random.Random(int.from_bytes(hashlib.sha256(seed.encode("utf-8")).digest(),"big"))
    return [[rng.randrange(n) for _ in range(n)] for _ in range(count)]

def _total(rows, field):
    values=[r.get(field) for r in rows]
    return None if any(v is None for v in values) else sum(values)

def analyze(records, bootstrap_samples=100000, *, manifest=None, solver_optima=None):
    if any(r.get("protocol_abort") for r in records): raise ValueError("aborted protocol is not confirmatory")
    by={}
    for r in records:
        key=(r.get("map_id"),r.get("condition")); by.setdefault(key,[]).append(r)
    maps=sorted({k[0] for k in by})
    if len(maps)!=10 or set(by)!={(m,c) for m in maps for c in "ABC"}: raise ValueError("analysis requires exactly 10 paired maps")
    if manifest is not None:
        expected={(b["map_id"],b["condition"]):b["block"] for b in manifest["schedule"]}
        if set(expected)!=set(by): raise ValueError("ledger differs from manifest schedule")
    for (m,c),calls in by.items():
        indices=sorted(r.get("call_index") for r in calls)
        if indices!=list(range(1,EXPECTED[c]+1)): raise ValueError(f"wrong exact call budget for {m}/{c}: {indices}")
        if manifest is not None and any(r.get("block")!=expected[m,c] for r in calls): raise ValueError("wrong schedule block")
    rows=[]
    for m in maps:
        row={"map_id":m}
        for c in "ABC":
            calls=by[m,c]; best=max(calls,key=lambda x:x["analysis_score"]); first=calls[0]
            successes=[x for x in calls if x.get("exit_reached") and x.get("treasures_collected")==6]
            row[c]={"best_score":best["analysis_score"],"success":bool(successes),"validity_rate":sum(bool(x.get("valid")) for x in calls)/len(calls),"collision_rate":sum(bool(x.get("collision")) for x in calls)/len(calls),"gain_from_call_1":best["analysis_score"]-first["analysis_score"],"strict_improvements":sum(bool(x.get("accepted")) for x in calls[1:]),"first_success_call":successes[0]["call_index"] if successes else None}
            if solver_optima is not None: row[c]["optimality_gap"]=solver_optima[m]-best["analysis_score"]
        for contrast in ("C-B","C-A","B-A"):
            x,y=contrast.split("-"); row[contrast]=row[x]["best_score"]-row[y]["best_score"]
        rows.append(row)
    diffs=[r["C-B"] for r in rows]; observed,p=sign_flip(diffs)
    vectors=bootstrap_index_vectors(10,bootstrap_samples)
    boot=sorted(statistics.mean(diffs[i] for i in v) for v in vectors)
    lo=max(0,int(.025*bootstrap_samples)-1); hi=min(bootstrap_samples-1,int(.975*bootstrap_samples)-1)
    conditions={}
    for c in "ABC":
        calls=[r for r in records if r["condition"]==c]
        conditions[c]={"calls_attempted":len(calls),"calls_completed":sum(r.get("status") not in ("transport_failure",) for r in calls),**{f"{f}_total":_total(calls,f) for f in TOKEN_FIELDS},"cost_total":_total(calls,"cost"),"success_rate":sum(bool(row[c]["success"]) for row in rows)/10,"validity_rate":sum(row[c]["validity_rate"] for row in rows)/10,"collision_rate":sum(row[c]["collision_rate"] for row in rows)/10,"mean_gain_from_call_1":statistics.mean(row[c]["gain_from_call_1"] for row in rows)}
    token_delta=None if conditions["B"]["total_tokens_total"] is None or conditions["C"]["total_tokens_total"] is None else conditions["C"]["total_tokens_total"]-conditions["B"]["total_tokens_total"]
    per_1000=None if not conditions["C"]["total_tokens_total"] else observed/(conditions["C"]["total_tokens_total"]/1000)
    return {"confirmatory_eligible":True,"rows":rows,"C_minus_B":{"differences":diffs,"mean":observed,"median":statistics.median(diffs),"positive":sum(d>0 for d in diffs),"tied":sum(d==0 for d in diffs),"negative":sum(d<0 for d in diffs),"exact_one_sided_p":p,"bootstrap_95_percentile":[boot[lo],boot[hi]],"score_per_1000_C_tokens":per_1000},"contrasts":{"C-A_mean":statistics.mean(r["C-A"] for r in rows),"B-A_mean":statistics.mean(r["B-A"] for r in rows),"C-B_success":conditions["C"]["success_rate"]-conditions["B"]["success_rate"],"C-B_validity":conditions["C"]["validity_rate"]-conditions["B"]["validity_rate"],"C-B_tokens":token_delta,"C-B_cost":None if conditions["C"]["cost_total"] is None or conditions["B"]["cost_total"] is None else conditions["C"]["cost_total"]-conditions["B"]["cost_total"]},"conditions":conditions,"bootstrap":{"samples":bootstrap_samples,"seed":BOOTSTRAP_SEED,"percentile_convention":"sorted nearest-rank floor at 2.5% and 97.5%; zero-based indices floor(p*N)-1 clamped"}}

def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument("ledger",type=Path); p.add_argument("--manifest",type=Path); p.add_argument("--output",type=Path); args=p.parse_args(argv)
    records=[json.loads(line) for line in args.ledger.read_text().splitlines() if line]; manifest=json.loads(args.manifest.read_text()) if args.manifest else None
    result=analyze(records,manifest=manifest); text=json.dumps(result,indent=2)+"\n"
    if args.output: args.output.write_text(text)
    else: print(text,end="")
    return 0
if __name__=="__main__": raise SystemExit(main())
