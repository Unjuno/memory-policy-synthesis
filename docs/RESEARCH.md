# Research specification v0.1

## Objective
Find whether an agent-generated and formally gated **fast memory-management policy** can improve Linux's effective memory capacity (minimum physical RAM for a fixed QoS), without modifying applications. The initial target is anonymous-page reclaim decisions surrounding MGLRU in `mm/vmscan.c`, *not* object-level JavaScript GC. The early stage-0 benchmark only drives `memory.reclaim` from userspace and cannot validate true kernel-policy replacement.

## Frozen boundary
- Policy design is learned or agent-generated, deployed as compiled code. No neural inference in the reclaim critical path.
- Phase 1: imitate current Linux behavior. Phase 2: replace decision policy at a future kernel decision interface. Phase 3: automatically improve learned policy with workload outcomes.
- Only decision mechanisms are candidates for replacement. Exact ownership/reference counts, page tables, locking, I/O, allocation correctness remain conventional kernel operations.
- Roll back to the existing MGLRU if generated policy is late, invalid or exhibits pathological behavior. Rollback state consistency MUST be established before kernel deployment; current stage-0 does not implement in-kernel switching.

## Prior work / primary references
- Denning (1968), *The Working Set Model for Program Behavior*, DOI 10.1145/363095.363141.
- Ross et al. (2011), DAgger imitation learning, https://proceedings.mlr.press/v15/ross11a.html.
- AlphaDev (2023), learning program optimization, DOI 10.1038/s41586-023-06004-9.
- `cache_ext` (SOSP 2025), eBPF-customizable Linux page cache, DOI 10.1145/3731569.3764820. **File cache, not direct anonymous MGLRU plug-in.**
- LearnedCache (2026), https://arxiv.org/abs/2605.26168; different page-cache workload/constraints.
- Linux kernel documentation: https://docs.kernel.org/mm/multigen_lru.html, https://docs.kernel.org/admin-guide/cgroup-v2.html.

## Hypothesis / test / decision
- **H:** discovered policies can match MGLRU's safety and app QoS with less physical RAM, net of model/controller overhead.
- **T:** balanced A/B with repeated workloads, multiple distinct memory budgets, process/GUI workload types; hold fixed CPU, guest kernel, swap mode, input and clock. Stage 0 uses only a synthetic anon-working-set probe.
- **PASS:** no new OOM/deadlocks and materially lower RAM needed for QoS on *unseen* workloads, with confidence intervals supporting the effect; formal and differential gates pass.
- **FAIL:** safety gate fails, unexplained OOM, broken rollback, significant performance regression, or no demonstrated benefit.
- **UNCERTAIN:** too few independent traces, VM noise, ambiguous differences or unverified Lean checks.
- **C:** default Linux's reclaim heuristics may already be near optimal and overhead may dominate.
- **U:** guest scheduling, swap I/O, warm caches, app behavior, stochastic training; report variance and confidence intervals; use k=2 expanded uncertainty only when a justified measurement uncertainty model is available.

## Distinguish evaluations
1. **Stage 0:** userspace cgroup reclaim request. It cannot select individual folios or replace kernel MGLRU.
2. **Stage 1:** custom kernel adapter decision boundary, ABI and MGLRU state maintenance. Requires separate code audit and fault-injection tests.
3. **Stage 2:** full RAM/QoS curve, actual desktop traces, application switching, held-out environments.

## Scope limits of formal proof
Lean 4 proves boundedness of an *abstract* action in the policy AST. It does NOT prove the generated C refines it, that `memory.reclaim` applies exactly the requested bytes, or that the Linux kernel will not crash. Python↔C randomized differential testing is additional evidence, not a refinement proof. Keep all safety claims explicit.
