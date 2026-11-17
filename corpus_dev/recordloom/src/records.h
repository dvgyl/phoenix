#ifndef RECORDLOOM_RECORDS_H
#define RECORDLOOM_RECORDS_H
#include <stdint.h>
#include <stdio.h>

#define RECORD_LIMIT 64
#define TEXT_LIMIT 128
#define PACKET_LIMIT 16384

struct Row
{
    char key[32];
    int32_t number;
    unsigned flags;
    char text[TEXT_LIMIT];
};

struct Registry
{
    struct Row rows[RECORD_LIMIT];
    unsigned count;
    unsigned revision;
    int order;
};

struct Reader
{
    FILE *input;
    unsigned line;
    int error;
};

struct Packet
{
    unsigned char bytes[PACKET_LIMIT];
    unsigned size;
    unsigned cursor;
    int error;
};

struct Snapshot
{
    struct Registry registry;
    int valid;
};

int record_error(const char *message);
int read_word(struct Reader *reader, char *word, unsigned capacity);
int required_word(struct Reader *reader, char *word, unsigned capacity);
int read_number(struct Reader *reader, int32_t *value);
int valid_key(const char *key);
int find_row(const struct Registry *registry, const char *key);
int insert_row(struct Registry *registry, const struct Row *row);
int read_row(struct Reader *reader, struct Row *row);
void print_row(FILE *output, const struct Row *row);
void display_registry(const struct Registry *registry);
int load_records(const char *path, struct Registry *registry, int merge);
int save_records(const char *path, const struct Registry *registry);
int split_records(const char *directory, const struct Registry *registry);
void registry_statistics(const struct Registry *registry);
void sort_registry(struct Registry *registry, int mode);
void transform_text(struct Registry *registry, int operation);
int pack_records(const struct Registry *registry, struct Packet *packet, int delta);
int unpack_records(struct Packet *packet, struct Registry *registry);
int write_packet(const char *path, const struct Packet *packet, int encoding);
int read_packet(const char *path, struct Packet *packet, int encoding);
unsigned packet_checksum(const struct Packet *packet);
int process_records(struct Reader *reader, struct Registry *registry, struct Snapshot *snapshot);
#endif
