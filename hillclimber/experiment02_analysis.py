"""Frozen exact analysis CLI for Experiment 02."""
from __future__ import annotations
import argparse, hashlib, itertools, json, random, statistics
from pathlib import Path

BOOTSTRAP_SEED="hermes-hillclimber-exp02-bootstrap-v1"

def analyze(records, bootstrap_samples=100000):
    by={}
    for r in records:
        key=(r["map_id"],r["condition"]); by.setdefault(key,[]).append(r)
    maps=sorted({k[0] for k in by})
    if len(maps)!=10 or any((m,c) not in by for m in maps for c in "ABC"):
        raise ValueError("analysis requires exactly 10 complete paired maps")
    rows=[]
    for m in maps:
        row={"map_id":m}
        for c in "ABC": row[c]=max(x["analysis_score"] for x in by[m,c])
        row["C-B"]=row["C"]-row["B"]; rows.append(row)
    diffs=[r["C-B"] for r in rows]; observed=statistics.mean(diffs)
    stats=[statistics.mean(d*s for d,s in zip(diffs,signs)) for signs in itertools.product((-1,1),repeat=10)]
    p=sum(x>=observed for x in stats)/len(stats)
    rng=random.Random(int.from_bytes(hashlib.sha256(BOOTSTRAP_SEED.encode()).digest(),"big"))
    boot=sorted(statistics.mean(rng.choices(diffs,k=10)) for _ in range(bootstrap_samples))
    def condition_summary(c):
        calls=[x for x in records if x["condition"]==c]
        def total(field):
            values=[x.get(field) for x in calls]; return None if any(v is None for v in values) else sum(values)
        return {"calls_attempted":len(calls),"calls_completed":sum(x["status"]=="completed" for x in calls),"total_tokens":total("total_tokens"),"cost":total("cost")}
    return {"rows":rows,"C_minus_B":{"differences":diffs,"mean":observed,"median":statistics.median(diffs),"positive":sum(d>0 for d in diffs),"tied":sum(d==0 for d in diffs),"negative":sum(d<0 for d in diffs),"exact_one_sided_p":p,"bootstrap_95_percentile":[boot[2499],boot[97499]]},"conditions":{c:condition_summary(c) for c in "ABC"},"bootstrap":{"samples":bootstrap_samples,"seed":BOOTSTRAP_SEED}}

def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument("ledger",type=Path); p.add_argument("--output",type=Path); args=p.parse_args(argv)
    records=[json.loads(line) for line in args.ledger.read_text().splitlines() if line]
    result=analyze(records); text=json.dumps(result,indent=2)+"\n"
    if args.output: args.output.write_text(text)
    else: print(text,end="")
    return 0
if __name__=="__main__": raise SystemExit(main())
