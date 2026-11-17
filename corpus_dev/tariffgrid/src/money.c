#include "billing.h"
#include <ctype.h>
#include <stdlib.h>
#include <string.h>

int bill_error(const char *text)
{
    fprintf(stderr, "%s\n", text);
    return 3;
}

int integer_token(FILE *input, int minimum, int maximum, int *value)
{
    char token[80];
    char *end;
    if (fscanf(input, "%79s", token) != 1)
        return 0;
    long number = strtol(token, &end, 10);
    if (*end || number < minimum || number > maximum)
        return 0;
    *value = (int)number;
    return 1;
}

int money_text(const char *text, int64_t *value)
{
    int negative = 0;
    if (*text == '-' || *text == '+')
        negative = *text++ == '-';
    if (!isdigit((unsigned char)*text))
        return 0;
    int64_t whole = 0;
    while (isdigit((unsigned char)*text))
    {
        whole = whole * 10 + *text++ - '0';
        if (whole > 1000000)
            return 0;
    }
    int fraction = 0;
    if (*text == '.')
    {
        text++;
        if (!isdigit((unsigned char)*text))
            return 0;
        fraction = (*text++ - '0') * 10;
        if (isdigit((unsigned char)*text))
            fraction += *text++ - '0';
    }
    if (*text)
        return 0;
    *value = whole * 100 + fraction;
    if (negative)
        *value = -*value;
    return 1;
}

int money_token(FILE *input, int64_t *value)
{
    char token[80];
    if (fscanf(input, "%79s", token) != 1)
        return 0;
    return money_text(token, value);
}

int code_token(FILE *input, char *code)
{
    char token[80];
    if (fscanf(input, "%79s", token) != 1 || strlen(token) > 31)
        return 0;
    for (const unsigned char *p = (const unsigned char *)token; *p; p++)
    {
        if (!isalnum(*p) && *p != '_' && *p != '-')
            return 0;
    }
    strcpy(code, token);
    return 1;
}

void print_money(FILE *output, int64_t value)
{
    if (value < 0)
    {
        fputc('-', output);
        value = -value;
    }
    fprintf(output, "%lld.%02lld", (long long)(value / 100), (long long)(value % 100));
}

int64_t divide_round(int64_t numerator, int64_t denominator, int mode)
{
    int negative = numerator < 0;
    if (negative)
        numerator = -numerator;
    int64_t result = numerator / denominator;
    int64_t remainder = numerator % denominator;
    switch (mode)
    {
        case 0:
            if (remainder * 2 >= denominator)
                result++;
            break;
        case 1:
            if (remainder * 2 > denominator ||
                (remainder * 2 == denominator && (result & 1)))
                result++;
            break;
        case 2:
            break;
        case 3:
            if (remainder)
                result++;
            break;
    }
    return negative ? -result : result;
}

int product_index(const struct Invoice *invoice, const char *code)
{
    for (unsigned i = 0; i < invoice->product_count; i++)
    {
        if (!strcmp(invoice->products[i].code, code))
            return (int)i;
    }
    return -1;
}

int64_t price_for(const struct Product *product, unsigned quantity)
{
    int64_t price = product->price;
    unsigned minimum = 0;
    for (unsigned i = 0; i < product->band_count; i++)
    {
        if (product->bands[i].minimum <= quantity && product->bands[i].minimum >= minimum)
        {
            minimum = product->bands[i].minimum;
            price = product->bands[i].price;
        }
    }
    return price;
}

struct Totals calculate_totals(const struct Invoice *invoice)
{
    struct Totals totals = {0};
    const struct Ledger *ledger = &invoice->ledger;
    for (unsigned i = 0; i < ledger->count; i++)
    {
        const struct Sale *sale = &ledger->sales[i];
        const struct Product *product = &invoice->products[sale->product];
        int64_t gross = sale->price * sale->quantity;
        int64_t discount = divide_round(gross * sale->discount, 10000, invoice->rounding);
        totals.gross += gross;
        totals.discount += discount;
        totals.bases[product->tax] += gross - discount;
        totals.units += sale->quantity;
    }
    int64_t available = totals.gross - totals.discount;
    int64_t coupon = 0;
    if (ledger->coupon == 1)
        coupon = ledger->coupon_value;
    else if (ledger->coupon == 2)
        coupon = divide_round(available * ledger->coupon_value, 10000, invoice->rounding);
    if (coupon > available && available >= 0)
        coupon = available;
    if (available != 0 && coupon != 0)
    {
        int64_t remaining = coupon;
        for (unsigned i = 0; i < 8; i++)
        {
            int64_t base = totals.bases[i];
            int64_t share = 0;
            if (remaining > 0 && base > 0)
                share = remaining < base ? remaining : base;
            else if (remaining < 0 && base < 0)
                share = remaining > base ? remaining : base;
            totals.bases[i] -= share;
            remaining -= share;
        }
    }
    totals.discount += coupon;
    for (unsigned i = 0; i < 8; i++)
        totals.taxes[i] = divide_round(totals.bases[i] * invoice->taxes[i], 10000, invoice->rounding);
    totals.credit = ledger->credit;
    totals.shipping = invoice->ship_base + ledger->shipping;
    if (totals.units > 0)
        totals.shipping += invoice->ship_unit * totals.units;
    if (invoice->ship_free > 0 && available - coupon >= invoice->ship_free)
        totals.shipping = 0;
    totals.total = totals.gross - totals.discount - totals.credit + totals.shipping;
    for (unsigned i = 0; i < 8; i++)
        totals.total += totals.taxes[i];
    return totals;
}

static void labelled_money(FILE *output, const char *label, int64_t amount)
{
    fprintf(output, "%s ", label);
    print_money(output, amount);
    fputc('\n', output);
}

void print_invoice(FILE *output, const struct Invoice *invoice, int detail)
{
    struct Totals totals = calculate_totals(invoice);
    fprintf(output, "currency %s\n", invoice->currency);
    if (detail)
    {
        for (unsigned i = 0; i < invoice->ledger.count; i++)
        {
            const struct Sale *sale = &invoice->ledger.sales[i];
            fprintf(output, "%u %s %d ", i, invoice->products[sale->product].code, sale->quantity);
            print_money(output, sale->price);
            fprintf(output, " %lld\n", (long long)sale->discount);
        }
    }
    labelled_money(output, "gross", totals.gross);
    labelled_money(output, "discount", totals.discount);
    labelled_money(output, "credit", totals.credit);
    labelled_money(output, "shipping", totals.shipping);
    for (unsigned i = 0; i < 8; i++)
    {
        if (totals.bases[i] || totals.taxes[i])
        {
            fprintf(output, "tax %u ", i);
            print_money(output, totals.bases[i]);
            fputc(' ', output);
            print_money(output, totals.taxes[i]);
            fputc('\n', output);
        }
    }
    fprintf(output, "units %d lines %u\n", totals.units, invoice->ledger.count);
    labelled_money(output, "total", totals.total);
}
