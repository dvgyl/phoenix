#ifndef TARIFFGRID_BILLING_H
#define TARIFFGRID_BILLING_H
#include <stdint.h>
#include <stdio.h>

struct Band
{
    unsigned minimum;
    int64_t price;
};

struct Product
{
    char code[32];
    int64_t price;
    unsigned tax;
    struct Band bands[8];
    unsigned band_count;
};

struct Sale
{
    unsigned product;
    int quantity;
    int64_t price;
    int64_t discount;
};

struct Ledger
{
    struct Sale sales[128];
    unsigned count;
    int64_t credit;
    int64_t shipping;
    unsigned coupon;
    int64_t coupon_value;
};

struct Invoice
{
    struct Product products[32];
    unsigned product_count;
    unsigned taxes[8];
    struct Ledger ledger;
    struct Ledger saved;
    int has_saved;
    int rounding;
    char currency[16];
    int64_t ship_base;
    int64_t ship_unit;
    int64_t ship_free;
};

struct Totals
{
    int64_t gross;
    int64_t discount;
    int64_t credit;
    int64_t shipping;
    int64_t taxes[8];
    int64_t bases[8];
    int64_t total;
    int units;
};

int bill_error(const char *text);
int integer_token(FILE *input, int minimum, int maximum, int *value);
int money_token(FILE *input, int64_t *value);
int money_text(const char *text, int64_t *value);
int code_token(FILE *input, char *code);
void print_money(FILE *output, int64_t value);
int64_t divide_round(int64_t numerator, int64_t denominator, int mode);
int product_index(const struct Invoice *invoice, const char *code);
int64_t price_for(const struct Product *product, unsigned quantity);
struct Totals calculate_totals(const struct Invoice *invoice);
void print_invoice(FILE *output, const struct Invoice *invoice, int detail);
int process_invoice(FILE *input, struct Invoice *invoice);
#endif
