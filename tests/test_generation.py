"""Verify that combinations of AST operators translate into equivalent C code."""
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from compile_policy import C_TEMPLATE
from policy_lib import c_expr, decide, validate

class GeneratedPrograms(unittest.TestCase):
    def test_random_ast_equivalence(self):
        rng = random.Random(1001)
        def expr(depth):
            if depth == 0 or rng.random() < 0.30:
                return rng.choice([{'op': 'lit', 'value': rng.randint(0, 100000)},
                                   {'op': 'feature', 'name': rng.choice(['idle_sec','anon_kib','psi_pct'])}])
            op = rng.choice(['add','sub','min','max','percent','if_ge'])
            if op in ('add','sub','min','max'):
                return {'op':op, 'left':expr(depth-1), 'right':expr(depth-1)}
            if op == 'percent':
                return {'op':op, 'value':rng.randrange(101), 'expr':expr(depth-1)}
            return {'op':op, 'feature':rng.choice(['idle_sec','anon_kib','psi_pct']),
                    'threshold':rng.randrange(500), 'then':expr(depth-1), 'else':expr(depth-1)}
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)/'policy.c'
            binary = Path(folder)/'policy'
            for _ in range(16):
                tree = expr(4)
                validate(tree)
                source.write_text(C_TEMPLATE.replace('__EXPR__', c_expr(tree)))
                subprocess.run(['gcc', '-std=gnu11', '-O2', '-Wall', '-Wextra', '-Werror',
                                str(source), '-o', str(binary)], check=True, capture_output=True)
                for _ in range(25):
                    vals = [rng.randrange(0, 200000), rng.randrange(0, 10000000),
                            rng.randrange(0, 200), rng.randrange(0, 32769)]
                    actual = int(subprocess.check_output([str(binary), *(str(v) for v in vals)], text=True).strip())
                    expected = decide(tree, *vals)
                    self.assertEqual(actual, expected, (tree, vals))
if __name__ == '__main__':
    unittest.main()
