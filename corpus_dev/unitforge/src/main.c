#define _POSIX_C_SOURCE 200809L
#include "quantity.h"
#include <getopt.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>

static int memory_command(FILE *input, struct Stack *stack, int store)
{
    char name[32];
    if (fscanf(input, "%31s", name) != 1 || strlen(name) != 1 || *name < 'a' || *name > 'z')
        return calc_error("Memory name must be a lower-case letter");
    unsigned index = (unsigned)(*name - 'a');
    if (store)
    {
        struct Quantity quantity;
        int result = pop(stack, &quantity);
        if (result)
            return result;
        stack->memory[index] = quantity;
        stack->assigned[index] = 1;
        return 0;
    }
    if (!stack->assigned[index])
        return calc_error("Memory is not assigned");
    return push(stack, stack->memory[index]);
}

static int interpolate(FILE *input, struct Stack *stack)
{
    double x0;
    double x1;
    double y0;
    double y1;
    double x;
    if (!numeric_token(input, &x0) || !numeric_token(input, &y0) ||
        !numeric_token(input, &x1) || !numeric_token(input, &y1) || !numeric_token(input, &x))
        return calc_error("Interpolation needs five numbers");
    if (x0 == x1)
        return calc_error("Interpolation abscissas are equal");
    struct Quantity result = {y0 + (x - x0) * (y1 - y0) / (x1 - x0), {0}};
    return push(stack, result);
}

static int weighted_mean(FILE *input, struct Stack *stack)
{
    unsigned count;
    if (!index_token(input, 64, &count) || !count)
        return calc_error("Invalid weighted sample count");
    double total = 0;
    double weights = 0;
    for (unsigned i = 0; i < count; i++)
    {
        double value;
        double weight;
        if (!numeric_token(input, &value) || !numeric_token(input, &weight) || weight < 0)
            return calc_error("Invalid weighted sample");
        total += value * weight;
        weights += weight;
    }
    if (weights == 0)
        return calc_error("Weights sum to zero");
    struct Quantity result = {total / weights, {0}};
    return push(stack, result);
}

static int distance(FILE *input, struct Stack *stack)
{
    unsigned count;
    if (!index_token(input, 16, &count) || !count)
        return calc_error("Invalid vector dimension");
    double sum = 0;
    for (unsigned i = 0; i < count; i++)
    {
        double left;
        double right;
        if (!numeric_token(input, &left) || !numeric_token(input, &right))
            return calc_error("Missing vector component");
        double difference = left - right;
        sum += difference * difference;
    }
    struct Quantity result = {sqrt(sum), {0}};
    return push(stack, result);
}

static int progression(FILE *input, struct Stack *stack)
{
    double first;
    double step;
    unsigned count;
    char unit_name[128];
    if (!numeric_token(input, &first) || !numeric_token(input, &step) ||
        !index_token(input, STACK_SIZE, &count) || fscanf(input, "%127s", unit_name) != 1)
        return calc_error("Invalid progression parameters");
    struct Unit unit;
    if (!unit_parse(unit_name, &unit))
        return calc_error("Invalid progression unit");
    if (count + stack->count > STACK_SIZE)
        return calc_error("Progression exceeds stack limit");
    for (unsigned i = 0; i < count; i++)
    {
        struct Quantity quantity = {(first + step * i) * unit.scale + unit.offset, {0}};
        memcpy(quantity.powers, unit.powers, sizeof(quantity.powers));
        int result = push(stack, quantity);
        if (result)
            return result;
    }
    return 0;
}

static int quadratic(FILE *input, struct Stack *stack)
{
    double a;
    double b;
    double c;
    if (!numeric_token(input, &a) || !numeric_token(input, &b) || !numeric_token(input, &c))
        return calc_error("Quadratic needs three coefficients");
    if (a == 0)
    {
        if (b == 0)
        {
            if (c == 0)
                puts("roots unconstrained");
            else
                puts("roots none");
            return 0;
        }
        struct Quantity root = {-c / b, {0}};
        puts("roots linear");
        return push(stack, root);
    }
    double discriminant = b * b - 4 * a * c;
    if (discriminant < 0)
    {
        double real = -b / (2 * a);
        double imaginary = sqrt(-discriminant) / fabs(2 * a);
        printf("roots complex %.*f %.*f\n", stack->precision, real,
            stack->precision, imaginary);
        return 0;
    }
    if (discriminant == 0)
    {
        struct Quantity root = {-b / (2 * a), {0}};
        puts("roots repeated");
        return push(stack, root);
    }
    double q = -0.5 * (b + copysign(sqrt(discriminant), b));
    double first = q / a;
    double second = c / q;
    if (first > second)
    {
        double saved = first;
        first = second;
        second = saved;
    }
    struct Quantity root = {first, {0}};
    int result = push(stack, root);
    if (result)
        return result;
    root.value = second;
    return push(stack, root);
}

