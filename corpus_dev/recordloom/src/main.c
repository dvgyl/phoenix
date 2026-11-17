#define _POSIX_C_SOURCE 200809L
#include "records.h"
#include <ctype.h>
#include <getopt.h>
#include <stdlib.h>
#include <string.h>

static int select_row(struct Reader *reader, const struct Registry *registry, unsigned *index)
{
    char key[32];
    if (required_word(reader, key, sizeof(key)))
        return 3;
    int found = find_row(registry, key);
    if (found < 0)
        return record_error("Record key is absent");
    *index = (unsigned)found;
    return 0;
}

static int delete_row(struct Reader *reader, struct Registry *registry)
{
    unsigned index = 0;
    int result = select_row(reader, registry, &index);
    if (result)
        return result;
    for (unsigned i = index + 1; i < registry->count; i++)
        registry->rows[i - 1] = registry->rows[i];
    registry->count--;
    registry->revision++;
    return 0;
}

static int arithmetic(struct Reader *reader, struct Registry *registry, int multiply)
{
    unsigned index = 0;
    int result = select_row(reader, registry, &index);
    if (result)
        return result;
    int32_t amount;
    if (!read_number(reader, &amount))
        return record_error("Invalid record arithmetic value");
    int64_t value = registry->rows[index].number;
    value = multiply ? value * amount : value + amount;
    if (value < -1000000 || value > 1000000)
        return record_error("Record arithmetic exceeds range");
    registry->rows[index].number = (int32_t)value;
    registry->revision++;
    return 0;
}

static int rename_record(struct Reader *reader, struct Registry *registry)
{
    unsigned index = 0;
    int result = select_row(reader, registry, &index);
    if (result)
        return result;
    char target[32];
    if (required_word(reader, target, sizeof(target)) || !valid_key(target))
        return record_error("Invalid replacement key");
    if (find_row(registry, target) >= 0)
        return record_error("Replacement key exists");
    strcpy(registry->rows[index].key, target);
    registry->revision++;
    return 0;
}

static int filter_records(struct Reader *reader, struct Registry *registry)
{
    int32_t low;
    int32_t high;
    if (!read_number(reader, &low) || !read_number(reader, &high) || low > high)
        return record_error("Invalid record interval");
    unsigned used = 0;
    for (unsigned i = 0; i < registry->count; i++)
    {
        int32_t value = registry->rows[i].number;
        if (value >= low && value <= high)
            registry->rows[used++] = registry->rows[i];
    }
    registry->count = used;
    registry->revision++;
    return 0;
}

static int flag_records(struct Reader *reader, struct Registry *registry)
{
    int32_t mask;
    int32_t value;
    if (!read_number(reader, &mask) || !read_number(reader, &value) ||
        mask < 0 || mask > 255 || value < 0 || value > 255)
        return record_error("Invalid record flag mask");
    for (unsigned i = 0; i < registry->count; i++)
        registry->rows[i].flags = (registry->rows[i].flags & ~(unsigned)mask) | ((unsigned)value & (unsigned)mask);
    registry->revision++;
    return 0;
}

static int prefix_records(struct Reader *reader, struct Registry *registry)
{
    char prefix[128];
    if (required_word(reader, prefix, sizeof(prefix)))
        return 3;
    size_t length = strlen(prefix);
    for (unsigned i = 0; i < registry->count; i++)
    {
        char *text = registry->rows[i].text;
        size_t old = strlen(text);
        if (old + length >= TEXT_LIMIT)
            return record_error("Prefixed text exceeds limit");
        memmove(text + length, text, old + 1);
        memcpy(text, prefix, length);
    }
    registry->revision++;
    return 0;
}

static void trim_records(struct Registry *registry)
{
    for (unsigned i = 0; i < registry->count; i++)
    {
        char *text = registry->rows[i].text;
        size_t first = 0;
        size_t end = strlen(text);
        while (isspace((unsigned char)text[first]))
            first++;
        while (end > first && isspace((unsigned char)text[end - 1]))
            end--;
        memmove(text, text + first, end - first);
        text[end - first] = 0;
    }
    registry->revision++;
}

static void deduplicate(struct Registry *registry)
{
    unsigned count = 0;
    for (unsigned i = 0; i < registry->count; i++)
    {
        unsigned j;
        for (j = 0; j < count; j++)
        {
            if (registry->rows[i].number == registry->rows[j].number &&
                registry->rows[i].flags == registry->rows[j].flags &&
                !strcmp(registry->rows[i].text, registry->rows[j].text))
                break;
        }
        if (j == count)
            registry->rows[count++] = registry->rows[i];
    }
    registry->count = count;
    registry->revision++;
}

