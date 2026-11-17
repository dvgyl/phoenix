#define _POSIX_C_SOURCE 200809L
#include "table.h"
#include <getopt.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>

static int column_parameter(FILE *input, const struct Table *table, unsigned *column)
{
    int parsed;
    if (!read_integer(input, &parsed) || parsed < 0 || parsed >= (int)table->columns)
        return problem("Invalid column index");
    *column = (unsigned)parsed;
    return 0;
}

static int row_parameter(FILE *input, const struct Table *table, unsigned *row)
{
    int parsed;
    if (!read_integer(input, &parsed) || parsed < 0 || parsed >= (int)table->rows)
        return problem("Invalid row index");
    *row = (unsigned)parsed;
    return 0;
}

static int transpose(struct Table *table)
{
    if (table->rows > COLS)
        return problem("Transpose column limit exceeded");
    struct Table result = {0};
    result.rows = table->columns;
    result.columns = table->rows;
    for (unsigned row = 0; row < table->rows; row++)
    {
        for (unsigned column = 0; column < table->columns; column++)
            result.cells[column][row] = table->cells[row][column];
    }
    initialize_labels(&result);
    *table = result;
    return 0;
}

static void reverse_rows(struct Table *table)
{
    for (unsigned row = 0; row < table->rows / 2; row++)
    {
        for (unsigned column = 0; column < table->columns; column++)
        {
            double saved = table->cells[row][column];
            table->cells[row][column] = table->cells[table->rows - row - 1][column];
            table->cells[table->rows - row - 1][column] = saved;
        }
    }
}

static int pair_compare(const void *a, const void *b)
{
    const struct Pair *left = a;
    const struct Pair *right = b;
    if (left->key < right->key)
        return -1;
    if (left->key > right->key)
        return 1;
    return (left->row > right->row) - (left->row < right->row);
}

static void sort_rows(struct Table *table, unsigned column)
{
    struct Pair pairs[ROWS];
    struct Table original = *table;
    for (unsigned row = 0; row < table->rows; row++)
    {
        pairs[row].key = table->cells[row][column];
        pairs[row].row = row;
    }
    qsort(pairs, table->rows, sizeof(*pairs), pair_compare);
    for (unsigned row = 0; row < table->rows; row++)
        memcpy(table->cells[row], original.cells[pairs[row].row], sizeof(table->cells[row]));
}

static void unique_rows(struct Table *table)
{
    unsigned count = 0;
    for (unsigned row = 0; row < table->rows; row++)
    {
        unsigned match;
        for (match = 0; match < count; match++)
        {
            unsigned column = 0;
            for (column = 0; column < table->columns; column++)
            {
                if (table->cells[row][column] != table->cells[match][column])
                    break;
            }
            if (column == table->columns)
                break;
        }
        if (match == count)
        {
            memcpy(table->cells[count], table->cells[row], sizeof(table->cells[row]));
            count++;
        }
    }
    table->rows = count;
}

static int scalar(struct Table *table, FILE *input, char operation)
{
    unsigned column = 0;
    int result = column_parameter(input, table, &column);
    if (result)
        return result;
    double parameter;
    if (!read_number(input, &parameter))
        return problem("Invalid scalar parameter");
    if (operation == '/' && parameter == 0)
        return problem("Zero divisor");
    for (unsigned row = 0; row < table->rows; row++)
    {
        double *value = &table->cells[row][column];
        switch (operation)
        {
            case '+':
                *value += parameter;
                break;
            case '*':
                *value *= parameter;
                break;
            case '/':
                *value /= parameter;
                break;
            case '<':
                if (*value < parameter)
                    *value = parameter;
                break;
            case '>':
                if (*value > parameter)
                    *value = parameter;
                break;
            case '=':
                *value = parameter;
                break;
            case '^':
                *value = pow(fabs(*value), parameter);
                break;
            case '%':
                *value = parameter == 0 ? 0 : fmod(*value, parameter);
                break;
            default:
                return problem("Invalid scalar operation");
        }
        if (!isfinite(*value) || fabs(*value) > 1e9)
            return problem("Scalar result exceeds limit");
    }
    return 0;
}

