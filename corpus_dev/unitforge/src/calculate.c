#include "quantity.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>

static double square(double value)
{
    return value * value;
}

static double cube(double value)
{
    return value * value * value;
}

static double reciprocal(double value)
{
    return value == 0 ? INFINITY : 1 / value;
}

static const struct Unary unary[] =
{
    {"neg", NULL, 1},
    {"abs", fabs, 1},
    {"floor", floor, 1},
    {"ceil", ceil, 1},
    {"round", round, 1},
    {"trunc", trunc, 1},
    {"sin", sin, 0},
    {"cos", cos, 0},
    {"tan", tan, 0},
    {"asin", asin, 0},
    {"acos", acos, 0},
    {"atan", atan, 0},
    {"exp", exp, 0},
    {"log", log, 0},
    {"log10", log10, 0},
    {"square", square, 2},
    {"cube", cube, 3},
    {"sqrt", sqrt, -2},
    {"cbrt", cbrt, -3},
    {"reciprocal", reciprocal, -1}
};

int unary_operation(struct Stack *stack, const char *name)
{
    unsigned index;
    for (index = 0; index < sizeof(unary) / sizeof(*unary); index++)
    {
        if (!strcmp(name, unary[index].name))
            break;
    }
    if (index == sizeof(unary) / sizeof(*unary))
        return -1;
    struct Quantity quantity;
    int result = pop(stack, &quantity);
    if (result)
        return result;
    int dimension = unary[index].dimensional;
    if (dimension == 0 && !dimensionless(&quantity))
        return calc_error("Function needs a dimensionless quantity");
    if (dimension == -2 || dimension == -3)
    {
        int divisor = -dimension;
        for (unsigned i = 0; i < DIMENSIONS; i++)
        {
            if (quantity.powers[i] % divisor)
                return calc_error("Root has a fractional dimension");
            quantity.powers[i] /= divisor;
        }
    }
    else if (dimension == 2 || dimension == 3 || dimension == -1)
    {
        for (unsigned i = 0; i < DIMENSIONS; i++)
            quantity.powers[i] *= dimension;
    }
    if (unary[index].function)
        quantity.value = unary[index].function(quantity.value);
    else
        quantity.value = -quantity.value;
    return push(stack, quantity);
}

int binary_operation(struct Stack *stack, int operation)
{
    struct Quantity left;
    struct Quantity right;
    if (pop(stack, &right) || pop(stack, &left))
        return 3;
    if (strchr("+-<>=!%", operation) && !same_dimension(&left, &right))
        return calc_error("Binary dimensions differ");
    switch (operation)
    {
        case '+':
            left.value += right.value;
            break;
        case '-':
            left.value -= right.value;
            break;
        case '*':
            left.value *= right.value;
            for (unsigned i = 0; i < DIMENSIONS; i++)
                left.powers[i] += right.powers[i];
            break;
        case '/':
            if (right.value == 0)
                return calc_error("Zero divisor");
            left.value /= right.value;
            for (unsigned i = 0; i < DIMENSIONS; i++)
                left.powers[i] -= right.powers[i];
            break;
        case '^':
            if (!dimensionless(&right) || floor(right.value) != right.value || fabs(right.value) > 8)
                return calc_error("Power needs an integer exponent from -8 to 8");
            left.value = pow(left.value, right.value);
            for (unsigned i = 0; i < DIMENSIONS; i++)
                left.powers[i] *= (int)right.value;
            break;
        case '<':
            left.value = fmin(left.value, right.value);
            break;
        case '>':
            left.value = fmax(left.value, right.value);
            break;
        case '%':
            if (right.value == 0)
                return calc_error("Zero remainder divisor");
            left.value = fmod(left.value, right.value);
            break;
        case '=':
            left.value = left.value == right.value;
            memset(left.powers, 0, sizeof(left.powers));
            break;
        case '!':
            left.value = left.value != right.value;
            memset(left.powers, 0, sizeof(left.powers));
            break;
        default:
            return calc_error("Unknown binary operation");
    }
    return push(stack, left);
}

