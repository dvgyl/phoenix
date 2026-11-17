#define _POSIX_C_SOURCE 200809L
#include "tree.h"
#include <ctype.h>
#include <getopt.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

static int need(struct Lexer *lexer, char *text)
{
    if (!token(lexer, text))
    {
        fprintf(stderr, "Missing command parameter at line %u\n", lexer->line);
        return 3;
    }
    return 0;
}

static int require_path(struct Lexer *lexer, const struct Tree *tree, int *index)
{
    char path[256];
    int result = need(lexer, path);
    if (result)
        return result;
    *index = path_find(tree, path);
    if (*index < 0)
        return tree_error("Path is absent");
    return 0;
}

static int section(struct Lexer *lexer, struct Tree *tree)
{
    char path[256];
    if (need(lexer, path))
        return 3;
    int index = path_create(tree, path, SECTION);
    if (index < 0 || tree->nodes[index].kind != SECTION)
        return tree_error("Cannot create section");
    tree->changed++;
    return 0;
}

static int assign(struct Lexer *lexer, struct Tree *tree)
{
    char path[256];
    char value[256];
    if (need(lexer, path) || need(lexer, value))
        return 3;
    return set_value(tree, path, value);
}

static int ancestry(const struct Tree *tree, int parent, int index)
{
    while (parent >= 0)
    {
        if (parent == index)
            return 1;
        parent = tree->nodes[parent].parent;
    }
    return 0;
}

static int copy_or_move(struct Lexer *lexer, struct Tree *tree, int move)
{
    int source;
    int result = require_path(lexer, tree, &source);
    if (result)
        return result;
    if (source == 0)
        return tree_error("Cannot transfer root");
    char target[256];
    if (need(lexer, target))
        return 3;
    if (path_find(tree, target) >= 0)
        return tree_error("Target path exists");
    char *slash = strrchr(target, '/');
    if (!slash || !slash[1])
        return tree_error("Invalid transfer path");
    char key[48];
    if (strlen(slash + 1) > 47)
        return tree_error("Transfer key limit exceeded");
    strcpy(key, slash + 1);
    if (slash == target)
        slash[1] = 0;
    else
        *slash = 0;
    int parent = path_find(tree, target);
    if (parent < 0 || tree->nodes[parent].kind != SECTION || ancestry(tree, parent, source))
        return tree_error("Invalid transfer parent");
    struct Summary summary = {0};
    summarize(tree, source, 0, &summary);
    unsigned parent_depth = 0;
    for (int ancestor = parent; ancestor > 0; ancestor = tree->nodes[ancestor].parent)
        parent_depth++;
    if (parent_depth + 1 + summary.depth > 16)
        return tree_error("Transfer depth limit exceeded");
    for (const char *p = key; *p; p++)
    {
        if (!isalnum((unsigned char)*p) && *p != '_' && *p != '-')
            return tree_error("Invalid transfer key");
    }
    if (move)
    {
        tree->nodes[source].parent = parent;
        strcpy(tree->nodes[source].key, key);
    }
    else if (clone_node(tree, source, parent, key, 0) < 0)
    {
        return tree_error("Copy limit exceeded");
    }
    tree->changed++;
    return 0;
}

static void transform_strings(struct Tree *tree, int index, int operation)
{
    struct Node *node = &tree->nodes[index];
    if (node->kind == STRING)
    {
        size_t length = strlen(node->text);
        for (size_t i = 0; i < length; i++)
        {
            if (operation == 0)
                node->text[i] = (char)toupper((unsigned char)node->text[i]);
            else if (operation == 1)
                node->text[i] = (char)tolower((unsigned char)node->text[i]);
        }
        if (operation == 2)
        {
            for (size_t i = 0; i < length / 2; i++)
            {
                char saved = node->text[i];
                node->text[i] = node->text[length - i - 1];
                node->text[length - i - 1] = saved;
            }
        }
    }
    int indices[NODE_LIMIT];
    int count = children(tree, index, indices);
    for (int i = 0; i < count; i++)
        transform_strings(tree, indices[i], operation);
}

static int scale_numbers(struct Lexer *lexer, struct Tree *tree)
{
    int index;
    int result = require_path(lexer, tree, &index);
    if (result)
        return result;
    char word[256];
    if (need(lexer, word))
        return 3;
    char *end;
    double factor = strtod(word, &end);
    if (!*word || *end || !isfinite(factor) || fabs(factor) > 1000)
        return tree_error("Invalid numeric factor");
    for (int i = 1; i < NODE_LIMIT; i++)
    {
        if (!tree->nodes[i].active || tree->nodes[i].kind != NUMBER || !ancestry(tree, i, index))
            continue;
        double number = tree->nodes[i].number * factor;
        if (fabs(number) > 1e9)
            return tree_error("Scaled number exceeds limit");
        tree->nodes[i].number = number;
    }
    tree->changed++;
    return 0;
}

