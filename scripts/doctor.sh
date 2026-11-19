#!/usr/bin/env bash
set -u
printf '%s\n' 'Memory Policy Synthesis environment diagnostic (read only)'
uname -srvm
printf 'Virtualization: '; systemd-detect-virt --vm 2>/dev/null || echo 'not detected'
printf 'cgroup fs: '; stat -fc '%T' /sys/fs/cgroup 2>/dev/null || true
printf 'cgroup mount flags: '; findmnt -n -o OPTIONS /sys/fs/cgroup 2>/dev/null || true
printf 'MGLRU enabled bits: '; cat /sys/kernel/mm/lru_gen/enabled 2>/dev/null || echo 'not available'
printf '%s\n' 'Swap devices:'; cat /proc/swaps
printf 'memory controller: '; grep -w memory /sys/fs/cgroup/cgroup.controllers 2>/dev/null || echo 'not delegated'
printf 'Lean: '; if command -v lean >/dev/null; then lean --version; else echo 'missing'; fi
printf 'Compiler: '; command -v gcc || true
printf '%s\n' 'No system settings have been changed.'
