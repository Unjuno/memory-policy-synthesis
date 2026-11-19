#!/usr/bin/env bash
set -euo pipefail
# PREPARES ONLY A DEDICATED CGROUP INSIDE A DISPOSABLE VM; never alters swap.
if [[ "${EUID}" -ne 0 ]] || ! systemd-detect-virt --quiet --vm; then
  echo 'REFUSED: run as root inside a disposable VM only' >&2
  exit 1
fi
if [[ "${1:-}" != '--confirm-disposable-vm' ]]; then
  echo 'Usage: sudo scripts/prepare_guest.sh --confirm-disposable-vm [memory_limit_mib (default 640)]' >&2
  exit 1
fi
mib="${2:-640}"
if ! [[ "$mib" =~ ^[0-9]+$ ]] || (( mib < 256 || mib > 4096 )); then
  echo 'Invalid memory limit' >&2; exit 1
fi
if [[ ! -f /sys/fs/cgroup/cgroup.controllers ]] || [[ ! -w /sys/fs/cgroup/cgroup.subtree_control ]]; then
  echo 'Missing writable cgroup v2: use a correctly configured isolated guest' >&2; exit 1
fi
if ! grep -qw memory /sys/fs/cgroup/cgroup.controllers; then
  echo 'Memory controller unavailable' >&2; exit 1
fi
if [[ ! -d /sys/fs/cgroup/mps-lab ]]; then
  # This changes root subtree_control only inside an explicitly confirmed VM.
  echo '+memory' > /sys/fs/cgroup/cgroup.subtree_control
  mkdir /sys/fs/cgroup/mps-lab
fi
if [[ -n "$(cat /sys/fs/cgroup/mps-lab/cgroup.procs)" ]]; then
  echo 'Refusing to reuse non-empty cgroup' >&2; exit 1
fi
printf '%s\n' "$(( mib*1024*1024 ))" > /sys/fs/cgroup/mps-lab/memory.max
printf 'Prepared /sys/fs/cgroup/mps-lab with memory.max=%s MiB.\n' "$mib"
printf 'Swap remains unchanged: inspect /proc/swaps before experiments.\n'
