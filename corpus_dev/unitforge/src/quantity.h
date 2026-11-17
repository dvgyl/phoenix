#ifndef UNITFORGE_QUANTITY_H
#define UNITFORGE_QUANTITY_H
#include <stdio.h>

#define STACK_SIZE 64
#define DIMENSIONS 5
#define DEGREE_LIMIT 16

struct Unit
{
    double scale;
    double offset;
    int powers[DIMENSIONS];
};

struct Quantity
{
    double value;
    int powers[DIMENSIONS];
};

struct UnitName
{
    const char *name;
    double scale;
    double offset;
    int powers[DIMENSIONS];
};

struct Stack
{
    struct Quantity values[STACK_SIZE];
    unsigned count;
    struct Quantity memory[26];
    unsigned char assigned[26];
    struct Quantity previous;
    int has_previous;
    int precision;
    int trace;
};

struct Polynomial
{
    double coefficients[DEGREE_LIMIT + 1];
    unsigned degree;
    int valid;
};

struct Workbench
{
    struct Stack stack;
    struct Polynomial polynomial;
    struct Polynomial saved;
};

struct Unary
{
    const char *name;
    double (*function)(double);
    int dimensional;
};

int calc_error(const char *message);
int numeric_text(const char *text, double *value);
int numeric_token(FILE *input, double *value);
int index_token(FILE *input, unsigned limit, unsigned *value);
int unit_parse(const char *text, struct Unit *unit);
int same_dimension(const struct Quantity *left, const struct Quantity *right);
int dimensionless(const struct Quantity *quantity);
int push(struct Stack *stack, struct Quantity quantity);
int pop(struct Stack *stack, struct Quantity *quantity);
void print_quantity(const struct Quantity *quantity, int precision);
int push_input(FILE *input, struct Stack *stack);
int convert_input(FILE *input, struct Stack *stack);
int binary_operation(struct Stack *stack, int operation);
int unary_operation(struct Stack *stack, const char *name);
int stack_operation(struct Stack *stack, const char *name);
int stack_statistics(struct Stack *stack, const char *name);
int polynomial_command(FILE *input, struct Workbench *workbench, const char *name);
int fit_command(FILE *input, struct Stack *stack);
int run_commands(FILE *input, struct Workbench *workbench);
#endif
