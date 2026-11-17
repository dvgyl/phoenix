#define _POSIX_C_SOURCE 200809L
#include <ctype.h>
#include <dirent.h>
#include <getopt.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

struct Rule
{
    char suffix[32];
    double factor;
};

struct Record
{
    char path[512];
    unsigned long size;
    unsigned long lines;
    unsigned long words;
    unsigned long controls;
    uint32_t hash;
    unsigned depth;
    double score;
};

struct Settings
{
    struct Rule rules[32];
    unsigned rule_count;
    char excluded[128];
    unsigned max_depth;
    unsigned long min_size;
    unsigned long max_size;
    int sort;
    int reverse;
    int format;
    int mode;
    int include_empty;
};

struct Catalog
{
    struct Record records[128];
    unsigned count;
    unsigned directories;
    unsigned ignored;
};

struct Scorer
{
    const char *name;
    double (*score)(const struct Record *);
};

static double byte_score(const struct Record *record)
{
    return (double)record->size;
}

static double line_score(const struct Record *record)
{
    return (double)record->lines;
}

static double word_score(const struct Record *record)
{
    return (double)record->words;
}

static double density_score(const struct Record *record)
{
    if (!record->size)
        return 0;
    return 100.0 * (record->size - record->controls) / record->size;
}

static const struct Scorer scorers[] =
{
    {"bytes", byte_score},
    {"lines", line_score},
    {"words", word_score},
    {"density", density_score}
};

static int error(const char *message)
{
    fprintf(stderr, "%s\n", message);
    return 3;
}

static char *trim(char *text)
{
    while (isspace((unsigned char)*text))
        text++;
    size_t size = strlen(text);
    while (size && isspace((unsigned char)text[size - 1]))
        text[--size] = 0;
    return text;
}

static int unsigned_number(const char *text, unsigned long *value)
{
    char *end;
    unsigned long parsed = strtoul(text, &end, 10);
    if (!*text || *end || parsed > 1000000)
        return 0;
    *value = parsed;
    return 1;
}

static int factor_number(const char *text, double *value)
{
    char *end;
    double parsed = strtod(text, &end);
    if (!*text || *end || !isfinite(parsed) || parsed < 0 || parsed > 1000)
        return 0;
    *value = parsed;
    return 1;
}

static int set_rule(struct Settings *settings, char *text)
{
    char *space = strchr(text, ' ');
    if (!space)
        return error("Rule needs a factor");
    *space++ = 0;
    double factor;
    if (!*text || strlen(text) > 31 || !factor_number(trim(space), &factor))
        return error("Invalid suffix rule");
    for (unsigned i = 0; i < settings->rule_count; i++)
    {
        if (!strcmp(text, settings->rules[i].suffix))
        {
            settings->rules[i].factor = factor;
            return 0;
        }
    }
    if (settings->rule_count == 32)
        return error("Rule limit exceeded");
    struct Rule *rule = &settings->rules[settings->rule_count++];
    strcpy(rule->suffix, text);
    rule->factor = factor;
    return 0;
}

static int remove_rule(struct Settings *settings, const char *suffix)
{
    for (unsigned i = 0; i < settings->rule_count; i++)
    {
        if (strcmp(settings->rules[i].suffix, suffix))
            continue;
        for (unsigned k = i + 1; k < settings->rule_count; k++)
            settings->rules[k - 1] = settings->rules[k];
        settings->rule_count--;
        return 0;
    }
    return error("Rule is absent");
}

