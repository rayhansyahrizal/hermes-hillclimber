import json,tempfile,unittest
from pathlib import Path
from hillclimber.experiment02 import Completion
from hillclimber.experiment02_runtime import HashChainLedger,Orchestrator,ProtocolAbort,RehearsalAdapter,preflight,verify_finalized
from hillclimber.experiment02_analysis import analyze
ROOT=Path(__file__).parents[1]; COMMIT=ROOT/'experiment-02/experiment-02-preflight-commitment-v3.json'

def values(n=90): return [Completion('{"moves":[]}',input_tokens=1,output_tokens=1,total_tokens=2,cost=0) for _ in range(n)]
class IntegrityV3(unittest.TestCase):
 def test_live_script_is_structurally_barred(self):
  with self.assertRaisesRegex(ProtocolAbort,'scripted') : preflight(ROOT,COMMIT,RehearsalAdapter([]),live=True)
 def test_every_commitment_field_required_and_exact(self):
  original=json.loads(COMMIT.read_text())
  for field in original:
   with tempfile.TemporaryDirectory() as d:
    c=dict(original); c.pop(field); p=Path(d)/'c.json';p.write_text(json.dumps(c))
    with self.assertRaises(ProtocolAbort): preflight(ROOT,p,RehearsalAdapter([]),live=False)
  with tempfile.TemporaryDirectory() as d:
   c=dict(original);c['feedback_template_sha256']='0'*64;p=Path(d)/'c';p.write_text(json.dumps(c))
   with self.assertRaisesRegex(ProtocolAbort,'prompt'):preflight(ROOT,p,RehearsalAdapter([]),live=False)
 def test_reservation_fsync_crash_restart_consumed(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'ledger'; a=RehearsalAdapter(values())
   with self.assertRaises(SystemExit):Orchestrator(ROOT,COMMIT,p,a).run(crash_after_dispatch=True)
   rows=HashChainLedger(p).records;self.assertEqual(['attempt_reserved'],[x['event'] for x in rows]);key=rows[0]['idempotency_key']
   b=RehearsalAdapter(values());Orchestrator(ROOT,COMMIT,p,b).run(stop_after=1)
   rows=HashChainLedger(p).records;self.assertEqual('ambiguous_transport',rows[1]['status']);self.assertNotIn(key,b.keys);self.assertEqual(-271,rows[1]['analysis_score'])
 def test_complete_rehearsal_finalized_and_analysis_outputs(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'ledger';a=RehearsalAdapter(values());Orchestrator(ROOT,COMMIT,p,a).run()
   rows=verify_finalized(p);self.assertEqual(181,len(rows));self.assertEqual(90,len(a.keys));self.assertEqual(90,len(set(a.keys)))
   out=analyze(rows,bootstrap_samples=100);self.assertIn('C-A_success',out['contrasts']);self.assertIn('B-A_success',out['contrasts']);self.assertIn('call1_to_best_gain_mean',out['C_minus_B'])
 def test_exact_feedback_bytes_and_protocol_abort(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'l'; a=RehearsalAdapter([AssertionError('bug')])
   with self.assertRaises(AssertionError):Orchestrator(ROOT,COMMIT,p,a).run()
   self.assertEqual(['attempt_reserved','protocol_abort'],[x['event'] for x in HashChainLedger(p).records])
 def test_analysis_rejects_unfinalized(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'l';HashChainLedger(p).append({'event':'x'})
   with self.assertRaises(ProtocolAbort):verify_finalized(p)
if __name__=='__main__':unittest.main()
