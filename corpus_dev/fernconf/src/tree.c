#include "tree.h"
#include <ctype.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>

int tree_error(const char *message)
{
    fprintf(stderr, "%s\n", message);
    return 3;
}

int token(struct Lexer *lexer, char *text)
{
    int c;
    for (;;)
    {
        c = fgetc(lexer->input);
        if (c == '\n')
            lexer->line++;
        if (c == '#')
        {
            while ((c = fgetc(lexer->input)) != EOF && c != '\n')
                ;
            if (c == '\n')
                lexer->line++;
        }
        if (c == EOF)
            return 0;
        if (!isspace((unsigned char)c))
            break;
    }
    int quoted = c == '"';
    unsigned used = 0;
    if (quoted)
        c = fgetc(lexer->input);
    while (c != EOF)
    {
        if (quoted && c == '\n')
            lexer->line++;
        if (quoted && c == '"')
        {
            text[used] = 0;
            return 1;
        }
        if (!quoted && isspace((unsigned char)c))
        {
            if (c == '\n')
                lexer->line++;
            text[used] = 0;
            return 1;
        }
        if (c == '\\')
        {
            c = fgetc(lexer->input);
            switch (c)
            {
                case 'n':
                    c = '\n';
                    break;
                case 'r':
                    c = '\r';
                    break;
                case 't':
                    c = '\t';
                    break;
                case 's':
                    c = ' ';
                    break;
                case 'q':
                    c = '"';
                    break;
                case '\\':
                    break;
                case '#':
                    break;
                case '/':
                    break;
                default:
                    lexer->error = tree_error("Invalid token escape");
                    return 0;
            }
        }
        if (used == TOKEN_LIMIT - 1 || c == 0)
        {
            lexer->error = tree_error("Token limit exceeded");
            return 0;
        }
        text[used++] = (char)c;
        c = fgetc(lexer->input);
    }
    if (quoted)
    {
        lexer->error = tree_error("Unclosed quoted token");
        return 0;
    }
    text[used] = 0;
    return 1;
}

void tree_init(struct Tree *tree)
{
    memset(tree, 0, sizeof(*tree));
    tree->nodes[0].active = 1;
    tree->nodes[0].parent = -1;
    tree->nodes[0].kind = SECTION;
    tree->precision = 6;
}

static int child_find(const struct Tree *tree, int parent, const char *key)
{
    for (int i = 1; i < NODE_LIMIT; i++)
    {
        const struct Node *node = &tree->nodes[i];
        if (node->active && node->parent == parent && !strcmp(node->key, key))
            return i;
    }
    return -1;
}

static int key_valid(const char *text)
{
    if (!*text || strlen(text) > 47)
        return 0;
    for (; *text; text++)
    {
        if (!isalnum((unsigned char)*text) && *text != '_' && *text != '-')
            return 0;
    }
    return 1;
}

static int allocate_node(struct Tree *tree, int parent, const char *key, enum Kind kind)
{
    for (int i = 1; i < NODE_LIMIT; i++)
    {
        if (tree->nodes[i].active)
            continue;
        struct Node *node = &tree->nodes[i];
        memset(node, 0, sizeof(*node));
        node->active = 1;
        node->parent = parent;
        node->kind = kind;
        node->order = ++tree->serial;
        strcpy(node->key, key);
        return i;
    }
    return -1;
}

static int resolve(struct Tree *tree, const char *path, int create, enum Kind kind)
{
    if (!strcmp(path, "/"))
        return 0;
    if (*path != '/' || strlen(path) > 240)
        return -1;
    char copy[256];
    strcpy(copy, path + 1);
    char *cursor = copy;
    int parent = 0;
    unsigned depth = 0;
    for (;;)
    {
        if (++depth > 16)
            return -1;
        char *slash = strchr(cursor, '/');
        if (slash)
            *slash = 0;
        if (!key_valid(cursor))
            return -1;
        int child = child_find(tree, parent, cursor);
        if (child < 0 && create)
            child = allocate_node(tree, parent, cursor, slash ? SECTION : kind);
        if (child < 0)
            return -1;
        if (slash && tree->nodes[child].kind != SECTION)
            return -1;
        if (!slash)
            return child;
        parent = child;
        cursor = slash + 1;
    }
}

int path_find(const struct Tree *tree, const char *path)
{
    struct Tree copy = *tree;
    return resolve(&copy, path, 0, SECTION);
}

int path_create(struct Tree *tree, const char *path, enum Kind kind)
{
    return resolve(tree, path, 1, kind);
}

int children(const struct Tree *tree, int parent, int *indices)
{
    int count = 0;
    for (int i = 1; i < NODE_LIMIT; i++)
    {
        if (tree->nodes[i].active && tree->nodes[i].parent == parent)
            indices[count++] = i;
    }
    for (int i = 1; i < count; i++)
    {
        int index = indices[i];
        int j = i;
        while (j > 0)
        {
            const struct Node *left = &tree->nodes[indices[j - 1]];
            const struct Node *right = &tree->nodes[index];
            int after;
            if (tree->sorted)
                after = strcmp(left->key, right->key) > 0;
            else
                after = left->order > right->order;
            if (!after)
                break;
            indices[j] = indices[j - 1];
            j--;
        }
        indices[j] = index;
    }
    return count;
}

