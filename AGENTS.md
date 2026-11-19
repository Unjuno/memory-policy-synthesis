# Coding-agent operating agreement — Memory Policy Synthesis

## Mission
Develop and evaluate **fast, compiled memory-policy algorithms**. Stage 0 chooses when/how much proactive anonymous-memory reclaim to request on cgroup v2. This **does not replace MGLRU**. Future kernel-policy replacement is a separate, audited milestone.

## Frozen constraints
1. Do not introduce neural inference on page-reclaim hot paths. A neural/agent system may synthesize, mutate or refine the policy **offline**.
2. Never run privileged benchmarks outside a disposable VM. Do not alter host swap/kernel or production cgroups. Stage-0 benchmarking must use `/sys/fs/cgroup/mps-lab*`, root privileges and explicit VM confirmation.
3. Mutate `policies/candidate.json` first. If extending the DSL, update Python semantics, C compiler, Lean semantics/proofs, and differential tests **together**.
4. Always run `make check` and `make formal`. Both must PASS before deployment/promotion. If Lean is unavailable or fails, mark **UNVERIFIED** and do not promote.
5. Do not use `sorry`, `admit`, or arbitrary axioms. Lean guarantees only the specified **abstract policy action bounds**, not C refinement or Linux correctness.
6. Keep scoring, workloads, held-out traces and baseline logs immutable while tuning a candidate. Record random seeds and input hashes. Compare against equal-budget random search / rule-based alternatives.
7. Do not promote a policy if tests crash, OOM, deadlock or show unresolved quality regressions. Stop the userspace controller and verify ordinary Linux reclaim remains active.
8. Do not write or deploy a `mm/vmscan.c` patch automatically. New kernel code needs its own review: ownership, locking, RCU, policy state, timeout, rollback state and VM fault injection.
9. Count inference/controller overhead, memory footprint and compilation cost where relevant. Distinguish training cost from deployed runtime cost.

## Iteration command sequence

```bash
make check
make formal
# IN A DISPOSABLE VM ONLY, AFTER scripts/doctor.sh and explicit setup:
sudo python3 tools/bench.py --policy candidate \
  --cgroup /sys/fs/cgroup/mps-lab --confirm-disposable-vm \
  --out results/candidate-v001.json
python3 tools/compare.py results/baseline-01.json results/candidate-v001.json
```

Record artifacts, time, kernel commit, hardware/clock, swap codec, p95 and PSI, cgroup OOM/refault statistics, and failure cases. Keep a versioned report of **what changed and why**. Do not infer physical-RAM savings from zram compressed bytes or cgroup memory use alone.

## Acceptance gates
- **G0:** code generation, deterministic C↔Python tests and Lean proofs all pass.
- **G1:** policy executes in disposable VM without invalid action; controller crash leaves stock Linux memory reclaim functional.
- **G2:** paired randomized replicates show consistent improvement on held-out workload traces; no OOM increase or unacceptable p95 regression.
- **G3 (future):** independent kernel-policy replacement passes reviewer audit, lock analysis, state migration and rollback failure injection.

Never claim that passing G0 or G1 establishes SOTA, production readiness or full MGLRU replacement.
