#define _POSIX_C_SOURCE 200809L
#include "billing.h"
#include <getopt.h>
#include <stdlib.h>
#include <string.h>

static int read_product(FILE *input, const struct Invoice *invoice, unsigned *index)
{
    char code[32];
    if (!code_token(input, code))
        return bill_error("Invalid product code");
    int found = product_index(invoice, code);
    if (found < 0)
        return bill_error("Product is absent");
    *index = (unsigned)found;
    return 0;
}

static int define_product(FILE *input, struct Invoice *invoice)
{
    char code[32];
    int64_t price;
    int tax;
    if (!code_token(input, code) || !money_token(input, &price) || price < 0 ||
        !integer_token(input, 0, 7, &tax))
        return bill_error("Invalid product definition");
    int found = product_index(invoice, code);
    if (found < 0)
    {
        if (invoice->product_count == 32)
            return bill_error("Product limit exceeded");
        found = (int)invoice->product_count++;
        strcpy(invoice->products[found].code, code);
    }
    invoice->products[found].price = price;
    invoice->products[found].tax = (unsigned)tax;
    return 0;
}

static int add_band(FILE *input, struct Invoice *invoice)
{
    unsigned index = 0;
    int result = read_product(input, invoice, &index);
    if (result)
        return result;
    int minimum;
    int64_t price;
    if (!integer_token(input, 1, 10000, &minimum) || !money_token(input, &price) || price < 0)
        return bill_error("Invalid volume band");
    struct Product *product = &invoice->products[index];
    for (unsigned i = 0; i < product->band_count; i++)
    {
        if (product->bands[i].minimum == (unsigned)minimum)
        {
            product->bands[i].price = price;
            return 0;
        }
    }
    if (product->band_count == 8)
        return bill_error("Volume band limit exceeded");
    struct Band *band = &product->bands[product->band_count++];
    band->minimum = (unsigned)minimum;
    band->price = price;
    return 0;
}

static int sale(FILE *input, struct Invoice *invoice, int returned)
{
    unsigned index = 0;
    int result = read_product(input, invoice, &index);
    if (result)
        return result;
    int quantity;
    if (!integer_token(input, 1, 10000, &quantity))
        return bill_error("Invalid sale quantity");
    if (invoice->ledger.count == 128)
        return bill_error("Sale line limit exceeded");
    struct Sale *line = &invoice->ledger.sales[invoice->ledger.count++];
    line->product = index;
    line->quantity = returned ? -quantity : quantity;
    line->price = price_for(&invoice->products[index], (unsigned)quantity);
    line->discount = 0;
    return 0;
}

static int line_index(FILE *input, const struct Invoice *invoice, unsigned *index)
{
    int number;
    if (!integer_token(input, 0, 127, &number) || number >= (int)invoice->ledger.count)
        return bill_error("Invalid sale line index");
    *index = (unsigned)number;
    return 0;
}

static int edit_line(FILE *input, struct Invoice *invoice, int mode)
{
    unsigned index = 0;
    int result = line_index(input, invoice, &index);
    if (result)
        return result;
    struct Sale *line = &invoice->ledger.sales[index];
    if (mode == 0)
    {
        int discount;
        if (!integer_token(input, 0, 10000, &discount))
            return bill_error("Invalid line discount");
        line->discount = discount;
    }
    else if (mode == 1)
    {
        int quantity;
        if (!integer_token(input, -10000, 10000, &quantity))
            return bill_error("Invalid replacement quantity");
        line->quantity = quantity;
    }
    else if (mode == 2)
    {
        int64_t price;
        if (!money_token(input, &price) || price < 0)
            return bill_error("Invalid replacement price");
        line->price = price;
    }
    else
    {
        for (unsigned i = index + 1; i < invoice->ledger.count; i++)
            invoice->ledger.sales[i - 1] = invoice->ledger.sales[i];
        invoice->ledger.count--;
    }
    return 0;
}

