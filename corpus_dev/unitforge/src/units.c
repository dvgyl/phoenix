#include "quantity.h"
#include <ctype.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>

static const struct UnitName units[] =
{
    {"1", 1, 0, {0, 0, 0, 0, 0}},
    {"m", 1, 0, {1, 0, 0, 0, 0}},
    {"cm", 0.01, 0, {1, 0, 0, 0, 0}},
    {"mm", 0.001, 0, {1, 0, 0, 0, 0}},
    {"km", 1000, 0, {1, 0, 0, 0, 0}},
    {"in", 0.0254, 0, {1, 0, 0, 0, 0}},
    {"ft", 0.3048, 0, {1, 0, 0, 0, 0}},
    {"kg", 1, 0, {0, 1, 0, 0, 0}},
    {"g", 0.001, 0, {0, 1, 0, 0, 0}},
    {"lb", 0.45359237, 0, {0, 1, 0, 0, 0}},
    {"s", 1, 0, {0, 0, 1, 0, 0}},
    {"ms", 0.001, 0, {0, 0, 1, 0, 0}},
    {"min", 60, 0, {0, 0, 1, 0, 0}},
    {"h", 3600, 0, {0, 0, 1, 0, 0}},
    {"K", 1, 0, {0, 0, 0, 1, 0}},
    {"C", 1, 273.15, {0, 0, 0, 1, 0}},
    {"F", 5.0 / 9, 255.3722222222222, {0, 0, 0, 1, 0}},
    {"mol", 1, 0, {0, 0, 0, 0, 1}},
    {"N", 1, 0, {1, 1, -2, 0, 0}},
    {"J", 1, 0, {2, 1, -2, 0, 0}},
    {"W", 1, 0, {2, 1, -3, 0, 0}},
    {"Pa", 1, 0, {-1, 1, -2, 0, 0}},
    {"Hz", 1, 0, {0, 0, -1, 0, 0}},
    {"L", 0.001, 0, {3, 0, 0, 0, 0}},
    {"rad", 1, 0, {0, 0, 0, 0, 0}},
    {"deg", 0.017453292519943295, 0, {0, 0, 0, 0, 0}}
};

int calc_error(const char *message)
{
    fprintf(stderr, "%s\n", message);
    return 3;
}

int numeric_text(const char *text, double *value)
{
    char *end;
    double parsed = strtod(text, &end);
    if (!*text || *end || !isfinite(parsed) || fabs(parsed) > 1e12)
        return 0;
    *value = parsed;
    return 1;
}

int numeric_token(FILE *input, double *value)
{
    char text[128];
    if (fscanf(input, "%127s", text) != 1)
        return 0;
    return numeric_text(text, value);
}

int index_token(FILE *input, unsigned limit, unsigned *value)
{
    char text[80];
    char *end;
    if (fscanf(input, "%79s", text) != 1)
        return 0;
    unsigned long parsed = strtoul(text, &end, 10);
    if (*end || parsed > limit)
        return 0;
    *value = (unsigned)parsed;
    return 1;
}

static int unit_atom(const char **cursor, struct Unit *unit)
{
    char name[16];
    unsigned used = 0;
    while (isalpha((unsigned char)**cursor) || **cursor == '1')
    {
        if (used == 15)
            return 0;
        name[used++] = *(*cursor)++;
    }
    name[used] = 0;
    if (!used)
        return 0;
    const struct UnitName *found = NULL;
    for (unsigned i = 0; i < sizeof(units) / sizeof(*units); i++)
    {
        if (!strcmp(name, units[i].name))
        {
            found = &units[i];
            break;
        }
    }
    if (!found)
        return 0;
    int exponent = 1;
    if (**cursor == '^')
    {
        (*cursor)++;
        char *end;
        long parsed = strtol(*cursor, &end, 10);
        if (end == *cursor || parsed < -8 || parsed > 8)
            return 0;
        *cursor = end;
        exponent = (int)parsed;
    }
    if (found->offset && exponent != 1)
        return 0;
    unit->scale = pow(found->scale, exponent);
    unit->offset = found->offset;
    for (unsigned i = 0; i < DIMENSIONS; i++)
        unit->powers[i] = found->powers[i] * exponent;
    return 1;
}

