#include "records.h"
#include <ctype.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

int record_error(const char *message)
{
    fprintf(stderr, "%s\n", message);
    return 3;
}

static int hex_value(int c)
{
    if (c >= '0' && c <= '9')
        return c - '0';
    if (c >= 'a' && c <= 'f')
        return c - 'a' + 10;
    if (c >= 'A' && c <= 'F')
        return c - 'A' + 10;
    return -1;
}

int read_word(struct Reader *reader, char *word, unsigned capacity)
{
    int c;
    for (;;)
    {
        c = fgetc(reader->input);
        if (c == '\n')
            reader->line++;
        if (c == '#')
        {
            while ((c = fgetc(reader->input)) != EOF && c != '\n')
                ;
            if (c == '\n')
                reader->line++;
        }
        if (c == EOF)
            return 0;
        if (!isspace((unsigned char)c))
            break;
    }
    int quoted = c == '"';
    if (quoted)
        c = fgetc(reader->input);
    unsigned used = 0;
    while (c != EOF)
    {
        if (quoted && c == '\n')
            reader->line++;
        if (quoted && c == '"')
        {
            word[used] = 0;
            return 1;
        }
        if (!quoted && isspace((unsigned char)c))
        {
            word[used] = 0;
            return 1;
        }
        if (c == '\\')
        {
            c = fgetc(reader->input);
            switch (c)
            {
                case 'n':
                    c = '\n';
                    break;
                case 't':
                    c = '\t';
                    break;
                case 'r':
                    c = '\r';
                    break;
                case 's':
                    c = ' ';
                    break;
                case '"':
                    break;
                case '\\':
                    break;
                case '#':
                    break;
                case 'x':
                {
                    int high = hex_value(fgetc(reader->input));
                    int low = hex_value(fgetc(reader->input));
                    if (high < 0 || low < 0)
                    {
                        reader->error = record_error("Invalid byte escape");
                        return 0;
                    }
                    c = high * 16 + low;
                    break;
                }
                default:
                    reader->error = record_error("Invalid word escape");
                    return 0;
            }
        }
        if (used + 1 >= capacity || c == 0)
        {
            reader->error = record_error("Word limit exceeded");
            return 0;
        }
        word[used++] = (char)c;
        c = fgetc(reader->input);
    }
    if (quoted)
    {
        reader->error = record_error("Unclosed record word");
        return 0;
    }
    word[used] = 0;
    return 1;
}

int required_word(struct Reader *reader, char *word, unsigned capacity)
{
    if (!read_word(reader, word, capacity))
    {
        fprintf(stderr, "Missing record parameter near line %u\n", reader->line);
        return 3;
    }
    return 0;
}

int read_number(struct Reader *reader, int32_t *value)
{
    char word[80];
    char *end;
    if (required_word(reader, word, sizeof(word)))
        return 0;
    long long number = strtoll(word, &end, 10);
    if (!*word || *end || number < -1000000 || number > 1000000)
        return 0;
    *value = (int32_t)number;
    return 1;
}

int valid_key(const char *key)
{
    if (!*key || strlen(key) > 31)
        return 0;
    for (; *key; key++)
    {
        if (!isalnum((unsigned char)*key) && *key != '_' && *key != '-')
            return 0;
    }
    return 1;
}

int find_row(const struct Registry *registry, const char *key)
{
    for (unsigned i = 0; i < registry->count; i++)
    {
        if (!strcmp(registry->rows[i].key, key))
            return (int)i;
    }
    return -1;
}

int insert_row(struct Registry *registry, const struct Row *row)
{
    if (!valid_key(row->key) || row->flags > 255)
        return record_error("Invalid record fields");
    int index = find_row(registry, row->key);
    if (index < 0)
    {
        if (registry->count == RECORD_LIMIT)
            return record_error("Record limit exceeded");
        index = (int)registry->count++;
    }
    registry->rows[index] = *row;
    registry->revision++;
    return 0;
}

int read_row(struct Reader *reader, struct Row *row)
{
    int32_t flags;
    if (required_word(reader, row->key, sizeof(row->key)) ||
        !read_number(reader, &row->number) || !read_number(reader, &flags) ||
        required_word(reader, row->text, sizeof(row->text)))
        return record_error("Invalid row input");
    if (!valid_key(row->key) || flags < 0 || flags > 255)
        return record_error("Invalid row key or flags");
    row->flags = (unsigned)flags;
    return 0;
}

static void quoted(FILE *output, const char *text)
{
    fputc('"', output);
    for (const unsigned char *p = (const unsigned char *)text; *p; p++)
    {
        switch (*p)
        {
            case '\n':
                fputs("\\n", output);
                break;
            case '\t':
                fputs("\\t", output);
                break;
            case '\r':
                fputs("\\r", output);
                break;
            case '"':
                fputs("\\\"", output);
                break;
            case '\\':
                fputs("\\\\", output);
                break;
            default:
                if (*p < 32 || *p > 126)
                    fprintf(output, "\\x%02x", *p);
                else
                    fputc(*p, output);
        }
    }
    fputc('"', output);
}

void print_row(FILE *output, const struct Row *row)
{
    fprintf(output, "%s %d %u ", row->key, row->number, row->flags);
    quoted(output, row->text);
    fputc('\n', output);
}

void display_registry(const struct Registry *registry)
{
    static const char *orders[] = {"key", "number", "length"};
    printf("records %u revision %u\n", registry->count, registry->revision);
    printf("sort %s\n", orders[registry->order]);
    for (unsigned i = 0; i < registry->count; i++)
        print_row(stdout, &registry->rows[i]);
}

