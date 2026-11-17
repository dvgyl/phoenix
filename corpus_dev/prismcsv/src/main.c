#define _POSIX_C_SOURCE 200809L
#include <ctype.h>
#include <getopt.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct Row
{
    char cells[16][128];
    unsigned count;
};

struct Transform
{
    const char *name;
    void (*apply)(char *);
};

static void upper(char *cell)
{
    for (; *cell; cell++)
        *cell = (char)toupper((unsigned char)*cell);
}

static void lower(char *cell)
{
    for (; *cell; cell++)
        *cell = (char)tolower((unsigned char)*cell);
}

static void reverse(char *cell)
{
    size_t length = strlen(cell);
    for (size_t i = 0; i < length / 2; i++)
    {
        char temp = cell[i];
        cell[i] = cell[length - i - 1];
        cell[length - i - 1] = temp;
    }
}

static void strip(char *cell)
{
    size_t first = 0;
    size_t last = strlen(cell);
    while (isspace((unsigned char)cell[first]))
        first++;
    while (last > first && isspace((unsigned char)cell[last - 1]))
        last--;
    memmove(cell, cell + first, last - first);
    cell[last - first] = 0;
}

static void length(char *cell)
{
    size_t count = strlen(cell);
    snprintf(cell, 128, "%zu", count);
}

static void slug(char *cell)
{
    for (; *cell; cell++)
    {
        if (isspace((unsigned char)*cell))
            *cell = '_';
        else
            *cell = (char)tolower((unsigned char)*cell);
    }
}

static const struct Transform transforms[] =
{
    {"upper", upper},
    {"lower", lower},
    {"reverse", reverse},
    {"strip", strip},
    {"length", length},
    {"slug", slug}
};

static int read_row(FILE *input, struct Row *row, int separator)
{
    unsigned column = 0;
    unsigned used = 0;
    int quoted = 0;
    int closed = 0;
    int any = 0;
    int c;
    memset(row, 0, sizeof(*row));
    while ((c = fgetc(input)) != EOF)
    {
        any = 1;
        if (quoted)
        {
            if (c == '"')
            {
                int next = fgetc(input);
                if (next == '"')
                    c = '"';
                else
                {
                    quoted = 0;
                    closed = 1;
                    if (next != EOF)
                        ungetc(next, input);
                    continue;
                }
            }
        }
        else
        {
            if (c == '"' && used == 0 && !closed)
            {
                quoted = 1;
                continue;
            }
            if (c == separator || c == '\n')
            {
                row->cells[column][used] = 0;
                column++;
                if (c == '\n')
                {
                    row->count = column;
                    return 1;
                }
                if (column == 16)
                {
                    fputs("Column limit exceeded\n", stderr);
                    return -1;
                }
                used = 0;
                closed = 0;
                continue;
            }
            if (closed)
            {
                fputs("Data after closing quote\n", stderr);
                return -1;
            }
            if (c == '\r')
                continue;
        }
        if (used == 127)
        {
            fputs("Cell limit exceeded\n", stderr);
            return -1;
        }
        row->cells[column][used++] = (char)c;
    }
    if (quoted)
    {
        fputs("Unclosed quote\n", stderr);
        return -1;
    }
    if (!any)
        return 0;
    row->cells[column][used] = 0;
    row->count = column + 1;
    return 1;
}

static void print_cell(const char *cell, int separator)
{
    int quote = strchr(cell, separator) || strchr(cell, '"') || strchr(cell, '\n');
    if (quote)
        putchar('"');
    for (; *cell; cell++)
    {
        if (*cell == '"')
            putchar('"');
        putchar(*cell);
    }
    if (quote)
        putchar('"');
}

static int numeric(const char *cell, double *value)
{
    char *end;
    *value = strtod(cell, &end);
    return *cell && !*end && isfinite(*value) && fabs(*value) <= 1e9;
}

