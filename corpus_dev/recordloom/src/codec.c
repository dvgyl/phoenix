#include "records.h"
#include <ctype.h>
#include <string.h>

static void byte_put(struct Packet *packet, unsigned value)
{
    if (packet->size == PACKET_LIMIT)
    {
        packet->error = 1;
        return;
    }
    packet->bytes[packet->size++] = (unsigned char)value;
}

static unsigned byte_get(struct Packet *packet)
{
    if (packet->cursor == packet->size)
    {
        packet->error = 1;
        return 0;
    }
    return packet->bytes[packet->cursor++];
}

static void unsigned_put(struct Packet *packet, uint32_t value)
{
    while (value > 127)
    {
        byte_put(packet, (value & 127) | 128);
        value >>= 7;
    }
    byte_put(packet, value);
}

static uint32_t unsigned_get(struct Packet *packet)
{
    uint32_t value = 0;
    for (unsigned shift = 0; shift <= 28; shift += 7)
    {
        unsigned byte = byte_get(packet);
        if (shift == 28 && byte > 15)
        {
            packet->error = 1;
            return 0;
        }
        value |= (uint32_t)(byte & 127) << shift;
        if (!(byte & 128))
            return value;
    }
    packet->error = 1;
    return 0;
}

static void signed_put(struct Packet *packet, int32_t value)
{
    uint32_t encoded = value < 0 ? (uint32_t)(-(int64_t)value * 2 - 1) : (uint32_t)value * 2;
    unsigned_put(packet, encoded);
}

static int32_t signed_get(struct Packet *packet)
{
    uint32_t encoded = unsigned_get(packet);
    if (encoded & 1)
        return (int32_t)(-(int64_t)(encoded / 2) - 1);
    return (int32_t)(encoded / 2);
}

unsigned packet_checksum(const struct Packet *packet)
{
    unsigned crc = 0xffff;
    for (unsigned i = 0; i < packet->size; i++)
    {
        crc ^= (unsigned)packet->bytes[i] << 8;
        for (unsigned bit = 0; bit < 8; bit++)
        {
            if (crc & 0x8000)
                crc = ((crc << 1) ^ 0x1021) & 0xffff;
            else
                crc = (crc << 1) & 0xffff;
        }
    }
    return crc;
}

static unsigned prefix_length(const char *left, const char *right)
{
    unsigned count = 0;
    while (left[count] && left[count] == right[count])
        count++;
    return count;
}

static void string_put(struct Packet *packet, const char *previous, const char *text)
{
    unsigned prefix = prefix_length(previous, text);
    unsigned length = (unsigned)strlen(text);
    byte_put(packet, prefix);
    byte_put(packet, length - prefix);
    for (unsigned i = prefix; i < length; i++)
        byte_put(packet, (unsigned char)text[i]);
}

static int string_get(struct Packet *packet, const char *previous, char *text, unsigned capacity)
{
    unsigned prefix = byte_get(packet);
    unsigned suffix = byte_get(packet);
    if (prefix > strlen(previous) || prefix + suffix >= capacity ||
        suffix > packet->size - packet->cursor)
        return record_error("Invalid compressed string length");
    memcpy(text, previous, prefix);
    for (unsigned i = 0; i < suffix; i++)
    {
        unsigned byte = byte_get(packet);
        if (byte == 0)
            return record_error("Compressed string contains a zero byte");
        text[prefix + i] = (char)byte;
    }
    text[prefix + suffix] = 0;
    return packet->error ? record_error("Truncated compressed string") : 0;
}

int pack_records(const struct Registry *registry, struct Packet *packet, int delta)
{
    memset(packet, 0, sizeof(*packet));
    byte_put(packet, 'R');
    byte_put(packet, 'L');
    byte_put(packet, 1);
    byte_put(packet, (unsigned)delta);
    byte_put(packet, registry->count);
    char previous_key[32] = "";
    char previous_text[TEXT_LIMIT] = "";
    int32_t previous_number = 0;
    for (unsigned i = 0; i < registry->count; i++)
    {
        const struct Row *row = &registry->rows[i];
        string_put(packet, previous_key, row->key);
        signed_put(packet, delta ? row->number - previous_number : row->number);
        byte_put(packet, row->flags);
        string_put(packet, previous_text, row->text);
        strcpy(previous_key, row->key);
        strcpy(previous_text, row->text);
        previous_number = row->number;
    }
    unsigned checksum = packet_checksum(packet);
    byte_put(packet, checksum >> 8);
    byte_put(packet, checksum & 255);
    if (packet->error)
        return record_error("Packed records exceed packet limit");
    return 0;
}