static int parse_settings(FILE *input, struct Settings *settings)
{
    char line[256];
    while (fgets(line, sizeof(line), input))
    {
        char *text = trim(line);
        if (!*text || *text == '#')
            continue;
        char *space = strchr(text, ' ');
        if (!space)
            return error("Setting needs a value");
        *space++ = 0;
        char *value = trim(space);
        if (!strcmp(text, "suffix"))
        {
            int result = set_rule(settings, value);
            if (result)
                return result;
        }
        else if (!strcmp(text, "remove"))
        {
            int result = remove_rule(settings, value);
            if (result)
                return result;
        }
        else if (!strcmp(text, "exclude"))
        {
            if (strlen(value) > 127)
                return error("Exclude pattern limit exceeded");
            strcpy(settings->excluded, value);
        }
        else if (!strcmp(text, "minimum") || !strcmp(text, "maximum"))
        {
            unsigned long number;
            if (!unsigned_number(value, &number))
                return error("Invalid size limit");
            if (!strcmp(text, "minimum"))
                settings->min_size = number;
            else
                settings->max_size = number;
        }
        else if (!strcmp(text, "depth"))
        {
            unsigned long number;
            if (!unsigned_number(value, &number) || number > 16)
                return error("Invalid depth");
            settings->max_depth = (unsigned)number;
        }
        else if (!strcmp(text, "mode"))
        {
            unsigned i;
            for (i = 0; i < sizeof(scorers) / sizeof(*scorers); i++)
            {
                if (!strcmp(value, scorers[i].name))
                    break;
            }
            if (i == sizeof(scorers) / sizeof(*scorers))
                return error("Invalid score mode");
            settings->mode = (int)i;
        }
        else
        {
            return error("Invalid setting");
        }
    }
    if (settings->min_size > settings->max_size)
        return error("Size limits are reversed");
    return 0;
}

static unsigned visit_number(void)
{
    static unsigned serial = 0;
    return ++serial;
}

static int inspect_file(const char *path, struct Record *record)
{
    FILE *input = fopen(path, "rb");
    if (!input)
        return error("Cannot read tree entry");
    int byte;
    int in_word = 0;
    int last = '\n';
    record->hash = UINT32_C(2166136261);
    while ((byte = fgetc(input)) != EOF)
    {
        record->size++;
        record->hash = (record->hash ^ (unsigned)byte) * UINT32_C(16777619);
        if (byte == '\n')
            record->lines++;
        if (isspace((unsigned char)byte))
        {
            in_word = 0;
        }
        else if (!in_word)
        {
            in_word = 1;
            record->words++;
        }
        if (byte < 32 && byte != '\n' && byte != '\t' && byte != '\r')
            record->controls++;
        last = byte;
    }
    if (last != '\n')
        record->lines++;
    fclose(input);
    return 0;
}

static double weight(const struct Settings *settings, const char *path)
{
    double result = 1;
    size_t length = strlen(path);
    for (unsigned i = 0; i < settings->rule_count; i++)
    {
        const struct Rule *rule = &settings->rules[i];
        size_t suffix = strlen(rule->suffix);
        if (suffix <= length && !strcmp(path + length - suffix, rule->suffix))
            result *= rule->factor;
    }
    return result;
}

static int name_compare(const void *a, const void *b)
{
    return strcmp((const char *)a, (const char *)b);
}

static int scan(const char *root, const char *relative, unsigned depth,
                const struct Settings *settings, struct Catalog *catalog)
{
    char full[1024];
    snprintf(full, sizeof(full), "%s%s%s", root, *relative ? "/" : "", relative);
    DIR *directory = opendir(full);
    if (!directory)
        return error("Cannot open tree directory");
    catalog->directories++;
    char names[128][256];
    unsigned count = 0;
    struct dirent *entry;
    while ((entry = readdir(directory)))
    {
        if (!strcmp(entry->d_name, ".") || !strcmp(entry->d_name, ".."))
            continue;
        if (count == 128)
        {
            closedir(directory);
            return error("Directory entry limit exceeded");
        }
        strcpy(names[count++], entry->d_name);
    }
    closedir(directory);
    qsort(names, count, sizeof(names[0]), name_compare);
    for (unsigned i = 0; i < count; i++)
    {
        char child[512];
        if (strlen(relative) + strlen(names[i]) + 2 > sizeof(child))
            return error("Tree path limit exceeded");
        strcpy(child, relative);
        if (*relative)
            strcat(child, "/");
        strcat(child, names[i]);
        if (*settings->excluded && strstr(child, settings->excluded))
        {
            catalog->ignored++;
            continue;
        }
        snprintf(full, sizeof(full), "%s/%s", root, child);
        struct stat status;
        if (lstat(full, &status))
            return error("Cannot inspect tree entry");
        if (S_ISDIR(status.st_mode))
        {
            if (depth < settings->max_depth)
            {
                int result = scan(root, child, depth + 1, settings, catalog);
                if (result)
                    return result;
            }
            else
            {
                catalog->ignored++;
            }
        }
        else if (S_ISREG(status.st_mode))
        {
            struct Record record = {{0}, 0, 0, 0, 0, 0, depth, 0};
            strcpy(record.path, child);
            int result = inspect_file(full, &record);
            if (result)
                return result;
            if (record.size < settings->min_size || record.size > settings->max_size ||
                (!settings->include_empty && record.size == 0))
            {
                catalog->ignored++;
                continue;
            }
            if (catalog->count == 128)
                return error("Catalog limit exceeded");
            record.score = scorers[settings->mode].score(&record) * weight(settings, child);
            catalog->records[catalog->count++] = record;
        }
        else
        {
            catalog->ignored++;
        }
    }
    return 0;
}