static int find_nodes(struct Lexer *lexer, const struct Tree *tree)
{
    char pattern[256];
    if (need(lexer, pattern))
        return 3;
    unsigned found = 0;
    for (int i = 1; i < NODE_LIMIT; i++)
    {
        const struct Node *node = &tree->nodes[i];
        if (!node->active)
            continue;
        if (strstr(node->key, pattern) || (node->kind == STRING && strstr(node->text, pattern)))
        {
            char path[1024] = {0};
            node_path(tree, i, path);
            puts(path);
            found++;
        }
    }
    printf("found %u\n", found);
    return 0;
}

static void print_summary(const struct Tree *tree, int index)
{
    struct Summary summary = {0};
    summarize(tree, index, 0, &summary);
    printf("changes %u\n", tree->changed);
    printf("kinds %u %u %u %u %u\n", summary.sections, summary.strings,
        summary.numbers, summary.booleans, summary.nulls);
    printf("characters %u depth %u\n", summary.characters, summary.depth);
    printf("numbers %.*f %.*f %.*f\n", tree->precision, summary.sum,
        tree->precision, summary.minimum, tree->precision, summary.maximum);
}

static int export_node(const struct Tree *tree, int index, const char *directory)
{
    const struct Node *node = &tree->nodes[index];
    if (node->kind == SECTION)
    {
        if (mkdir(directory, 0755))
            return tree_error("Cannot create section directory");
        int indices[NODE_LIMIT];
        int count = children(tree, index, indices);
        for (int i = 0; i < count; i++)
        {
            char path[2048];
            snprintf(path, sizeof(path), "%s/%s", directory, tree->nodes[indices[i]].key);
            if (strlen(path) > 1900)
                return tree_error("Export path limit exceeded");
            int result = export_node(tree, indices[i], path);
            if (result)
                return result;
        }
    }
    else
    {
        FILE *output = fopen(directory, "w");
        if (!output)
            return tree_error("Cannot create value file");
        switch (node->kind)
        {
            case STRING:
                fprintf(output, "s:%s\n", node->text);
                break;
            case NUMBER:
                fprintf(output, "n:%.*f\n", tree->precision, node->number);
                break;
            case BOOLEAN:
                fprintf(output, "b:%s\n", node->number ? "true" : "false");
                break;
            case NOTHING:
                fputs("z:null\n", output);
                break;
            default:
                break;
        }
        fclose(output);
    }
    return 0;
}

static int merge_sections(struct Tree *tree, int source, int target, unsigned depth)
{
    if (depth > 16)
        return tree_error("Merge depth limit exceeded");
    int sources[NODE_LIMIT];
    int count = children(tree, source, sources);
    for (int i = 0; i < count; i++)
    {
        int child = sources[i];
        int targets[NODE_LIMIT];
        int target_count = children(tree, target, targets);
        int existing = -1;
        for (int j = 0; j < target_count; j++)
        {
            if (!strcmp(tree->nodes[child].key, tree->nodes[targets[j]].key))
            {
                existing = targets[j];
                break;
            }
        }
        if (existing >= 0 && tree->nodes[child].kind == SECTION &&
            tree->nodes[existing].kind == SECTION)
        {
            int result = merge_sections(tree, child, existing, depth + 1);
            if (result)
                return result;
        }
        else
        {
            if (existing >= 0)
                remove_node(tree, existing);
            if (clone_node(tree, child, target, tree->nodes[child].key, depth + 1) < 0)
                return tree_error("Merge node limit exceeded");
        }
    }
    return 0;
}

static int merge_command(struct Lexer *lexer, struct Tree *tree)
{
    int source;
    int target;
    if (require_path(lexer, tree, &source) || require_path(lexer, tree, &target))
        return 3;
    if (tree->nodes[source].kind != SECTION || tree->nodes[target].kind != SECTION ||
        ancestry(tree, source, target) || ancestry(tree, target, source))
        return tree_error("Merge needs separate sections");
    struct Summary summary = {0};
    summarize(tree, source, 0, &summary);
    unsigned depth = 0;
    for (int ancestor = target; ancestor > 0; ancestor = tree->nodes[ancestor].parent)
        depth++;
    if (depth + summary.depth > 16)
        return tree_error("Merged tree exceeds depth limit");
    int result = merge_sections(tree, source, target, depth);
    if (!result)
        tree->changed++;
    return result;
}

