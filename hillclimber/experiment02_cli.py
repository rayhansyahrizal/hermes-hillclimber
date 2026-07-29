"""Material preparation and zero-cost protocol dry run. No live adapter is exposed here."""
import argparse, json
from pathlib import Path
from hillclimber.experiment02 import prepare_materials, run_condition, write_immutable_ledger
from hillclimber.judge import parse_map
from hillclimber.model import ScriptedModel

def main(argv=None):
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest="command",required=True)
    prep=sub.add_parser("prepare"); prep.add_argument("--root",type=Path,default=Path("experiment-02")); prep.add_argument("--preregistration",type=Path,default=Path("experiment-02-preregistration.md"))
    dry=sub.add_parser("dry-run"); dry.add_argument("manifest",type=Path); dry.add_argument("--output",type=Path,required=True)
    args=p.parse_args(argv)
    if args.command=="prepare":
        manifest,sealed=prepare_materials(args.root,args.preregistration); print(f"Manifest: {manifest}\nSealed solver manifest: {sealed}"); return 0
    manifest=json.loads(args.manifest.read_text()); root=args.manifest.parent; records=[]
    for block in manifest["schedule"]:
        item=next(x for x in manifest["maps"] if x["map_id"]==block["map_id"]); puzzle=parse_map((root/item["path"]).read_text())
        calls=1 if block["condition"]=="A" else 4
        responses=[json.dumps({"moves":[]}) for _ in range(calls)]
        factory=lambda responses=iter(responses): ScriptedModel([next(responses)])
        records.extend(run_condition(puzzle,block["map_id"],block["condition"],factory))
    write_immutable_ledger(args.output,records); print(f"Dry-run ledger: {args.output}\nCalls: {len(records)}\nModel: scripted-local (zero cost)"); return 0
if __name__=="__main__": raise SystemExit(main())
