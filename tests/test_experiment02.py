"""Legacy deterministic generation/statistics regression tests; integrity tests are in v3 suite."""
import unittest
from hillclimber.experiment02 import frozen_schedule,generate_maps,solve_and_validate
from hillclimber.experiment02_analysis import bootstrap_index_vectors,sign_flip
from hillclimber.experiment02_runtime import verify_schedule
class Experiment02RegressionTests(unittest.TestCase):
 def test_generation_and_schedule(self):
  a,log=generate_maps(1,max_attempts=50000);self.assertEqual(a[0][2]['optimum_length'],solve_and_validate(a[0][1])['optimum_length']);self.assertGreater(log['attempts'],0)
  verify_schedule(frozen_schedule([f'm{i}' for i in range(10)]))
 def test_statistical_goldens(self):
  self.assertEqual((0,1.0),sign_flip([0]*10));self.assertEqual((-1,1.0),sign_flip([-1]*10));self.assertEqual((.1,.5),sign_flip([2,-1,0,3,-4,1,0,-2,5,-3]));self.assertEqual([[3,1,2,3],[0,1,3,1],[0,3,0,3]],bootstrap_index_vectors(4,3))
if __name__=='__main__':unittest.main()