static int arithmetic(char *cell, int operation, double parameter)
{
    double value;
    if (!numeric(cell, &value))
    {
        fputs("Non-numeric cell\n", stderr);
        return 3;
    }
    switch (operation)
    {
        case 'a':
            value += parameter;
            break;
        case 'm':
            value *= parameter;
            break;
        case 'n':
            value = -value;
            break;
        case 'b':
            value = fabs(value);
            break;
        case 'f':
            value = floor(value);
            break;
        case 'c':
            value = ceil(value);
            break;
        case 's':
            value = value * value;
            break;
        case 'z':
            value = value > 0 ? 1 : value < 0 ? -1 : 0;
            break;
        default:
            fputs("Invalid numeric operation\n", stderr);
            return 2;
    }
    snprintf(cell, 128, "%.6f", value);
    return 0;
}

static int column_index(const char *text, unsigned *value)
{
    char *end;
    unsigned long parsed = strtoul(text, &end, 10);
    if (!*text || *end || parsed > 15)
        return 0;
    *value = (unsigned)parsed;
    return 1;
}

int main(int argc, char **argv)
{
    int separator = ',';
    int output_separator = ',';
    unsigned column = 0;
    int selected = 0;
    int numeric_op = 0;
    double parameter = 1;
    const struct Transform *transform = NULL;
    int reverse_columns = 0;
    int option;
    opterr = 0;
    while ((option = getopt(argc, argv, "d:o:k:t:x:p:r")) != -1)
    {
        switch (option)
        {
            case 'd':
            case 'o':
                if (strlen(optarg) != 1 || *optarg == '"' || *optarg == '\n')
                {
                    fputs("Invalid separator\n", stderr);
                    return 2;
                }
                if (option == 'd')
                    separator = (unsigned char)*optarg;
                else
                    output_separator = (unsigned char)*optarg;
                break;
            case 'k':
                if (!column_index(optarg, &column))
                {
                    fputs("Invalid column\n", stderr);
                    return 2;
                }
                selected = 1;
                break;
            case 't':
                transform = NULL;
                for (unsigned i = 0; i < sizeof(transforms) / sizeof(*transforms); i++)
                {
                    if (!strcmp(optarg, transforms[i].name))
                        transform = &transforms[i];
                }
                if (!transform)
                {
                    fputs("Invalid transform\n", stderr);
                    return 2;
                }
                break;
            case 'x':
                numeric_op = (unsigned char)*optarg;
                break;
            case 'p':
                if (!numeric(optarg, &parameter))
                {
                    fputs("Invalid parameter\n", stderr);
                    return 2;
                }
                break;
            case 'r':
                reverse_columns = 1;
                break;
            default:
                fputs("Invalid option\n", stderr);
                return 2;
        }
    }
    if (argc - optind > 1)
    {
        fputs("Too many files\n", stderr);
        return 2;
    }
    FILE *input = stdin;
    if (optind < argc)
    {
        input = fopen(argv[optind], "r");
        if (!input)
        {
            fputs("Cannot open input\n", stderr);
            return 4;
        }
    }
    struct Row row;
    int state;
    int result = 0;
    while ((state = read_row(input, &row, separator)) > 0)
    {
        if (selected && column >= row.count)
        {
            fputs("Column is absent\n", stderr);
            result = 3;
            break;
        }
        for (unsigned i = 0; i < row.count; i++)
        {
            if (selected && i != column)
                continue;
            if (transform)
                transform->apply(row.cells[i]);
            if (numeric_op)
            {
                result = arithmetic(row.cells[i], numeric_op, parameter);
                if (result)
                    break;
            }
        }
        if (result)
            break;
        for (unsigned i = 0; i < row.count; i++)
        {
            unsigned index = reverse_columns ? row.count - i - 1 : i;
            if (i)
                putchar(output_separator);
            print_cell(row.cells[index], output_separator);
        }
        putchar('\n');
    }
    if (state < 0)
        result = 3;
    if (input != stdin)
        fclose(input);
    return result;
}
