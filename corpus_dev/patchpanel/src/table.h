#ifndef PATCHPANEL_TABLE_H
#define PATCHPANEL_TABLE_H
#include <stdio.h>

#define ROWS 32
#define COLS 16

struct Table
{
    unsigned rows;
    unsigned columns;
    double cells[ROWS][COLS];
    char labels[COLS][32];
};

struct State
{
    struct Table table;
    struct Table saved;
    int has_saved;
    int precision;
    int header;
};

struct Aggregate
{
    double sum;
    double square;
    double minimum;
    double maximum;
    double mean;
    unsigned count;
};

struct Pair
{
    double key;
    unsigned row;
};

int problem(const char *message);
int read_integer(FILE *input, int *value);
int read_number(FILE *input, double *value);
int read_table(FILE *input, struct Table *table);
int write_csv(const char *path, const struct Table *table, int precision);
int load_csv(const char *path, struct Table *table, int separator);
void display(const struct Table *table, int precision, int header);
void initialize_labels(struct Table *table);
void aggregate_add(struct Aggregate *aggregate, double value);
struct Aggregate aggregate_column(const struct Table *table, unsigned column);
void print_aggregate(const struct Aggregate *aggregate, int precision);
int execute(FILE *input, struct State *state);
#endif
