import random
import subprocess
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from policy_lib import InvalidPolicy, U64_MAX, decide, load_policy, validate

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / 'build' / 'policy'

class PolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.expr = load_policy(ROOT / 'policies/candidate.json')

    def eval_c(self, idle, anon, psi, cap):
        result = subprocess.run([str(BIN), str(idle), str(anon), str(psi), str(cap)],
                                text=True, capture_output=True, check=True)
        return int(result.stdout.strip())

    def test_boundary_cases(self):
        for x in [0, 1, 9, 10, 30, 86400, U64_MAX]:
            for anon in [0, 1, 2000, 268435456, U64_MAX]:
                for cap in [0, 1, 4096, 32768, U64_MAX]:
                    with self.subTest(x=x, anon=anon, cap=cap):
                        v = self.eval_c(x, anon, 50, cap)
                        self.assertEqual(v, decide(self.expr, x, anon, 50, cap))
                        self.assertLessEqual(v, min(cap, anon))
                        if x == 0:
                            self.assertEqual(v, 0)

    def test_randomized_equivalence(self):
        rng = random.Random(0xA57A)
        for _ in range(500):
            vals = [rng.randrange(0, 10**10), rng.randrange(0, 10**10),
                    rng.randrange(0, 1000), rng.randrange(0, 10**10)]
            self.assertEqual(self.eval_c(*vals), decide(self.expr, *vals))

    def test_invalid_ast(self):
        for e in [
            {'op': 'system', 'cmd': 'rm -rf /'},
            {'op': 'lit', 'value': -1},
            {'op': 'percent', 'value': 101, 'expr': {'op': 'lit', 'value': 5}},
            {'op': 'feature', 'name': 'kernel_pointer'},
            {'op': 'lit', 'value': True},
        ]:
            with self.subTest(e=e), self.assertRaises(InvalidPolicy):
                validate(e)

    def test_workload_smoke(self):
        worker = subprocess.Popen([str(ROOT / 'build' / 'workload'), '4'],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True)
        out, err = worker.communicate('INIT\nRUN\nQUIT\n', timeout=15)
        self.assertEqual(worker.returncode, 0, err)
        self.assertEqual(out.splitlines()[0:2], ['WAITING', 'READY'])
        self.assertRegex(out, r'LATENCY_NS \d+ CHECKSUM \d+')

    def test_reject_invalid_cli(self):
        for arg in ['-1', '1x', '18446744073709551616']:
            run = subprocess.run([str(BIN), arg, '1', '1', '1'], capture_output=True)
            self.assertNotEqual(run.returncode, 0)

if __name__ == '__main__':
    unittest.main()