int stack_operation(struct Stack *stack, const char *name)
{
    if (!strcmp(name, "clear"))
    {
        stack->count = 0;
        return 0;
    }
    if (!strcmp(name, "last"))
    {
        if (!stack->has_previous)
            return calc_error("No previous quantity");
        struct Quantity previous = stack->previous;
        return push(stack, previous);
    }
    if (!strcmp(name, "depth"))
    {
        printf("depth %u\n", stack->count);
        return 0;
    }
    if (!strcmp(name, "all"))
    {
        for (unsigned i = 0; i < stack->count; i++)
        {
            printf("%u ", i);
            print_quantity(&stack->values[i], stack->precision);
        }
        return 0;
    }
    if (!stack->count)
        return calc_error("Stack operation needs a quantity");
    if (!strcmp(name, "dup"))
    {
        struct Quantity value = stack->values[stack->count - 1];
        return push(stack, value);
    }
    if (!strcmp(name, "drop"))
    {
        struct Quantity discarded;
        return pop(stack, &discarded);
    }
    if (!strcmp(name, "show"))
    {
        print_quantity(&stack->values[stack->count - 1], stack->precision);
        return 0;
    }
    if (stack->count < 2)
        return calc_error("Stack operation needs two quantities");
    if (!strcmp(name, "over"))
    {
        struct Quantity value = stack->values[stack->count - 2];
        return push(stack, value);
    }
    if (!strcmp(name, "swap"))
    {
        struct Quantity value = stack->values[stack->count - 1];
        stack->values[stack->count - 1] = stack->values[stack->count - 2];
        stack->values[stack->count - 2] = value;
        return 0;
    }
    if (stack->count < 3)
        return calc_error("Rotation needs three quantities");
    struct Quantity value = stack->values[stack->count - 3];
    stack->values[stack->count - 3] = stack->values[stack->count - 2];
    stack->values[stack->count - 2] = stack->values[stack->count - 1];
    stack->values[stack->count - 1] = value;
    return 0;
}

static int compare_double(const void *a, const void *b)
{
    double left = *(const double *)a;
    double right = *(const double *)b;
    return (left > right) - (left < right);
}

int stack_statistics(struct Stack *stack, const char *name)
{
    if (!stack->count)
        return calc_error("Statistics need quantities");
    struct Quantity result = stack->values[0];
    double values[STACK_SIZE];
    double sum = 0;
    double mean = 0;
    double square_sum = 0;
    double minimum = result.value;
    double maximum = result.value;
    for (unsigned i = 0; i < stack->count; i++)
    {
        const struct Quantity *quantity = &stack->values[i];
        if (!same_dimension(&result, quantity))
            return calc_error("Statistics dimensions differ");
        values[i] = quantity->value;
        sum += quantity->value;
        double delta = quantity->value - mean;
        mean += delta / (i + 1);
        square_sum += delta * (quantity->value - mean);
        if (quantity->value < minimum)
            minimum = quantity->value;
        if (quantity->value > maximum)
            maximum = quantity->value;
    }
    if (!strcmp(name, "sum"))
        result.value = sum;
    else if (!strcmp(name, "mean"))
        result.value = mean;
    else if (!strcmp(name, "sd"))
        result.value = sqrt(fmax(0, square_sum / stack->count));
    else if (!strcmp(name, "minimum"))
        result.value = minimum;
    else if (!strcmp(name, "maximum"))
        result.value = maximum;
    else if (!strcmp(name, "range"))
        result.value = maximum - minimum;
    else
    {
        qsort(values, stack->count, sizeof(double), compare_double);
        if (stack->count % 2)
            result.value = values[stack->count / 2];
        else
            result.value = (values[stack->count / 2 - 1] + values[stack->count / 2]) / 2;
    }
    stack->count = 0;
    return push(stack, result);
}

static double evaluate(const struct Polynomial *polynomial, double x)
{
    double value = polynomial->coefficients[polynomial->degree];
    for (unsigned i = polynomial->degree; i > 0; i--)
        value = value * x + polynomial->coefficients[i - 1];
    return value;
}

static void trim_polynomial(struct Polynomial *polynomial)
{
    while (polynomial->degree && polynomial->coefficients[polynomial->degree] == 0)
        polynomial->degree--;
}

static int polynomial_read(FILE *input, struct Polynomial *polynomial)
{
    unsigned degree;
    if (!index_token(input, DEGREE_LIMIT, &degree))
        return calc_error("Invalid polynomial degree");
    memset(polynomial, 0, sizeof(*polynomial));
    polynomial->degree = degree;
    for (unsigned i = 0; i <= degree; i++)
    {
        if (!numeric_token(input, &polynomial->coefficients[i]))
            return calc_error("Invalid polynomial coefficient");
    }
    trim_polynomial(polynomial);
    polynomial->valid = 1;
    return 0;
}

