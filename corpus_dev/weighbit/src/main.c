#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint32_t rotate(uint32_t value, unsigned count)
{
    return (value << count) | (value >> (32 - count));
}

int main(int argc, char **argv)
{
    uint32_t state = UINT32_C(0x31415926);
    uint32_t total = 0;
    unsigned long length = 0;
    unsigned rotation = 5;
    int value;
    FILE *input = stdin;
    if (argc < 2 || argc > 3)
    {
        fputs("Use: weighbit rotation [file]\n", stderr);
        return 2;
    }
    char *end;
    unsigned long parsed = strtoul(argv[1], &end, 10);
    if (*end || parsed < 1 || parsed > 31)
    {
        fputs("Rotation must be 1 to 31\n", stderr);
        return 2;
    }
    rotation = (unsigned)parsed;
    if (argc == 3)
    {
        input = fopen(argv[2], "rb");
        if (input == NULL)
        {
            fputs("Cannot open input\n", stderr);
            return 4;
        }
    }
    while ((value = fgetc(input)) != EOF)
    {
        state = rotate(state ^ (uint32_t)value, rotation);
        total += (uint32_t)value;
        if (value & 1)
            state += UINT32_C(0x9e3779b9);
        else
            state ^= total;
        length++;
    }
    if (input != stdin)
        fclose(input);
    printf("%08x %u %lu\n", state, total, length);
    return 0;
}
