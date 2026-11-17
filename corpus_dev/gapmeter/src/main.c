#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct Sequence
{
    double values[2048];
    unsigned count;
    double threshold;
    unsigned bins[10];
    unsigned rises;
    unsigned falls;
    unsigned flats;
    unsigned longest;
    double total_gap;
    double largest_gap;
};

static int number(const char *word, double *value)
{
    char *end;
    *value = strtod(word, &end);
    return *word && !*end && isfinite(*value) && fabs(*value) <= 1e9;
}

static int load(FILE *input, struct Sequence *sequence)
{
    char word[128];
    while (fscanf(input, "%127s", word) == 1)
    {
        double value;
        if (!number(word, &value))
        {
            fputs("Invalid value\n", stderr);
            return 3;
        }
        if (sequence->count == 2048)
        {
            fputs("Value limit exceeded\n", stderr);
            return 3;
        }
        sequence->values[sequence->count++] = value;
    }
    if (!sequence->count)
    {
        fputs("No values\n", stderr);
        return 3;
    }
    return 0;
}

static void measure(struct Sequence *sequence)
{
    unsigned run = 1;
    int direction = 0;
    sequence->longest = 1;
    for (unsigned i = 1; i < sequence->count; i++)
    {
        double gap = sequence->values[i] - sequence->values[i - 1];
        double magnitude = fabs(gap);
        unsigned bin;
        int next;
        if (gap > sequence->threshold)
        {
            sequence->rises++;
            next = 1;
        }
        else if (gap < -sequence->threshold)
        {
            sequence->falls++;
            next = -1;
        }
        else
        {
            sequence->flats++;
            next = 0;
        }
        if (next == direction)
        {
            run++;
        }
        else
        {
            run = 2;
            direction = next;
        }
        if (run > sequence->longest)
            sequence->longest = run;
        sequence->total_gap += magnitude;
        if (magnitude > sequence->largest_gap)
            sequence->largest_gap = magnitude;
        if (magnitude >= 9)
            bin = 9;
        else
            bin = (unsigned)magnitude;
        sequence->bins[bin]++;
    }
}

static void print_summary(const struct Sequence *sequence)
{
    double displacement = sequence->values[sequence->count - 1] - sequence->values[0];
    double efficiency = 0;
    if (sequence->total_gap > 0)
    {
        efficiency = fabs(displacement) / sequence->total_gap;
    }
    printf("efficiency %.6f\n", efficiency);
    printf("reversals %u\n", sequence->rises < sequence->falls ?
        sequence->rises : sequence->falls);
    printf("count %u\n", sequence->count);
    printf("directions %u %u %u\n", sequence->rises, sequence->falls,
        sequence->flats);
    printf("run %u\n", sequence->longest);
    printf("travel %.6f\n", sequence->total_gap);
    printf("largest %.6f\n", sequence->largest_gap);
    printf("net %.6f\n", sequence->values[sequence->count - 1] - sequence->values[0]);
}

static void print_histogram(const struct Sequence *sequence)
{
    for (unsigned i = 0; i < 10; i++)
    {
        printf("%u %u ", i, sequence->bins[i]);
        unsigned stars = sequence->bins[i];
        if (stars > 40)
            stars = 40;
        for (unsigned k = 0; k < stars; k++)
            putchar('*');
        putchar('\n');
    }
}

static void print_segments(const struct Sequence *sequence)
{
    unsigned start = 0;
    for (unsigned i = 1; i <= sequence->count; i++)
    {
        int split = i == sequence->count;
        if (!split)
            split = fabs(sequence->values[i] - sequence->values[i - 1]) >
                sequence->threshold;
        if (split)
        {
            double sum = 0;
            double low = sequence->values[start];
            double high = low;
            for (unsigned k = start; k < i; k++)
            {
                double value = sequence->values[k];
                sum += value;
                if (value < low)
                    low = value;
                if (value > high)
                    high = value;
            }
            printf("%u %u %.6f %.6f %.6f\n", start, i - start,
                sum / (i - start), low, high);
            start = i;
        }
    }
}

static void print_crossings(const struct Sequence *sequence, double level)
{
    unsigned above = 0;
    unsigned below = 0;
    unsigned touches = 0;
    for (unsigned i = 0; i < sequence->count; i++)
    {
        double value = sequence->values[i];
        if (value == level)
            touches++;
        if (i == 0)
            continue;
        double previous = sequence->values[i - 1];
        if (previous < level && value > level)
        {
            above++;
            printf("up %u\n", i);
        }
        if (previous > level && value < level)
        {
            below++;
            printf("down %u\n", i);
        }
    }
    printf("crossings %u %u %u\n", above, below, touches);
}

int main(int argc, char **argv)
{
    struct Sequence sequence = {{0}, 0, 1, {0}, 0, 0, 0, 0, 0, 0};
    int mode = 0;
    double level = 0;
    int index = 1;
    FILE *input = stdin;
    while (index < argc && argv[index][0] == '-')
    {
        const char *option = argv[index++];
        if (!strcmp(option, "-h"))
        {
            mode = 1;
        }
        else if (!strcmp(option, "-s"))
        {
            mode = 2;
        }
        else if (!strcmp(option, "-t") || !strcmp(option, "-c"))
        {
            double value;
            if (index == argc)
            {
                fputs("Missing numeric option\n", stderr);
                return 2;
            }
            if (!number(argv[index++], &value))
            {
                fputs("Invalid numeric option\n", stderr);
                return 2;
            }
            if (!strcmp(option, "-t"))
            {
                if (value < 0)
                {
                    fputs("Negative threshold\n", stderr);
                    return 2;
                }
                sequence.threshold = value;
            }
            else
            {
                level = value;
                mode = 3;
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
    int result = load(input, &sequence);
    if (input != stdin)
        fclose(input);
    if (result)
        return result;
    measure(&sequence);
    if (mode == 1)
        print_histogram(&sequence);
    else if (mode == 2)
        print_segments(&sequence);
    else if (mode == 3)
        print_crossings(&sequence, level);
    else
        print_summary(&sequence);
    return 0;
}