static int polynomial_integrate(struct Polynomial *polynomial)
{
    if (polynomial->degree == DEGREE_LIMIT)
        return calc_error("Integral degree exceeds limit");
    for (unsigned i = polynomial->degree + 1; i > 0; i--)
        polynomial->coefficients[i] = polynomial->coefficients[i - 1] / i;
    polynomial->coefficients[0] = 0;
    polynomial->degree++;
    return 0;
}

static void polynomial_differentiate(struct Polynomial *polynomial)
{
    if (!polynomial->degree)
    {
        polynomial->coefficients[0] = 0;
        return;
    }
    for (unsigned i = 0; i < polynomial->degree; i++)
        polynomial->coefficients[i] = polynomial->coefficients[i + 1] * (i + 1);
    polynomial->coefficients[polynomial->degree--] = 0;
    trim_polynomial(polynomial);
}

static int polynomial_combine(struct Polynomial *left, const struct Polynomial *right, int multiply)
{
    if (!right->valid)
        return calc_error("No saved polynomial");
    struct Polynomial result = {{0}, 0, 1};
    if (multiply)
    {
        if (left->degree + right->degree > DEGREE_LIMIT)
            return calc_error("Product degree exceeds limit");
        result.degree = left->degree + right->degree;
        for (unsigned i = 0; i <= left->degree; i++)
        {
            for (unsigned j = 0; j <= right->degree; j++)
                result.coefficients[i + j] += left->coefficients[i] * right->coefficients[j];
        }
    }
    else
    {
        result.degree = left->degree > right->degree ? left->degree : right->degree;
        for (unsigned i = 0; i <= result.degree; i++)
            result.coefficients[i] = left->coefficients[i] + right->coefficients[i];
    }
    for (unsigned i = 0; i <= result.degree; i++)
    {
        if (!isfinite(result.coefficients[i]) || fabs(result.coefficients[i]) > 1e12)
            return calc_error("Polynomial coefficient exceeds limit");
    }
    trim_polynomial(&result);
    *left = result;
    return 0;
}

static int polynomial_root(FILE *input, const struct Polynomial *polynomial, struct Stack *stack)
{
    double low;
    double high;
    if (!numeric_token(input, &low) || !numeric_token(input, &high) || low >= high)
        return calc_error("Invalid root interval");
    double left = evaluate(polynomial, low);
    double right = evaluate(polynomial, high);
    if (!isfinite(left) || !isfinite(right))
        return calc_error("Root interval produces an invalid value");
    if (left != 0 && right != 0 && (left < 0) == (right < 0))
        return calc_error("Root interval does not bracket a sign change");
    double root = left == 0 ? low : high;
    if (left != 0 && right != 0)
    {
        for (unsigned iteration = 0; iteration < 60; iteration++)
        {
            root = low + (high - low) / 2;
            double value = evaluate(polynomial, root);
            if (value == 0)
                break;
            if ((value < 0) == (left < 0))
            {
                low = root;
                left = value;
            }
            else
                high = root;
        }
    }
    struct Quantity result = {root, {0}};
    return push(stack, result);
}

static int polynomial_shift(FILE *input, struct Polynomial *polynomial)
{
    double shift;
    if (!numeric_token(input, &shift) || fabs(shift) > 100)
        return calc_error("Invalid polynomial shift");
    struct Polynomial result = {{0}, polynomial->degree, 1};
    for (unsigned i = 0; i <= polynomial->degree; i++)
    {
        double binomial = 1;
        for (unsigned j = 0; j <= i; j++)
        {
            result.coefficients[j] += polynomial->coefficients[i] * binomial * pow(shift, (double)(i - j));
            if (j < i)
                binomial = binomial * (i - j) / (j + 1);
        }
    }
    for (unsigned i = 0; i <= result.degree; i++)
    {
        if (!isfinite(result.coefficients[i]) || fabs(result.coefficients[i]) > 1e12)
            return calc_error("Shifted coefficient exceeds limit");
    }
    *polynomial = result;
    return 0;
}

