#!/usr/bin/env python3
"""VM-only, root-only cgroup v2 userspace reclaim experiment.

WARNING: This does NOT replace Linux MGLRU. It controls proactive cgroup reclaim.
Never run on a production host or in an unisolated system.
"""
from __future__ import annotations
import argparse
import json
import os
import platform
import re
import select
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / 'build' / 'policy'
WORKLOAD = ROOT / 'build' / 'workload'


def get_vm_status() -> bool:
    if shutil.which('systemd-detect-virt') is None:
        return False
    return subprocess.run(['systemd-detect-virt', '--quiet', '--vm']).returncode == 0


def read_stats(group: Path) -> dict:
    stats = {}
    for fname in ('memory.current', 'memory.swap.current'):
        try:
            stats[fname] = int((group / fname).read_text().strip())
        except FileNotFoundError:
            stats[fname] = None
    for fname in ('memory.events', 'memory.stat'):
        try:
            values = {}
            for line in (group / fname).read_text().splitlines():
                name, val = line.split()
                values[name] = int(val)
            stats[fname] = values
        except FileNotFoundError:
            stats[fname] = {}
    try:
        stats['memory.pressure'] = (group / 'memory.pressure').read_text().strip()
    except FileNotFoundError:
        stats['memory.pressure'] = None
    return stats


def psi_pct(group: Path) -> int:
    try:
        text = (group / 'memory.pressure').read_text()
        m = re.search(r'^some\s+avg10=([0-9.]+)', text, re.M)
        return min(100, max(0, round(float(m.group(1))))) if m else 0
    except (FileNotFoundError, ValueError):
        return 0


def send(worker, command: str) -> str:
    if worker.poll() is not None:
        raise RuntimeError(f'workload died, rc={worker.returncode}')
    worker.stdin.write(command + '\n')
    worker.stdin.flush()
    readable, _, _ = select.select([worker.stdout], [], [], 15)
    if not readable:
        raise RuntimeError('workload response timeout (15 s); fail and clean up')
    answer = worker.stdout.readline().strip()
    if not answer:
        raise RuntimeError('workload EOF')
    if answer.startswith('ERROR'):
        raise RuntimeError(answer)
    return answer


