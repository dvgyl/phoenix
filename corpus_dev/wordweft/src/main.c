#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct Writer
{
    unsigned width;
    unsigned column;
    unsigned long bytes;
    int fold;
};

static void write_symbol(struct Writer *writer, int c)
{
    if (writer->width && writer->column == writer->width)
    {
        putchar('\n');
        writer->column = 0;
    }
    putchar(c);
    writer->column++;
    writer->bytes++;
}

static void write_byte(struct Writer *writer, unsigned byte)
{
    static const char digits[] = "0123456789ABCDEF";
    if (writer->fold && byte >= 'A' && byte <= 'Z')
        byte += 'a' - 'A';
    if (isalnum(byte) || byte == '_' || byte == '.' || byte == '-')
    {
        write_symbol(writer, (int)byte);
    }
    else if (byte == ' ')
    {
        write_symbol(writer, '+');
    }
    else
    {
        write_symbol(writer, '~');
        write_symbol(writer, digits[byte >> 4]);
        write_symbol(writer, digits[byte & 15]);
    }
}

static int digit(int c)
{
    if (c >= '0' && c <= '9')
        return c - '0';
    if (c >= 'A' && c <= 'F')
        return c - 'A' + 10;
    if (c >= 'a' && c <= 'f')
        return c - 'a' + 10;
    return -1;
}

static int next_symbol(FILE *input)
{
    int c;
    do
    {
        c = fgetc(input);
    } while (c == '\n' || c == '\r');
    return c;
}

static int decode(FILE *input, int fold)
{
    int c;
    unsigned long count = 0;
    unsigned long lines = 0;
    while ((c = next_symbol(input)) != EOF)
    {
        if (c == '~')
        {
            int high = next_symbol(input);
            int low = next_symbol(input);
            if (digit(high) < 0 || digit(low) < 0)
            {
                fputs("Invalid escape\n", stderr);
                return 3;
            }
            c = digit(high) * 16 + digit(low);
        }
        else if (c == '+')
        {
            c = ' ';
        }
        else if (!isalnum((unsigned char)c) && c != '_' && c != '.' && c != '-')
        {
            fputs("Invalid symbol\n", stderr);
            return 3;
        }
        if (c == '\n')
            lines++;
        if (fold && c >= 'A' && c <= 'Z')
            c += 'a' - 'A';
        putchar(c);
        count++;
    }
    if (fold)
    {
        fprintf(stderr, "decoded %lu bytes in %lu lines\n", count, lines);
    }
    return 0;
}

static int encode(FILE *input, struct Writer *writer)
{
    int c;
    while ((c = fgetc(input)) != EOF)
        write_byte(writer, (unsigned)c);
    if (writer->bytes)
        putchar('\n');
    return 0;
}

static int width_value(const char *text, unsigned *width)
{
    char *end;
    unsigned long value = strtoul(text, &end, 10);
    if (!*text || *end || value > 4096)
        return 0;
    *width = (unsigned)value;
    return 1;
}

static int inspect(FILE *input)
{
    unsigned long plain = 0;
    unsigned long escaped = 0;
    unsigned long spaces = 0;
    unsigned long upper = 0;
    int c;
    while ((c = fgetc(input)) != EOF)
    {
        if (c == ' ')
        {
            spaces++;
        }
        else if (isalnum((unsigned char)c) || c == '_' || c == '.' || c == '-')
        {
            plain++;
        }
        else
        {
            escaped++;
        }
        if (c >= 'A' && c <= 'Z')
            upper++;
    }
    printf("plain %lu\n", plain);
    printf("spaces %lu\n", spaces);
    printf("escaped %lu\n", escaped);
    printf("uppercase %lu\n", upper);
    printf("encoded %lu\n", plain + spaces + 3 * escaped);
    return 0;
}

int main(int argc, char **argv)
{
    struct Writer writer = {0, 0, 0, 0};
    int mode = 0;
    int index = 1;
    FILE *input = stdin;
    while (index < argc && argv[index][0] == '-')
    {
        const char *option = argv[index++];
        if (!strcmp(option, "-d"))
        {
            mode = 1;
        }
        else if (!strcmp(option, "-i"))
        {
            mode = 2;
        }
        else if (!strcmp(option, "-l"))
        {
            writer.fold = 1;
        }
        else if (!strcmp(option, "-w"))
        {
            if (index == argc)
            {
                fputs("Missing width\n", stderr);
                return 2;
            }
            if (!width_value(argv[index++], &writer.width))
            {
                fputs("Invalid width\n", stderr);
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
    int result;
    if (mode == 1)
    {
        result = decode(input, writer.fold);
    }
    else if (mode == 2)
    {
        result = inspect(input);
    }
    else
    {
        result = encode(input, &writer);
    }
    if (input != stdin)
        fclose(input);
    return result;
}