static int set_tax(FILE *input, struct Invoice *invoice)
{
    int tax;
    int rate;
    if (!integer_token(input, 0, 7, &tax) || !integer_token(input, 0, 10000, &rate))
        return bill_error("Invalid tax rate");
    invoice->taxes[tax] = (unsigned)rate;
    return 0;
}

static int set_coupon(FILE *input, struct Invoice *invoice)
{
    char kind[32];
    if (fscanf(input, "%31s", kind) != 1)
        return bill_error("Missing coupon kind");
    if (!strcmp(kind, "none"))
    {
        invoice->ledger.coupon = 0;
        invoice->ledger.coupon_value = 0;
    }
    else if (!strcmp(kind, "amount"))
    {
        int64_t amount;
        if (!money_token(input, &amount) || amount < 0)
            return bill_error("Invalid coupon amount");
        invoice->ledger.coupon = 1;
        invoice->ledger.coupon_value = amount;
    }
    else if (!strcmp(kind, "rate"))
    {
        int rate;
        if (!integer_token(input, 0, 10000, &rate))
            return bill_error("Invalid coupon rate");
        invoice->ledger.coupon = 2;
        invoice->ledger.coupon_value = rate;
    }
    else
    {
        return bill_error("Invalid coupon kind");
    }
    return 0;
}

static int shipping(FILE *input, struct Invoice *invoice)
{
    int64_t base;
    int64_t unit;
    int64_t free_at;
    if (!money_token(input, &base) || !money_token(input, &unit) ||
        !money_token(input, &free_at) || base < 0 || unit < 0 || free_at < 0)
        return bill_error("Invalid shipping schedule");
    invoice->ship_base = base;
    invoice->ship_unit = unit;
    invoice->ship_free = free_at;
    return 0;
}

static int line_compare(const void *a, const void *b)
{
    const struct Sale *left = a;
    const struct Sale *right = b;
    if (left->product != right->product)
        return (left->product > right->product) - (left->product < right->product);
    if (left->price != right->price)
        return (left->price > right->price) - (left->price < right->price);
    return (left->quantity > right->quantity) - (left->quantity < right->quantity);
}

static void merge_lines(struct Invoice *invoice)
{
    struct Ledger *ledger = &invoice->ledger;
    unsigned count = 0;
    for (unsigned i = 0; i < ledger->count; i++)
    {
        struct Sale line = ledger->sales[i];
        unsigned j;
        for (j = 0; j < count; j++)
        {
            struct Sale *other = &ledger->sales[j];
            if (other->product == line.product && other->price == line.price &&
                other->discount == line.discount)
            {
                other->quantity += line.quantity;
                break;
            }
        }
        if (j == count)
            ledger->sales[count++] = line;
    }
    ledger->count = count;
}

static void product_report(const struct Invoice *invoice)
{
    for (unsigned p = 0; p < invoice->product_count; p++)
    {
        int quantity = 0;
        int64_t gross = 0;
        for (unsigned i = 0; i < invoice->ledger.count; i++)
        {
            const struct Sale *line = &invoice->ledger.sales[i];
            if (line->product != p)
                continue;
            quantity += line->quantity;
            gross += line->price * line->quantity;
        }
        printf("product %s %d ", invoice->products[p].code, quantity);
        print_money(stdout, gross);
        putchar('\n');
    }
}

static void catalog_report(const struct Invoice *invoice)
{
    for (unsigned i = 0; i < invoice->product_count; i++)
    {
        const struct Product *product = &invoice->products[i];
        printf("item %s ", product->code);
        print_money(stdout, product->price);
        printf(" %u\n", product->tax);
        for (unsigned j = 0; j < product->band_count; j++)
        {
            printf("band %s %u ", product->code, product->bands[j].minimum);
            print_money(stdout, product->bands[j].price);
            putchar('\n');
        }
    }
}

