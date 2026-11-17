#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct Sample
{
    double value;
    unsigned position;
};

static int compare(const void *a, const void *b)
{
    const struct Sample *left = a;
    const struct Sample *right = b;
    if (left->value < right->value)
        return -1;
    if (left->value > right->value)
        return 1;
    return (left->position > right->position) - (left->position < right->position);
}

static double quantile(const struct Sample *values, unsigned count, double p)
{
    double point = p * (count - 1);
    unsigned lower = (unsigned)point;
    unsigned upper = lower + 1;
    if (upper >= count)
        return values[lower].value;
    return values[lower].value + (point - lower) *
        (values[upper].value - values[lower].value);
}

static int read_samples(FILE *input, struct Sample *values, unsigned *count)
{
    char word[128];
    *count = 0;
    while (fscanf(input, "%127s", word) == 1)
    {
        char *end;
        double value = strtod(word, &end);
        if (!*word || *end || !isfinite(value) || fabs(value) > 1e9)
        {
            fputs("Invalid sample\n", stderr);
            return 3;
        }
        if (*count == 1024)
        {
            fputs("Sample limit exceeded\n", stderr);
            return 3;
        }
        values[*count].value = value;
        values[*count].position = *count;
        (*count)++;
    }
    return 0;
}

static void ranks(const struct Sample *values, unsigned count, int reverse)
{
    unsigned index = 0;
    while (index < count)
    {
        unsigned end = index + 1;
        while (end < count && values[end].value == values[index].value)
            end++;
        double rank = ((double)index + end + 1) / 2;
        if (reverse)
            rank = count + 1 - rank;
        for (unsigned k = index; k < end; k++)
            printf("%u %.6f %.3f\n", values[k].position, values[k].value, rank);
        index = end;
    }
}

static void summary(const struct Sample *values, unsigned count)
{
    double median = quantile(values, count, 0.5);
    double lower = quantile(values, count, 0.25);
    double upper = quantile(values, count, 0.75);
    double spread = upper - lower;
    unsigned outliers = 0;
    for (unsigned i = 0; i < count; i++)
    {
        if (values[i].value < lower - 1.5 * spread ||
            values[i].value > upper + 1.5 * spread)
            outliers++;
    }
    printf("quartiles %.6f %.6f %.6f\n", lower, median, upper);
    printf("spread %.6f\n", spread);
    printf("minimum %.6f\n", values[0].value);
    printf("maximum %.6f\n", values[count - 1].value);
    printf("deciles %.6f %.6f\n", quantile(values, count, 0.1),
        quantile(values, count, 0.9));
    printf("outliers %u\n", outliers);
}

int main(int argc, char **argv)
{
    struct Sample values[1024];
    unsigned count;
    int mode = 0;
    int reverse = 0;
    int index = 1;
    double probability = 0.5;
    FILE *input = stdin;
    while (index < argc && argv[index][0] == '-')
    {
        const char *option = argv[index++];
        if (!strcmp(option, "-r"))
            reverse = 1;
        else if (!strcmp(option, "-s"))
            mode = 1;
        else if (!strcmp(option, "-q"))
        {
            char *end;
            if (index == argc)
            {
                fputs("Missing probability\n", stderr);
                return 2;
            }
            probability = strtod(argv[index++], &end);
            if (*end || !isfinite(probability) || probability < 0 || probability > 1)
            {
                fputs("Invalid probability\n", stderr);
                return 2;
            }
            mode = 2;
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
    int result = read_samples(input, values, &count);
    if (input != stdin)
        fclose(input);
    if (result)
        return result;
    if (!count)
    {
        fputs("No samples\n", stderr);
        return 3;
    }
    qsort(values, count, sizeof(*values), compare);
    if (mode == 1)
        summary(values, count);
    else if (mode == 2)
        printf("%.6f\n", quantile(values, count, probability));
    else
        ranks(values, count, reverse);
    return 0;
}
