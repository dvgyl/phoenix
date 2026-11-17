#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void emit(int byte, unsigned count)
{
    printf("%02x:%u;", byte, count);
}

static int encode(FILE *input)
{
    int previous = -1;
    unsigned count = 0;
    int byte;
    while ((byte = fgetc(input)) != EOF)
    {
        if (byte == previous && count < 255)
        {
            count++;
            continue;
        }
        if (count)
            emit(previous, count);
        previous = byte;
        count = 1;
    }
    if (count)
        emit(previous, count);
    putchar('\n');
    return 0;
}

static int hex(int c)
{
    if (c >= '0' && c <= '9')
        return c - '0';
    if (c >= 'a' && c <= 'f')
        return c - 'a' + 10;
    return -1;
}

static int decode(FILE *input)
{
    int a;
    while ((a = fgetc(input)) != EOF)
    {
        int b;
        unsigned count = 0;
        int c;
        if (isspace((unsigned char)a))
            continue;
        b = fgetc(input);
        if (hex(a) < 0 || hex(b) < 0 || fgetc(input) != ':')
        {
            fputs("Invalid byte record\n", stderr);
            return 3;
        }
        c = fgetc(input);
        if (c < '0' || c > '9')
        {
            fputs("Missing count\n", stderr);
            return 3;
        }
        do
        {
            count = count * 10 + (unsigned)(c - '0');
            if (count > 255)
            {
                fputs("Count exceeds 255\n", stderr);
                return 3;
            }
            c = fgetc(input);
        } while (c >= '0' && c <= '9');
        if (c != ';' || count == 0)
        {
            fputs("Invalid count terminator\n", stderr);
            return 3;
        }
        while (count--)
            putchar(hex(a) * 16 + hex(b));
    }
    return 0;
}

int main(int argc, char **argv)
{
    FILE *input = stdin;
    int result;
    if (argc < 2 || argc > 3)
    {
        fputs("Use: runepack encode|decode [file]\n", stderr);
        return 2;
    }
    if (strcmp(argv[1], "encode") && strcmp(argv[1], "decode"))
    {
        fputs("Invalid operation\n", stderr);
        return 2;
    }
    if (argc == 3)
    {
        input = fopen(argv[2], "rb");
        if (!input)
        {
            fputs("Cannot open input\n", stderr);
            return 4;
        }
    }
    result = strcmp(argv[1], "encode") == 0 ? encode(input) : decode(input);
    if (input != stdin)
        fclose(input);
    return result;
}