static int quote(FILE *input, const struct Invoice *invoice)
{
    unsigned index = 0;
    int result = read_product(input, invoice, &index);
    if (result)
        return result;
    int quantity;
    if (!integer_token(input, 1, 10000, &quantity))
        return bill_error("Invalid quote quantity");
    int64_t price = price_for(&invoice->products[index], (unsigned)quantity);
    int64_t subtotal = price * quantity;
    unsigned rate = invoice->taxes[invoice->products[index].tax];
    printf("quote %s %d ", invoice->products[index].code, quantity);
    print_money(stdout, price);
    putchar(' ');
    print_money(stdout, subtotal + divide_round(subtotal * rate, 10000, invoice->rounding));
    putchar('\n');
    return 0;
}

static int receipt(FILE *input, const struct Invoice *invoice)
{
    char path[256];
    if (fscanf(input, "%255s", path) != 1)
        return bill_error("Missing receipt path");
    FILE *output = fopen(path, "w");
    if (!output)
        return bill_error("Cannot create receipt");
    print_invoice(output, invoice, 1);
    fclose(output);
    return 0;
}

static int reprice(FILE *input, struct Invoice *invoice)
{
    unsigned product = 0;
    int result = read_product(input, invoice, &product);
    if (result)
        return result;
    for (unsigned i = 0; i < invoice->ledger.count; i++)
    {
        struct Sale *line = &invoice->ledger.sales[i];
        if (line->product != product)
            continue;
        unsigned quantity = (unsigned)abs(line->quantity);
        line->price = price_for(&invoice->products[product], quantity);
    }
    return 0;
}

static int plan(FILE *input, const struct Invoice *invoice)
{
    int periods;
    int rate;
    if (!integer_token(input, 1, 120, &periods) ||
        !integer_token(input, 0, 10000, &rate))
        return bill_error("Invalid payment plan");
    struct Totals totals = calculate_totals(invoice);
    if (totals.total < 0)
        return bill_error("Cannot finance a negative invoice");
    int64_t balance = totals.total;
    int64_t principal = divide_round(balance, periods, invoice->rounding);
    int64_t interest_total = 0;
    for (int period = 1; period <= periods; period++)
    {
        int64_t interest = divide_round(balance * rate, 10000, invoice->rounding);
        int64_t paid = principal;
        if (period == periods || paid > balance)
            paid = balance;
        balance -= paid;
        interest_total += interest;
        printf("payment %d ", period);
        print_money(stdout, paid);
        putchar(' ');
        print_money(stdout, interest);
        putchar(' ');
        print_money(stdout, balance);
        putchar('\n');
    }
    fputs("interest ", stdout);
    print_money(stdout, interest_total);
    putchar('\n');
    return 0;
}

static int settle(FILE *input, const struct Invoice *invoice)
{
    int64_t tendered;
    if (!money_token(input, &tendered) || tendered < 0)
        return bill_error("Invalid tendered amount");
    struct Totals totals = calculate_totals(invoice);
    int64_t difference = tendered - totals.total;
    if (difference >= 0)
    {
        fputs("change ", stdout);
        print_money(stdout, difference);
    }
    else
    {
        fputs("due ", stdout);
        print_money(stdout, -difference);
    }
    putchar('\n');
    return 0;
}

static int cash_total(FILE *input, const struct Invoice *invoice)
{
    int step;
    if (!integer_token(input, 1, 100, &step))
        return bill_error("Invalid cash step");
    struct Totals totals = calculate_totals(invoice);
    int64_t rounded = divide_round(totals.total, step, invoice->rounding) * step;
    fputs("cash ", stdout);
    print_money(stdout, rounded);
    fputs(" adjustment ", stdout);
    print_money(stdout, rounded - totals.total);
    putchar('\n');
    return 0;
}