int unpack_records(struct Packet *packet, struct Registry *registry)
{
    if (packet->size < 7)
        return record_error("Record packet is too short");
    unsigned expected = ((unsigned)packet->bytes[packet->size - 2] << 8) |
        packet->bytes[packet->size - 1];
    packet->size -= 2;
    if (packet_checksum(packet) != expected)
        return record_error("Record packet checksum differs");
    if (byte_get(packet) != 'R' || byte_get(packet) != 'L')
        return record_error("Invalid record packet signature");
    if (byte_get(packet) != 1)
        return record_error("Unsupported record packet version");
    unsigned delta = byte_get(packet);
    unsigned count = byte_get(packet);
    if (delta > 1 || count > RECORD_LIMIT)
        return record_error("Invalid packet settings");
    struct Registry result = {0};
    char previous_key[32] = "";
    char previous_text[TEXT_LIMIT] = "";
    int64_t previous_number = 0;
    for (unsigned i = 0; i < count; i++)
    {
        struct Row row = {{0}, 0, 0, {0}};
        if (string_get(packet, previous_key, row.key, sizeof(row.key)))
            return 3;
        int64_t value = signed_get(packet);
        if (delta)
            value += previous_number;
        if (value < -1000000 || value > 1000000)
            return record_error("Decoded number exceeds range");
        row.number = (int32_t)value;
        row.flags = byte_get(packet);
        if (string_get(packet, previous_text, row.text, sizeof(row.text)))
            return 3;
        if (packet->error)
            return record_error("Truncated record packet");
        if (find_row(&result, row.key) >= 0)
            return record_error("Packet repeats a record key");
        int failure = insert_row(&result, &row);
        if (failure)
            return failure;
        strcpy(previous_key, row.key);
        strcpy(previous_text, row.text);
        previous_number = row.number;
    }
    if (packet->cursor != packet->size)
        return record_error("Trailing packet data");
    *registry = result;
    return 0;
}

static const char alphabet[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";

static void armor_write(FILE *output, const struct Packet *packet)
{
    unsigned accumulator = 0;
    unsigned bits = 0;
    unsigned column = 0;
    for (unsigned i = 0; i < packet->size; i++)
    {
        accumulator = (accumulator << 8) | packet->bytes[i];
        bits += 8;
        while (bits >= 6)
        {
            bits -= 6;
            fputc(alphabet[(accumulator >> bits) & 63], output);
            if (++column == 64)
            {
                fputc('\n', output);
                column = 0;
            }
        }
    }
    if (bits)
    {
        fputc(alphabet[(accumulator << (6 - bits)) & 63], output);
        column++;
    }
    if (column)
        fputc('\n', output);
}

static int armor_read(FILE *input, struct Packet *packet)
{
    unsigned accumulator = 0;
    unsigned bits = 0;
    unsigned symbols = 0;
    int c;
    while ((c = fgetc(input)) != EOF)
    {
        if (isspace((unsigned char)c))
            continue;
        const char *digit = strchr(alphabet, c);
        if (!digit || c == 0)
            return record_error("Invalid armor symbol");
        accumulator = (accumulator << 6) | (unsigned)(digit - alphabet);
        bits += 6;
        symbols++;
        if (bits >= 8)
        {
            bits -= 8;
            byte_put(packet, accumulator >> bits);
            if (packet->error)
                return record_error("Armor packet limit exceeded");
        }
    }
    if (symbols % 4 == 1 || (bits && (accumulator & ((1u << bits) - 1))))
        return record_error("Invalid armor padding");
    return 0;
}

static int hex_digit(int c)
{
    if (c >= '0' && c <= '9')
        return c - '0';
    if (c >= 'a' && c <= 'f')
        return c - 'a' + 10;
    if (c >= 'A' && c <= 'F')
        return c - 'A' + 10;
    return -1;
}

int write_packet(const char *path, const struct Packet *packet, int encoding)
{
    FILE *output = fopen(path, "wb");
    if (!output)
        return record_error("Cannot create packet file");
    if (encoding == 0)
        fwrite(packet->bytes, 1, packet->size, output);
    else if (encoding == 1)
    {
        for (unsigned i = 0; i < packet->size; i++)
            fprintf(output, "%02x", packet->bytes[i]);
        fputc('\n', output);
    }
    else
        armor_write(output, packet);
    fclose(output);
    return 0;
}

int read_packet(const char *path, struct Packet *packet, int encoding)
{
    FILE *input = fopen(path, "rb");
    if (!input)
        return record_error("Cannot open packet file");
    memset(packet, 0, sizeof(*packet));
    int failure = 0;
    if (encoding == 2)
    {
        failure = armor_read(input, packet);
    }
    else
    {
        int c;
        while ((c = fgetc(input)) != EOF)
        {
            if (encoding == 1)
            {
                if (isspace((unsigned char)c))
                    continue;
                int high = hex_digit(c);
                int low = hex_digit(fgetc(input));
                if (high < 0 || low < 0)
                {
                    failure = record_error("Invalid packet hexadecimal byte");
                    break;
                }
                c = high * 16 + low;
            }
            byte_put(packet, (unsigned)c);
            if (packet->error)
            {
                failure = record_error("Input packet limit exceeded");
                break;
            }
        }
    }
    fclose(input);
    return failure;
}