static void normalize_column(struct Table *table, unsigned column)
{
    struct Aggregate aggregate = aggregate_column(table, column);
    double range = aggregate.maximum - aggregate.minimum;
    for (unsigned row = 0; row < table->rows; row++)
    {
        if (range == 0)
            table->cells[row][column] = 0;
        else
            table->cells[row][column] = (table->cells[row][column] - aggregate.minimum) / range;
    }
}

static void standardize_column(struct Table *table, unsigned column)
{
    struct Aggregate aggregate = aggregate_column(table, column);
    double deviation = sqrt(fmax(0, aggregate.square / aggregate.count));
    for (unsigned row = 0; row < table->rows; row++)
    {
        if (deviation == 0)
            table->cells[row][column] = 0;
        else
            table->cells[row][column] = (table->cells[row][column] - aggregate.mean) / deviation;
    }
}

static void accumulate_column(struct Table *table, unsigned column)
{
    double total = 0;
    for (unsigned row = 0; row < table->rows; row++)
    {
        total += table->cells[row][column];
        table->cells[row][column] = total;
    }
}

static void difference_column(struct Table *table, unsigned column)
{
    double previous = 0;
    for (unsigned row = 0; row < table->rows; row++)
    {
        double value = table->cells[row][column];
        table->cells[row][column] = value - previous;
        previous = value;
    }
}

static int rolling_column(struct Table *table, unsigned column, FILE *input)
{
    int width;
    if (!read_integer(input, &width) || width < 1 || width > ROWS)
        return problem("Invalid rolling width");
    double original[ROWS];
    for (unsigned row = 0; row < table->rows; row++)
        original[row] = table->cells[row][column];
    for (unsigned row = 0; row < table->rows; row++)
    {
        unsigned start = row + 1 > (unsigned)width ? row + 1 - (unsigned)width : 0;
        double total = 0;
        for (unsigned i = start; i <= row; i++)
            total += original[i];
        table->cells[row][column] = total / (row + 1 - start);
    }
    return 0;
}

static void rank_column(struct Table *table, unsigned column)
{
    struct Pair pairs[ROWS];
    for (unsigned row = 0; row < table->rows; row++)
    {
        pairs[row].key = table->cells[row][column];
        pairs[row].row = row;
    }
    qsort(pairs, table->rows, sizeof(*pairs), pair_compare);
    unsigned start = 0;
    while (start < table->rows)
    {
        unsigned end = start + 1;
        while (end < table->rows && pairs[start].key == pairs[end].key)
            end++;
        double rank = (start + end + 1.0) / 2;
        for (unsigned i = start; i < end; i++)
            table->cells[pairs[i].row][column] = rank;
        start = end;
    }
}

static int filter_rows(struct Table *table, unsigned column, FILE *input)
{
    double low;
    double high;
    if (!read_number(input, &low) || !read_number(input, &high) || low > high)
        return problem("Invalid filter interval");
    unsigned count = 0;
    for (unsigned row = 0; row < table->rows; row++)
    {
        double value = table->cells[row][column];
        if (value < low || value > high)
            continue;
        memcpy(table->cells[count++], table->cells[row], sizeof(table->cells[row]));
    }
    if (!count)
        return problem("Filter removed all rows");
    table->rows = count;
    return 0;
}