def request_reclaim(group: Path, amount_kib: int) -> str:
    if amount_kib == 0:
        return 'skipped'
    data = f'{amount_kib * 1024} swappiness=max'
    try:
        (group / 'memory.reclaim').write_text(data)
        return 'accepted'
    except OSError as e:
        # EAGAIN means reclaim progress did not satisfy the request; record explicitly.
        if e.errno == 11:
            return 'eagain'
        raise RuntimeError(f'memory.reclaim rejected {data!r} in {group}: {e}') from e


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--policy', required=True, choices=('baseline', 'fixed', 'candidate'))
    ap.add_argument('--cgroup', required=True, help='precreated dedicated cgroup v2 parent; must have memory.max set')
    ap.add_argument('--out', required=True)
    ap.add_argument('--confirm-disposable-vm', action='store_true')
    ap.add_argument('--mib-per-worker', type=int, default=256)
    ap.add_argument('--workers', type=int, default=3)
    ap.add_argument('--warmups', type=int, default=3)
    ap.add_argument('--rounds', type=int, default=12)
    ap.add_argument('--sleep', type=float, default=2)
    ap.add_argument('--cap-kib', type=int, default=32768)
    args = ap.parse_args()
    if not args.confirm_disposable_vm or not get_vm_status() or os.geteuid() != 0:
        sys.exit('REFUSED: requires root, --confirm-disposable-vm and verified virtual machine')
    if args.workers < 2 or args.workers > 8 or args.mib_per_worker < 1 or args.mib_per_worker > 1024:
        sys.exit('REFUSED: requested workload is outside safety bounds')
    if args.rounds < 1 or args.rounds > 100 or args.warmups < 0 or args.warmups > 10:
        sys.exit('REFUSED: invalid round count')
    if not 0.1 <= args.sleep <= 30 or not 0 <= args.cap_kib <= 32768:
        sys.exit('REFUSED: invalid interval / reclaim cap')
    parent = Path(args.cgroup).resolve()
    if not str(parent).startswith('/sys/fs/cgroup/mps-lab') or not (parent/'memory.max').exists():
        sys.exit('REFUSED: use a dedicated /sys/fs/cgroup/mps-lab* parent with memory.max')
    if (parent/'memory.max').read_text().strip() == 'max':
        sys.exit('REFUSED: parent memory.max must be finite')
    try:
        mglru_bits = int(Path('/sys/kernel/mm/lru_gen/enabled').read_text().strip(), 0)
    except (OSError, ValueError):
        sys.exit('REFUSED: cannot read MGLRU enabled bits')
    if mglru_bits == 0:
        sys.exit('REFUSED: MGLRU is not enabled')
    swaps = Path('/proc/swaps').read_text().splitlines()
    if len(swaps) < 2:
        sys.exit('REFUSED: no active swap; anonymous-page reclaim needs swap backing')
    if args.policy == 'candidate' and not POLICY.exists():
        sys.exit('Missing compiled policy: run make check')
    if not WORKLOAD.exists():
        sys.exit('Missing workload: run make check')
    if not (parent / 'cgroup.subtree_control').exists():
        sys.exit('REFUSED: no cgroup v2 subtree control')
    if (parent / 'cgroup.procs').read_text().strip():
        sys.exit('REFUSED: parent cgroup contains tasks; it must be empty')

    # Enabling +memory inside a dedicated, task-free parent. Does not touch host swap.
    ctl = (parent / 'cgroup.subtree_control').read_text().split()
    if 'memory' not in ctl:
        (parent / 'cgroup.subtree_control').write_text('+memory')

    children: list[Path] = []
    processes = []
    latencies = []
    actions = []
    start_stats = read_stats(parent)
    start = time.monotonic()
    last_active = [start] * args.workers
    try:
        for i in range(args.workers):
            path = parent / f'worker-{i}'
            path.mkdir(exist_ok=False)
            children.append(path)
            child = subprocess.Popen([str(WORKLOAD), str(args.mib_per_worker)],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True, bufsize=1)
            processes.append(child)
            readable, _, _ = select.select([child.stdout], [], [], 15)
            if not readable or child.stdout.readline().strip() != 'WAITING':
                raise RuntimeError('workload did not enter waiting state')
            (path / 'cgroup.procs').write_text(str(child.pid))
            if send(child, 'INIT') != 'READY':
                raise RuntimeError('workload initialization failed')
        for turn in range(args.warmups + args.rounds):
            active = turn % args.workers
            for j, (path, proc) in enumerate(zip(children, processes)):
                if j == active:
                    continue
                idle_sec = int(max(0.0, time.monotonic()-last_active[j]))
                anon_kib = read_stats(path)['memory.stat'].get('anon', 0)//1024
                p = psi_pct(path)
                if args.policy == 'baseline':
                    req = 0
                elif args.policy == 'fixed':
                    req = min(args.cap_kib, anon_kib//10) if idle_sec >= 3 else 0
                else:
                    output = subprocess.check_output([str(POLICY), str(idle_sec),
                                     str(anon_kib), str(p), str(args.cap_kib)], text=True)
                    req = int(output.strip())
                if not 0 <= req <= min(anon_kib, args.cap_kib):
                    raise RuntimeError(f'invalid policy output {req}')
                status = request_reclaim(path, req)
                actions.append({'turn': turn, 'worker': j, 'idle_sec': idle_sec,
                                'requested_kib': req, 'status': status})
            response = send(processes[active], 'RUN')
            match = re.fullmatch(r'LATENCY_NS (\d+) CHECKSUM (\d+)', response)
            if not match:
                raise RuntimeError(f'bad workload result: {response}')
            last_active[active] = time.monotonic()
            if turn >= args.warmups:
                latencies.append(int(match.group(1)))
            time.sleep(args.sleep)
        end_stats = read_stats(parent)
        if end_stats['memory.events'].get('oom_kill', 0) > start_stats['memory.events'].get('oom_kill', 0):
            raise RuntimeError('OOM kill detected: mark this experiment FAIL')
        sorted_ns = sorted(latencies)
        p95_ns = sorted_ns[max(0, (95 * len(sorted_ns)+99)//100-1)]
        report = {'stage': 'userspace_reclaim_not_MGLRU_replacement',
                  'policy': args.policy, 'kernel': platform.release(),
                  'machine': platform.machine(), 'cgroup': str(parent),
                  'config': {'workers': args.workers, 'mib_per_worker': args.mib_per_worker,
                             'warmups': args.warmups, 'rounds': args.rounds,
                             'sleep': args.sleep, 'cap_kib': args.cap_kib,
                             'memory_max': (parent/'memory.max').read_text().strip()},
                  'duration_s': time.monotonic()-start,
                  'latency_ns': latencies, 'p95_ns': p95_ns,
                  'median_ns': statistics.median(latencies), 'actions': actions,
                  'start': start_stats, 'end': end_stats}
        output_file = Path(args.out)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json.dumps(report, indent=2)+'\n')
        print(f'Wrote {output_file} (p95={p95_ns/1e6:.3f} ms)')
    finally:
        for proc in processes:
            if proc.poll() is None:
                try:
                    proc.stdin.write('QUIT\n')
                    proc.stdin.flush()
                    proc.wait(timeout=2)
                except (OSError, subprocess.TimeoutExpired):
                    proc.kill()
                    proc.wait(timeout=3)
            for pipe in (proc.stdin, proc.stdout, proc.stderr):
                if pipe:
                    pipe.close()
        for path in reversed(children):
            try:
                path.rmdir()
            except OSError as e:
                print(f'WARNING: cgroup cleanup needed: {path}: {e}', file=sys.stderr)

if __name__ == '__main__':
    main()
