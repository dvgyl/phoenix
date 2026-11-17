#include <stdio.h>
#include <string.h>

int main(int argc, char **argv)
{
    const char *digits = "abcdefghijklmnop";
    int decode = 0;
    int value;
    int high = -1;
    unsigned long count = 0;
    FILE *input = stdin;
    if (argc < 2 || argc > 3)
    {
        fputs("Use: niblace encode|decode [file]\n", stderr);
        return 2;
    }
    if (strcmp(argv[1], "decode") == 0)
        decode = 1;
    else if (strcmp(argv[1], "encode") != 0)
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
    while ((value = fgetc(input)) != EOF)
    {
        if (!decode)
        {
            putchar(digits[(unsigned)value >> 4]);
            putchar(digits[value & 15]);
            count++;
        }
        else
        {
            const char *digit;
            if (value == '\n' || value == ' ')
                continue;
            digit = strchr(digits, value);
            if (digit == NULL || value == 0)
            {
                fputs("Invalid digit\n", stderr);
                return 3;
            }
            if (high < 0)
                high = (int)(digit - digits);
            else
            {
                putchar(high * 16 + (int)(digit - digits));
                high = -1;
                count++;
            }
        }
    }
    if (input != stdin)
        fclose(input);
    if (high >= 0)
    {
        fputs("Incomplete byte\n", stderr);
        return 3;
    }
    if (!decode && count > 0)
        putchar('\n');
    return 0;
}
