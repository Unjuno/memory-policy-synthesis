# Memory Policy Synthesis

**Research scaffolding v0.1 — policy synthesis, Lean 4 abstract proofs and Linux cgroup v2 experiments.**

> **Status:** This repository is a **stage-0 userspace experiment**, **not** a patched Linux MGLRU, a trained neural model, or a demonstrated SOTA result. It is intended as the first safe workspace for a coding agent to iterate on candidate algorithms. The actual MGLRU replacement is a subsequent research milestone.

## Frozen research direction

The long-term objective is to replace **Linux MGLRU anonymous-page reclaim decisions** with a lightweight, compiled policy discovered through model imitation and agentic optimization. The generated policy must run without neural inference on the reclaim hot path. Existing kernel page ownership, locking, mapping, reclaim execution and swap remain in conventional kernel code. Faulty policies must be rejected or rolled back to MGLRU before irrecoverable kernel corruption.

Stage 0 is deliberately smaller: control **proactive** reclaim through cgroup v2 `memory.reclaim` inside a disposable virtual machine. This tests agent iteration and benchmarking, **not** per-folio replacement. See [research design](docs/RESEARCH.md) and [agent rules](AGENTS.md).

## Included

| Path | Purpose |
|---|---|
| `policies/candidate.json` | Restricted expression-tree policy which agents may mutate |
| `tools/policy_lib.py` | Python reference semantics and structural validation |
| `tools/compile_policy.py` | Generates C policy and Lean expression |
| `formal/MemoryPolicy.lean` | Proves abstract per-call cap, anonymous-memory bound and active-process no-op |
| `formal/Candidate.lean` | Generated instantiation of abstract theorems |
| `src/workload.c` | Anonymous-memory page-touch process with controlled RUN requests |
| `tools/bench.py` | **Root + disposable VM only** cgroup memory-reclaim benchmark |
| `tools/compare.py` | Exploratory comparison of equivalent experiment JSON logs |
| `scripts/doctor.sh` | Read-only system capabilities diagnostic |
| `scripts/prepare_guest.sh` | Prepare a dedicated memory-limited cgroup inside a **confirmed VM only** |
| `.github/workflows/ci.yml` | Build, differential tests and Lean 4 proof checks |

## 1. Compile / test on ordinary Linux

Prerequisites: GCC, Make and Python 3.10+.

```bash
make check
./build/policy 12 262144 2 32768
./scripts/doctor.sh
```

This compiles the generated C policy and a synthetic memory workload, runs Python↔C differential tests plus a small workload smoke test. No root or kernel modification is needed. The policy CLI arguments are, in order: `idle_sec anon_kib psi_pct max_reclaim_kib`. It outputs requested reclaim in KiB, **not** a success indication from Linux.

### Lean 4 verification

Install Lean 4 version `v4.36.0` using [the official Lean/elan instructions](https://lean-lang.org/install/manual/) and ensure `lean` is on `PATH`. Then run:

```bash
make formal
```

The policy generator emits `formal/Candidate.lean`; this invokes three general theorems from `formal/MemoryPolicy.lean`. The proven invariants are *only* properties of the mathematical expression-tree wrapper:

- Requested reclaim never exceeds the per-action cap.
- Requested reclaim never exceeds the provided anonymous-memory capacity.
- No proactive reclaim is requested for `idle_sec = 0`.

**Lean does not prove** generated C refines this mathematical implementation, that the kernel actually reclaims the requested bytes, rollback correctness, absence of deadlocks, safety of an MGLRU patch, or any performance benefit. C↔Python randomized testing gives limited implementation cross-checking only.

## 2. Experiment inside a disposable Linux VM (never on the host)

Suggested VM: x86-64 Ubuntu 24.04+ or similar, Linux with MGLRU enabled, 2 vCPUs, 3–4 GiB RAM, available swap or zram, writable cgroup v2, GCC and Python. These are *starting settings*, not benchmark results. KVM on the host is convenient, but a cloud VM is also acceptable. Ensure the guest reports itself as a VM via `systemd-detect-virt --vm`.

**Inside the disposable VM only:**

```bash
make check
./scripts/doctor.sh
# Confirm kernel reports nonzero MGLRU enablement, swap is configured,
# and /sys/fs/cgroup is writable before running experiments.
sudo ./scripts/prepare_guest.sh --confirm-disposable-vm 640
sudo python3 tools/bench.py --policy baseline \
  --cgroup /sys/fs/cgroup/mps-lab --confirm-disposable-vm \
  --out results/baseline-01.json
sudo python3 tools/bench.py --policy fixed \
  --cgroup /sys/fs/cgroup/mps-lab --confirm-disposable-vm \
  --out results/fixed-01.json
sudo python3 tools/bench.py --policy candidate \
  --cgroup /sys/fs/cgroup/mps-lab --confirm-disposable-vm \
  --out results/candidate-01.json
python3 tools/compare.py results/baseline-01.json results/candidate-01.json
```

**Safety:** `prepare_guest.sh` *only* changes cgroup configuration inside a detected VM; it does **not** automatically configure swap. `bench.py` refuses to run without root, `--confirm-disposable-vm`, a detected VM, a finite `memory.max`, and a dedicated `/sys/fs/cgroup/mps-lab*` hierarchy. The same host should **never** be used for production workloads. Each run can create pressure and invoke OOM; take a snapshot and use a disposable guest. If swap or required controllers are missing, provision the VM rather than forcing the command.

The initial defaults are 3 processes × 256 MiB anonymous allocations, parent group `memory.max=640 MiB`, 3 warmup + 12 measured full-page sweeps, 2 seconds between rounds, and a 32 MiB reclaim cap per action. Parent `memory.max` is **not** the same as physically removing RAM from the guest. `memory.reclaim` is a reclaim *request*, not a guarantee of actual bytes freed. The benchmark's p95 measures full-page sweep latency, not the responsiveness of an Electron GUI. Re-run with balanced/randomized order and restored VM snapshots; one run proves nothing statistically.

## 3. Agentic development loop

Agent instructions are in [`AGENTS.md`](AGENTS.md). A permitted candidate edit is generally a modification to `policies/candidate.json`, e.g., rewriting the expression-tree algorithm. Each candidate must:

1. Pass `make check && make formal` (Lean unavailable = **UNVERIFIED**, not a pass).
2. Run against unchanged baseline/fixed policies in the disposable VM.
3. Record policy SHA256, generated C SHA256, kernel, CPU, governor/clock, memory configuration, workload sequence, swap configuration and full overhead.
4. Reject crashes/OOM, repeated regressions, or missing proof. Do not claim SOTA based on synthetic stage-0 traces.

The next milestone is a carefully audited **custom kernel decision-interface patch** and a demonstrated return path to stock MGLRU. That patch does not yet exist in this repository.

## Licensing and publication

This repository contains no open-source license. Its GitHub visibility is managed in repository settings. Choose a license before inviting third-party reuse; set visibility to Private if public access was not intended.
