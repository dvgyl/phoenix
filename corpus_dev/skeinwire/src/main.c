#define _POSIX_C_SOURCE 200809L
#include <ctype.h>
#include <getopt.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct Buffer
{
    unsigned char bytes[8192];
    unsigned size;
    unsigned cursor;
    int error;
};

static int fail(const char *message)
{
    fprintf(stderr, "%s\n", message);
    return 3;
}

static int put(struct Buffer *buffer, unsigned value)
{
    if (buffer->size == sizeof(buffer->bytes))
    {
        buffer->error = 1;
        return 0;
    }
    buffer->bytes[buffer->size++] = (unsigned char)value;
    return 1;
}

static unsigned get(struct Buffer *buffer)
{
    if (buffer->cursor == buffer->size)
    {
        buffer->error = 1;
        return 0;
    }
    return buffer->bytes[buffer->cursor++];
}

static void varput(struct Buffer *buffer, uint32_t value)
{
    do
    {
        unsigned byte = value & 127;
        value >>= 7;
        if (value)
            byte |= 128;
        put(buffer, byte);
    } while (value);
}

static uint32_t varget(struct Buffer *buffer)
{
    uint32_t value = 0;
    for (unsigned shift = 0; shift <= 28; shift += 7)
    {
        unsigned byte = get(buffer);
        if (shift == 28 && byte > 15)
        {
            buffer->error = 1;
            return 0;
        }
        value |= (uint32_t)(byte & 127) << shift;
        if (!(byte & 128))
            return value;
    }
    buffer->error = 1;
    return 0;
}

static uint32_t zigzag(int32_t value)
{
    if (value < 0)
        return (uint32_t)(-(int64_t)value * 2 - 1);
    return (uint32_t)value * 2;
}

static int32_t unzigzag(uint32_t value)
{
    if (value & 1)
        return (int32_t)(-(int64_t)(value / 2) - 1);
    return (int32_t)(value / 2);
}

static int number(const char *word, int32_t *value)
{
    char *end;
    long long parsed = strtoll(word, &end, 10);
    if (!*word || *end || parsed < -1000000 || parsed > 1000000)
        return 0;
    *value = (int32_t)parsed;
    return 1;
}

static int hex(int c)
{
    if (c >= '0' && c <= '9')
        return c - '0';
    if (c >= 'a' && c <= 'f')
        return c - 'a' + 10;
    if (c >= 'A' && c <= 'F')
        return c - 'A' + 10;
    return -1;
}

static int hexread(const char *text, struct Buffer *buffer)
{
    while (*text)
    {
        if (isspace((unsigned char)*text))
        {
            text++;
            continue;
        }
        int high = hex((unsigned char)*text++);
        if (!*text)
            return fail("Incomplete hexadecimal byte");
        int low = hex((unsigned char)*text++);
        if (high < 0 || low < 0)
            return fail("Invalid hexadecimal byte");
        if (!put(buffer, (unsigned)(high * 16 + low)))
            return fail("Buffer limit exceeded");
    }
    return 0;
}

static void hexwrite(const struct Buffer *buffer, int separated)
{
    for (unsigned i = 0; i < buffer->size; i++)
    {
        if (separated && i)
            putchar(' ');
        printf("%02x", buffer->bytes[i]);
    }
    putchar('\n');
}

static unsigned checksum(const struct Buffer *buffer)
{
    unsigned sum = 0;
    for (unsigned i = 0; i < buffer->size; i++)
        sum = (sum + buffer->bytes[i] * (i + 1)) % 65521;
    return sum;
}

static int encode_list(char *text, struct Buffer *payload, int delta)
{
    int32_t previous = 0;
    unsigned count = 0;
    char *save;
    char *word = strtok_r(text, ",", &save);
    while (word)
    {
        int32_t value;
        if (!number(word, &value))
            return fail("Invalid list value");
        int32_t stored = delta ? value - previous : value;
        varput(payload, zigzag(stored));
        previous = value;
        count++;
        word = strtok_r(NULL, ",", &save);
    }
    if (!count)
        return fail("Empty numeric list");
    return 0;
}

