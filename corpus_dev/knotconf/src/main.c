#define _POSIX_C_SOURCE 200809L
#include <ctype.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

struct Entry
{
    char key[64];
    char value[256];
    unsigned revision;
};

struct Config
{
    struct Entry entries[64];
    unsigned count;
    int strict;
};

static char *trim(char *text)
{
    while (isspace((unsigned char)*text))
        text++;
    size_t length = strlen(text);
    while (length && isspace((unsigned char)text[length - 1]))
        text[--length] = 0;
    return text;
}

static int key_valid(const char *key)
{
    if (!*key || strlen(key) > 63)
        return 0;
    for (const unsigned char *p = (const unsigned char *)key; *p; p++)
    {
        if (!isalnum(*p) && *p != '_' && *p != '-')
            return 0;
    }
    return 1;
}

static int locate(const struct Config *config, const char *key)
{
    for (unsigned i = 0; i < config->count; i++)
    {
        if (!strcmp(config->entries[i].key, key))
            return (int)i;
    }
    return -1;
}

static unsigned revision(void)
{
    static unsigned serial = 0;
    return ++serial;
}

static int put(struct Config *config, const char *key, const char *value)
{
    if (!key_valid(key) || strlen(value) > 255)
    {
        fputs("Invalid entry\n", stderr);
        return 3;
    }
    int position = locate(config, key);
    if (position < 0)
    {
        if (config->count == 64)
        {
            fputs("Entry limit exceeded\n", stderr);
            return 3;
        }
        position = (int)config->count++;
        strcpy(config->entries[position].key, key);
    }
    strcpy(config->entries[position].value, value);
    config->entries[position].revision = revision();
    return 0;
}

static int drop(struct Config *config, const char *key)
{
    int position = locate(config, key);
    if (position < 0)
    {
        if (config->strict)
        {
            fputs("Missing key\n", stderr);
            return 3;
        }
        return 0;
    }
    for (unsigned i = (unsigned)position + 1; i < config->count; i++)
        config->entries[i - 1] = config->entries[i];
    config->count--;
    return 0;
}

static int transform(struct Config *config, char *text)
{
    char *space = strchr(text, ' ');
    if (!space)
    {
        fputs("Transform needs a key\n", stderr);
        return 3;
    }
    *space++ = 0;
    int position = locate(config, trim(space));
    if (position < 0)
    {
        fputs("Missing transform key\n", stderr);
        return 3;
    }
    char *value = config->entries[position].value;
    size_t length = strlen(value);
    switch (text[0])
    {
        case 'u':
            for (size_t i = 0; i < length; i++)
                value[i] = (char)toupper((unsigned char)value[i]);
            break;
        case 'l':
            for (size_t i = 0; i < length; i++)
                value[i] = (char)tolower((unsigned char)value[i]);
            break;
        case 'r':
            for (size_t i = 0; i < length / 2; i++)
            {
                char temp = value[i];
                value[i] = value[length - i - 1];
                value[length - i - 1] = temp;
            }
            break;
        case 't':
            memmove(value, trim(value), strlen(trim(value)) + 1);
            break;
        case 'n':
            snprintf(value, 256, "%zu", length);
            break;
        case 'e':
            value[0] = 0;
            break;
        case 'd':
            for (size_t i = 0; i < length; i++)
            {
                if (isdigit((unsigned char)value[i]))
                    value[i] = '#';
            }
            break;
        case 's':
            for (size_t i = 0; i < length; i++)
            {
                if (isspace((unsigned char)value[i]))
                    value[i] = '_';
            }
            break;
        default:
            fputs("Invalid transform\n", stderr);
            return 3;
    }
    config->entries[position].revision = revision();
    return 0;
}

static int compare(const void *left, const void *right)
{
    return strcmp(((const struct Entry *)left)->key,
                  ((const struct Entry *)right)->key);
}

static int load(struct Config *config, FILE *input, unsigned depth);

static int statement(struct Config *config, char *text, unsigned depth)
{
    text = trim(text);
    if (!*text || *text == '#')
        return 0;
    if (*text == '@')
    {
        if (depth == 8)
        {
            fputs("Include depth exceeded\n", stderr);
            return 3;
        }
        FILE *file = fopen(trim(text + 1), "r");
        if (!file)
        {
            fputs("Cannot open include\n", stderr);
            return 4;
        }
        int result = load(config, file, depth + 1);
        fclose(file);
        return result;
    }
    if (*text == '-')
        return drop(config, trim(text + 1));
    if (*text == '?')
    {
        int position = locate(config, trim(text + 1));
        if (position < 0)
        {
            fputs("Missing query key\n", stderr);
            return 3;
        }
        puts(config->entries[position].value);
        return 0;
    }
    if (*text == '!')
    {
        if (!strcmp(text, "!sort"))
        {
            qsort(config->entries, config->count, sizeof(struct Entry), compare);
            return 0;
        }
        return transform(config, text + 1);
    }
    char *equals = strchr(text, '=');
    if (!equals)
    {
        fputs("Missing assignment\n", stderr);
        return 3;
    }
    *equals++ = 0;
    return put(config, trim(text), trim(equals));
}

static int load(struct Config *config, FILE *input, unsigned depth)
{
    char line[512];
    while (fgets(line, sizeof(line), input))
    {
        if (!strchr(line, '\n') && !feof(input))
        {
            fputs("Line limit exceeded\n", stderr);
            return 3;
        }
        int result = statement(config, line, depth);
        if (result)
            return result;
    }
    return 0;
}

static int export(const struct Config *config, const char *directory)
{
    if (mkdir(directory, 0755) != 0)
    {
        fputs("Cannot create output directory\n", stderr);
        return 4;
    }
    for (unsigned i = 0; i < config->count; i++)
    {
        char path[512];
        snprintf(path, sizeof(path), "%s/%s", directory, config->entries[i].key);
        FILE *file = fopen(path, "w");
        if (!file)
        {
            fputs("Cannot create output entry\n", stderr);
            return 4;
        }
        fprintf(file, "%s\n", config->entries[i].value);
        fclose(file);
    }
    return 0;
}

int main(int argc, char **argv)
{
    struct Config config = {{{{0}, {0}, 0}}, 0, 0};
    const char *prefix = "";
    const char *directory = NULL;
    int revisions = 0;
    int option;
    opterr = 0;
    while ((option = getopt(argc, argv, "sip:o:")) != -1)
    {
        switch (option)
        {
            case 's':
                config.strict = 1;
                break;
            case 'i':
                revisions = 1;
                break;
            case 'p':
                prefix = optarg;
                break;
            case 'o':
                directory = optarg;
                if (strlen(directory) > 240)
                {
                    fputs("Output path limit exceeded\n", stderr);
                    return 2;
                }
                break;
            default:
                fputs("Invalid option\n", stderr);
                return 2;
        }
    }
    if (argc - optind > 1)
    {
        fputs("Too many files\n", stderr);
        return 2;
    }
    FILE *input = stdin;
    if (optind < argc)
    {
        input = fopen(argv[optind], "r");
        if (!input)
        {
            fputs("Cannot open input\n", stderr);
            return 4;
        }
    }
    int result = load(&config, input, 0);
    if (input != stdin)
        fclose(input);
    if (result)
        return result;
    if (directory)
        return export(&config, directory);
    for (unsigned i = 0; i < config.count; i++)
    {
        const struct Entry *entry = &config.entries[i];
        if (strncmp(entry->key, prefix, strlen(prefix)))
            continue;
        printf("%s=%s", entry->key, entry->value);
        if (revisions)
            printf(" [%u]", entry->revision);
        putchar('\n');
    }
    return 0;
}