static int delete_band(FILE *input, struct Invoice *invoice)
{
    unsigned index = 0;
    int result = read_product(input, invoice, &index);
    if (result)
        return result;
    int minimum;
    if (!integer_token(input, 1, 10000, &minimum))
        return bill_error("Invalid removed band");
    struct Product *product = &invoice->products[index];
    for (unsigned i = 0; i < product->band_count; i++)
    {
        if (product->bands[i].minimum != (unsigned)minimum)
            continue;
        for (unsigned j = i + 1; j < product->band_count; j++)
            product->bands[j - 1] = product->bands[j];
        product->band_count--;
        return 0;
    }
    return bill_error("Volume band is absent");
}

static void tax_report(const struct Invoice *invoice)
{
    struct Totals totals = calculate_totals(invoice);
    int64_t sum = 0;
    for (unsigned i = 0; i < 8; i++)
    {
        printf("class %u rate %u base ", i, invoice->taxes[i]);
        print_money(stdout, totals.bases[i]);
        fputs(" tax ", stdout);
        print_money(stdout, totals.taxes[i]);
        putchar('\n');
        sum += totals.taxes[i];
    }
    fputs("tax-total ", stdout);
    print_money(stdout, sum);
    putchar('\n');
}

static int export_catalog(FILE *input, const struct Invoice *invoice)
{
    char path[256];
    if (fscanf(input, "%255s", path) != 1)
        return bill_error("Missing catalog path");
    FILE *output = fopen(path, "w");
    if (!output)
        return bill_error("Cannot create catalog");
    fputs("code,price,tax,bands\n", output);
    for (unsigned i = 0; i < invoice->product_count; i++)
    {
        const struct Product *product = &invoice->products[i];
        fprintf(output, "%s,", product->code);
        print_money(output, product->price);
        fprintf(output, ",%u,%u\n", product->tax, product->band_count);
    }
    fclose(output);
    return 0;
}

static void audit(const struct Invoice *invoice)
{
    struct Totals totals = calculate_totals(invoice);
    unsigned discounted = 0;
    unsigned returned = 0;
    unsigned zero = 0;
    int64_t smallest = 0;
    int64_t largest = 0;
    for (unsigned i = 0; i < invoice->ledger.count; i++)
    {
        const struct Sale *line = &invoice->ledger.sales[i];
        int64_t value = line->price * line->quantity;
        if (i == 0 || value < smallest)
            smallest = value;
        if (i == 0 || value > largest)
            largest = value;
        discounted += line->discount != 0;
        returned += line->quantity < 0;
        zero += line->quantity == 0 || line->price == 0;
    }
    printf("audit products %u discounted %u returned %u zero %u\n",
        invoice->product_count, discounted, returned, zero);
    fputs("line-range ", stdout);
    print_money(stdout, smallest);
    putchar(' ');
    print_money(stdout, largest);
    putchar('\n');
    printf("saved %s\n", invoice->has_saved ? "yes" : "no");
    fputs("net-merchandise ", stdout);
    print_money(stdout, totals.gross - totals.discount);
    putchar('\n');
}