static int encode_record(char *line, struct Buffer *output)
{
    char *space = strchr(line, ' ');
    if (!space)
        return fail("Record needs a value");
    *space++ = 0;
    struct Buffer payload = {{0}, 0, 0, 0};
    unsigned type;
    int32_t value;
    if (!strcmp(line, "text"))
    {
        type = 1;
        for (const unsigned char *p = (const unsigned char *)space; *p; p++)
            put(&payload, *p);
    }
    else if (!strcmp(line, "integer"))
    {
        type = 2;
        if (!number(space, &value))
            return fail("Invalid integer");
        varput(&payload, zigzag(value));
    }
    else if (!strcmp(line, "bytes"))
    {
        type = 3;
        int result = hexread(space, &payload);
        if (result)
            return result;
    }
    else if (!strcmp(line, "list") || !strcmp(line, "delta"))
    {
        type = !strcmp(line, "list") ? 4 : 5;
        int result = encode_list(space, &payload, type == 5);
        if (result)
            return result;
    }
    else if (!strcmp(line, "bits"))
    {
        type = 6;
        unsigned byte = 0;
        unsigned used = 0;
        varput(&payload, (uint32_t)strlen(space));
        for (const char *p = space; *p; p++)
        {
            if (*p != '0' && *p != '1')
                return fail("Invalid bit string");
            byte |= (unsigned)(*p - '0') << used++;
            if (used == 8)
            {
                put(&payload, byte);
                used = 0;
                byte = 0;
            }
        }
        if (used)
            put(&payload, byte);
    }
    else if (!strcmp(line, "runs"))
    {
        type = 7;
        const unsigned char *p = (const unsigned char *)space;
        while (*p)
        {
            unsigned byte = *p++;
            unsigned count = 1;
            while (*p == byte && count < 255)
            {
                count++;
                p++;
            }
            put(&payload, count);
            put(&payload, byte);
        }
    }
    else if (!strcmp(line, "fixed"))
    {
        type = 8;
        if (!number(space, &value))
            return fail("Invalid fixed integer");
        uint32_t bits = zigzag(value);
        for (unsigned i = 0; i < 4; i++)
            put(&payload, bits >> (8 * i));
    }
    else if (!strcmp(line, "flag"))
    {
        type = 9;
        if (!strcmp(space, "true"))
            put(&payload, 1);
        else if (!strcmp(space, "false"))
            put(&payload, 0);
        else
            return fail("Invalid flag");
    }
    else
    {
        return fail("Invalid record type");
    }
    if (payload.error || payload.size > 1024)
        return fail("Record limit exceeded");
    put(output, type);
    varput(output, payload.size);
    for (unsigned i = 0; i < payload.size; i++)
        put(output, payload.bytes[i]);
    if (output->error)
        return fail("Packet limit exceeded");
    return 0;
}

static int printable(unsigned byte)
{
    return byte >= 32 && byte <= 126 && byte != '\\';
}

static void escaped(unsigned byte)
{
    if (printable(byte))
        putchar((int)byte);
    else
        printf("\\x%02x", byte);
}

