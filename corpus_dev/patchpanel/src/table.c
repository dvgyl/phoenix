#include "table.h"
#include <ctype.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>

int problem(const char *message)
{
    fprintf(stderr, "%s\n", message);
    return 3;
}

int read_integer(FILE *input, int *value)
{
    char word[80];
    char *end;
    if (fscanf(input, "%79s", word) != 1)
        return 0;
    long parsed = strtol(word, &end, 10);
    if (*end || parsed < -10000 || parsed > 10000)
        return 0;
    *value = (int)parsed;
    return 1;
}

int read_number(FILE *input, double *value)
{
    char word[80];
    char *end;
    if (fscanf(input, "%79s", word) != 1)
        return 0;
    double parsed = strtod(word, &end);
    if (*end || !isfinite(parsed) || fabs(parsed) > 1e9)
        return 0;
    *value = parsed;
    return 1;
}

void initialize_labels(struct Table *table)
{
    for (unsigned i = 0; i < table->columns; i++)
        snprintf(table->labels[i], sizeof(table->labels[i]), "c%u", i);
}

int read_table(FILE *input, struct Table *table)
{
    int rows;
    int columns;
    if (!read_integer(input, &rows) || !read_integer(input, &columns) ||
        rows < 1 || rows > ROWS || columns < 1 || columns > COLS)
        return problem("Invalid table dimensions");
    table->rows = (unsigned)rows;
    table->columns = (unsigned)columns;
    initialize_labels(table);
    for (unsigned row = 0; row < table->rows; row++)
    {
        for (unsigned column = 0; column < table->columns; column++)
        {
            if (!read_number(input, &table->cells[row][column]))
                return problem("Invalid table cell");
        }
    }
    return 0;
}

void display(const struct Table *table, int precision, int header)
{
    printf("%u %u\n", table->rows, table->columns);
    if (header)
    {
        for (unsigned column = 0; column < table->columns; column++)
        {
            if (column)
                putchar(',');
            fputs(table->labels[column], stdout);
        }
        putchar('\n');
    }
    for (unsigned row = 0; row < table->rows; row++)
    {
        for (unsigned column = 0; column < table->columns; column++)
        {
            if (column)
                putchar(',');
            double value = table->cells[row][column];
            if (value == 0)
                value = 0;
            printf("%.*f", precision, value);
        }
        putchar('\n');
    }
}

int write_csv(const char *path, const struct Table *table, int precision)
{
    FILE *output = fopen(path, "w");
    if (!output)
        return problem("Cannot create CSV output");
    for (unsigned row = 0; row < table->rows; row++)
    {
        for (unsigned column = 0; column < table->columns; column++)
        {
            if (column)
                fputc(',', output);
            fprintf(output, "%.*f", precision, table->cells[row][column]);
        }
        fputc('\n', output);
    }
    fclose(output);
    return 0;
}

int load_csv(const char *path, struct Table *table, int separator)
{
    FILE *input = fopen(path, "r");
    if (!input)
        return problem("Cannot open CSV input");
    struct Table result = {0};
    char line[4096];
    int failure = 0;
    while (fgets(line, sizeof(line), input))
    {
        if (result.rows == ROWS)
        {
            failure = problem("CSV row limit exceeded");
            break;
        }
        unsigned column = 0;
        char *cursor = line;
        for (;;)
        {
            if (column == COLS)
            {
                failure = problem("CSV column limit exceeded");
                break;
            }
            char *end;
            double value = strtod(cursor, &end);
            if (end == cursor || !isfinite(value) || fabs(value) > 1e9)
            {
                failure = problem("Invalid numeric CSV field");
                break;
            }
            result.cells[result.rows][column++] = value;
            while (*end == ' ' || *end == '\t' || *end == '\r')
                end++;
            if (*end == '\n' || *end == 0)
                break;
            if (*end != separator)
            {
                failure = problem("Invalid CSV separator");
                break;
            }
            cursor = end + 1;
        }
        if (failure)
            break;
        if (result.rows && result.columns != column)
        {
            failure = problem("CSV row width differs");
            break;
        }
        result.columns = column;
        result.rows++;
    }
    fclose(input);
    if (failure)
        return failure;
    if (!result.rows)
        return problem("CSV input is empty");
    initialize_labels(&result);
    *table = result;
    return 0;
}

void aggregate_add(struct Aggregate *aggregate, double value)
{
    if (aggregate->count == 0)
    {
        aggregate->minimum = value;
        aggregate->maximum = value;
    }
    aggregate->count++;
    aggregate->sum += value;
    double delta = value - aggregate->mean;
    aggregate->mean += delta / aggregate->count;
    aggregate->square += delta * (value - aggregate->mean);
    if (value < aggregate->minimum)
        aggregate->minimum = value;
    if (value > aggregate->maximum)
        aggregate->maximum = value;
}

struct Aggregate aggregate_column(const struct Table *table, unsigned column)
{
    struct Aggregate result = {0};
    for (unsigned row = 0; row < table->rows; row++)
        aggregate_add(&result, table->cells[row][column]);
    return result;
}

void print_aggregate(const struct Aggregate *aggregate, int precision)
{
    double variance = 0;
    if (aggregate->count)
        variance = aggregate->square / aggregate->count;
    if (variance < 0)
        variance = 0;
    printf("%u %.*f %.*f %.*f %.*f %.*f\n", aggregate->count,
        precision, aggregate->sum, precision, aggregate->mean,
        precision, aggregate->minimum, precision, aggregate->maximum,
        precision, sqrt(variance));
}
