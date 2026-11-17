#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct Tile
{
    uint32_t lanes[8];
    uint32_t parity;
    unsigned used;
    unsigned width;
    unsigned long offset;
    unsigned long number;
};

static uint32_t mix(uint32_t value)
{
    value ^= value >> 16;
    value *= UINT32_C(0x45d9f3b);
    value ^= value >> 16;
    return value;
}

static void reset(struct Tile *tile)
{
    for (unsigned i = 0; i < 8; i++)
        tile->lanes[i] = i + 1;
    tile->parity = 0;
    tile->used = 0;
}

static void push(struct Tile *tile, unsigned byte)
{
    unsigned lane = tile->used % 8;
    uint32_t value = tile->lanes[lane];
    value = mix(value + byte + tile->used);
    tile->lanes[lane] = value;
    tile->parity ^= (uint32_t)byte << (8 * (tile->used % 4));
    tile->used++;
    tile->offset++;
}

static uint32_t digest(const struct Tile *tile)
{
    uint32_t value = tile->parity;
    for (unsigned i = 0; i < 8; i++)
        value = mix(value ^ tile->lanes[i]);
    return value ^ tile->used;
}

static void report(struct Tile *tile, int detailed)
{
    printf("%lu %u %08x", tile->number, tile->used, digest(tile));
    if (detailed)
    {
        for (unsigned i = 0; i < 8; i++)
            printf(" %08x", tile->lanes[i]);
        printf(" %08x", tile->parity);
    }
    putchar('\n');
    tile->number++;
}

static int parse(const char *text, unsigned *value)
{
    char *end;
    unsigned long result = strtoul(text, &end, 10);
    if (!*text || *end || result < 1 || result > 65536)
        return 0;
    *value = (unsigned)result;
    return 1;
}

static int hex(int c)
{
    if (c >= '0' && c <= '9')
        return c - '0';
    if (c >= 'a' && c <= 'f')
        return c - 'a' + 10;
    if (c >= 'A' && c <= 'F')
        return c - 'A' + 10;
    return -1;
}

static int next_byte(FILE *input, int hexadecimal, int *invalid)
{
    int high = fgetc(input);
    if (!hexadecimal)
        return high;
    while (high == ' ' || high == '\n' || high == '\t' || high == '\r')
        high = fgetc(input);
    if (high == EOF)
        return EOF;
    int low = fgetc(input);
    if (hex(high) < 0 || hex(low) < 0)
    {
        *invalid = 1;
        return EOF;
    }
    return hex(high) * 16 + hex(low);
}

static void histogram(FILE *input)
{
    unsigned long bins[16] = {0};
    unsigned long count = 0;
    int byte;
    while ((byte = fgetc(input)) != EOF)
    {
        bins[(unsigned)byte >> 4]++;
        count++;
    }
    unsigned long largest = 0;
    unsigned occupied = 0;
    unsigned peak = 0;
    for (unsigned i = 0; i < 16; i++)
    {
        printf("%x %lu\n", i, bins[i]);
        if (bins[i])
        {
            occupied++;
        }
        if (bins[i] > largest)
        {
            largest = bins[i];
            peak = i;
        }
    }
    printf("occupied %u\n", occupied);
    printf("peak %x %lu\n", peak, largest);
    printf("bytes %lu\n", count);
}

static int process(FILE *input, struct Tile *tile, int hexadecimal,
                   int detailed, int cumulative)
{
    int invalid = 0;
    int byte;
    unsigned in_block = 0;
    while ((byte = next_byte(input, hexadecimal, &invalid)) != EOF)
    {
        push(tile, (unsigned)byte);
        in_block++;
        if (in_block == tile->width)
        {
            report(tile, detailed);
            if (!cumulative)
                reset(tile);
            in_block = 0;
        }
    }
    if (invalid)
    {
        fputs("Invalid hexadecimal input\n", stderr);
        return 3;
    }
    if (in_block || tile->offset == 0)
        report(tile, detailed);
    printf("bytes %lu\n", tile->offset);
    return 0;
}

int main(int argc, char **argv)
{
    struct Tile tile = {{0}, 0, 0, 64, 0, 0};
    int hexadecimal = 0;
    int hist = 0;
    int detailed = 0;
    int cumulative = 0;
    int index = 1;
    FILE *input = stdin;
    reset(&tile);
    while (index < argc && argv[index][0] == '-')
    {
        const char *option = argv[index++];
        if (!strcmp(option, "-h"))
        {
            hist = 1;
        }
        else if (!strcmp(option, "-x"))
        {
            hexadecimal = 1;
        }
        else if (!strcmp(option, "-d"))
        {
            detailed = 1;
        }
        else if (!strcmp(option, "-c"))
        {
            cumulative = 1;
        }
        else if (!strcmp(option, "-w"))
        {
            if (index == argc)
            {
                fputs("Missing tile width\n", stderr);
                return 2;
            }
            if (!parse(argv[index++], &tile.width))
            {
                fputs("Invalid tile width\n", stderr);
                return 2;
            }
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
    int result = 0;
    if (hist)
    {
        histogram(input);
    }
    else
    {
        result = process(input, &tile, hexadecimal, detailed, cumulative);
    }
    if (input != stdin)
        fclose(input);
    return result;
}
