#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>

static int parse_decimal(const char *text, uint64_t *value)
{
    uint64_t result = 0;
    if (*text == '\0') {
        return 0;
    }
    for (; *text != '\0'; ++text) {
        if (*text < '0' || *text > '9') {
            return 0;
        }
        unsigned digit = (unsigned)(*text - '0');
        if (result > (UINT64_MAX - digit) / 10U) {
            return 0;
        }
        result = result * 10U + digit;
    }
    *value = result;
    return 1;
}

int main(int argc, char **argv)
{
    uint64_t amount;
    uint64_t charge;

    if (argc != 3) {
        fputs("supply amount and charge\n", stderr);
        return 2;
    }
    if (!parse_decimal(argv[1], &amount) || !parse_decimal(argv[2], &charge)) {
        fputs("invalid decimal\n", stderr);
        return 3;
    }
    uint64_t balance = amount >= charge ? amount - charge : 0;
    return printf("%" PRIu64 "\n", balance) < 0;
}
