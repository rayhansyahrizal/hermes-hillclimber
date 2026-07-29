"""Experiment 02 v2 fail-closed runtime. Live execution is disabled by default."""
from __future__ import annotations
import hashlib, json, os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from hillclimber.experiment02 import BASE_PROMPT, Completion, INVALID_SCORE, MODEL, _feedback_prompt, sha256
from hillclimber.judge import InvalidRoute, parse_map, score_route

MAX_CALLS = 90
EXPECTED_CALLS = {"A": 1, "B": 4, "C": 4}
GENESIS = "0" * 64

class ProtocolAbort(RuntimeError): pass
class OutagePause(RuntimeError): pass
class TransportFailure(RuntimeError): pass

@dataclass(frozen=True)
class AdapterIdentity:
    provider: str
    model: str
    hermes_version: str
    config_sha256: str
    invocation: tuple[str, ...]
    fresh_one_turn: bool = True
    tools_enabled: bool = False
    personal_rules: bool = False

class HashChainLedger:
    """Append-only JSONL with chained canonical records and fsync per attempt."""
    def __init__(self, path: Path):
        self.path = path; path.parent.mkdir(parents=True, exist_ok=True)
        self.records = self.verify(path) if path.exists() else []
        self.previous = self.records[-1]["entry_sha256"] if self.records else GENESIS
    @staticmethod
    def verify(path: Path) -> list[dict[str, Any]]:
        out=[]; previous=GENESIS
        for number,line in enumerate(path.read_text(encoding="utf-8").splitlines(),1):
            try: item=json.loads(line)
            except json.JSONDecodeError as e: raise ProtocolAbort(f"malformed ledger line {number}") from e
            claimed=item.pop("entry_sha256",None)
            if item.get("previous_sha256") != previous: raise ProtocolAbort(f"ledger chain broken at line {number}")
            actual=sha256(json.dumps(item,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode())
            if claimed != actual: raise ProtocolAbort(f"ledger tamper at line {number}")
            item["entry_sha256"]=claimed; out.append(item); previous=claimed
        return out
    def append(self, record: dict[str,Any]) -> dict[str,Any]:
        item={**record,"previous_sha256":self.previous}
        digest=sha256(json.dumps(item,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode())
        item["entry_sha256"]=digest
        flags=os.O_WRONLY|os.O_CREAT|os.O_APPEND
        fd=os.open(self.path,flags,0o600)
        try:
            os.write(fd,(json.dumps(item,sort_keys=True,separators=(",",":"),ensure_ascii=False)+"\n").encode()); os.fsync(fd)
        finally: os.close(fd)
        self.records.append(item); self.previous=digest
        return item

def verify_schedule(schedule):
    if len(schedule)!=30 or [x.get("block") for x in schedule]!=list(range(1,31)): raise ProtocolAbort("schedule must be blocks 1..30")
    rotations=("ABC","BCA","CAB")
    for group in range(10):
        literal="".join(x["condition"] for x in schedule[group*3:group*3+3])
        if literal != rotations[group%3]: raise ProtocolAbort(f"counterbalancing triple {group+1}: {literal}")
    mids={x["map_id"] for x in schedule}
    if len(mids)!=10: raise ProtocolAbort("schedule requires 10 maps")
    for mid in mids:
        if sorted(x["condition"] for x in schedule if x["map_id"]==mid)!=list("ABC"): raise ProtocolAbort(f"map allocation {mid}")
    if any(a["map_id"]==b["map_id"] for a,b in zip(schedule,schedule[1:])): raise ProtocolAbort("adjacent map")

def canonical_hash(value: Any) -> str:
    return sha256(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode())

def preflight(root: Path, commitment_path: Path, adapter: AdapterIdentity, *, spend_cap: float) -> tuple[dict,dict]:
    commitment=json.loads(commitment_path.read_text()); manifest_path=root/commitment["manifest_path"]
    manifest=json.loads(manifest_path.read_text())
    if sha256(manifest_path.read_bytes())!=commitment["manifest_sha256"]: raise ProtocolAbort("manifest hash mismatch")
    verify_schedule(manifest["schedule"])
    if canonical_hash(asdict(adapter))!=canonical_hash(commitment["adapter"]): raise ProtocolAbort("adapter identity/config mismatch")
    if adapter.provider+"/"+adapter.model != MODEL: raise ProtocolAbort("wrong model/provider")
    if not adapter.fresh_one_turn or adapter.tools_enabled or adapter.personal_rules: raise ProtocolAbort("adapter isolation failure")
    if spend_cap != commitment["currency_cap"]: raise ProtocolAbort("spend cap mismatch")
    for item in manifest["maps"]:
        if sha256((root/item["path"]).read_bytes()) != item["sha256"]: raise ProtocolAbort(f"map hash mismatch: {item['map_id']}")
    if sha256(BASE_PROMPT.encode()) != commitment["base_prompt_sha256"]: raise ProtocolAbort("base prompt mismatch")
    return manifest,commitment

class Orchestrator:
    """Resumable block runner. Construction is harmless; run requires explicit audited enable flag."""
    def __init__(self, root: Path, commitment: Path, ledger: Path, adapter_identity: AdapterIdentity,
                 factory: Callable[[],Any], *, spend_cap: float, live_enabled: bool=False, clock=lambda:"dry-run"):
        self.root=root; self.manifest,self.commitment=preflight(root,commitment,adapter_identity,spend_cap=spend_cap)
        self.ledger=HashChainLedger(ledger); self.factory=factory; self.cap=spend_cap; self.live_enabled=live_enabled; self.clock=clock
        self._validate_prefix()
    def _validate_prefix(self):
        expected=[]
        for b in self.manifest["schedule"]:
            expected += [(b, i) for i in range(1,EXPECTED_CALLS[b["condition"]]+1)]
        if len(self.ledger.records)>MAX_CALLS: raise ProtocolAbort("global call cap exceeded")
        for r,(b,i) in zip(self.ledger.records,expected):
            if (r.get("block"),r.get("map_id"),r.get("condition"),r.get("call_index")) != (b["block"],b["map_id"],b["condition"],i): raise ProtocolAbort("ledger is not a schedule prefix")
        if sum((r.get("cost") or 0) for r in self.ledger.records)>self.cap: raise ProtocolAbort("spend cap exceeded")
    def run(self, *, stop_after: int|None=None):
        if not self.live_enabled: raise ProtocolAbort("live orchestrator disabled; re-audit required")
        done=len(self.ledger.records); consecutive=sum(1 for r in self.ledger.records[-2:] if r.get("status")=="transport_failure")
        attempted=0
        for block in self.manifest["schedule"]:
            calls=EXPECTED_CALLS[block["condition"]]
            before=sum(1 for r in self.ledger.records if r["block"]==block["block"])
            if before==calls: continue
            if before: start=before+1
            else: start=1
            item=next(x for x in self.manifest["maps"] if x["map_id"]==block["map_id"])
            puzzle=parse_map((self.root/item["path"]).read_text())
            prior=[r for r in self.ledger.records if r["block"]==block["block"] and r.get("accepted")]
            incumbent=max(prior,key=lambda r:r["analysis_score"],default=None)
            for index in range(start,calls+1):
                if len(self.ledger.records)>=MAX_CALLS: raise ProtocolAbort("global call cap")
                if sum((r.get("cost") or 0) for r in self.ledger.records)>self.cap: raise ProtocolAbort("spend cap")
                prompt=BASE_PROMPT.format(board="\n".join(puzzle.rows))
                if block["condition"]=="C" and incumbent:
                    route=incumbent["parsed_route"]; result=score_route(puzzle,route); prompt=_feedback_prompt(puzzle,route,result)
                record={"block":block["block"],"map_id":block["map_id"],"condition":block["condition"],"call_index":index,"started_at":self.clock(),"prompt_sha256":sha256(prompt.encode())}
                completion=Completion(""); route=None; judged=None; error=None
                try:
                    value=self.factory().complete(prompt)
                    completion=value if isinstance(value,Completion) else Completion(str(value))
                    if not completion.text: raise TransportFailure("empty transport response")
                    try: route=json.loads(completion.text)
                    except json.JSONDecodeError as e: error=f"JSONDecodeError: {e}"
                    if route is not None:
                        try: judged=score_route(puzzle,route)
                        except (InvalidRoute,TypeError,ValueError) as e: error=f"{type(e).__name__}: {e}"
                    consecutive=0
                except (TransportFailure,TimeoutError,ConnectionError) as e:
                    error=f"{type(e).__name__}: {e}"; consecutive+=1
                score=judged.score if judged else INVALID_SCORE; accepted=judged is not None and (incumbent is None or score>incumbent["analysis_score"])
                record.update({"raw_output":completion.text,"parsed_route":route,"analysis_score":score,"steps":judged.steps if judged else None,"treasures_collected":judged.treasures_collected if judged else None,"exit_reached":judged.reached_exit if judged else None,"collision":judged.collided if judged else None,"valid":judged is not None,"accepted":accepted,"finished_at":self.clock(),"status":"transport_failure" if isinstance(error,str) and error.startswith(("TransportFailure","TimeoutError","ConnectionError")) else ("completed" if judged else "invalid"),"error":error,**{k:getattr(completion,k) for k in ("input_tokens","cached_input_tokens","output_tokens","reasoning_tokens","total_tokens","cost")}})
                saved=self.ledger.append(record); attempted+=1
                if accepted: incumbent=saved
                if completion.cost is not None and sum((r.get("cost") or 0) for r in self.ledger.records)>self.cap: raise ProtocolAbort("cumulative spend above cap")
                if consecutive>=2: raise OutagePause("two consecutive transport failures; resume frozen next call without replacement")
                if stop_after is not None and attempted>=stop_after: return
