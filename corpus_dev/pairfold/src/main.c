#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct Fold
{
    uint32_t left;
    uint32_t right;
    unsigned long count;
    unsigned width;
    uint32_t prime;
};

static void update(struct Fold *fold, unsigned byte)
{
    fold->left = (fold->left + byte + 1) % fold->prime;
    fold->right = (fold->right + fold->left) % fold->prime;
    fold->count++;
}

static void report(const struct Fold *fold, unsigned long block)
{
    printf("%lu:%lu:%u:%u\n", block, fold->count, fold->left, fold->right);
}

static int number(const char *text, unsigned long limit, unsigned *value)
{
    char *end;
    unsigned long parsed = strtoul(text, &end, 10);
    if (!*text || *end || parsed < 1 || parsed > limit)
        return 0;
    *value = (unsigned)parsed;
    return 1;
}

static int process(FILE *input, struct Fold *fold, int chunks)
{
    unsigned used = 0;
    unsigned long block = 0;
    int byte;
    while ((byte = fgetc(input)) != EOF)
    {
        update(fold, (unsigned)byte);
        used++;
        if (chunks && used == fold->width)
        {
            report(fold, block++);
            fold->left = 0;
            fold->right = 0;
            fold->count = 0;
            used = 0;
        }
    }
    if (!chunks || used)
        report(fold, block);
    return 0;
}

int main(int argc, char **argv)
{
    struct Fold fold = {0, 0, 0, 16, 251};
    int chunks = 0;
    int index = 1;
    FILE *input = stdin;
    while (index < argc && argv[index][0] == '-')
    {
        const char *option = argv[index++];
        if (!strcmp(option, "-c"))
            chunks = 1;
        else if (!strcmp(option, "-w"))
        {
            if (index == argc || !number(argv[index++], 4096, &fold.width))
            {
                fputs("Invalid block width\n", stderr);
                return 2;
            }
        }
        else if (!strcmp(option, "-p"))
        {
            unsigned prime;
            if (index == argc || !number(argv[index++], 65521, &prime))
            {
                fputs("Invalid modulus\n", stderr);
                return 2;
            }
            fold.prime = prime;
        }
        else
        {
            fputs("Invalid option\n", stderr);
            return 2;
        }
    }
    if (argc - index > 1)
    {
        fputs("Too many files\n", stderr);
        return 2;
    }
    if (index < argc)
    {
        input = fopen(argv[index], "rb");
        if (!input)
        {
            fputs("Cannot open input\n", stderr);
            return 4;
        }
    }
    int result = process(input, &fold, chunks);
    if (input != stdin)
        fclose(input);
    return result;
}
