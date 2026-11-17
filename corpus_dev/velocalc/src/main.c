#define _POSIX_C_SOURCE 200809L
#include <ctype.h>
#include <getopt.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct Parser
{
    const char *cursor;
    double variables[26];
    int error;
    unsigned depth;
};

struct Function
{
    const char *name;
    double (*call)(double);
};

static const struct Function functions[] =
{
    {"abs", fabs},
    {"floor", floor},
    {"ceil", ceil},
    {"sin", sin},
    {"cos", cos},
    {"sqrt", sqrt},
    {"log", log},
    {"exp", exp}
};

static void spaces(struct Parser *parser)
{
    while (isspace((unsigned char)*parser->cursor))
        parser->cursor++;
}

static double expression(struct Parser *parser, int minimum);

static double atom(struct Parser *parser)
{
    spaces(parser);
    if (parser->depth == 32)
    {
        parser->error = 1;
        return 0;
    }
    parser->depth++;
    double result = 0;
    if (*parser->cursor == '(')
    {
        parser->cursor++;
        result = expression(parser, 1);
        spaces(parser);
        if (*parser->cursor != ')')
            parser->error = 1;
        else
            parser->cursor++;
    }
    else if (*parser->cursor == '-' || *parser->cursor == '+')
    {
        int negative = *parser->cursor++ == '-';
        result = atom(parser);
        if (negative)
            result = -result;
    }
    else if (*parser->cursor == '!')
    {
        parser->cursor++;
        result = atom(parser) == 0;
    }
    else if (isalpha((unsigned char)*parser->cursor))
    {
        char name[32];
        unsigned used = 0;
        while (isalpha((unsigned char)*parser->cursor))
        {
            if (used < 31)
                name[used++] = *parser->cursor;
            parser->cursor++;
        }
        name[used] = 0;
        spaces(parser);
        if (*parser->cursor == '(')
        {
            parser->cursor++;
            double argument = expression(parser, 1);
            spaces(parser);
            if (*parser->cursor != ')')
                parser->error = 1;
            else
                parser->cursor++;
            unsigned i;
            for (i = 0; i < sizeof(functions) / sizeof(*functions); i++)
            {
                if (!strcmp(name, functions[i].name))
                    break;
            }
            if (i == sizeof(functions) / sizeof(*functions))
                parser->error = 1;
            else
                result = functions[i].call(argument);
        }
        else if (used == 1 && name[0] >= 'a' && name[0] <= 'z')
        {
            result = parser->variables[name[0] - 'a'];
        }
        else
        {
            parser->error = 1;
        }
    }
    else
    {
        char *end;
        result = strtod(parser->cursor, &end);
        if (end == parser->cursor)
            parser->error = 1;
        parser->cursor = end;
    }
    parser->depth--;
    if (!isfinite(result) || fabs(result) > 1e12)
    {
        parser->error = 1;
        result = 0;
    }
    return result;
}

static int precedence(int operator)
{
    switch (operator)
    {
        case '|':
            return 1;
        case '&':
            return 2;
        case '=':
        case '<':
        case '>':
            return 3;
        case '+':
        case '-':
            return 4;
        case '*':
        case '/':
        case '%':
            return 5;
        case '^':
            return 6;
        default:
            return 0;
    }
}

static double calculate(struct Parser *parser, int operator, double left, double right)
{
    switch (operator)
    {
        case '+':
            return left + right;
        case '-':
            return left - right;
        case '*':
            return left * right;
        case '/':
            if (right == 0)
            {
                parser->error = 1;
                return 0;
            }
            return left / right;
        case '%':
            if (right == 0)
            {
                parser->error = 1;
                return 0;
            }
            return fmod(left, right);
        case '^':
            return pow(left, right);
        case '<':
            return left < right;
        case '>':
            return left > right;
        case '=':
            return left == right;
        case '&':
            return left != 0 && right != 0;
        case '|':
            return left != 0 || right != 0;
        default:
            parser->error = 1;
            return 0;
    }
}

static double expression(struct Parser *parser, int minimum)
{
    double left = atom(parser);
    while (!parser->error)
    {
        spaces(parser);
        int operator = (unsigned char)*parser->cursor;
        int level = precedence(operator);
        if (level < minimum)
            break;
        parser->cursor++;
        double right = expression(parser, level + (operator != '^'));
        left = calculate(parser, operator, left, right);
        if (!isfinite(left) || fabs(left) > 1e12)
        {
            parser->error = 1;
            left = 0;
        }
    }
    return left;
}

static unsigned sequence(void)
{
    static unsigned count = 0;
    return ++count;
}

static int process(FILE *input, struct Parser *parser, int precision, int numbered)
{
    char line[1024];
    while (fgets(line, sizeof(line), input))
    {
        parser->cursor = line;
        parser->error = 0;
        spaces(parser);
        if (!*parser->cursor || *parser->cursor == '#')
            continue;
        int variable = -1;
        if (parser->cursor[0] >= 'a' && parser->cursor[0] <= 'z' &&
            parser->cursor[1] == ':')
        {
            variable = parser->cursor[0] - 'a';
            parser->cursor += 2;
        }
        double result = expression(parser, 1);
        spaces(parser);
        if (parser->error || *parser->cursor)
        {
            fputs("Invalid expression\n", stderr);
            return 3;
        }
        if (variable >= 0)
            parser->variables[variable] = result;
        if (numbered)
            printf("%u ", sequence());
        if (result == 0)
            result = 0;
        printf("%.*f\n", precision, result);
    }
    return 0;
}

int main(int argc, char **argv)
{
    struct Parser parser = {NULL, {0}, 0, 0};
    int precision = 6;
    int numbered = 0;
    int option;
    opterr = 0;
    while ((option = getopt(argc, argv, "np:v:")) != -1)
    {
        switch (option)
        {
            case 'n':
                numbered = 1;
                break;
            case 'p':
            {
                char *end;
                long value = strtol(optarg, &end, 10);
                if (!*optarg || *end || value < 0 || value > 9)
                {
                    fputs("Invalid precision\n", stderr);
                    return 2;
                }
                precision = (int)value;
                break;
            }
            case 'v':
            {
                char *end;
                if (strlen(optarg) < 3 || optarg[0] < 'a' || optarg[0] > 'z' || optarg[1] != '=')
                {
                    fputs("Invalid variable assignment\n", stderr);
                    return 2;
                }
                double value = strtod(optarg + 2, &end);
                if (*end || !isfinite(value) || fabs(value) > 1e9)
                {
                    fputs("Invalid variable value\n", stderr);
                    return 2;
                }
                parser.variables[optarg[0] - 'a'] = value;
                break;
            }
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
    int result = process(input, &parser, precision, numbered);
    if (input != stdin)
        fclose(input);
    return result;
}