static int record_compare(const void *a, const void *b)
{
    const struct Record *left = a;
    const struct Record *right = b;
    if (left->score < right->score)
        return -1;
    if (left->score > right->score)
        return 1;
    return strcmp(left->path, right->path);
}

static void csv_path(const char *path)
{
    putchar('"');
    for (; *path; path++)
    {
        if (*path == '"')
            putchar('"');
        putchar(*path);
    }
    putchar('"');
}

static void display(const struct Catalog *catalog, const struct Settings *settings)
{
    double total = 0;
    unsigned long bytes = 0;
    unsigned long lines = 0;
    unsigned long words = 0;
    for (unsigned i = 0; i < catalog->count; i++)
    {
        unsigned index = settings->reverse ? catalog->count - i - 1 : i;
        const struct Record *record = &catalog->records[index];
        total += record->score;
        bytes += record->size;
        lines += record->lines;
        words += record->words;
        switch (settings->format)
        {
            case 0:
                printf("%u %s %lu %08x %.6f\n", visit_number(), record->path,
                    record->size, record->hash, record->score);
                break;
            case 1:
                csv_path(record->path);
                printf(",%lu,%lu,%lu,%.6f\n", record->size, record->lines,
                    record->words, record->score);
                break;
            case 2:
                printf("%s\n", record->path);
                break;
            case 3:
                printf("%08x %s\n", record->hash, record->path);
                break;
            case 4:
                printf("%u %s\n", record->depth, record->path);
                break;
            case 5:
                printf("%lu %lu %s\n", record->lines, record->words, record->path);
                break;
            case 6:
                printf("%.6f\t%s\n", record->score, record->path);
                break;
            case 7:
                break;
        }
    }
    printf("total %u %lu %lu %lu %.6f\n", catalog->count, bytes, lines, words, total);
    printf("directories %u ignored %u\n", catalog->directories, catalog->ignored);
}

static void depth_totals(const struct Catalog *catalog)
{
    unsigned files[17] = {0};
    unsigned long bytes[17] = {0};
    double scores[17] = {0};
    for (unsigned i = 0; i < catalog->count; i++)
    {
        const struct Record *record = &catalog->records[i];
        files[record->depth]++;
        bytes[record->depth] += record->size;
        scores[record->depth] += record->score;
    }
    for (unsigned depth = 0; depth <= 16; depth++)
    {
        if (!files[depth])
            continue;
        printf("depth %u %u %lu %.6f\n", depth, files[depth], bytes[depth], scores[depth]);
    }
}

static void suffix_totals(const struct Catalog *catalog)
{
    char suffixes[128][256];
    unsigned counts[128] = {0};
    unsigned long bytes[128] = {0};
    unsigned groups = 0;
    for (unsigned i = 0; i < catalog->count; i++)
    {
        const char *path = catalog->records[i].path;
        const char *name = strrchr(path, '/');
        if (!name)
            name = path;
        const char *suffix = strrchr(name, '.');
        if (!suffix)
            suffix = "";
        unsigned group;
        for (group = 0; group < groups; group++)
        {
            if (!strcmp(suffixes[group], suffix))
                break;
        }
        if (group == groups)
        {
            strcpy(suffixes[groups++], suffix);
        }
        counts[group]++;
        bytes[group] += catalog->records[i].size;
    }
    for (unsigned i = 0; i < groups; i++)
        printf("suffix %s %u %lu\n", suffixes[i], counts[i], bytes[i]);
}