static int decode_record(unsigned type, struct Buffer *payload, int quiet)
{
    if (quiet)
        printf("type %u length %u\n", type, payload->size);
    switch (type)
    {
        case 1:
            if (!quiet)
                fputs("text ", stdout);
            while (payload->cursor < payload->size)
            {
                unsigned byte = get(payload);
                if (!quiet)
                    escaped(byte);
            }
            break;
        case 2:
        {
            int32_t value = unzigzag(varget(payload));
            if (!quiet)
                printf("integer %d", value);
            break;
        }
        case 3:
            if (!quiet)
                fputs("bytes ", stdout);
            while (payload->cursor < payload->size)
            {
                unsigned byte = get(payload);
                if (!quiet)
                    printf("%02x", byte);
            }
            break;
        case 4:
        case 5:
        {
            int64_t previous = 0;
            unsigned count = 0;
            if (!quiet)
                fputs(type == 4 ? "list " : "delta ", stdout);
            while (payload->cursor < payload->size && !payload->error)
            {
                int64_t value = unzigzag(varget(payload));
                if (type == 5)
                    value += previous;
                if (value < -1000000 || value > 1000000)
                    return fail("Decoded list value exceeds limit");
                previous = value;
                if (!quiet)
                {
                    if (count)
                        putchar(',');
                    printf("%lld", (long long)value);
                }
                count++;
            }
            if (!count)
                return fail("Empty encoded list");
            break;
        }
        case 6:
        {
            uint32_t count = varget(payload);
            if (count > 8192 || payload->size - payload->cursor != (count + 7) / 8)
                return fail("Invalid bit count");
            if (!quiet)
                fputs("bits ", stdout);
            unsigned byte = 0;
            for (uint32_t i = 0; i < count; i++)
            {
                if (i % 8 == 0)
                    byte = get(payload);
                if (!quiet)
                    putchar('0' + (int)((byte >> (i % 8)) & 1));
            }
            break;
        }
        case 7:
            if (!quiet)
                fputs("runs ", stdout);
            while (payload->cursor < payload->size)
            {
                unsigned count = get(payload);
                unsigned byte = get(payload);
                if (!count)
                    return fail("Invalid zero run");
                if (!quiet)
                {
                    for (unsigned i = 0; i < count; i++)
                        escaped(byte);
                }
            }
            break;
        case 8:
        {
            uint32_t value = 0;
            for (unsigned i = 0; i < 4; i++)
                value |= (uint32_t)get(payload) << (8 * i);
            if (!quiet)
                printf("fixed %d", unzigzag(value));
            break;
        }
        case 9:
        {
            unsigned flag = get(payload);
            if (flag > 1)
                return fail("Invalid encoded flag");
            if (!quiet)
                printf("flag %s", flag ? "true" : "false");
            break;
        }
        default:
            return fail("Unknown encoded type");
    }
    if (payload->error || payload->cursor != payload->size)
        return fail("Invalid encoded length");
    if (!quiet)
        putchar('\n');
    return 0;
}

static int decode_packet(struct Buffer *packet, int quiet, int selected)
{
    unsigned records = 0;
    while (packet->cursor < packet->size)
    {
        unsigned type = get(packet);
        uint32_t length = varget(packet);
        if (packet->error || length > 1024 || length > packet->size - packet->cursor)
            return fail("Truncated record");
        struct Buffer payload = {{0}, length, 0, 0};
        memcpy(payload.bytes, packet->bytes + packet->cursor, length);
        packet->cursor += length;
        records++;
        if (selected && selected != (int)type)
            continue;
        int result = decode_record(type, &payload, quiet);
        if (result)
            return result;
    }
    if (quiet)
        printf("records %u checksum %04x\n", records, checksum(packet));
    return 0;
}

static int encode_input(FILE *input, struct Buffer *packet)
{
    char line[4096];
    while (fgets(line, sizeof(line), input))
    {
        size_t length = strlen(line);
        if (length && line[length - 1] == '\n')
            line[--length] = 0;
        if (length && line[length - 1] == '\r')
            line[--length] = 0;
        if (!length || line[0] == '#')
            continue;
        int result = encode_record(line, packet);
        if (result)
            return result;
    }
    return 0;
}

static int read_packet(FILE *input, struct Buffer *packet, int binary)
{
    if (binary)
    {
        int byte;
        while ((byte = fgetc(input)) != EOF)
        {
            if (!put(packet, (unsigned)byte))
                return fail("Packet limit exceeded");
        }
    }
    else
    {
        char line[4096];
        while (fgets(line, sizeof(line), input))
        {
            int result = hexread(line, packet);
            if (result)
                return result;
        }
    }
    return 0;
}

