"""Frozen Experiment 02 protocol harness (standard-library only).

Solver answers are written only to a separately permissioned sealed manifest.  The
public manifest and run ledgers contain hashes, never solver routes.
"""
from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import itertools
import json
from pathlib import Path
import random
from typing import Any, Callable, Iterable

from hillclimber.judge import InvalidRoute, Puzzle, RouteResult, parse_map, score_route

MAP_SEED = "hermes-hillclimber-exp02-maps-v1"
SCHEDULE_SEED = MAP_SEED
INVALID_SCORE = -271
MODEL = "openai-codex/gpt-5.6-sol"
BASE_PROMPT = ("Solve this deterministic treasure puzzle. Return JSON only, exactly: "
               "{{\"moves\":[\"U\",\"R\",\"D\",\"L\"]}}.\nScoring: +30 per unique treasure, "
               "-1 per step, -20 and stop on collision, +50 for reaching E after collecting every "
               "treasure. Maximum 250 moves.\n\nMap:\n{board}\n")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _rng(seed: str) -> random.Random:
    return random.Random(int.from_bytes(hashlib.sha256(seed.encode("utf-8")).digest(), "big"))


def _neighbors(rows: list[list[str]] | tuple[str, ...], p: tuple[int, int]):
    for dr, dc, move in ((-1,0,"U"),(0,1,"R"),(1,0,"D"),(0,-1,"L")):
        q=(p[0]+dr,p[1]+dc)
        if 0 <= q[0] < len(rows) and 0 <= q[1] < len(rows[0]) and rows[q[0]][q[1]] != "#":
            yield q, move


def _path(puzzle: Puzzle, start: tuple[int,int], end: tuple[int,int]) -> tuple[str,...]:
    queue=deque([start]); prev={start: (start, "")}
    while queue:
        p=queue.popleft()
        if p == end: break
        for q,m in _neighbors(puzzle.rows,p):
            if q not in prev: prev[q]=(p,m); queue.append(q)
    if end not in prev: raise ValueError("unreachable relevant cell")
    moves=[]; p=end
    while p != start:
        old,m=prev[p]; moves.append(m); p=old
    return tuple(reversed(moves))


def solve_and_validate(text: str) -> dict[str, Any]:
    """Mechanically validate a map and return its unique optimum witness."""
    puzzle=parse_map(text)
    failures=[]
    if len(puzzle.rows)!=15 or any(len(r)!=15 for r in puzzle.rows): failures.append("dimensions")
    if len(puzzle.treasures)!=6: failures.append("treasure_count")
    relevant=(puzzle.start, *sorted(puzzle.treasures), puzzle.exit)
    paths={}
    try:
        for a,b in itertools.permutations(relevant,2): paths[a,b]=_path(puzzle,a,b)
    except ValueError: failures.append("reachability")
    junctions=sum(1 for r,row in enumerate(puzzle.rows) for c,ch in enumerate(row)
                  if ch!="#" and sum(1 for _ in _neighbors(puzzle.rows,(r,c)))>=3)
    if junctions<8: failures.append("junctions")
    candidates=[]
    if not failures:
        for order in itertools.permutations(sorted(puzzle.treasures)):
            points=(puzzle.start,*order,puzzle.exit)
            route=tuple(m for a,b in zip(points,points[1:]) for m in paths[a,b])
            candidates.append((len(route),order,route))
        best_len=min(x[0] for x in candidates)
        best=[x for x in candidates if x[0]==best_len]
        # In a perfect maze each pair has one path; require one optimal treasure order too.
        if len(best)!=1: failures.append("non_unique_optimum")
        if not 45<=best_len<=100: failures.append("optimum_length")
        if len({x[0] for x in candidates})<2: failures.append("treasure_order_choices")
        direct=set()
        p=puzzle.start
        for m in paths[puzzle.start,puzzle.exit]:
            dr,dc={"U":(-1,0),"R":(0,1),"D":(1,0),"L":(0,-1)}[m]; p=(p[0]+dr,p[1]+dc); direct.add(p)
        if puzzle.treasures <= direct: failures.append("direct_path_collects_all")
    if failures: raise ValueError(",".join(failures))
    route={"moves":list(best[0][2])}; result=score_route(puzzle,route)
    return {"optimum_length":best_len,"optimum_score":result.score,"junctions":junctions,"route":route}


