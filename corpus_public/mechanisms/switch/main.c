#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

static volatile uint32_t state;

__attribute__((noinline)) static uint32_t choose_path(uint32_t key, uint32_t value) {
    switch (key & 15u) {
    case 0:
        state += value;
        break;
    case 1:
        state ^= value * 3u;
        break;
    case 2:
        state -= value + 5u;
        break;
    case 3:
        state |= value << 2u;
        break;
    case 4:
        state &= value + 17u;
        break;
    case 5:
        state = state * 7u + value;
        break;
    case 6:
        state = (state >> 3u) ^ value;
        break;
    case 7:
        state = value / (state | 1u);
        break;
    case 8:
        state = value % (state | 3u);
        break;
    case 9:
        state = (state + value) ^ 0x91u;
        break;
    case 10:
        state = (state | value) * 11u;
        break;
    case 11:
        state = (state & value) + 29u;
        break;
    default:
        state = value ^ 0xa5u;
        break;
    }
    return state;
}

int main(int argc, char **argv) {
    uint32_t key = argc > 1 ? (uint32_t)strtoul(argv[1], NULL, 10) : 0u;
    int byte = getchar();
    uint32_t value = byte == EOF ? 0u : (unsigned char)byte;
    printf("%u\n", (unsigned int)choose_path(key, value));
    return 0;
}