static int packet_command(struct Reader *reader, struct Registry *registry, int decode)
{
    char path[256];
    int32_t encoding;
    if (required_word(reader, path, sizeof(path)) || !read_number(reader, &encoding) ||
        encoding < 0 || encoding > 2)
        return record_error("Invalid packet command");
    struct Packet packet = {{0}, 0, 0, 0};
    if (decode)
    {
        int result = read_packet(path, &packet, encoding);
        if (result)
            return result;
        return unpack_records(&packet, registry);
    }
    int32_t delta;
    if (!read_number(reader, &delta) || delta < 0 || delta > 1)
        return record_error("Invalid packet delta mode");
    int result = pack_records(registry, &packet, delta);
    if (result)
        return result;
    printf("packed %u checksum %04x\n", packet.size, packet_checksum(&packet));
    return write_packet(path, &packet, encoding);
}

static int replace_text(struct Reader *reader, struct Registry *registry)
{
    char search[128];
    char replacement[128];
    if (required_word(reader, search, sizeof(search)) ||
        required_word(reader, replacement, sizeof(replacement)) || !*search)
        return record_error("Replacement needs nonempty search text");
    size_t search_length = strlen(search);
    size_t replacement_length = strlen(replacement);
    unsigned replacements = 0;
    for (unsigned i = 0; i < registry->count; i++)
    {
        char result[TEXT_LIMIT];
        size_t used = 0;
        const char *cursor = registry->rows[i].text;
        while (*cursor)
        {
            if (!strncmp(cursor, search, search_length))
            {
                if (used + replacement_length >= sizeof(result))
                    return record_error("Replacement text exceeds limit");
                memcpy(result + used, replacement, replacement_length);
                used += replacement_length;
                cursor += search_length;
                replacements++;
            }
            else
            {
                if (used + 1 >= sizeof(result))
                    return record_error("Copied replacement text exceeds limit");
                result[used++] = *cursor++;
            }
        }
        result[used] = 0;
        strcpy(registry->rows[i].text, result);
    }
    registry->revision++;
    printf("replacements %u\n", replacements);
    return 0;
}

static int numeric_histogram(struct Reader *reader, const struct Registry *registry)
{
    int32_t low;
    int32_t width;
    if (!read_number(reader, &low) || !read_number(reader, &width) || width < 1)
        return record_error("Invalid histogram interval");
    unsigned bins[10] = {0};
    unsigned below = 0;
    unsigned above = 0;
    for (unsigned i = 0; i < registry->count; i++)
    {
        int64_t relative = (int64_t)registry->rows[i].number - low;
        if (relative < 0)
        {
            below++;
        }
        else if (relative / width >= 10)
        {
            above++;
        }
        else
        {
            bins[relative / width]++;
        }
    }
    for (unsigned i = 0; i < 10; i++)
        printf("bin %lld %u\n", (long long)((int64_t)low + (int64_t)i * width), bins[i]);
    printf("outside %u %u\n", below, above);
    return 0;
}

static int group_flags(struct Reader *reader, struct Registry *registry)
{
    int32_t mask;
    if (!read_number(reader, &mask) || mask < 0 || mask > 255)
        return record_error("Invalid grouping mask");
    struct Registry grouped = {0};
    unsigned counts[RECORD_LIMIT] = {0};
    int64_t sums[RECORD_LIMIT] = {0};
    for (unsigned i = 0; i < registry->count; i++)
    {
        unsigned flags = registry->rows[i].flags & (unsigned)mask;
        char key[32];
        snprintf(key, sizeof(key), "group_%02x", flags);
        int found = find_row(&grouped, key);
        if (found < 0)
        {
            found = (int)grouped.count++;
            strcpy(grouped.rows[found].key, key);
            grouped.rows[found].flags = flags;
        }
        sums[found] += registry->rows[i].number;
        counts[found]++;
    }
    for (unsigned i = 0; i < grouped.count; i++)
    {
        grouped.rows[i].number = (int32_t)(sums[i] / counts[i]);
        snprintf(grouped.rows[i].text, TEXT_LIMIT, "count=%u sum=%lld", counts[i], (long long)sums[i]);
    }
    grouped.revision = registry->revision + 1;
    *registry = grouped;
    return 0;
}

static int rotate_records(struct Reader *reader, struct Registry *registry)
{
    int32_t count;
    if (!read_number(reader, &count))
        return record_error("Invalid record rotation");
    if (!registry->count)
        return 0;
    int shift = count % (int)registry->count;
    if (shift < 0)
        shift += (int)registry->count;
    struct Registry original = *registry;
    for (unsigned i = 0; i < registry->count; i++)
        registry->rows[(i + (unsigned)shift) % registry->count] = original.rows[i];
    registry->revision++;
    return 0;
}

