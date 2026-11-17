#define _POSIX_C_SOURCE 200809L
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct Stats
{
    double mean;
    double square;
    double sum;
    double low;
    double high;
    double previous;
    double movement;
    unsigned count;
    unsigned rising;
    unsigned falling;
    unsigned equal;
};

static int parse(const char *text, double *value)
{
    char *end;
    *value = strtod(text, &end);
    return *text && !*end && isfinite(*value) && fabs(*value) <= 1e9;
}

static void add(struct Stats *s, double value)
{
    if (s->count == 0)
    {
        s->low = value;
        s->high = value;
    }
    else
    {
        double change = value - s->previous;
        s->movement += fabs(change);
        if (change > 0)
            s->rising++;
        else if (change < 0)
            s->falling++;
        else
            s->equal++;
    }
    s->count++;
    double delta = value - s->mean;
    s->mean += delta / s->count;
    s->square += delta * (value - s->mean);
    s->sum += value;
    s->previous = value;
    if (value < s->low)
        s->low = value;
    if (value > s->high)
        s->high = value;
}

static void report(const struct Stats *s, int sample, int compact)
{
    double variance = 0;
    if (s->count > (unsigned)sample)
        variance = s->square / (s->count - (unsigned)sample);
    if (variance < 0)
        variance = 0;
    if (compact)
    {
        printf("%u %.6f %.6f\n", s->count, s->mean, sqrt(variance));
        return;
    }
    printf("count %u\n", s->count);
    printf("sum %.6f\n", s->sum);
    printf("mean %.6f\n", s->mean);
    printf("deviation %.6f\n", sqrt(variance));
    printf("range %.6f %.6f\n", s->low, s->high);
    printf("movement %.6f\n", s->movement);
    printf("steps %u %u %u\n", s->rising, s->falling, s->equal);
}

static int read_values(FILE *input, struct Stats *stats, double scale, int skip)
{
    char text[256];
    unsigned rejected = 0;
    while (fscanf(input, "%255s", text) == 1)
    {
        double value;
        if (!parse(text, &value))
        {
            if (!skip)
            {
                fputs("Invalid numeric input\n", stderr);
                return 3;
            }
            rejected++;
            continue;
        }
        if (stats->count == 10000)
        {
            fputs("Too many values\n", stderr);
            return 3;
        }
        add(stats, value * scale);
    }
    if (skip)
        printf("rejected %u\n", rejected);
    return 0;
}

int main(int argc, char **argv)
{
    struct Stats stats = {0};
    double scale = 1;
    int compact = 0;
    int sample = 0;
    int skip = 0;
    int index = 1;
    FILE *input = stdin;
    while (index < argc && argv[index][0] == '-')
    {
        const char *option = argv[index++];
        if (!strcmp(option, "-c"))
            compact = 1;
        else if (!strcmp(option, "-s"))
            sample = 1;
        else if (!strcmp(option, "-k"))
            skip = 1;
        else if (!strcmp(option, "-m"))
        {
            if (index == argc || !parse(argv[index++], &scale))
            {
                fputs("Invalid scale\n", stderr);
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
        input = fopen(argv[index], "r");
        if (!input)
        {
            fputs("Cannot open input\n", stderr);
            return 4;
        }
    }
    int result = read_values(input, &stats, scale, skip);
    if (input != stdin)
        fclose(input);
    if (result)
        return result;
    if (!stats.count)
    {
        fputs("No values\n", stderr);
        return 3;
    }
    report(&stats, sample, compact);
    return 0;
}