static int derive_column(struct Table *table, FILE *input)
{
    unsigned left = 0;
    unsigned right = 0;
    int result = column_parameter(input, table, &left);
    if (!result)
        result = column_parameter(input, table, &right);
    if (result)
        return result;
    char operation[8];
    if (fscanf(input, "%7s", operation) != 1 || strlen(operation) != 1)
        return problem("Invalid derived operation");
    if (table->columns == COLS)
        return problem("Derived column limit exceeded");
    unsigned column = table->columns;
    for (unsigned row = 0; row < table->rows; row++)
    {
        double a = table->cells[row][left];
        double b = table->cells[row][right];
        double value;
        switch (*operation)
        {
            case '+':
                value = a + b;
                break;
            case '-':
                value = a - b;
                break;
            case '*':
                value = a * b;
                break;
            case '/':
                if (b == 0)
                    return problem("Derived zero divisor");
                value = a / b;
                break;
            case '<':
                value = fmin(a, b);
                break;
            case '>':
                value = fmax(a, b);
                break;
            case '=':
                value = a == b;
                break;
            case '!':
                value = a != b;
                break;
            default:
                return problem("Unknown derived operation");
        }
        if (!isfinite(value) || fabs(value) > 1e9)
            return problem("Derived result exceeds limit");
        table->cells[row][column] = value;
    }
    snprintf(table->labels[column], sizeof(table->labels[column]), "d%u", column);
    table->columns++;
    return 0;
}

static int remove_column(struct Table *table, unsigned column)
{
    if (table->columns == 1)
        return problem("Cannot remove the remaining column");
    for (unsigned i = column + 1; i < table->columns; i++)
    {
        strcpy(table->labels[i - 1], table->labels[i]);
        for (unsigned row = 0; row < table->rows; row++)
            table->cells[row][i - 1] = table->cells[row][i];
    }
    table->columns--;
    return 0;
}

static int swap_columns(struct Table *table, unsigned left, FILE *input)
{
    unsigned right = 0;
    int result = column_parameter(input, table, &right);
    if (result)
        return result;
    char label[32];
    strcpy(label, table->labels[left]);
    strcpy(table->labels[left], table->labels[right]);
    strcpy(table->labels[right], label);
    for (unsigned row = 0; row < table->rows; row++)
    {
        double saved = table->cells[row][left];
        table->cells[row][left] = table->cells[row][right];
        table->cells[row][right] = saved;
    }
    return 0;
}

static int combine(struct State *state, int append)
{
    if (!state->has_saved)
        return problem("No saved table");
    struct Table *table = &state->table;
    const struct Table *saved = &state->saved;
    if (append)
    {
        if (table->columns != saved->columns || table->rows + saved->rows > ROWS)
            return problem("Cannot append saved rows");
        for (unsigned row = 0; row < saved->rows; row++)
            memcpy(table->cells[table->rows + row], saved->cells[row], sizeof(table->cells[row]));
        table->rows += saved->rows;
    }
    else
    {
        if (table->rows != saved->rows || table->columns + saved->columns > COLS)
            return problem("Cannot join saved columns");
        for (unsigned column = 0; column < saved->columns; column++)
        {
            strcpy(table->labels[table->columns + column], saved->labels[column]);
            for (unsigned row = 0; row < table->rows; row++)
                table->cells[row][table->columns + column] = saved->cells[row][column];
        }
        table->columns += saved->columns;
    }
    return 0;
}

static int correlation(const struct Table *table, unsigned a, FILE *input, int precision)
{
    unsigned b = 0;
    int result = column_parameter(input, table, &b);
    if (result)
        return result;
    struct Aggregate left = aggregate_column(table, a);
    struct Aggregate right = aggregate_column(table, b);
    double product = 0;
    for (unsigned row = 0; row < table->rows; row++)
    {
        product += (table->cells[row][a] - left.mean) *
            (table->cells[row][b] - right.mean);
    }
    double denominator = sqrt(left.square * right.square);
    double coefficient = denominator == 0 ? 0 : product / denominator;
    printf("correlation %.*f\n", precision, coefficient);
    return 0;
}

