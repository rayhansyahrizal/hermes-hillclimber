"""Experiment 02 execution-integrity runtime. No live authorization is embedded here."""
from __future__ import annotations
import hashlib, json, os, subprocess, uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from hillclimber.experiment02 import BASE_PROMPT, Completion, INVALID_SCORE, MODEL, _feedback_prompt, sha256
from hillclimber.judge import InvalidRoute, parse_map, score_route

MAX_CALLS=90; EXPECTED_CALLS={"A":1,"B":4,"C":4}; GENESIS="0"*64
class ProtocolAbort(RuntimeError): pass
class OutagePause(RuntimeError): pass
class TransportFailure(RuntimeError): pass


def canonical_hash(value): return sha256(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode())
def feedback_template_bytes(): return b"\nCurrent route: {route}\nCurrent score: {score}\nJudge feedback: {feedback}\nPropose one complete replacement route that scores higher."

class HashChainLedger:
    def __init__(self,path:Path):
        self.path=path; path.parent.mkdir(parents=True,exist_ok=True)
        self.records=self.verify(path) if path.exists() else []; self.previous=self.records[-1]["entry_sha256"] if self.records else GENESIS
    @staticmethod
    def verify(path:Path):
        out=[]; previous=GENESIS
        for n,line in enumerate(path.read_text().splitlines(),1):
            try: full=json.loads(line)
            except json.JSONDecodeError as e: raise ProtocolAbort(f"malformed ledger line {n}") from e
            item=dict(full); claimed=item.pop("entry_sha256",None)
            if item.get("previous_sha256")!=previous: raise ProtocolAbort(f"ledger chain broken at line {n}")
            if claimed!=canonical_hash(item): raise ProtocolAbort(f"ledger tamper at line {n}")
            full["entry_sha256"]=claimed; out.append(full); previous=claimed
        return out
    def append(self,record):
        item={**record,"previous_sha256":self.previous}; item["entry_sha256"]=canonical_hash(item)
        fd=os.open(self.path,os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
        try: os.write(fd,(json.dumps(item,sort_keys=True,separators=(",",":"))+"\n").encode()); os.fsync(fd)
        finally: os.close(fd)
        self.records.append(item); self.previous=item["entry_sha256"]; return item
    def finalize(self):
        if unresolved(self.records): raise ProtocolAbort("cannot finalize unresolved reservations")
        if self.records and self.records[-1].get("event")=="ledger_finalized": return self.records[-1]
        return self.append({"event":"ledger_finalized","event_count":len(self.records),"finalized_prefix_sha256":self.previous})

def unresolved(records):
    reserved={r["attempt_id"]:r for r in records if r.get("event")=="attempt_reserved"}
    resolved={r["attempt_id"] for r in records if r.get("event") in {"attempt_result","protocol_abort"}}
    return [v for k,v in reserved.items() if k not in resolved]

def verify_finalized(path:Path):
    rows=HashChainLedger.verify(path)
    if not rows or rows[-1].get("event")!="ledger_finalized": raise ProtocolAbort("ledger is not finalized")
    if rows[-1]["event_count"]!=len(rows)-1 or rows[-1]["finalized_prefix_sha256"]!=(rows[-2]["entry_sha256"] if len(rows)>1 else GENESIS): raise ProtocolAbort("invalid finalization")
    if unresolved(rows): raise ProtocolAbort("unresolved reservation")
    return rows

def verify_schedule(schedule):
    if len(schedule)!=30 or [x.get("block") for x in schedule]!=list(range(1,31)): raise ProtocolAbort("schedule must be blocks 1..30")
    rotations=("ABC","BCA","CAB")
    for g in range(10):
        if "".join(x["condition"] for x in schedule[g*3:g*3+3])!=rotations[g%3]: raise ProtocolAbort("counterbalancing triple")
    mids={x["map_id"] for x in schedule}
    if len(mids)!=10 or any(sorted(x["condition"] for x in schedule if x["map_id"]==m)!=list("ABC") for m in mids): raise ProtocolAbort("map allocation")
    if any(a["map_id"]==b["map_id"] for a,b in zip(schedule,schedule[1:])): raise ProtocolAbort("adjacent map")

@dataclass(frozen=True)
class RuntimeIdentity:
    executable:str; executable_sha256:str; provider:str; model:str; hermes_version:str; config_sha256:str; invocation:tuple[str,...]; fresh_one_turn:bool; tools_enabled:bool; personal_rules:bool

class HermesAdapter:
    """Only live adapter. Identity is measured from executable/config, never caller supplied."""
    rehearsal=False
    def __init__(self,executable:Path,config:Path,invocation:tuple[str,...]): self.executable=executable.resolve(); self.config=config.resolve(); self.invocation=invocation
    def introspect(self):
        if not self.executable.is_file() or not os.access(self.executable,os.X_OK): raise ProtocolAbort("Hermes executable unavailable")
        version=subprocess.run([str(self.executable),"--version"],capture_output=True,text=True,check=True).stdout.strip()
        args=list(self.invocation); provider=args[args.index("--provider")+1]; model=args[args.index("--model")+1]
        return RuntimeIdentity(str(self.executable),sha256(self.executable.read_bytes()),provider,model,version,sha256(self.config.read_bytes()),self.invocation,"--max-turns" in args and args[args.index("--max-turns")+1]=="1",False,"--ignore-rules" in args)
    def complete(self,prompt,idempotency_key):
        # stdin only; executable and full argv are the inspected values above.
        p=subprocess.run([str(self.executable),*self.invocation[1:],"--idempotency-key",idempotency_key],input=prompt,capture_output=True,text=True,check=True)
        return Completion(p.stdout)

class RehearsalAdapter:
    """Scripted zero-cost adapter; structurally barred from live preflight."""
    rehearsal=True
    def __init__(self,values): self.values=iter(values); self.prompts=[]; self.keys=[]
    def complete(self,prompt,idempotency_key):
        self.prompts.append(prompt); self.keys.append(idempotency_key); v=next(self.values)
        if isinstance(v,BaseException): raise v
        c=v if isinstance(v,Completion) else Completion(str(v))
        if c.cost not in (None,0,0.0): raise ProtocolAbort("rehearsal adapter returned nonzero cost")
        return c

def _git(root,*args): return subprocess.run(["git",*args],cwd=root,capture_output=True,text=True,check=True).stdout.strip()
def source_tree_digest(root):
    files=_git(root,"ls-files").splitlines(); h=hashlib.sha256()
    for name in sorted(files):
        if name.startswith("runs/live/"): continue
        data=(root/name).read_bytes(); h.update(name.encode()+b"\0"+sha256(data).encode()+b"\n")
    return h.hexdigest()

def preflight(root,commitment_path,adapter,*,live):
    c=json.loads(commitment_path.read_text())
    for field in ("protocol","manifest_path","manifest_sha256","preregistration_path","preregistration_sha256","amendment_path","amendment_sha256","base_prompt_sha256","feedback_template_sha256","full_prompt_map_sha256","caps","custody_request_path","custody_request_sha256","source_binding_path"):
        if field not in c: raise ProtocolAbort(f"missing commitment field: {field}")
    manifest=json.loads((root/c["manifest_path"]).read_text())
    checks=((c["manifest_path"],c["manifest_sha256"]),(c["preregistration_path"],c["preregistration_sha256"]),(c["amendment_path"],c["amendment_sha256"]),(c["custody_request_path"],c["custody_request_sha256"]))
    for path,digest in checks:
        if sha256((root/path).read_bytes())!=digest: raise ProtocolAbort(f"commitment mismatch: {path}")
    verify_schedule(manifest["schedule"])
    if sha256(BASE_PROMPT.encode())!=c["base_prompt_sha256"] or sha256(feedback_template_bytes())!=c["feedback_template_sha256"]: raise ProtocolAbort("prompt commitment mismatch")
    manifest_dir=(root/c["manifest_path"]).parent
    prompt_map={m["map_id"]:sha256(BASE_PROMPT.format(board=(manifest_dir/m["path"]).read_text().rstrip("\n")).encode()) for m in manifest["maps"]}
    if canonical_hash(prompt_map)!=c["full_prompt_map_sha256"]: raise ProtocolAbort("full prompt map mismatch")
    if c["caps"]!={"calls":90,"per_block":{"A":1,"B":4,"C":4},"input_tokens":900000,"output_tokens":90000,"total_tokens":990000,"currency_usd":10.0,"max_reserved_usd_per_call":0.11}: raise ProtocolAbort("caps mismatch")
    for m in manifest["maps"]:
        if sha256((manifest_dir/m["path"]).read_bytes())!=m["sha256"]: raise ProtocolAbort("map mismatch")
    if live:
        if adapter.rehearsal: raise ProtocolAbort("scripted adapter can never satisfy live preflight")
        binding=root/c["source_binding_path"]
        if not binding.exists(): raise ProtocolAbort("independent source/custody acknowledgment absent")
        b=json.loads(binding.read_text()); ident=adapter.introspect()
        if b.get("source_tree_sha256")!=source_tree_digest(root) or b.get("adapter_identity")!=json.loads(json.dumps(ident.__dict__)): raise ProtocolAbort("audited source/adapter binding mismatch")
        if not b.get("compass_signature"): raise ProtocolAbort("Compass signature absent")
        if not b.get("provider_enforcement",{}).get("currency_cap_verified") or not b.get("provider_enforcement",{}).get("call_cap_verified"): raise ProtocolAbort("provider/account dollar and call enforcement unverifiable")
        dirty=[x for x in _git(root,"status","--porcelain").splitlines() if x and " runs/live/" not in x]
        if dirty: raise ProtocolAbort("source tree not clean")
    return manifest,c

class Orchestrator:
    def __init__(self,root,commitment,ledger,adapter,*,mode="rehearsal",clock=lambda:"rehearsal"):
        self.root=root; self.adapter=adapter; self.live=mode=="live"; self.manifest,self.commitment=preflight(root,commitment,adapter,live=self.live); self.ledger=HashChainLedger(ledger); self.clock=clock
        if self.live and adapter.rehearsal: raise ProtocolAbort("rehearsal adapter barred from live")
        self._recover(); self._validate()
    def _recover(self):
        for r in unresolved(self.ledger.records):
            self.ledger.append({"event":"attempt_result","attempt_id":r["attempt_id"],"status":"ambiguous_transport","analysis_score":INVALID_SCORE,"valid":False,"accepted":False,"error":"reserved without result on resume; consumed and never redispatched","finished_at":self.clock(),"cost":None})
    def _validate(self):
        reservations=[r for r in self.ledger.records if r.get("event")=="attempt_reserved"]
        if len(reservations)>MAX_CALLS: raise ProtocolAbort("call cap exceeded")
        if sum(r["reserved_usd"] for r in reservations)>10: raise ProtocolAbort("reserved spend cap exceeded")
    def run(self,stop_after=None,crash_after_dispatch=False):
        if self.ledger.records and self.ledger.records[-1].get("event")=="ledger_finalized": raise ProtocolAbort("ledger finalized")
        attempted=0
        results={r["attempt_id"]:r for r in self.ledger.records if r.get("event")=="attempt_result"}
        slots=[(b,i) for b in self.manifest["schedule"] for i in range(1,EXPECTED_CALLS[b["condition"]]+1)]
        consumed={(r["block"],r["call_index"]) for r in self.ledger.records if r.get("event")=="attempt_reserved"}
        incumbents={}
        for res in results.values():
            if res.get("accepted"): incumbents[res["block"]]=res
        for block,index in slots:
            if (block["block"],index) in consumed: continue
            reservations=sum(r.get("reserved_usd",0) for r in self.ledger.records if r.get("event")=="attempt_reserved")
            if len(consumed)>=90 or reservations+0.11>10: raise ProtocolAbort("conservative reservation cap")
            manifest_dir=(self.root/self.commitment["manifest_path"]).parent
            puzzle=parse_map((manifest_dir/next(m["path"] for m in self.manifest["maps"] if m["map_id"]==block["map_id"])).read_text())
            incumbent=incumbents.get(block["block"]); prompt=BASE_PROMPT.format(board="\n".join(puzzle.rows))
            if block["condition"]=="C" and incumbent:
                result=score_route(puzzle,incumbent["parsed_route"]); prompt=_feedback_prompt(puzzle,incumbent["parsed_route"],result)
            aid=str(uuid.uuid4()); key=f"experiment-02:{block['block']}:{index}:{aid}"
            reservation=self.ledger.append({"event":"attempt_reserved","attempt_id":aid,"idempotency_key":key,"block":block["block"],"map_id":block["map_id"],"condition":block["condition"],"call_index":index,"prompt_sha256":sha256(prompt.encode()),"prompt_bytes":prompt,"reserved_usd":0.11,"reserved_input_tokens":10000,"reserved_output_tokens":1000,"started_at":self.clock()})
            try:
                completion=self.adapter.complete(prompt,key)
                if crash_after_dispatch: raise SystemExit("injected post-dispatch crash")
                if completion.input_tokens is not None and completion.input_tokens>reservation["reserved_input_tokens"]: raise ProtocolAbort("input token reservation exceeded")
                if completion.output_tokens is not None and completion.output_tokens>reservation["reserved_output_tokens"]: raise ProtocolAbort("output token reservation exceeded")
                prior_results=[r for r in self.ledger.records if r.get("event")=="attempt_result"]
                if completion.total_tokens is not None and sum(r.get("total_tokens") or 0 for r in prior_results)+completion.total_tokens>990000: raise ProtocolAbort("total token ceiling exceeded")
                route=None; judged=None; error=None
                try: route=json.loads(completion.text); judged=score_route(puzzle,route)
                except (json.JSONDecodeError,InvalidRoute,TypeError,ValueError) as e: error=f"{type(e).__name__}: {e}"
                score=judged.score if judged else INVALID_SCORE; accepted=judged is not None and (incumbent is None or score>incumbent["analysis_score"])
                rec={"event":"attempt_result","attempt_id":aid,"status":"completed" if judged else "invalid","raw_output":completion.text,"parsed_route":route,"analysis_score":score,"valid":judged is not None,"accepted":accepted,"error":error,"steps":judged.steps if judged else None,"treasures_collected":judged.treasures_collected if judged else None,"exit_reached":judged.reached_exit if judged else None,"collision":judged.collided if judged else None,"finished_at":self.clock(),**{k:getattr(completion,k) for k in ("input_tokens","cached_input_tokens","output_tokens","reasoning_tokens","total_tokens","cost")},**{k:reservation[k] for k in ("block","map_id","condition","call_index","prompt_sha256")}}
                saved=self.ledger.append(rec)
                if accepted: incumbents[block["block"]]=saved
            except (TransportFailure,TimeoutError,ConnectionError) as e:
                self.ledger.append({"event":"attempt_result","attempt_id":aid,"status":"transport_failure","analysis_score":INVALID_SCORE,"valid":False,"accepted":False,"error":f"{type(e).__name__}: {e}","finished_at":self.clock(),"cost":None,**{k:reservation[k] for k in ("block","map_id","condition","call_index","prompt_sha256")}})
            except SystemExit: raise
            except BaseException as e:
                self.ledger.append({"event":"protocol_abort","attempt_id":aid,"error":f"{type(e).__name__}: {e}","finished_at":self.clock()}); raise
            consumed.add((block["block"],index)); attempted+=1
            if stop_after and attempted>=stop_after:return
        self.ledger.finalize()
