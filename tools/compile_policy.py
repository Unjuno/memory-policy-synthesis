#!/usr/bin/env python3
"""Generate a bounded C userspace policy and Lean AST from validated JSON."""
from __future__ import annotations
import argparse
from pathlib import Path
from policy_lib import c_expr, lean_expr, load_policy

C_TEMPLATE = r'''/* GENERATED FILE: do not edit; edit policies/candidate.json instead. */
#include <errno.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

static inline uint64_t min_u64(uint64_t a, uint64_t b) { return a < b ? a : b; }
static inline uint64_t max_u64(uint64_t a, uint64_t b) { return a > b ? a : b; }
static inline uint64_t sat_add(uint64_t a, uint64_t b) { return UINT64_MAX - a < b ? UINT64_MAX : a+b; }
static inline uint64_t sat_sub(uint64_t a, uint64_t b) { return a > b ? a-b : 0; }
static inline uint64_t percent_u64(uint64_t x, uint64_t pct) {
  return (uint64_t)(((__uint128_t)x * pct) / 100);
}
static int parse_u64(const char *s, uint64_t *out) {
  if (!s || !*s || *s == '-') return 0;
  errno = 0;
  char *end = NULL;
  unsigned long long v = strtoull(s, &end, 10);
  if (errno || !end || *end) return 0;
  *out = (uint64_t)v;
  return 1;
}
static inline uint64_t policy(uint64_t idle_sec, uint64_t anon_kib,
                       uint64_t psi_pct, uint64_t cap_kib) {
  if (!idle_sec) return 0;
  idle_sec = min_u64(idle_sec, UINT64_C(86400));
  anon_kib = min_u64(anon_kib, UINT64_C(268435456));
  psi_pct = min_u64(psi_pct, UINT64_C(100));
  const uint64_t recommendation = __EXPR__;
  return min_u64(cap_kib, min_u64(anon_kib, recommendation));
}
int main(int argc, char **argv) {
  uint64_t idle, anon, psi, cap;
  if (argc != 5 || !parse_u64(argv[1], &idle) || !parse_u64(argv[2], &anon)
      || !parse_u64(argv[3], &psi) || !parse_u64(argv[4], &cap)) {
    fprintf(stderr, "usage: policy idle_sec anon_kib psi_pct cap_kib (all uint64)\n");
    return 2;
  }
  printf("%" PRIu64 "\n", policy(idle, anon, psi, cap));
  return 0;
}
'''
LEAN_TEMPLATE = '''import MemoryPolicy
namespace Candidate
open MemoryPolicy

def candidate : Expr := __EXPR__

theorem cap_safe (s : Snapshot) (cap : Nat) :
    decide candidate s cap ≤ cap := decide_le_cap candidate s cap

theorem anon_safe (s : Snapshot) (cap : Nat) :
    decide candidate s cap ≤ s.anonKiB := decide_le_anon candidate s cap

theorem zero_when_active (s : Snapshot) (cap : Nat) (h : s.idleSec = 0) :
    decide candidate s cap = 0 := decide_zero_when_active candidate s cap h
end Candidate
'''

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--policy', default='policies/candidate.json')
    ap.add_argument('--out-c', default='build/policy.c')
    ap.add_argument('--out-lean', default='formal/Candidate.lean')
    args = ap.parse_args()
    expr = load_policy(args.policy)
    for filename, content in ((args.out_c, C_TEMPLATE.replace('__EXPR__', c_expr(expr))),
                              (args.out_lean, LEAN_TEMPLATE.replace('__EXPR__', lean_expr(expr)))):
        target = Path(filename)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        print('generated', target)

if __name__ == '__main__':
    main()
