import json, tempfile, unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from hillclimber.experiment02 import BASE_PROMPT, Completion, frozen_schedule, generate_maps, sha256, solve_and_validate
from hillclimber.experiment02_analysis import analyze, bootstrap_index_vectors, sign_flip
from hillclimber.experiment02_runtime import (AdapterIdentity, HashChainLedger, Orchestrator, OutagePause,
    ProtocolAbort, TransportFailure, verify_schedule)

ROOT=Path(__file__).parents[1]/"experiment-02"
COMMIT=ROOT/"experiment-02-preflight-commitment-v2.json"
def identity():
    a=json.loads(COMMIT.read_text())["adapter"]
    a["invocation"]=tuple(a["invocation"])
    return AdapterIdentity(**a)

class Responses:
    def __init__(self, values): self.values=iter(values); self.prompts=[]; self.instances=0
    def __call__(self):
        self.instances+=1; outer=self
        class Fresh:
            def complete(self,prompt):
                outer.prompts.append(prompt); value=next(outer.values)
                if isinstance(value,BaseException): raise value
                return value
        return Fresh()

def record(mid,c,i,score=0,**kw):
    return {"map_id":mid,"condition":c,"call_index":i,"analysis_score":score,"status":"completed","valid":True,"collision":False,"exit_reached":False,"treasures_collected":0,"accepted":i==1,"input_tokens":1,"cached_input_tokens":0,"output_tokens":1,"reasoning_tokens":0,"total_tokens":2,"cost":0.0,**kw}

