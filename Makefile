PYTHON ?= python3
CC ?= gcc
CFLAGS ?= -std=gnu11 -O2 -Wall -Wextra -Werror
.PHONY: all generate check formal clean
all: check
generate:
	$(PYTHON) tools/compile_policy.py
build/policy: policies/candidate.json tools/compile_policy.py tools/policy_lib.py
	$(PYTHON) tools/compile_policy.py
	$(CC) $(CFLAGS) build/policy.c -o build/policy
build/workload: src/workload.c
	mkdir -p build
	$(CC) $(CFLAGS) src/workload.c -o build/workload
check: build/policy build/workload
	$(PYTHON) -m unittest discover -s tests -v
formal: generate
	@command -v lean >/dev/null || (echo 'Lean 4 is not installed; formal check UNVERIFIED' >&2; exit 1)
	LEAN_PATH=formal lean -o formal/MemoryPolicy.olean formal/MemoryPolicy.lean
	LEAN_PATH=formal lean formal/Candidate.lean
clean:
	rm -rf build formal/*.olean formal/*.ilean
