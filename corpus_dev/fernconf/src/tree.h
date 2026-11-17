#ifndef FERNCONF_TREE_H
#define FERNCONF_TREE_H
#include <stdio.h>

#define NODE_LIMIT 128
#define TOKEN_LIMIT 256

enum Kind
{
    SECTION,
    STRING,
    NUMBER,
    BOOLEAN,
    NOTHING
};

struct Node
{
    char key[48];
    char text[256];
    double number;
    enum Kind kind;
    int parent;
    int active;
    unsigned order;
};

struct Tree
{
    struct Node nodes[NODE_LIMIT];
    unsigned serial;
    unsigned changed;
    int sorted;
    int precision;
};

struct Lexer
{
    FILE *input;
    unsigned line;
    int error;
};

struct Summary
{
    unsigned sections;
    unsigned strings;
    unsigned numbers;
    unsigned booleans;
    unsigned nulls;
    unsigned characters;
    unsigned depth;
    double sum;
    double minimum;
    double maximum;
};

int tree_error(const char *message);
int token(struct Lexer *lexer, char *text);
void tree_init(struct Tree *tree);
int path_find(const struct Tree *tree, const char *path);
int path_create(struct Tree *tree, const char *path, enum Kind kind);
int set_value(struct Tree *tree, const char *path, const char *value);
void remove_node(struct Tree *tree, int index);
int children(const struct Tree *tree, int parent, int *indices);
void node_path(const struct Tree *tree, int index, char *path);
void print_node(const struct Tree *tree, int index, unsigned depth, int flat);
void summarize(const struct Tree *tree, int index, unsigned depth, struct Summary *summary);
int clone_node(struct Tree *tree, int source, int parent, const char *key, unsigned depth);
int process(struct Lexer *lexer, struct Tree *tree, unsigned depth);
#endif
