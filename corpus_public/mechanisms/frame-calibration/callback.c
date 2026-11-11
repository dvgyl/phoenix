#include <stdio.h>
#include <stdlib.h>

__attribute__((noinline)) static int compare_values(
    const void *left, const void *right) {
    int first = *(const int *)left;
    int second = *(const int *)right;
    return (first > second) - (first < second);
}

int main(void) {
    int input = getchar();
    int value = input == EOF ? 0 : (unsigned char)input;
    int values[4] = {value, 3, 2, 1};
    qsort(values, 4, sizeof(values[0]), compare_values);
    printf("%d %d %d %d\n", values[0], values[1], values[2], values[3]);
    return 0;
}