class Experiment02V2Tests(unittest.TestCase):
    def test_generation_deterministic(self):
        a,log=generate_maps(1,max_attempts=50000); b,_=generate_maps(1,max_attempts=50000)
        self.assertEqual(a[0][0],b[0][0]); self.assertEqual(a[0][2]["optimum_length"],solve_and_validate(a[0][1])["optimum_length"]); self.assertGreater(log["attempts"],0)
    def test_literal_counterbalancing_and_adversarial_rejection(self):
        s=frozen_schedule([f"m{i}" for i in range(10)]); verify_schedule(s)
        self.assertEqual(["ABC","BCA","CAB","ABC","BCA","CAB","ABC","BCA","CAB","ABC"],["".join(x["condition"] for x in s[i:i+3]) for i in range(0,30,3)])
        bad=json.loads(json.dumps(s)); bad[0]["condition"]="B"
        with self.assertRaises(ProtocolAbort): verify_schedule(bad)
    def test_preflight_disabled_and_wrong_identity_hash_map_spend(self):
        f=Responses([])
        with tempfile.TemporaryDirectory() as d:
            ledger=Path(d)/"l"
            o=Orchestrator(ROOT,COMMIT,ledger,identity(),f,spend_cap=10.0)
            with self.assertRaisesRegex(ProtocolAbort,"disabled"): o.run()
            with self.assertRaises(ProtocolAbort): Orchestrator(ROOT,COMMIT,ledger,replace(identity(),model="wrong"),f,spend_cap=10.0)
            with self.assertRaises(ProtocolAbort): Orchestrator(ROOT,COMMIT,ledger,identity(),f,spend_cap=9.0)
    def test_hash_chain_fsync_tamper_and_restart(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"ledger"; l=HashChainLedger(p)
            with patch("hillclimber.experiment02_runtime.os.fsync") as fs: l.append({"x":1}); fs.assert_called_once()
            self.assertEqual(1,len(HashChainLedger(p).records))
            p.write_text(p.read_text().replace('"x":1','"x":2'))
            with self.assertRaises(ProtocolAbort): HashChainLedger(p)
    def test_interrupted_resume_exact_nonreplacement_and_prompt_isolation(self):
        values=[Completion(json.dumps({"moves":[]})) for _ in range(90)]; f=Responses(values)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"ledger"
            Orchestrator(ROOT,COMMIT,p,identity(),f,spend_cap=10.0,live_enabled=True).run(stop_after=7)
            self.assertEqual(7,len(HashChainLedger(p).records))
            Orchestrator(ROOT,COMMIT,p,identity(),f,spend_cap=10.0,live_enabled=True).run()
            rows=HashChainLedger(p).records; self.assertEqual(90,len(rows)); self.assertEqual(90,len({(r['block'],r['call_index']) for r in rows})); self.assertEqual(90,f.instances)
            manifest=json.loads((ROOT/'experiment-02-manifest-v2.json').read_text())
            for b in manifest['schedule']:
                calls=[r for r in rows if r['block']==b['block']]; self.assertEqual(list(range(1,2 if b['condition']=='A' else 5)),[r['call_index'] for r in calls])
            base_hashes={r['prompt_sha256'] for r in rows if r['condition'] in 'AB'}; self.assertEqual(10,len(base_hashes)) # exactly one map-specific base hash, no history
    def test_outage_pauses_after_durable_consumed_calls_and_programming_error_escapes(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"l"; f=Responses([TransportFailure("x"),TimeoutError("y")])
            with self.assertRaises(OutagePause): Orchestrator(ROOT,COMMIT,p,identity(),f,spend_cap=10.0,live_enabled=True).run()
            rows=HashChainLedger(p).records; self.assertEqual([(1,1),(2,1)],[(r['block'],r['call_index']) for r in rows]); self.assertTrue(all(r['analysis_score']==-271 for r in rows))
        with tempfile.TemporaryDirectory() as d:
            f=Responses([AssertionError("judge regression")])
            with self.assertRaises(AssertionError): Orchestrator(ROOT,COMMIT,Path(d)/"l",identity(),f,spend_cap=10.0,live_enabled=True).run()
    def test_schema_move_cap_tokens_invalid_and_feedback_incumbent(self):
        # malformed JSON and >250 schema are invalid but attempted; invalid retains token accounting.
        vals=[Completion(json.dumps({"moves":[]}),total_tokens=3),Completion("bad",total_tokens=4),Completion(json.dumps({"moves":["R"]*251}),total_tokens=5),Completion(json.dumps({"moves":[]}),total_tokens=6)]
        f=Responses(vals)
        with tempfile.TemporaryDirectory() as d:
            Orchestrator(ROOT,COMMIT,Path(d)/"l",identity(),f,spend_cap=10.0,live_enabled=True).run(stop_after=4)
            rows=HashChainLedger(Path(d)/"l").records
            self.assertEqual([3,4,5,6],[r['total_tokens'] for r in rows]); self.assertFalse(rows[1]['valid']); self.assertFalse(rows[2]['valid'])
            if rows[0]['condition']=='C': self.assertIn("Current route:",f.prompts[1])
    def test_analysis_exact_budget_rejections_and_outputs(self):
        records=[]
        for i in range(10):
            for c,v in zip("ABC",(0,1,2)):
                records += [record(str(i),c,j,v+j-1) for j in range(1,2 if c=='A' else 5)]
        out=analyze(records,bootstrap_samples=1000)
        self.assertEqual(1,out['C_minus_B']['mean']); self.assertEqual(1/1024,out['C_minus_B']['exact_one_sided_p'])
        for key in ('contrasts','conditions','bootstrap','rows'): self.assertIn(key,out)
        malformed=records[:-1]
        with self.assertRaises(ValueError): analyze(malformed,bootstrap_samples=10)
        extra=records+[record('0','A',2)]
        with self.assertRaises(ValueError): analyze(extra,bootstrap_samples=10)
    def test_independent_statistical_goldens(self):
        self.assertEqual((0,1.0),sign_flip([0]*10)); self.assertEqual((-1,1.0),sign_flip([-1]*10))
        obs,p=sign_flip([2,-1,0,3,-4,1,0,-2,5,-3]); self.assertEqual(.1,obs); self.assertEqual(0.5,p)
        self.assertEqual([[3,1,2,3],[0,1,3,1],[0,3,0,3]],bootstrap_index_vectors(4,3))

if __name__=="__main__": unittest.main()