static void toggle_booleans(struct Tree *tree)
{
    unsigned count = 0;
    for (int i = 1; i < NODE_LIMIT; i++)
    {
        if (!tree->nodes[i].active || tree->nodes[i].kind != BOOLEAN)
            continue;
        tree->nodes[i].number = !tree->nodes[i].number;
        count++;
    }
    tree->changed += count;
    printf("toggled %u\n", count);
}

int process(struct Lexer *lexer, struct Tree *tree, unsigned depth)
{
    char command[256];
    while (token(lexer, command))
    {
        int result = 0;
        if (!strcmp(command, "merge"))
            result = merge_command(lexer, tree);
        else if (!strcmp(command, "toggle"))
            toggle_booleans(tree);
        else if (!strcmp(command, "section"))
            result = section(lexer, tree);
        else if (!strcmp(command, "set"))
            result = assign(lexer, tree);
        else if (!strcmp(command, "copy") || !strcmp(command, "move"))
            result = copy_or_move(lexer, tree, !strcmp(command, "move"));
        else if (!strcmp(command, "scale"))
            result = scale_numbers(lexer, tree);
        else if (!strcmp(command, "find"))
            result = find_nodes(lexer, tree);
        else if (!strcmp(command, "sort"))
            tree->sorted = 1;
        else if (!strcmp(command, "order"))
            tree->sorted = 0;
        else if (!strcmp(command, "reset"))
            tree_init(tree);
        else if (!strcmp(command, "include"))
        {
            char path[256];
            if (need(lexer, path))
                return 3;
            if (depth == 8)
                return tree_error("Include depth exceeded");
            FILE *input = fopen(path, "r");
            if (!input)
                return tree_error("Cannot open included commands");
            struct Lexer nested = {input, 1, 0};
            result = process(&nested, tree, depth + 1);
            fclose(input);
        }
        else if (!strcmp(command, "print") || !strcmp(command, "flat") ||
                 !strcmp(command, "remove") || !strcmp(command, "stats") ||
                 !strcmp(command, "upper") || !strcmp(command, "lower") ||
                 !strcmp(command, "reverse") || !strcmp(command, "export"))
        {
            int index;
            result = require_path(lexer, tree, &index);
            if (result)
                return result;
            if (!strcmp(command, "remove"))
                remove_node(tree, index);
            else if (!strcmp(command, "stats"))
                print_summary(tree, index);
            else if (!strcmp(command, "upper") || !strcmp(command, "lower") || !strcmp(command, "reverse"))
            {
                int operation = !strcmp(command, "upper") ? 0 : !strcmp(command, "lower") ? 1 : 2;
                transform_strings(tree, index, operation);
                tree->changed++;
            }
            else if (!strcmp(command, "export"))
            {
                char path[256];
                if (need(lexer, path))
                    return 3;
                result = export_node(tree, index, path);
            }
            else
                print_node(tree, index, 0, !strcmp(command, "flat"));
        }
        else
            return tree_error("Unknown tree command");
        if (result)
            return result;
    }
    return lexer->error;
}

int main(int argc, char **argv)
{
    struct Tree tree;
    tree_init(&tree);
    int quiet = 0;
    int flat = 0;
    int option;
    opterr = 0;
    while ((option = getopt(argc, argv, "qfsp:")) != -1)
    {
        if (option == 'q')
            quiet = 1;
        else if (option == 'f')
            flat = 1;
        else if (option == 's')
            tree.sorted = 1;
        else if (option == 'p')
        {
            char *end;
            long precision = strtol(optarg, &end, 10);
            if (!*optarg || *end || precision < 0 || precision > 9)
                return tree_error("Invalid precision");
            tree.precision = (int)precision;
        }
        else
            return tree_error("Invalid option");
    }
    if (argc - optind > 1)
        return tree_error("Too many files");
    FILE *input = stdin;
    if (optind < argc)
    {
        input = fopen(argv[optind], "r");
        if (!input)
            return tree_error("Cannot open input");
    }
    struct Lexer lexer = {input, 1, 0};
    int result = process(&lexer, &tree, 0);
    if (input != stdin)
        fclose(input);
    if (result)
        return result;
    if (!quiet)
        print_node(&tree, 0, 0, flat);
    return 0;
}