int unit_parse(const char *text, struct Unit *unit)
{
    if (!unit_atom(&text, unit))
        return 0;
    while (*text)
    {
        int divide = *text == '/';
        if (*text != '*' && !divide)
            return 0;
        text++;
        struct Unit next;
        if (!unit_atom(&text, &next) || unit->offset || next.offset)
            return 0;
        if (divide)
            unit->scale /= next.scale;
        else
            unit->scale *= next.scale;
        for (unsigned i = 0; i < DIMENSIONS; i++)
        {
            unit->powers[i] += divide ? -next.powers[i] : next.powers[i];
            if (unit->powers[i] < -16 || unit->powers[i] > 16)
                return 0;
        }
    }
    return isfinite(unit->scale) && unit->scale > 0;
}

int same_dimension(const struct Quantity *left, const struct Quantity *right)
{
    for (unsigned i = 0; i < DIMENSIONS; i++)
    {
        if (left->powers[i] != right->powers[i])
            return 0;
    }
    return 1;
}

int dimensionless(const struct Quantity *quantity)
{
    for (unsigned i = 0; i < DIMENSIONS; i++)
    {
        if (quantity->powers[i])
            return 0;
    }
    return 1;
}

int push(struct Stack *stack, struct Quantity quantity)
{
    if (stack->count == STACK_SIZE)
        return calc_error("Stack limit exceeded");
    if (!isfinite(quantity.value) || fabs(quantity.value) > 1e12)
        return calc_error("Quantity exceeds numeric limit");
    for (unsigned i = 0; i < DIMENSIONS; i++)
    {
        if (quantity.powers[i] < -16 || quantity.powers[i] > 16)
            return calc_error("Dimension exponent exceeds limit");
    }
    stack->values[stack->count++] = quantity;
    return 0;
}

int pop(struct Stack *stack, struct Quantity *quantity)
{
    if (!stack->count)
        return calc_error("Stack is empty");
    *quantity = stack->values[--stack->count];
    stack->previous = *quantity;
    stack->has_previous = 1;
    return 0;
}

void print_quantity(const struct Quantity *quantity, int precision)
{
    double value = quantity->value;
    if (value == 0)
        value = 0;
    printf("%.*f", precision, value);
    static const char *names[DIMENSIONS] = {"m", "kg", "s", "K", "mol"};
    for (unsigned i = 0; i < DIMENSIONS; i++)
    {
        if (quantity->powers[i])
            printf(" %s^%d", names[i], quantity->powers[i]);
    }
    putchar('\n');
}

int push_input(FILE *input, struct Stack *stack)
{
    double value;
    char name[128];
    if (!numeric_token(input, &value) || fscanf(input, "%127s", name) != 1)
        return calc_error("Push needs a value and a unit");
    struct Unit unit;
    if (!unit_parse(name, &unit))
        return calc_error("Invalid unit expression");
    struct Quantity quantity = {value * unit.scale + unit.offset, {0}};
    memcpy(quantity.powers, unit.powers, sizeof(quantity.powers));
    return push(stack, quantity);
}

int convert_input(FILE *input, struct Stack *stack)
{
    char name[128];
    if (fscanf(input, "%127s", name) != 1 || !stack->count)
        return calc_error("Convert needs a unit and a quantity");
    struct Unit unit;
    if (!unit_parse(name, &unit))
        return calc_error("Invalid target unit");
    struct Quantity target = {0, {0}};
    memcpy(target.powers, unit.powers, sizeof(target.powers));
    const struct Quantity *quantity = &stack->values[stack->count - 1];
    if (!same_dimension(quantity, &target))
        return calc_error("Target unit has a different dimension");
    double value = (quantity->value - unit.offset) / unit.scale;
    if (!isfinite(value) || fabs(value) > 1e15)
        return calc_error("Converted value exceeds limit");
    printf("%.*f %s\n", stack->precision, value == 0 ? 0 : value, name);
    return 0;
}