static int wrap(struct Buffer *packet)
{
    if (packet->size > sizeof(packet->bytes) - 8)
        return fail("Envelope limit exceeded");
    unsigned size = packet->size;
    unsigned sum = checksum(packet);
    memmove(packet->bytes + 8, packet->bytes, size);
    packet->bytes[0] = 'S';
    packet->bytes[1] = 'W';
    packet->bytes[2] = 1;
    packet->bytes[3] = (unsigned char)size;
    packet->bytes[4] = (unsigned char)(size >> 8);
    packet->bytes[5] = (unsigned char)sum;
    packet->bytes[6] = (unsigned char)(sum >> 8);
    packet->bytes[7] = (unsigned char)(size ^ sum);
    packet->size += 8;
    return 0;
}

static int unwrap(struct Buffer *packet)
{
    if (packet->size < 8)
    {
        return fail("Truncated envelope");
    }
    if (packet->bytes[0] != 'S' || packet->bytes[1] != 'W')
    {
        return fail("Invalid envelope signature");
    }
    if (packet->bytes[2] != 1)
    {
        return fail("Unsupported envelope version");
    }
    unsigned size = packet->bytes[3] + ((unsigned)packet->bytes[4] << 8);
    unsigned sum = packet->bytes[5] + ((unsigned)packet->bytes[6] << 8);
    if (size != packet->size - 8)
    {
        return fail("Envelope size mismatch");
    }
    if (packet->bytes[7] != (unsigned char)(size ^ sum))
    {
        return fail("Envelope guard mismatch");
    }
    memmove(packet->bytes, packet->bytes + 8, size);
    packet->size = size;
    if (checksum(packet) != sum)
    {
        return fail("Envelope checksum mismatch");
    }
    return 0;
}

static void packet_stats(const struct Buffer *packet)
{
    unsigned bins[256] = {0};
    unsigned distinct = 0;
    unsigned low = 255;
    unsigned high = 0;
    for (unsigned i = 0; i < packet->size; i++)
    {
        unsigned byte = packet->bytes[i];
        bins[byte]++;
        if (byte < low)
            low = byte;
        if (byte > high)
            high = byte;
    }
    for (unsigned i = 0; i < 256; i++)
        distinct += bins[i] != 0;
    if (!packet->size)
        low = 0;
    fprintf(stderr, "packet %u distinct %u range %u %u checksum %04x\n",
        packet->size, distinct, low, high, checksum(packet));
}

int main(int argc, char **argv)
{
    int decode = 0;
    int envelope = 0;
    int stats = 0;
    int binary = 0;
    int quiet = 0;
    int separated = 0;
    int selected = 0;
    int option;
    opterr = 0;
    while ((option = getopt(argc, argv, "edbqsSt:")) != -1)
    {
        switch (option)
        {
            case 'e':
                envelope = 1;
                break;
            case 'S':
                stats = 1;
                break;
            case 'd':
                decode = 1;
                break;
            case 'b':
                binary = 1;
                break;
            case 'q':
                quiet = 1;
                break;
            case 's':
                separated = 1;
                break;
            case 't':
            {
                int32_t value;
                if (!number(optarg, &value) || value < 1 || value > 9)
                    return fail("Invalid type selection");
                selected = value;
                break;
            }
            default:
                return fail("Invalid option");
        }
    }
    if (argc - optind > 1)
        return fail("Too many files");
    FILE *input = stdin;
    if (optind < argc)
    {
        input = fopen(argv[optind], "rb");
        if (!input)
            return fail("Cannot open input");
    }
    struct Buffer packet = {{0}, 0, 0, 0};
    int result;
    if (decode)
        result = read_packet(input, &packet, binary);
    else
        result = encode_input(input, &packet);
    if (input != stdin)
        fclose(input);
    if (result)
        return result;
    if (envelope)
    {
        result = decode ? unwrap(&packet) : wrap(&packet);
        if (result)
            return result;
    }
    if (stats)
        packet_stats(&packet);
    if (decode)
        return decode_packet(&packet, quiet, selected);
    if (binary)
        fwrite(packet.bytes, 1, packet.size, stdout);
    else
        hexwrite(&packet, separated);
    return 0;
}