static void duplicates(const struct Catalog *catalog)
{
    unsigned char used[128] = {0};
    unsigned groups = 0;
    unsigned long saved = 0;
    for (unsigned i = 0; i < catalog->count; i++)
    {
        if (used[i])
            continue;
        unsigned matches = 0;
        for (unsigned j = i + 1; j < catalog->count; j++)
        {
            if (catalog->records[i].size != catalog->records[j].size ||
                catalog->records[i].hash != catalog->records[j].hash)
                continue;
            if (matches == 0)
            {
                groups++;
                printf("candidate %u %s", groups, catalog->records[i].path);
            }
            printf(" %s", catalog->records[j].path);
            used[j] = 1;
            matches++;
            saved += catalog->records[j].size;
        }
        if (matches)
            putchar('\n');
    }
    printf("candidate-groups %u bytes %lu\n", groups, saved);
}

static void score_distribution(const struct Catalog *catalog)
{
    if (!catalog->count)
    {
        puts("distribution empty");
        return;
    }
    double mean = 0;
    double square = 0;
    double low = catalog->records[0].score;
    double high = low;
    for (unsigned i = 0; i < catalog->count; i++)
    {
        double score = catalog->records[i].score;
        double delta = score - mean;
        mean += delta / (i + 1);
        square += delta * (score - mean);
        if (score < low)
            low = score;
        if (score > high)
            high = score;
    }
    double variance = square / catalog->count;
    if (variance < 0)
        variance = 0;
    double relative = 0;
    if (mean > 0)
        relative = sqrt(variance) / mean;
    printf("relative-deviation %.6f\n", relative);
    printf("distribution %.6f %.6f %.6f %.6f\n", low, high, mean, sqrt(variance));
}

int main(int argc, char **argv)
{
    struct Settings settings = {{{{0}, 0}}, 0, {0}, 8, 0, 1000000, 0, 0, 0, 0, 0};
    struct Catalog catalog = {{{{0}, 0, 0, 0, 0, 0, 0, 0}}, 0, 0, 0};
    const char *config_path = NULL;
    const char *group = NULL;
    int option;
    opterr = 0;
    while ((option = getopt(argc, argv, "c:f:g:ser")) != -1)
    {
        switch (option)
        {
            case 'g':
                group = optarg;
                break;
            case 'c':
                config_path = optarg;
                break;
            case 'f':
            {
                unsigned long format;
                if (!unsigned_number(optarg, &format) || format > 7)
                    return error("Invalid output format");
                settings.format = (int)format;
                break;
            }
            case 's':
                settings.sort = 1;
                break;
            case 'e':
                settings.include_empty = 1;
                break;
            case 'r':
                settings.reverse = 1;
                break;
            default:
                return error("Invalid option");
        }
    }
    if (argc - optind != 1)
        return error("One input directory is required");
    if (strlen(argv[optind]) > 240)
        return error("Root path limit exceeded");
    if (config_path)
    {
        FILE *input = fopen(config_path, "r");
        if (!input)
            return error("Cannot open settings");
        int result = parse_settings(input, &settings);
        fclose(input);
        if (result)
            return result;
    }
    int result = scan(argv[optind], "", 0, &settings, &catalog);
    if (result)
        return result;
    if (settings.sort)
        qsort(catalog.records, catalog.count, sizeof(struct Record), record_compare);
    display(&catalog, &settings);
    if (group)
    {
        if (!strcmp(group, "depth"))
            depth_totals(&catalog);
        else if (!strcmp(group, "suffix"))
            suffix_totals(&catalog);
        else if (!strcmp(group, "duplicates"))
            duplicates(&catalog);
        else if (!strcmp(group, "distribution"))
            score_distribution(&catalog);
        else
            return error("Invalid grouping");
    }
    return 0;
}