static int column_command(const char *command, FILE *input, struct State *state)
{
    unsigned column = 0;
    struct Table *table = &state->table;
    int result = column_parameter(input, table, &column);
    if (result)
        return result;
    if (!strcmp(command, "sort"))
        sort_rows(table, column);
    else if (!strcmp(command, "normalize"))
        normalize_column(table, column);
    else if (!strcmp(command, "standardize"))
        standardize_column(table, column);
    else if (!strcmp(command, "accumulate"))
        accumulate_column(table, column);
    else if (!strcmp(command, "difference"))
        difference_column(table, column);
    else if (!strcmp(command, "rank"))
        rank_column(table, column);
    else if (!strcmp(command, "rolling"))
        result = rolling_column(table, column, input);
    else if (!strcmp(command, "filter"))
        result = filter_rows(table, column, input);
    else if (!strcmp(command, "drop"))
        result = remove_column(table, column);
    else if (!strcmp(command, "swap"))
        result = swap_columns(table, column, input);
    else if (!strcmp(command, "correlate"))
        result = correlation(table, column, input, state->precision);
    else if (!strcmp(command, "stats"))
    {
        struct Aggregate aggregate = aggregate_column(table, column);
        print_aggregate(&aggregate, state->precision);
    }
    else
    {
        char label[32];
        if (fscanf(input, "%31s", label) != 1)
            return problem("Missing column label");
        strcpy(table->labels[column], label);
    }
    return result;
}

static int multiply_saved(struct State *state)
{
    if (!state->has_saved)
        return problem("No saved factor");
    const struct Table *left = &state->table;
    const struct Table *right = &state->saved;
    if (left->columns != right->rows)
        return problem("Matrix dimensions differ");
    struct Table result = {0};
    result.rows = left->rows;
    result.columns = right->columns;
    initialize_labels(&result);
    for (unsigned row = 0; row < result.rows; row++)
    {
        for (unsigned column = 0; column < result.columns; column++)
        {
            double total = 0;
            for (unsigned k = 0; k < left->columns; k++)
                total += left->cells[row][k] * right->cells[k][column];
            if (!isfinite(total) || fabs(total) > 1e9)
                return problem("Matrix result exceeds limit");
            result.cells[row][column] = total;
        }
    }
    state->table = result;
    return 0;
}

static int group_rows(struct Table *table, FILE *input)
{
    unsigned key = 0;
    int result = column_parameter(input, table, &key);
    if (result)
        return result;
    struct Table grouped = {0};
    grouped.columns = table->columns;
    memcpy(grouped.labels, table->labels, sizeof(grouped.labels));
    unsigned counts[ROWS] = {0};
    for (unsigned row = 0; row < table->rows; row++)
    {
        unsigned group;
        for (group = 0; group < grouped.rows; group++)
        {
            if (grouped.cells[group][key] == table->cells[row][key])
                break;
        }
        if (group == grouped.rows)
        {
            grouped.cells[group][key] = table->cells[row][key];
            grouped.rows++;
        }
        counts[group]++;
        for (unsigned column = 0; column < table->columns; column++)
        {
            if (column != key)
                grouped.cells[group][column] += table->cells[row][column];
        }
    }
    for (unsigned row = 0; row < grouped.rows; row++)
    {
        for (unsigned column = 0; column < grouped.columns; column++)
        {
            if (column != key)
                grouped.cells[row][column] /= counts[row];
        }
    }
    *table = grouped;
    return 0;
}

static void covariance(const struct Table *table, int precision)
{
    double means[COLS] = {0};
    for (unsigned column = 0; column < table->columns; column++)
    {
        struct Aggregate aggregate = aggregate_column(table, column);
        means[column] = aggregate.mean;
    }
    for (unsigned a = 0; a < table->columns; a++)
    {
        for (unsigned b = 0; b < table->columns; b++)
        {
            double total = 0;
            for (unsigned row = 0; row < table->rows; row++)
            {
                total += (table->cells[row][a] - means[a]) *
                    (table->cells[row][b] - means[b]);
            }
            if (b)
                putchar(',');
            printf("%.*f", precision, total / table->rows);
        }
        putchar('\n');
    }
}