static int polynomial_divide(struct Workbench *workbench)
{
    struct Polynomial remainder = workbench->polynomial;
    const struct Polynomial *divisor = &workbench->saved;
    if (!divisor->valid)
        return calc_error("No polynomial divisor");
    if (divisor->coefficients[divisor->degree] == 0)
        return calc_error("Polynomial divisor is zero");
    struct Polynomial quotient = {{0}, 0, 1};
    if (remainder.degree >= divisor->degree)
    {
        quotient.degree = remainder.degree - divisor->degree;
        for (int i = (int)quotient.degree; i >= 0; i--)
        {
            double factor = remainder.coefficients[(unsigned)i + divisor->degree] /
                divisor->coefficients[divisor->degree];
            if (!isfinite(factor) || fabs(factor) > 1e12)
                return calc_error("Polynomial quotient exceeds limit");
            quotient.coefficients[i] = factor;
            for (unsigned j = 0; j <= divisor->degree; j++)
            {
                remainder.coefficients[(unsigned)i + j] -= factor * divisor->coefficients[j];
                if (!isfinite(remainder.coefficients[(unsigned)i + j]) ||
                    fabs(remainder.coefficients[(unsigned)i + j]) > 1e12)
                    return calc_error("Polynomial remainder exceeds limit");
            }
            remainder.coefficients[(unsigned)i + divisor->degree] = 0;
        }
    }
    trim_polynomial(&quotient);
    trim_polynomial(&remainder);
    printf("remainder %u", remainder.degree);
    for (unsigned i = 0; i <= remainder.degree; i++)
        printf(" %.*f", workbench->stack.precision, remainder.coefficients[i]);
    putchar('\n');
    workbench->polynomial = quotient;
    return 0;
}

static int polynomial_area(FILE *input, const struct Polynomial *polynomial, struct Stack *stack)
{
    double low;
    double high;
    if (!numeric_token(input, &low) || !numeric_token(input, &high))
        return calc_error("Area needs two bounds");
    double area = 0;
    double low_power = low;
    double high_power = high;
    for (unsigned i = 0; i <= polynomial->degree; i++)
    {
        area += polynomial->coefficients[i] * (high_power - low_power) / (i + 1);
        low_power *= low;
        high_power *= high;
    }
    struct Quantity result = {area, {0}};
    return push(stack, result);
}

static int polynomial_grid(FILE *input, const struct Polynomial *polynomial, struct Stack *stack)
{
    double start;
    double step;
    unsigned count;
    if (!numeric_token(input, &start) || !numeric_token(input, &step) ||
        !index_token(input, 128, &count))
        return calc_error("Invalid polynomial grid");
    for (unsigned i = 0; i < count; i++)
    {
        double x = start + step * i;
        double value = evaluate(polynomial, x);
        if (!isfinite(value) || fabs(value) > 1e12)
            return calc_error("Grid value exceeds limit");
        printf("grid %.*f %.*f\n", stack->precision, x, stack->precision, value);
    }
    return 0;
}

static int polynomial_newton(FILE *input, const struct Polynomial *polynomial, struct Stack *stack)
{
    double x;
    unsigned iterations;
    if (!numeric_token(input, &x) || !index_token(input, 100, &iterations) || !iterations)
        return calc_error("Invalid Newton parameters");
    struct Polynomial derivative = *polynomial;
    polynomial_differentiate(&derivative);
    for (unsigned i = 0; i < iterations; i++)
    {
        double value = evaluate(polynomial, x);
        double slope = evaluate(&derivative, x);
        if (!isfinite(value) || !isfinite(slope))
            return calc_error("Newton evaluation exceeds limit");
        if (value == 0)
            break;
        if (slope == 0)
            return calc_error("Newton derivative is zero");
        double next = x - value / slope;
        if (!isfinite(next) || fabs(next) > 1e12)
            return calc_error("Newton iterate exceeds limit");
        if (next == x)
            break;
        x = next;
    }
    struct Quantity result = {x, {0}};
    return push(stack, result);
}

static int polynomial_compose(struct Workbench *workbench)
{
    const struct Polynomial *outer = &workbench->polynomial;
    const struct Polynomial *inner = &workbench->saved;
    if (!inner->valid)
        return calc_error("No inner polynomial");
    if (outer->degree * inner->degree > DEGREE_LIMIT)
        return calc_error("Composition degree exceeds limit");
    struct Polynomial result = {{0}, 0, 1};
    result.coefficients[0] = outer->coefficients[outer->degree];
    for (unsigned i = outer->degree; i > 0; i--)
    {
        int failure = polynomial_combine(&result, inner, 1);
        if (failure)
            return failure;
        result.coefficients[0] += outer->coefficients[i - 1];
        if (fabs(result.coefficients[0]) > 1e12)
            return calc_error("Composition constant exceeds limit");
    }
    trim_polynomial(&result);
    workbench->polynomial = result;
    return 0;
}