int load_records(const char *path, struct Registry *registry, int merge)
{
    FILE *input = fopen(path, "r");
    if (!input)
        return record_error("Cannot open records");
    struct Registry result = merge ? *registry : (struct Registry){0};
    struct Reader reader = {input, 1, 0};
    char key[32];
    int failure = 0;
    while (read_word(&reader, key, sizeof(key)))
    {
        struct Row row = {{0}, 0, 0, {0}};
        strcpy(row.key, key);
        int32_t flags;
        if (!read_number(&reader, &row.number) || !read_number(&reader, &flags) ||
            required_word(&reader, row.text, sizeof(row.text)) || flags < 0 || flags > 255)
        {
            failure = record_error("Invalid records file");
            break;
        }
        row.flags = (unsigned)flags;
        failure = insert_row(&result, &row);
        if (failure)
            break;
    }
    fclose(input);
    if (failure || reader.error)
        return failure ? failure : reader.error;
    *registry = result;
    return 0;
}

int save_records(const char *path, const struct Registry *registry)
{
    FILE *output = fopen(path, "w");
    if (!output)
        return record_error("Cannot create records file");
    for (unsigned i = 0; i < registry->count; i++)
        print_row(output, &registry->rows[i]);
    fclose(output);
    return 0;
}

int split_records(const char *directory, const struct Registry *registry)
{
    if (strlen(directory) > 200 || mkdir(directory, 0755))
        return record_error("Cannot create record directory");
    for (unsigned i = 0; i < registry->count; i++)
    {
        char path[256];
        snprintf(path, sizeof(path), "%s/%s", directory, registry->rows[i].key);
        FILE *output = fopen(path, "w");
        if (!output)
            return record_error("Cannot create split record");
        print_row(output, &registry->rows[i]);
        fclose(output);
    }
    return 0;
}

void registry_statistics(const struct Registry *registry)
{
    double mean = 0;
    double square = 0;
    int32_t low = 0;
    int32_t high = 0;
    unsigned flags[8] = {0};
    unsigned characters = 0;
    unsigned empty = 0;
    unsigned shortest = TEXT_LIMIT;
    unsigned longest = 0;
    char common[32] = "";
    if (registry->count)
        strcpy(common, registry->rows[0].key);
    for (unsigned i = 0; i < registry->count; i++)
    {
        const struct Row *row = &registry->rows[i];
        double delta = row->number - mean;
        mean += delta / (i + 1);
        square += delta * (row->number - mean);
        if (i == 0 || row->number < low)
            low = row->number;
        if (i == 0 || row->number > high)
            high = row->number;
        unsigned length = (unsigned)strlen(row->text);
        characters += length;
        empty += length == 0;
        if (length < shortest)
            shortest = length;
        if (length > longest)
            longest = length;
        unsigned prefix = 0;
        while (common[prefix] && common[prefix] == row->key[prefix])
            prefix++;
        common[prefix] = 0;
        for (unsigned bit = 0; bit < 8; bit++)
            flags[bit] += (row->flags >> bit) & 1;
    }
    if (!registry->count)
        shortest = 0;
    printf("text-lengths %u %u\n", shortest, longest);
    printf("empty-texts %u\n", empty);
    printf("key-prefix-length %zu\n", strlen(common));
    printf("common-key-prefix %s\n", common);
    double variance = registry->count ? square / registry->count : 0;
    printf("statistics %u %d %d %.6f %.6f %u\n", registry->count,
        low, high, mean, sqrt(fmax(0, variance)), characters);
    for (unsigned bit = 0; bit < 8; bit++)
        printf("flag %u %u\n", bit, flags[bit]);
}

static int key_compare(const void *a, const void *b)
{
    return strcmp(((const struct Row *)a)->key, ((const struct Row *)b)->key);
}

static int number_compare(const void *a, const void *b)
{
    const struct Row *left = a;
    const struct Row *right = b;
    if (left->number != right->number)
        return (left->number > right->number) - (left->number < right->number);
    return strcmp(left->key, right->key);
}

static int length_compare(const void *a, const void *b)
{
    const struct Row *left = a;
    const struct Row *right = b;
    size_t l = strlen(left->text);
    size_t r = strlen(right->text);
    if (l != r)
        return (l > r) - (l < r);
    return strcmp(left->key, right->key);
}

void sort_registry(struct Registry *registry, int mode)
{
    int (*comparators[])(const void *, const void *) =
    {
        key_compare,
        number_compare,
        length_compare
    };
    qsort(registry->rows, registry->count, sizeof(struct Row), comparators[mode]);
    registry->order = mode;
    registry->revision++;
}

void transform_text(struct Registry *registry, int operation)
{
    for (unsigned i = 0; i < registry->count; i++)
    {
        char *text = registry->rows[i].text;
        size_t length = strlen(text);
        if (operation == 2)
        {
            for (size_t j = 0; j < length / 2; j++)
            {
                char saved = text[j];
                text[j] = text[length - j - 1];
                text[length - j - 1] = saved;
            }
        }
        else
        {
            for (size_t j = 0; j < length; j++)
            {
                if (operation == 0)
                    text[j] = (char)toupper((unsigned char)text[j]);
                else
                    text[j] = (char)tolower((unsigned char)text[j]);
            }
        }
    }
    registry->revision++;
}
