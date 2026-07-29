import json,re,shutil,subprocess,tempfile,unittest
from pathlib import Path
from hillclimber.experiment02 import Completion
from hillclimber.experiment02_runtime import HashChainLedger,HermesAdapter,Orchestrator,OutagePause,ProtocolAbort,RehearsalAdapter,TransportFailure,preflight,verify_finalized
from hillclimber.experiment02_analysis import analyze
ROOT=Path(__file__).parents[1]; COMMIT=ROOT/'experiment-02/experiment-02-preflight-commitment-v3.json'

def values(n=90): return [Completion('{"moves":[]}',input_tokens=1,output_tokens=1,total_tokens=2,cost=0) for _ in range(n)]
class IntegrityV3(unittest.TestCase):
 def test_actual_hermes_invocation_contract_zero_cost(self):
  executable=Path(shutil.which('hermes') or '')
  if not executable.is_file(): self.skipTest('Hermes executable unavailable')
  invocation=('hermes','chat','--quiet','--ignore-rules','--max-turns','1','--source','tool','--provider','openai-codex','--model','gpt-5.6-sol')
  adapter=HermesAdapter(executable,Path.home()/'.hermes/config.yaml',invocation)
  help_text=subprocess.run([str(executable),'chat','--help'],capture_output=True,text=True,check=True).stdout
  supported=set(re.findall(r'(?<!\w)--[a-z][a-z-]+',help_text))
  argv=adapter.build_argv(); options={x for x in argv if x.startswith('--')}
  self.assertLessEqual(options,supported)
  self.assertNotIn('--idempotency-key',argv)
  self.assertEqual('openai-codex',argv[argv.index('--provider')+1]);self.assertEqual('gpt-5.6-sol',argv[argv.index('--model')+1])
  self.assertEqual('1',argv[argv.index('--max-turns')+1]);self.assertIn('--ignore-rules',argv);self.assertIn('--quiet',argv)
 def test_two_failures_fsync_pause_and_one_explicit_frozen_resume(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'ledger'; first=RehearsalAdapter([TransportFailure('one'),TimeoutError('two')])
   with self.assertRaises(OutagePause): Orchestrator(ROOT,COMMIT,p,first).run()
   rows=HashChainLedger(p).records; pause=rows[-1]
   self.assertEqual('outage_paused',pause['event']);self.assertEqual(2,pause['consecutive_transport_failures'])
   self.assertEqual((2,2),(pause['next_block'],pause['next_call_index']))
   self.assertEqual(2,len([r for r in rows if r.get('event')=='attempt_reserved']))
   with self.assertRaises(OutagePause): Orchestrator(ROOT,COMMIT,p,RehearsalAdapter(values())).run()
   resumed=RehearsalAdapter(values());Orchestrator(ROOT,COMMIT,p,resumed).run(stop_after=1,resume_outage=True)
   rows=HashChainLedger(p).records
   self.assertEqual(1,len([r for r in rows if r.get('event')=='outage_resumed']))
   self.assertEqual((2,2),(rows[-2]['block'],rows[-2]['call_index']))
   self.assertEqual(3,len({r['idempotency_key'] for r in rows if r.get('event')=='attempt_reserved'}))
   with self.assertRaises(ProtocolAbort): Orchestrator(ROOT,COMMIT,p,RehearsalAdapter(values())).run(resume_outage=True)
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
