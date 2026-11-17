#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct Codec
{
    const char *alphabet;
    unsigned radix;
    unsigned width;
    int reverse;
    int check;
    unsigned long count;
    uint32_t sum;
};

static const char alphabet[] = "0123456789ABCDEFGHJKLMNPQRSTUVWXYZ";

static unsigned digits_needed(unsigned radix)
{
    unsigned width = 1;
    unsigned capacity = radix;
    while (capacity < 256)
    {
        width++;
        capacity *= radix;
    }
    return width;
}

static void update(struct Codec *codec, unsigned byte)
{
    codec->count++;
    codec->sum = (codec->sum * 33 + byte + 1) % 65521;
}

static void emit_byte(struct Codec *codec, unsigned byte)
{
    char digits[8];
    unsigned value = byte;
    for (unsigned i = 0; i < codec->width; i++)
    {
        digits[i] = codec->alphabet[value % codec->radix];
        value /= codec->radix;
    }
    for (unsigned i = 0; i < codec->width; i++)
    {
        unsigned position;
        if (codec->reverse)
            position = i;
        else
            position = codec->width - i - 1;
        putchar(digits[position]);
    }
    update(codec, byte);
}

static int encode(FILE *input, struct Codec *codec)
{
    int byte;
    while ((byte = fgetc(input)) != EOF)
        emit_byte(codec, (unsigned)byte);
    if (codec->check)
        printf("!%04x", codec->sum);
    putchar('\n');
    return 0;
}

static int digit_value(const struct Codec *codec, int c)
{
    for (unsigned i = 0; i < codec->radix; i++)
    {
        if (codec->alphabet[i] == c)
            return (int)i;
    }
    return -1;
}

static int checksum(FILE *input, const struct Codec *codec)
{
    unsigned expected = 0;
    for (unsigned i = 0; i < 4; i++)
    {
        int c = fgetc(input);
        unsigned digit;
        if (c >= '0' && c <= '9')
            digit = (unsigned)(c - '0');
        else if (c >= 'a' && c <= 'f')
            digit = (unsigned)(c - 'a' + 10);
        else
        {
            fputs("Invalid checksum text\n", stderr);
            return 3;
        }
        expected = expected * 16 + digit;
    }
    int end;
    do
    {
        end = fgetc(input);
    } while (end == '\n' || end == ' ' || end == '\r');
    if (end != EOF)
    {
        fputs("Data after checksum\n", stderr);
        return 3;
    }
    if (expected != codec->sum)
    {
        fputs("Checksum mismatch\n", stderr);
        return 3;
    }
    return 0;
}

static int decode(FILE *input, struct Codec *codec)
{
    unsigned value = 0;
    unsigned place = 1;
    unsigned used = 0;
    int c;
    while ((c = fgetc(input)) != EOF)
    {
        if (c == ' ' || c == '\n' || c == '\r')
            continue;
        if (c == '!' && codec->check && used == 0)
            return checksum(input, codec);
        int digit = digit_value(codec, c);
        if (digit < 0)
        {
            fputs("Invalid token digit\n", stderr);
            return 3;
        }
        if (codec->reverse)
        {
            value += (unsigned)digit * place;
            place *= codec->radix;
        }
        else
        {
            value = value * codec->radix + (unsigned)digit;
        }
        used++;
        if (used == codec->width)
        {
            if (value > 255)
            {
                fputs("Token exceeds byte range\n", stderr);
                return 3;
            }
            putchar((int)value);
            update(codec, value);
            value = 0;
            used = 0;
            place = 1;
        }
    }
    if (used)
    {
        fputs("Incomplete token\n", stderr);
        return 3;
    }
    if (codec->check)
    {
        fputs("Missing checksum\n", stderr);
        return 3;
    }
    return 0;
}

static int radix_value(const char *text, unsigned *radix)
{
    char *end;
    unsigned long value = strtoul(text, &end, 10);
    if (!*text || *end || value < 2 || value > 34)
        return 0;
    *radix = (unsigned)value;
    return 1;
}

static void describe(const struct Codec *codec)
{
    printf("radix %u\n", codec->radix);
    printf("width %u\n", codec->width);
    fputs("alphabet ", stdout);
    for (unsigned i = 0; i < codec->radix; i++)
        putchar(codec->alphabet[i]);
    putchar('\n');
    unsigned capacity = 1;
    for (unsigned i = 0; i < codec->width; i++)
        capacity *= codec->radix;
    printf("unused %u\n", capacity - 256);
    printf("order %s\n", codec->reverse ? "low" : "high");
    printf("check %s\n", codec->check ? "yes" : "no");
}

int main(int argc, char **argv)
{
    struct Codec codec = {alphabet, 16, 2, 0, 0, 0, 0};
    int mode = 0;
    int summary = 0;
    int index = 1;
    FILE *input = stdin;
    while (index < argc && argv[index][0] == '-')
    {
        const char *option = argv[index++];
        if (!strcmp(option, "-s"))
        {
            summary = 1;
        }
        else if (!strcmp(option, "-d"))
        {
            mode = 1;
        }
        else if (!strcmp(option, "-i"))
        {
            mode = 2;
        }
        else if (!strcmp(option, "-r"))
        {
            codec.reverse = 1;
        }
        else if (!strcmp(option, "-c"))
        {
            codec.check = 1;
        }
        else if (!strcmp(option, "-b"))
        {
            if (index == argc)
            {
                fputs("Missing radix\n", stderr);
                return 2;
            }
            if (!radix_value(argv[index++], &codec.radix))
            {
                fputs("Invalid radix\n", stderr);
                return 2;
            }
            codec.width = digits_needed(codec.radix);
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
    int result;
    if (mode == 1)
        result = decode(input, &codec);
    else if (mode == 2)
    {
        describe(&codec);
        result = 0;
    }
    else
        result = encode(input, &codec);
    if (input != stdin)
        fclose(input);
    if (summary)
    {
        fprintf(stderr, "bytes %lu\n", codec.count);
        fprintf(stderr, "checksum %04x\n", codec.sum);
        fprintf(stderr, "symbols %lu\n", codec.count * codec.width);
    }
    return result;
}
