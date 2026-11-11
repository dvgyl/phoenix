#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

typedef uint64_t (*recursive_function)(uint64_t, uint64_t, uint64_t, uint64_t);
typedef void (*empty_function)(void);

__attribute__((noinline)) static uint64_t recurse(
    uint64_t depth, uint64_t first, uint64_t second, uint64_t third);

static recursive_function volatile recursive_step = recurse;

__attribute__((noinline, used)) static void empty(void) {}

static empty_function volatile first_empty = empty;
static empty_function volatile second_empty = empty;

__attribute__((noinline)) static void sequence(void) {
    empty_function first = first_empty;
    empty_function second = second_empty;
    first();
    second();
}

__attribute__((noinline)) static uint64_t recurse(
    uint64_t depth, uint64_t first, uint64_t second, uint64_t third) {
    if (depth == 0) {
        return (first ^ second) + third;
    }
    uint64_t result = recursive_step(
        depth - 1,
        first + UINT64_C(0x102030405060708),
        second ^ (depth * UINT64_C(0x1111111111111111)),
        (third << 7) | (third >> 57));
    return ((result ^ (first + third)) + (second | UINT64_C(1)))
        * UINT64_C(0x100000001b3) + depth;
}

int main(int argc, char **argv) {
    char *end = NULL;
    unsigned long depth = 2;
    if (argc > 2) {
        return 64;
    }
    if (argc == 2) {
        depth = strtoul(argv[1], &end, 10);
        if (*argv[1] == '\0' || *end != '\0' || depth > 8) {
            return 64;
        }
    }
    int input = getchar();
    uint64_t value = input == EOF ? 0 : (unsigned char)input;
    sequence();
    uint64_t result = recursive_step(
        depth,
        UINT64_C(0x1122334455667700) + value,
        UINT64_C(0x8877665544332200) ^ value,
        UINT64_C(0x13579bdf2468ace0) + depth);
    printf("%" PRIu64 "\n", result);
    return 0;
}