void remove_node(struct Tree *tree, int index)
{
    int indices[NODE_LIMIT];
    int count = children(tree, index, indices);
    for (int i = 0; i < count; i++)
        remove_node(tree, indices[i]);
    if (index)
        tree->nodes[index].active = 0;
    tree->changed++;
}

int set_value(struct Tree *tree, const char *path, const char *value)
{
    if (!value[0] || value[1] != ':')
        return tree_error("Value needs a type prefix");
    enum Kind kind;
    double number = 0;
    switch (*value)
    {
        case 's':
            kind = STRING;
            break;
        case 'n':
        {
            char *end;
            number = strtod(value + 2, &end);
            if (!value[2] || *end || !isfinite(number) || fabs(number) > 1e9)
                return tree_error("Invalid numeric value");
            kind = NUMBER;
            break;
        }
        case 'b':
            if (strcmp(value + 2, "true") && strcmp(value + 2, "false"))
                return tree_error("Invalid boolean value");
            number = !strcmp(value + 2, "true");
            kind = BOOLEAN;
            break;
        case 'z':
            if (strcmp(value + 2, "null"))
                return tree_error("Invalid null value");
            kind = NOTHING;
            break;
        default:
            return tree_error("Unknown value type");
    }
    int index = path_create(tree, path, kind);
    if (index <= 0)
        return tree_error("Cannot create value path");
    if (tree->nodes[index].kind == SECTION)
        remove_node(tree, index);
    struct Node *node = &tree->nodes[index];
    node->active = 1;
    node->kind = kind;
    node->number = number;
    strcpy(node->text, value + 2);
    tree->changed++;
    return 0;
}

void node_path(const struct Tree *tree, int index, char *path)
{
    if (index == 0)
    {
        strcpy(path, "");
        return;
    }
    node_path(tree, tree->nodes[index].parent, path);
    strcat(path, "/");
    strcat(path, tree->nodes[index].key);
}

static void quoted(const char *text)
{
    putchar('"');
    for (; *text; text++)
    {
        switch (*text)
        {
            case '\n':
                fputs("\\n", stdout);
                break;
            case '\t':
                fputs("\\t", stdout);
                break;
            case '\r':
                fputs("\\r", stdout);
                break;
            case '"':
                fputs("\\q", stdout);
                break;
            case '\\':
                fputs("\\\\", stdout);
                break;
            default:
                putchar(*text);
        }
    }
    putchar('"');
}

void print_node(const struct Tree *tree, int index, unsigned depth, int flat)
{
    const struct Node *node = &tree->nodes[index];
    if (flat)
    {
        char path[1024] = {0};
        node_path(tree, index, path);
        fputs(*path ? path : "/", stdout);
    }
    else
    {
        for (unsigned i = 0; i < depth; i++)
            fputs("  ", stdout);
        fputs(index ? node->key : "/", stdout);
    }
    if (node->kind == SECTION)
    {
        puts(" {");
        int indices[NODE_LIMIT];
        int count = children(tree, index, indices);
        for (int i = 0; i < count; i++)
            print_node(tree, indices[i], depth + 1, flat);
        if (!flat)
        {
            for (unsigned i = 0; i < depth; i++)
                fputs("  ", stdout);
        }
        puts("}");
    }
    else
    {
        fputs(" = ", stdout);
        switch (node->kind)
        {
            case STRING:
                quoted(node->text);
                break;
            case NUMBER:
                printf("%.*f", tree->precision, node->number);
                break;
            case BOOLEAN:
                fputs(node->number ? "true" : "false", stdout);
                break;
            case NOTHING:
                fputs("null", stdout);
                break;
            default:
                break;
        }
        putchar('\n');
    }
}

void summarize(const struct Tree *tree, int index, unsigned depth, struct Summary *summary)
{
    const struct Node *node = &tree->nodes[index];
    if (depth > summary->depth)
        summary->depth = depth;
    switch (node->kind)
    {
        case SECTION:
        {
            summary->sections++;
            int indices[NODE_LIMIT];
            int count = children(tree, index, indices);
            for (int i = 0; i < count; i++)
                summarize(tree, indices[i], depth + 1, summary);
            break;
        }
        case STRING:
            summary->strings++;
            summary->characters += (unsigned)strlen(node->text);
            break;
        case NUMBER:
            if (!summary->numbers || node->number < summary->minimum)
                summary->minimum = node->number;
            if (!summary->numbers || node->number > summary->maximum)
                summary->maximum = node->number;
            summary->numbers++;
            summary->sum += node->number;
            break;
        case BOOLEAN:
            summary->booleans++;
            break;
        case NOTHING:
            summary->nulls++;
            break;
    }
}

int clone_node(struct Tree *tree, int source, int parent, const char *key, unsigned depth)
{
    if (depth > 16)
        return -1;
    int index = allocate_node(tree, parent, key, tree->nodes[source].kind);
    if (index < 0)
        return -1;
    tree->nodes[index].number = tree->nodes[source].number;
    strcpy(tree->nodes[index].text, tree->nodes[source].text);
    int indices[NODE_LIMIT];
    int count = children(tree, source, indices);
    for (int i = 0; i < count; i++)
    {
        int child = indices[i];
        if (clone_node(tree, child, index, tree->nodes[child].key, depth + 1) < 0)
            return -1;
    }
    return index;
}
