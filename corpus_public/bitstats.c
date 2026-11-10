#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifndef PHOENIX_MUTANT
#define PHOENIX_MUTANT 0
#endif

int main(int argc, char **argv) {
    if (argc != 2 || (strcmp(argv[1], "sum") && strcmp(argv[1], "count"))) {
        fputs(PHOENIX_MUTANT == 1 ? "usage error\n" : "use sum or count\n", stderr);
        return PHOENIX_MUTANT == 2 ? 4 : 3;
    }

    uint32_t sum = 0;
    uint32_t count = 0;
    int byte;
    while ((byte = getchar()) != EOF) {
        sum += (uint32_t)byte;
        count++;
    }

    if (strcmp(argv[1], "sum") == 0) {
        printf("%u\n", sum + (PHOENIX_MUTANT == 3));
    } else {
        printf("%u\n", count + (PHOENIX_MUTANT == 4));
    }
    if (getenv("PHOENIX_TAG") != NULL && PHOENIX_MUTANT != 5) {
        puts(getenv("PHOENIX_TAG"));
    }
    return 0;
}
