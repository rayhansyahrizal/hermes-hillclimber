import json, tempfile, unittest
from pathlib import Path
from hillclimber.experiment02 import Completion, frozen_schedule, generate_maps, run_condition, solve_and_validate, write_immutable_ledger
from hillclimber.experiment02_analysis import analyze
from hillclimber.judge import parse_map

class Factory:
    def __init__(self,responses): self.responses=iter(responses); self.prompts=[]
    def __call__(self):
        outer=self
        class M:
            def complete(self,p): outer.prompts.append(p); return next(outer.responses)
        return M()

class Experiment02Tests(unittest.TestCase):
    def test_generation_is_deterministic_and_valid(self):
        a,log=generate_maps(1,max_attempts=50000); b,_=generate_maps(1,max_attempts=50000)
        self.assertEqual(a[0][0],b[0][0]); self.assertEqual(6,a[0][1].count("T")); self.assertEqual(a[0][2]["optimum_length"],solve_and_validate(a[0][1])["optimum_length"])
        self.assertGreater(log["attempts"],0)
    def test_schedule_complete_separated_and_rotated(self):
        ids=[f"m{i}" for i in range(10)]; s=frozen_schedule(ids)
        self.assertEqual(30,len(s))
        for mid in ids:
            positions=[i for i,x in enumerate(s) if x["map_id"]==mid]
            self.assertEqual(set("ABC"),{s[i]["condition"] for i in positions}); self.assertTrue(all(b-a>1 for a,b in zip(positions,positions[1:])))
    def test_conditions_budget_stateless_feedback_and_accounting(self):
        puzzle=parse_map("#####\n#STE#\n#####")
        f=Factory([Completion(json.dumps({"moves":["R"]}),total_tokens=2,cost=0.0),"bad",json.dumps({"moves":["R","R"]}),json.dumps({"moves":[]})])
        rows=run_condition(puzzle,"m","C",f,clock=lambda:"fixed")
        self.assertEqual(4,len(rows)); self.assertEqual(-271,rows[1]["analysis_score"]); self.assertEqual(2,rows[0]["total_tokens"]); self.assertIn("Judge feedback:",f.prompts[1]); self.assertNotIn("Judge feedback:",f.prompts[0])
        blind=Factory([json.dumps({"moves":[]})]*4); run_condition(puzzle,"m","B",blind)
        self.assertTrue(all("Current route:" not in p for p in blind.prompts))
    def test_ledger_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"x.jsonl"; write_immutable_ledger(p,[{"a":1}])
            with self.assertRaises(FileExistsError): write_immutable_ledger(p,[])
    def test_exact_analysis(self):
        records=[]
        for i in range(10):
            for c,v in zip("ABC",(0,1,2)):
                records.append({"map_id":str(i),"condition":c,"analysis_score":v,"status":"completed","total_tokens":None,"cost":None})
        result=analyze(records,bootstrap_samples=100000)
        self.assertEqual(1,result["C_minus_B"]["mean"]); self.assertEqual(1/1024,result["C_minus_B"]["exact_one_sided_p"])
        self.assertIsNone(result["conditions"]["B"]["cost"])
if __name__=="__main__": unittest.main()