int execute(FILE *input, struct State *state)
{
    char command[80];
    while (fscanf(input, "%79s", command) == 1)
    {
        int result = 0;
        struct Table *table = &state->table;
        if (!strcmp(command, "multiply"))
            result = multiply_saved(state);
        else if (!strcmp(command, "group"))
            result = group_rows(table, input);
        else if (!strcmp(command, "covariance"))
            covariance(table, state->precision);
        else if (!strcmp(command, "show"))
            display(table, state->precision, state->header);
        else if (!strcmp(command, "transpose"))
            result = transpose(table);
        else if (!strcmp(command, "reverse"))
            reverse_rows(table);
        else if (!strcmp(command, "unique"))
            unique_rows(table);
        else if (!strcmp(command, "scalar"))
        {
            char operation[8];
            if (fscanf(input, "%7s", operation) != 1 || strlen(operation) != 1)
                return problem("Missing scalar operation");
            result = scalar(table, input, *operation);
        }
        else if (!strcmp(command, "derive"))
            result = derive_column(table, input);
        else if (!strcmp(command, "save"))
        {
            state->saved = *table;
            state->has_saved = 1;
        }
        else if (!strcmp(command, "restore"))
        {
            if (!state->has_saved)
                return problem("No saved table");
            *table = state->saved;
        }
        else if (!strcmp(command, "append") || !strcmp(command, "join"))
            result = combine(state, !strcmp(command, "append"));
        else if (!strcmp(command, "csv") || !strcmp(command, "load"))
        {
            char path[256];
            if (fscanf(input, "%255s", path) != 1)
                return problem("Missing CSV path");
            if (!strcmp(command, "csv"))
                result = write_csv(path, table, state->precision);
            else
                result = load_csv(path, table, ',');
        }
        else if (!strcmp(command, "set"))
        {
            unsigned row = 0;
            unsigned column = 0;
            double value;
            result = row_parameter(input, table, &row);
            if (!result)
                result = column_parameter(input, table, &column);
            if (!result)
            {
                if (!read_number(input, &value))
                    return problem("Missing replacement cell");
                table->cells[row][column] = value;
            }
        }
        else if (!strcmp(command, "sort") || !strcmp(command, "normalize") ||
                 !strcmp(command, "standardize") || !strcmp(command, "accumulate") ||
                 !strcmp(command, "difference") || !strcmp(command, "rank") ||
                 !strcmp(command, "rolling") || !strcmp(command, "filter") ||
                 !strcmp(command, "drop") || !strcmp(command, "swap") ||
                 !strcmp(command, "correlate") || !strcmp(command, "stats") ||
                 !strcmp(command, "label"))
        {
            result = column_command(command, input, state);
        }
        else
        {
            return problem("Unknown table command");
        }
        if (result)
            return result;
    }
    return 0;
}

int main(int argc, char **argv)
{
    struct State state = {0};
    state.precision = 6;
    int option;
    int quiet = 0;
    opterr = 0;
    while ((option = getopt(argc, argv, "qhp:")) != -1)
    {
        if (option == 'q')
        {
            quiet = 1;
        }
        else if (option == 'h')
        {
            state.header = 1;
        }
        else if (option == 'p')
        {
            char *end;
            long value = strtol(optarg, &end, 10);
            if (!*optarg || *end || value < 0 || value > 9)
                return problem("Invalid precision");
            state.precision = (int)value;
        }
        else
        {
            return problem("Invalid option");
        }
    }
    if (argc - optind > 1)
        return problem("Too many files");
    FILE *input = stdin;
    if (optind < argc)
    {
        input = fopen(argv[optind], "r");
        if (!input)
            return problem("Cannot open input");
    }
    int result = read_table(input, &state.table);
    if (!result)
        result = execute(input, &state);
    if (input != stdin)
        fclose(input);
    if (result)
        return result;
    if (!quiet)
        display(&state.table, state.precision, state.header);
    return 0;
}