int run_commands(FILE *input, struct Workbench *workbench)
{
    char command[80];
    struct Stack *stack = &workbench->stack;
    unsigned count = 0;
    while (fscanf(input, "%79s", command) == 1)
    {
        if (++count > 4096)
            return calc_error("Command limit exceeded");
        int result;
        if (!strcmp(command, "quadratic"))
            result = quadratic(input, stack);
        else if (!strcmp(command, "push"))
            result = push_input(input, stack);
        else if (!strcmp(command, "convert"))
            result = convert_input(input, stack);
        else if (strlen(command) == 1 && strchr("+-*/^<>=!%", *command))
            result = binary_operation(stack, *command);
        else if (!strcmp(command, "store") || !strcmp(command, "load"))
            result = memory_command(input, stack, !strcmp(command, "store"));
        else if (!strcmp(command, "sum") || !strcmp(command, "mean") ||
                 !strcmp(command, "sd") || !strcmp(command, "minimum") ||
                 !strcmp(command, "maximum") || !strcmp(command, "median") ||
                 !strcmp(command, "range"))
            result = stack_statistics(stack, command);
        else if (!strcmp(command, "poly") || !strcmp(command, "psave") ||
                 !strcmp(command, "padd") || !strcmp(command, "pmul") ||
                 !strcmp(command, "differentiate") || !strcmp(command, "integrate") ||
                 !strcmp(command, "root") || !strcmp(command, "peval") ||
                 !strcmp(command, "pshow") || !strcmp(command, "pshift") ||
                 !strcmp(command, "pdivide") || !strcmp(command, "area") ||
                 !strcmp(command, "grid") || !strcmp(command, "newton") ||
                 !strcmp(command, "compose") || !strcmp(command, "lagrange"))
            result = polynomial_command(input, workbench, command);
        else if (!strcmp(command, "fit"))
            result = fit_command(input, stack);
        else if (!strcmp(command, "interpolate"))
            result = interpolate(input, stack);
        else if (!strcmp(command, "weighted"))
            result = weighted_mean(input, stack);
        else if (!strcmp(command, "distance"))
            result = distance(input, stack);
        else if (!strcmp(command, "progression"))
            result = progression(input, stack);
        else if (!strcmp(command, "clear") || !strcmp(command, "last") ||
                 !strcmp(command, "depth") || !strcmp(command, "all") ||
                 !strcmp(command, "dup") || !strcmp(command, "drop") ||
                 !strcmp(command, "show") || !strcmp(command, "over") ||
                 !strcmp(command, "swap") || !strcmp(command, "rot"))
            result = stack_operation(stack, command);
        else
        {
            result = unary_operation(stack, command);
            if (result < 0)
                return calc_error("Unknown calculator command");
        }
        if (result)
            return result;
        if (stack->trace)
        {
            printf("step %u depth %u\n", count, stack->count);
            if (stack->count)
                print_quantity(&stack->values[stack->count - 1], stack->precision);
        }
    }
    return 0;
}

int main(int argc, char **argv)
{
    struct Workbench workbench = {0};
    workbench.stack.precision = 6;
    int quiet = 0;
    int option;
    opterr = 0;
    while ((option = getopt(argc, argv, "qtp:")) != -1)
    {
        if (option == 'q')
            quiet = 1;
        else if (option == 't')
            workbench.stack.trace = 1;
        else if (option == 'p')
        {
            char *end;
            long precision = strtol(optarg, &end, 10);
            if (!*optarg || *end || precision < 0 || precision > 9)
                return calc_error("Invalid precision");
            workbench.stack.precision = (int)precision;
        }
        else
            return calc_error("Invalid option");
    }
    if (argc - optind > 1)
        return calc_error("Too many files");
    FILE *input = stdin;
    if (optind < argc)
    {
        input = fopen(argv[optind], "r");
        if (!input)
            return calc_error("Cannot open input");
    }
    int result = run_commands(input, &workbench);
    if (input != stdin)
        fclose(input);
    if (result)
        return result;
    if (!quiet)
    {
        printf("stack %u\n", workbench.stack.count);
        for (unsigned i = 0; i < workbench.stack.count; i++)
            print_quantity(&workbench.stack.values[i], workbench.stack.precision);
    }
    return 0;
}
