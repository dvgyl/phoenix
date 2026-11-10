#include <stdio.h>
#include <string.h>
#include <sys/stat.h>

#ifndef PHOENIX_MUTANT
#define PHOENIX_MUTANT 0
#endif

int main(int argc, char **argv) {
    if (argc != 2 || strcmp(argv[1], "write") != 0) {
        return 2;
    }
    FILE *input = fopen("input", "rb");
    if (input == NULL) {
        fputs("missing input\n", stderr);
        return 5;
    }
    if (mkdir("output", PHOENIX_MUTANT == 1 ? 0755 : 0700) != 0) {
        fclose(input);
        return 6;
    }
    const char *path = PHOENIX_MUTANT == 2 ? "output/log" : "output/result";
    FILE *output = fopen(path, "wb");
    if (output == NULL) {
        fclose(input);
        return 7;
    }

    unsigned int count = 0;
    int byte;
    while ((byte = fgetc(input)) != EOF) {
        fputc(byte ^ (PHOENIX_MUTANT == 3 ? 0x5a : 0xa5), output);
        count++;
    }
    fclose(input);
    if (fclose(output) != 0 || chmod(path, PHOENIX_MUTANT == 4 ? 0644 : 0600) != 0) {
        return 8;
    }
    if (PHOENIX_MUTANT == 5) {
        remove("input");
    }
    printf("%u\n", count);
    return 0;
}