def _maze(rng: random.Random) -> list[list[str]]:
    rows=[["#"]*15 for _ in range(15)]; start=(rng.randrange(7),rng.randrange(7)); stack=[start]; seen={start}
    rows[2*start[0]+1][2*start[1]+1]="."
    while stack:
        cell=stack[-1]; options=[]
        for dr,dc in ((-1,0),(0,1),(1,0),(0,-1)):
            nxt=(cell[0]+dr,cell[1]+dc)
            if 0<=nxt[0]<7 and 0<=nxt[1]<7 and nxt not in seen: options.append(nxt)
        if not options: stack.pop(); continue
        nxt=rng.choice(options); seen.add(nxt)
        rows[cell[0]+nxt[0]+1][cell[1]+nxt[1]+1]="."
        rows[2*nxt[0]+1][2*nxt[1]+1]="."; stack.append(nxt)
    return rows


def generate_maps(count: int=10, seed: str=MAP_SEED, max_attempts: int=200000):
    rng=_rng(seed); accepted=[]; rejection_counts={}; attempts=0
    while len(accepted)<count and attempts<max_attempts:
        attempts+=1; rows=_maze(rng); open_cells=[(r,c) for r in range(15) for c in range(15) if rows[r][c]=="."]
        chosen=rng.sample(open_cells,8); rows[chosen[0][0]][chosen[0][1]]="S"; rows[chosen[1][0]][chosen[1][1]]="E"
        for p in chosen[2:]: rows[p[0]][p[1]]="T"
        text="\n".join("".join(row) for row in rows)+"\n"
        try: solved=solve_and_validate(text)
        except ValueError as e:
            for failure in str(e).split(","): rejection_counts[failure]=rejection_counts.get(failure,0)+1
            continue
        digest=sha256(text.encode()); accepted.append((digest,text,solved))
    if len(accepted)!=count: raise RuntimeError(f"generated {len(accepted)}/{count} maps in {attempts} attempts")
    accepted.sort(key=lambda x:x[0])
    return accepted,{"seed":seed,"attempts":attempts,"accepted":count,"rejection_counts":rejection_counts}


def frozen_schedule(map_ids: Iterable[str], seed: str=SCHEDULE_SEED) -> list[dict[str,Any]]:
    """v2 schedule: literal successive triples ABC/BCA/CAB, with exact map allocation."""
    ids=sorted(map_ids)
    if len(ids)!=10 or len(set(ids))!=10: raise ValueError("schedule requires 10 unique maps")
    conditions="".join(("ABC","BCA","CAB")[i%3] for i in range(10))
    # Deterministic rejection sampling assigns each condition's ten map slots.
    rng=_rng(seed)
    for _ in range(100000):
        pools={c:ids[:] for c in "ABC"}
        for pool in pools.values(): rng.shuffle(pool)
        schedule=[]
        for condition in conditions:
            choices=[m for m in pools[condition] if not schedule or m!=schedule[-1]["map_id"]]
            if not choices: break
            mid=choices[0]; pools[condition].remove(mid)
            schedule.append({"block":len(schedule)+1,"map_id":mid,"condition":condition})
        if len(schedule)==30:
            return schedule
    raise RuntimeError("unable to construct counterbalanced schedule")


