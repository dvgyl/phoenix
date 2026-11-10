#include "fixture.h"
#include <stdio.h>
#include <string.h>

int main(int argc, char **argv) {
    if (argc != 2 || (strcmp(argv[1], "inc") && strcmp(argv[1], "xor"))) {
        return 2;
    }
    unsigned char buffer[8] = {0};
    size_t length = fread(buffer, 1, sizeof(buffer), stdin);
    size_t split = length / 2;
    struct node second = {buffer + split, length - split, NULL};
    struct node first = {buffer, split, &second};
    operation selected = strcmp(argv[1], "inc") == 0 ? increment : exclusive_or;
#ifdef WRONG_TARGET
    selected = exclusive_or;
#endif
    size_t changed = walk(&first, selected);
#ifdef WRONG_COUNT
    if (changed) {
        --changed;
    }
#endif
    size_t written = fwrite(buffer, 1, changed, stdout);
    return written == changed && !ferror(stdin) && !ferror(stdout) ? 0 : 3;
}
