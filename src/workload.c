/* Deterministic anonymous-memory working-set workload. Does not free other processes' pages. */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>

static uint64_t ns_now(void) {
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t) != 0) { perror("clock_gettime"); exit(1); }
    return (uint64_t)t.tv_sec * UINT64_C(1000000000) + (uint64_t)t.tv_nsec;
}
int main(int argc, char **argv) {
    if (argc != 2) { fprintf(stderr, "usage: workload allocation_mib\n"); return 2; }
    char *end = NULL;
    errno = 0;
    unsigned long long mib = strtoull(argv[1], &end, 10);
    if (errno || !end || *end || mib < 1 || mib > 4096) return 2;
    size_t len = (size_t)mib * 1024 * 1024;
    unsigned char *mem = NULL;
    char line[32];
    setvbuf(stdout, NULL, _IOLBF, 0);
    puts("WAITING");
    while (fgets(line, sizeof line, stdin)) {
        if (strncmp(line, "INIT", 4) == 0 && !mem) {
            mem = mmap(NULL, len, PROT_READ | PROT_WRITE,
                       MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
            if (mem == MAP_FAILED) { perror("mmap"); return 1; }
            for (size_t i = 0; i < len; i += 4096) mem[i] = (unsigned char)(i >> 12);
            puts("READY");
        } else if (strncmp(line, "RUN", 3) == 0 && mem) {
            uint64_t start = ns_now();
            volatile uint64_t check = 0;
            for (size_t i = 0; i < len; i += 4096) check += mem[i];
            printf("LATENCY_NS %" PRIu64 " CHECKSUM %" PRIu64 "\n", ns_now() - start, (uint64_t)check);
        } else if (strncmp(line, "QUIT", 4) == 0) {
            break;
        } else {
            puts("ERROR bad command");
        }
    }
    if (mem) munmap(mem, len);
    return 0;
}