def prepare_materials(root: Path, preregistration: Path) -> tuple[Path,Path]:
    maps,log=generate_maps(); maps_dir=root/"maps"; maps_dir.mkdir(parents=True,exist_ok=True)
    sealed={"sealed":True,"entries":[]}; public=[]
    for digest,text,solution in maps:
        mid=digest[:12]; path=maps_dir/f"{mid}.txt"; path.write_text(text,encoding="utf-8")
        sealed["entries"].append({"map_id":mid,"sha256":digest,**solution})
        public.append({"map_id":mid,"sha256":digest,"path":str(path.relative_to(root)),"route_sha256":sha256(json.dumps(solution["route"],sort_keys=True,separators=(",",":")).encode())})
    private=root/"private"; private.mkdir(exist_ok=True); sealed_path=private/"experiment-02-solver-manifest.json"
    sealed_path.write_text(json.dumps(sealed,indent=2)+"\n"); sealed_path.chmod(0o600)
    manifest={"protocol":"experiment-02","model":MODEL,"map_seed":MAP_SEED,"preregistration_sha256":sha256(preregistration.read_bytes()),"generation":log,"maps":public,"schedule":frozen_schedule(x["map_id"] for x in public)}
    manifest_path=root/"experiment-02-manifest.json"; manifest_path.write_text(json.dumps(manifest,indent=2)+"\n")
    return manifest_path,sealed_path

@dataclass(frozen=True)
class Completion:
    text: str
    input_tokens: int|None=None; cached_input_tokens: int|None=None; output_tokens: int|None=None; reasoning_tokens: int|None=None; total_tokens: int|None=None; cost: float|None=None


def _feedback_prompt(puzzle: Puzzle, route: dict[str,Any], result: RouteResult) -> str:
    return BASE_PROMPT.format(board="\n".join(puzzle.rows))+f"\nCurrent route: {json.dumps(route,separators=(',',':'))}\nCurrent score: {result.score}\nJudge feedback: {result.feedback}\nPropose one complete replacement route that scores higher."


def run_condition(puzzle: Puzzle, map_id: str, condition: str, model_factory: Callable[[],Any], *, clock: Callable[[],str]|None=None):
    """Run one stateless A/B/C block. A=1 call; B/C=4; failures consume calls."""
    if condition not in "ABC" or len(condition)!=1: raise ValueError("condition must be A, B, or C")
    clock=clock or (lambda:datetime.now(timezone.utc).isoformat()); calls=1 if condition=="A" else 4
    incumbent=None; incumbent_result=None; ledger=[]
    for index in range(1,calls+1):
        prompt=BASE_PROMPT.format(board="\n".join(puzzle.rows))
        if condition=="C" and incumbent is not None: prompt=_feedback_prompt(puzzle,incumbent,incumbent_result)
        started=clock(); raw=""; error=None; completion=Completion("")
        try:
            model=model_factory()  # a fresh invocation, including each retry
            value=model.complete(prompt)
            completion=value if isinstance(value,Completion) else Completion(str(value)); raw=completion.text
            route=json.loads(raw); judged=score_route(puzzle,route); score=judged.score; valid=True
        except Exception as exc:
            route=None; judged=None; score=INVALID_SCORE; valid=False; error=f"{type(exc).__name__}: {exc}"
        accepted=valid and (incumbent_result is None or score>incumbent_result.score)
        if accepted: incumbent,incumbent_result=route,judged
        ledger.append({"map_id":map_id,"condition":condition,"call_index":index,"raw_output":raw,"parsed_route":route,"analysis_score":score,"steps":judged.steps if judged else None,"treasures_collected":judged.treasures_collected if judged else None,"exit_reached":judged.reached_exit if judged else None,"collision":judged.collided if judged else None,"valid":valid,"accepted":accepted,"prompt_sha256":sha256(prompt.encode()),"started_at":started,"finished_at":clock(),"status":"completed" if valid else "failed","error":error,"input_tokens":completion.input_tokens,"cached_input_tokens":completion.cached_input_tokens,"output_tokens":completion.output_tokens,"reasoning_tokens":completion.reasoning_tokens,"total_tokens":completion.total_tokens,"cost":completion.cost})
    return tuple(ledger)


def write_immutable_ledger(path: Path, records: Iterable[dict[str,Any]]) -> None:
    if path.exists(): raise FileExistsError(f"immutable ledger already exists: {path}")
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text("".join(json.dumps(r,sort_keys=True,separators=(",",":"))+"\n" for r in records)); path.chmod(0o444)
