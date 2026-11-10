#include "fixture.h"

unsigned char increment(unsigned char value) {
    return (unsigned char)(value + 1);
}

unsigned char exclusive_or(unsigned char value) {
    return (unsigned char)(value ^ 0x5a);
}

size_t walk(struct node *head, operation apply) {
    size_t changed = 0;
    for (struct node *current = head; current; current = current->next) {
        for (size_t index = 0; index < current->length; ++index) {
            current->bytes[index] = apply(current->bytes[index]);
            ++changed;
        }
    }
    return changed;
}