static int lagrange(FILE *input, struct Stack *stack)
{
    unsigned count;
    double x;
    if (!index_token(input, 16, &count) || count < 1 || !numeric_token(input, &x))
        return calc_error("Invalid interpolation size");
    double xs[16];
    double ys[16];
    for (unsigned i = 0; i < count; i++)
    {
        if (!numeric_token(input, &xs[i]) || !numeric_token(input, &ys[i]))
            return calc_error("Invalid interpolation point");
        for (unsigned j = 0; j < i; j++)
        {
            if (xs[i] == xs[j])
                return calc_error("Interpolation abscissas repeat");
        }
    }
    double value = 0;
    for (unsigned i = 0; i < count; i++)
    {
        double term = ys[i];
        for (unsigned j = 0; j < count; j++)
        {
            if (i != j)
                term *= (x - xs[j]) / (xs[i] - xs[j]);
        }
        value += term;
    }
    struct Quantity result = {value, {0}};
    return push(stack, result);
}

int polynomial_command(FILE *input, struct Workbench *workbench, const char *name)
{
    struct Polynomial *polynomial = &workbench->polynomial;
    if (!strcmp(name, "lagrange"))
        return lagrange(input, &workbench->stack);
    if (!strcmp(name, "poly"))
        return polynomial_read(input, polynomial);
    if (!polynomial->valid)
        return calc_error("No current polynomial");
    if (!strcmp(name, "pshift"))
        return polynomial_shift(input, polynomial);
    if (!strcmp(name, "pdivide"))
        return polynomial_divide(workbench);
    if (!strcmp(name, "area"))
        return polynomial_area(input, polynomial, &workbench->stack);
    if (!strcmp(name, "grid"))
        return polynomial_grid(input, polynomial, &workbench->stack);
    if (!strcmp(name, "newton"))
        return polynomial_newton(input, polynomial, &workbench->stack);
    if (!strcmp(name, "compose"))
        return polynomial_compose(workbench);
    if (!strcmp(name, "psave"))
        workbench->saved = *polynomial;
    else if (!strcmp(name, "padd") || !strcmp(name, "pmul"))
        return polynomial_combine(polynomial, &workbench->saved, !strcmp(name, "pmul"));
    else if (!strcmp(name, "differentiate"))
        polynomial_differentiate(polynomial);
    else if (!strcmp(name, "integrate"))
        return polynomial_integrate(polynomial);
    else if (!strcmp(name, "root"))
        return polynomial_root(input, polynomial, &workbench->stack);
    else if (!strcmp(name, "peval"))
    {
        double x;
        if (!numeric_token(input, &x))
            return calc_error("Missing polynomial argument");
        struct Quantity quantity = {evaluate(polynomial, x), {0}};
        return push(&workbench->stack, quantity);
    }
    else
    {
        printf("polynomial %u", polynomial->degree);
        for (unsigned i = 0; i <= polynomial->degree; i++)
            printf(" %.*f", workbench->stack.precision, polynomial->coefficients[i]);
        putchar('\n');
    }
    return 0;
}

int fit_command(FILE *input, struct Stack *stack)
{
    unsigned count;
    if (!index_token(input, 128, &count) || count < 2)
        return calc_error("Fit needs 2 to 128 points");
    double xs[128];
    double ys[128];
    double mx = 0;
    double my = 0;
    for (unsigned i = 0; i < count; i++)
    {
        if (!numeric_token(input, &xs[i]) || !numeric_token(input, &ys[i]))
            return calc_error("Invalid fit point");
        mx += xs[i] / count;
        my += ys[i] / count;
    }
    double numerator = 0;
    double denominator = 0;
    for (unsigned i = 0; i < count; i++)
    {
        numerator += (xs[i] - mx) * (ys[i] - my);
        denominator += (xs[i] - mx) * (xs[i] - mx);
    }
    if (denominator == 0)
        return calc_error("Fit abscissas are constant");
    double slope = numerator / denominator;
    double intercept = my - slope * mx;
    double residual = 0;
    for (unsigned i = 0; i < count; i++)
    {
        double error = ys[i] - (slope * xs[i] + intercept);
        residual += error * error;
    }
    printf("fit %.*f %.*f residual %.*f\n", stack->precision, slope,
        stack->precision, intercept, stack->precision, residual);
    struct Quantity result = {slope, {0}};
    return push(stack, result);
}
