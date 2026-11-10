#ifndef M2_TRACE_FIXTURE_H
#define M2_TRACE_FIXTURE_H
#include <stddef.h>

struct node {
    unsigned char *bytes;
    size_t length;
    struct node *next;
};
typedef unsigned char (*operation)(unsigned char);
unsigned char increment(unsigned char value);
unsigned char exclusive_or(unsigned char value);
size_t walk(struct node *head, operation apply);
#endif