int process_records(struct Reader *reader, struct Registry *registry, struct Snapshot *snapshot)
{
    char command[80];
    unsigned count = 0;
    while (read_word(reader, command, sizeof(command)))
    {
        if (++count > 4096)
            return record_error("Record command limit exceeded");
        int result = 0;
        if (!strcmp(command, "replace"))
            result = replace_text(reader, registry);
        else if (!strcmp(command, "histogram"))
            result = numeric_histogram(reader, registry);
        else if (!strcmp(command, "group"))
            result = group_flags(reader, registry);
        else if (!strcmp(command, "rotate"))
            result = rotate_records(reader, registry);
        else if (!strcmp(command, "put"))
        {
            struct Row row;
            result = read_row(reader, &row);
            if (!result)
                result = insert_row(registry, &row);
        }
        else if (!strcmp(command, "drop"))
            result = delete_row(reader, registry);
        else if (!strcmp(command, "get"))
        {
            unsigned index = 0;
            result = select_row(reader, registry, &index);
            if (!result)
                print_row(stdout, &registry->rows[index]);
        }
        else if (!strcmp(command, "add") || !strcmp(command, "multiply"))
            result = arithmetic(reader, registry, !strcmp(command, "multiply"));
        else if (!strcmp(command, "rename"))
            result = rename_record(reader, registry);
        else if (!strcmp(command, "filter"))
            result = filter_records(reader, registry);
        else if (!strcmp(command, "flags"))
            result = flag_records(reader, registry);
        else if (!strcmp(command, "prefix"))
            result = prefix_records(reader, registry);
        else if (!strcmp(command, "trim"))
            trim_records(registry);
        else if (!strcmp(command, "dedup"))
            deduplicate(registry);
        else if (!strcmp(command, "upper") || !strcmp(command, "lower") || !strcmp(command, "reverse"))
            transform_text(registry, !strcmp(command, "upper") ? 0 : !strcmp(command, "lower") ? 1 : 2);
        else if (!strcmp(command, "sort"))
        {
            char order[32];
            if (required_word(reader, order, sizeof(order)))
                return 3;
            int mode = !strcmp(order, "key") ? 0 : !strcmp(order, "number") ? 1 :
                !strcmp(order, "length") ? 2 : -1;
            if (mode < 0)
                return record_error("Invalid record order");
            sort_registry(registry, mode);
        }
        else if (!strcmp(command, "pack") || !strcmp(command, "unpack"))
            result = packet_command(reader, registry, !strcmp(command, "unpack"));
        else if (!strcmp(command, "load") || !strcmp(command, "merge") ||
                 !strcmp(command, "save") || !strcmp(command, "split"))
        {
            char path[256];
            if (required_word(reader, path, sizeof(path)))
                return 3;
            if (!strcmp(command, "load") || !strcmp(command, "merge"))
                result = load_records(path, registry, !strcmp(command, "merge"));
            else if (!strcmp(command, "save"))
                result = save_records(path, registry);
            else
                result = split_records(path, registry);
        }
        else if (!strcmp(command, "snapshot"))
        {
            snapshot->registry = *registry;
            snapshot->valid = 1;
        }
        else if (!strcmp(command, "restore"))
        {
            if (!snapshot->valid)
                return record_error("No record snapshot");
            *registry = snapshot->registry;
        }
        else if (!strcmp(command, "clear"))
        {
            registry->count = 0;
            registry->revision++;
        }
        else if (!strcmp(command, "stats"))
            registry_statistics(registry);
        else if (!strcmp(command, "show"))
            display_registry(registry);
        else
            return record_error("Unknown record command");
        if (result)
            return result;
    }
    return reader->error;
}

int main(int argc, char **argv)
{
    struct Registry registry = {0};
    struct Snapshot snapshot = {0};
    int quiet = 0;
    int report = 0;
    const char *preload = NULL;
    int option;
    opterr = 0;
    while ((option = getopt(argc, argv, "qrl:")) != -1)
    {
        if (option == 'q')
            quiet = 1;
        else if (option == 'r')
            report = 1;
        else if (option == 'l')
            preload = optarg;
        else
            return record_error("Invalid option");
    }
    if (argc - optind > 1)
        return record_error("Too many files");
    if (preload)
    {
        int result = load_records(preload, &registry, 0);
        if (result)
            return result;
    }
    FILE *input = stdin;
    if (optind < argc)
    {
        input = fopen(argv[optind], "r");
        if (!input)
            return record_error("Cannot open input");
    }
    struct Reader reader = {input, 1, 0};
    int result = process_records(&reader, &registry, &snapshot);
    if (input != stdin)
        fclose(input);
    if (result)
        return result;
    if (report)
        registry_statistics(&registry);
    if (!quiet)
        display_registry(&registry);
    return 0;
}