int process_invoice(FILE *input, struct Invoice *invoice)
{
    char command[80];
    unsigned commands = 0;
    while (fscanf(input, "%79s", command) == 1)
    {
        if (++commands > 4096)
            return bill_error("Command limit exceeded");
        int result = 0;
        if (!strcmp(command, "plan"))
            result = plan(input, invoice);
        else if (!strcmp(command, "settle"))
            result = settle(input, invoice);
        else if (!strcmp(command, "cash"))
            result = cash_total(input, invoice);
        else if (!strcmp(command, "unband"))
            result = delete_band(input, invoice);
        else if (!strcmp(command, "taxes"))
            tax_report(invoice);
        else if (!strcmp(command, "export"))
            result = export_catalog(input, invoice);
        else if (!strcmp(command, "audit"))
            audit(invoice);
        else if (!strcmp(command, "item"))
            result = define_product(input, invoice);
        else if (!strcmp(command, "band"))
            result = add_band(input, invoice);
        else if (!strcmp(command, "sale"))
            result = sale(input, invoice, 0);
        else if (!strcmp(command, "return"))
            result = sale(input, invoice, 1);
        else if (!strcmp(command, "discount"))
            result = edit_line(input, invoice, 0);
        else if (!strcmp(command, "quantity"))
            result = edit_line(input, invoice, 1);
        else if (!strcmp(command, "price"))
            result = edit_line(input, invoice, 2);
        else if (!strcmp(command, "drop"))
            result = edit_line(input, invoice, 3);
        else if (!strcmp(command, "tax"))
            result = set_tax(input, invoice);
        else if (!strcmp(command, "coupon"))
            result = set_coupon(input, invoice);
        else if (!strcmp(command, "shipping"))
            result = shipping(input, invoice);
        else if (!strcmp(command, "credit") || !strcmp(command, "fee"))
        {
            int64_t amount;
            if (!money_token(input, &amount))
                return bill_error("Invalid ledger amount");
            if (!strcmp(command, "credit"))
                invoice->ledger.credit = amount;
            else
                invoice->ledger.shipping = amount;
        }
        else if (!strcmp(command, "round"))
        {
            int mode;
            if (!integer_token(input, 0, 3, &mode))
                return bill_error("Invalid rounding mode");
            invoice->rounding = mode;
        }
        else if (!strcmp(command, "currency"))
        {
            char code[32];
            if (!code_token(input, code) || strlen(code) > 15)
                return bill_error("Invalid currency name");
            strcpy(invoice->currency, code);
        }
        else if (!strcmp(command, "save"))
        {
            invoice->saved = invoice->ledger;
            invoice->has_saved = 1;
        }
        else if (!strcmp(command, "restore"))
        {
            if (!invoice->has_saved)
                return bill_error("No saved ledger");
            invoice->ledger = invoice->saved;
        }
        else if (!strcmp(command, "clear"))
        {
            memset(&invoice->ledger, 0, sizeof(invoice->ledger));
        }
        else if (!strcmp(command, "sort"))
        {
            qsort(invoice->ledger.sales, invoice->ledger.count,
                sizeof(struct Sale), line_compare);
        }
        else if (!strcmp(command, "merge"))
            merge_lines(invoice);
        else if (!strcmp(command, "products"))
            product_report(invoice);
        else if (!strcmp(command, "catalog"))
            catalog_report(invoice);
        else if (!strcmp(command, "quote"))
            result = quote(input, invoice);
        else if (!strcmp(command, "receipt"))
            result = receipt(input, invoice);
        else if (!strcmp(command, "reprice"))
            result = reprice(input, invoice);
        else if (!strcmp(command, "show"))
            print_invoice(stdout, invoice, 1);
        else
            return bill_error("Unknown invoice command");
        if (result)
            return result;
    }
    return 0;
}

int main(int argc, char **argv)
{
    struct Invoice invoice = {0};
    strcpy(invoice.currency, "unit");
    int detail = 0;
    int quiet = 0;
    int option;
    opterr = 0;
    while ((option = getopt(argc, argv, "dqr:")) != -1)
    {
        switch (option)
        {
            case 'd':
                detail = 1;
                break;
            case 'q':
                quiet = 1;
                break;
            case 'r':
            {
                char *end;
                long mode = strtol(optarg, &end, 10);
                if (!*optarg || *end || mode < 0 || mode > 3)
                    return bill_error("Invalid rounding option");
                invoice.rounding = (int)mode;
                break;
            }
            default:
                return bill_error("Invalid option");
        }
    }
    if (argc - optind > 1)
        return bill_error("Too many files");
    FILE *input = stdin;
    if (optind < argc)
    {
        input = fopen(argv[optind], "r");
        if (!input)
            return bill_error("Cannot open input");
    }
    int result = process_invoice(input, &invoice);
    if (input != stdin)
        fclose(input);
    if (result)
        return result;
    if (!quiet)
        print_invoice(stdout, &invoice, detail);
    return 0;
}
