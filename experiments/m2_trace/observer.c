/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Copyright 2026 Phoenix contributors. */
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include "qemu-plugin.h"

QEMU_PLUGIN_EXPORT int qemu_plugin_version = QEMU_PLUGIN_VERSION;
enum {
    NSITES = 128,
    NFRAMES = 64,
    SAMPLE = 256,
    EVENTS = 10000,
    MAX_SAMPLED = 65536,
    MAX_CALLBACKS = 1000000,
    MAX_TRANSLATED = 1000000,
    MAX_LINE = 2048,
    MAX_WIRE = 8 * 1024 * 1024,
    MAX_BINARY = 16 * 1024 * 1024,
    MAX_PLAN = 16384,
    MAX_INSTRUCTION = 15,
    GUEST_PAGE = 4096,
    REGISTER_BYTES = 8,
    ELF_HEADER = 64,
    PROGRAM_HEADER = 56,
    MAX_PROGRAM_HEADERS = 128
};
enum register_index { RDI, RSI, RDX, RCX, RAX, RSP, NREGS };
enum transfer_kind { NO_TRANSFER, CALL_TRANSFER, RETURN_TRANSFER };
enum kind { CALL, INDIRECT, FREAD, FWRITE, RET, CONTINUATION };
static const char *kinds[] = {"call",   "indirect", "fread",
                              "fwrite", "ret",      "continuation"};
static const char *names[NREGS] = {[RDI] = "rdi", [RSI] = "rsi", [RDX] = "rdx",
                                   [RCX] = "rcx", [RAX] = "rax", [RSP] = "rsp"};
struct site {
    enum kind kind;
    uint64_t pc;
    unsigned size;
    unsigned char bytes[MAX_INSTRUCTION];
    bool checked;
};
struct frame {
    struct site *site;
    unsigned seq;
    uint64_t regs[NREGS];
};
struct pending_transfer {
    enum transfer_kind kind;
    unsigned seq;
    union {
        struct frame call;
        uint64_t return_target;
    } data;
};
static struct {
    struct site sites[NSITES];
    unsigned nsites, depth, seq, sampled, callbacks, translated;
    struct frame frames[NFRAMES];
    struct pending_transfer pending;
    struct qemu_plugin_register *regs[NREGS];
    GByteArray *scratch;
    GChecksum *checksum;
    struct qemu_plugin_scoreboard *enabled;
    FILE *output;
    uint64_t start, end, bias;
    unsigned wire_bytes;
    bool mapped, stopped, limited, gap;
    char binary[65], plan[65];
} state;

static bool load_binary(void);

static void write_line(const char *line) {
    size_t size = strlen(line);
    if (fwrite(line, 1, size, state.output) != size) {
        state.stopped = state.gap = true;
    }
    g_checksum_update(state.checksum, (const guchar *)line, size);
    state.wire_bytes += size;
}

static void stop(const char *reason) {
    if (!state.stopped) {
        char line[80];
        snprintf(line, sizeof(line), "G\t%u\t%s\n", state.seq++, reason);
        write_line(line);
        state.limited = strcmp(reason, "limit") == 0;
        state.gap = state.stopped = true;
        qemu_plugin_u64_set(qemu_plugin_scoreboard_u64(state.enabled), 0, 0);
    }
}

static void emit(const char *format, ...) {
    if (state.stopped) {
        return;
    }
    if (state.seq >= EVENTS - 1 || state.wire_bytes + MAX_LINE > MAX_WIRE) {
        stop("limit");
        return;
    }
    va_list args;
    va_start(args, format);
    char *line = g_strdup_vprintf(format, args);
    va_end(args);
    write_line(line);
    g_free(line);
    ++state.seq;
}

static bool read_reg(unsigned index, uint64_t *value) {
    g_byte_array_set_size(state.scratch, 0);
    if (!state.regs[index] ||
        qemu_plugin_read_register(state.regs[index], state.scratch) != REGISTER_BYTES ||
        state.scratch->len != REGISTER_BYTES) {
        stop("register");
        return false;
    }
    *value = 0;
    for (unsigned i = 0; i < REGISTER_BYTES; ++i) {
        *value |= (uint64_t)state.scratch->data[i] << (8 * i);
    }
    return true;
}

static bool read_guest(uint64_t pointer, unsigned length, unsigned char *output) {
    if (!pointer || pointer > UINT64_MAX - length) {
        return false;
    }
    unsigned done = 0;
    while (done < length) {
        unsigned chunk =
            MIN(length - done, GUEST_PAGE - ((pointer + done) & (GUEST_PAGE - 1)));
        g_byte_array_set_size(state.scratch, 0);
        if (!qemu_plugin_read_memory_vaddr(pointer + done, state.scratch, chunk) ||
            state.scratch->len != chunk) {
            return false;
        }
        memcpy(output + done, state.scratch->data, chunk);
        done += chunk;
    }
    return true;
}

static void sample(struct frame *frame, bool continuation, uint64_t result) {
    uint64_t pointer = frame->regs[RDI], size = frame->regs[RSI],
             count = frame->regs[RDX];
    uint64_t items = continuation ? result : count;
    const char *status = "ok";
    unsigned char bytes[SAMPLE];
    char encoded[2 * SAMPLE + 1] = "-";
    unsigned length = 0;
    if ((size && count > UINT64_MAX / size) || items > count) {
        status = "overflow";
    } else {
        uint64_t span = size * items;
        if (span && !pointer) {
            status = "null";
        } else if (pointer > UINT64_MAX - span) {
            status = "overflow";
        } else if (span > SAMPLE) {
            status = "limit";
        } else {
            length = span;
            if (state.sampled + length > MAX_SAMPLED) {
                status = "limit";
                length = 0;
            } else if (length && !read_guest(pointer, length, bytes)) {
                status = "unreadable";
                length = 0;
            }
        }
    }
    if (length) {
        for (unsigned i = 0; i < length; ++i) {
            snprintf(encoded + 2 * i, 3, "%02x", bytes[i]);
        }
    }
    state.sampled += length;
    emit("B\t%u\t%u\t%s\t%016" PRIx64 "\t%016" PRIx64 "\t%016" PRIx64 "\t%016" PRIx64
         "\t%s\t%s\n",
         state.seq, frame->seq, continuation ? "continuation" : "entry", pointer, size,
         count, result, status, encoded);
    if (strcmp(status, "ok")) {
        stop(!strcmp(status, "limit") ? "limit" : "memory");
    }
}

static void execute(unsigned vcpu, void *userdata) {
    if (state.stopped) {
        return;
    }
    if (vcpu) {
        stop("vcpu");
        return;
    }
    if (++state.callbacks > MAX_CALLBACKS) {
        stop("limit");
        return;
    }
    uint64_t pc = (uintptr_t)userdata;
    if (state.pending.kind != NO_TRANSFER) {
        emit("T\t%u\t%u\t%016" PRIx64 "\n", state.seq, state.pending.seq, pc);
        if (state.pending.kind == CALL_TRANSFER) {
            if (state.depth == NFRAMES) {
                stop("limit");
                return;
            }
            state.frames[state.depth++] = state.pending.data.call;
        } else if (pc != state.pending.data.return_target) {
            stop("stack");
            return;
        }
        state.pending.kind = NO_TRANSFER;
    }
    if (state.depth) {
        struct frame *frame = &state.frames[state.depth - 1];
        uint64_t continuation = frame->site->pc + frame->site->size + state.bias;
        if (pc == continuation) {
            uint64_t rsp, rax;
            if (!read_reg(RSP, &rsp) || !read_reg(RAX, &rax)) {
                return;
            }
            if (rsp != frame->regs[RSP]) {
                stop("stack");
                return;
            }
            emit("C\t%u\t%u\t%016" PRIx64 "\t%016" PRIx64 "\t%016" PRIx64 "\n",
                 state.seq, frame->seq, pc - state.bias, rax, rsp);
            if (frame->site->kind == FREAD) {
                sample(frame, true, rax);
            }
            --state.depth;
        }
    }
    if (state.stopped || pc < state.bias) {
        return;
    }
    for (unsigned i = 0; i < state.nsites; ++i) {
        struct site *site = &state.sites[i];
        if (site->pc != pc - state.bias || site->kind == CONTINUATION) {
            continue;
        }
        if (!site->checked) {
            stop("witness");
            return;
        }
        if (site->kind == RET) {
            if (!state.depth) {
                return;
            }
            uint64_t rsp, rax, target = 0;
            unsigned char bytes[REGISTER_BYTES];
            if (!read_reg(RSP, &rsp) || !read_reg(RAX, &rax)) {
                return;
            }
            if (!read_guest(rsp, REGISTER_BYTES, bytes)) {
                stop("memory");
                return;
            }
            for (unsigned j = 0; j < REGISTER_BYTES; ++j) {
                target |= (uint64_t)bytes[j] << (8 * j);
            }
            struct frame *top = &state.frames[state.depth - 1];
            if (rsp != top->regs[RSP] - REGISTER_BYTES ||
                target != top->site->pc + top->site->size + state.bias) {
                stop("stack");
                return;
            }
            state.pending.seq = state.seq;
            state.pending.data.return_target = target;
            emit("R\t%u\t%016" PRIx64 "\t%016" PRIx64 "\t%016" PRIx64 "\t%016" PRIx64
                 "\n",
                 state.seq, site->pc, target, rsp, rax);
            state.pending.kind = RETURN_TRANSFER;
        } else {
            struct frame frame = {.site = site, .seq = state.seq};
            for (unsigned j = 0; j < NREGS; ++j) {
                if (!read_reg(j, &frame.regs[j])) {
                    return;
                }
            }
            emit("A\t%u\t%016" PRIx64 "\t%016" PRIx64 "\t%016" PRIx64 "\t%016" PRIx64
                 "\t%016" PRIx64 "\t%016" PRIx64 "\t%016" PRIx64 "\n",
                 state.seq, site->pc, frame.regs[RDI], frame.regs[RSI], frame.regs[RDX],
                 frame.regs[RCX], frame.regs[RAX], frame.regs[RSP]);
            state.pending.seq = frame.seq;
            state.pending.data.call = frame;
            state.pending.kind = CALL_TRANSFER;
            if (site->kind == FWRITE) {
                sample(&frame, false, 0);
            }
        }
        return;
    }
}

static void translate(qemu_plugin_id_t id, struct qemu_plugin_tb *tb) {
    (void)id;
    if (state.stopped) {
        return;
    }
    if (!state.mapped) {
        if (!load_binary()) {
            stop("mapping");
            return;
        }
        uint64_t start = qemu_plugin_start_code(), end = qemu_plugin_end_code();
        if (start < state.start || end < start ||
            end - start != state.end - state.start) {
            stop("mapping");
            return;
        }
        state.bias = start - state.start;
        char line[256];
        snprintf(line, sizeof(line),
                 "M2TRACE\t1\t%s\t%s\t%016" PRIx64 "\t%016" PRIx64 "\n", state.binary,
                 state.plan, start, end);
        write_line(line);
        state.mapped = true;
    }
    size_t count = qemu_plugin_tb_n_insns(tb);
    if (count > MAX_TRANSLATED - state.translated) {
        stop("limit");
        return;
    }
    state.translated += count;
    for (size_t i = 0; i < count; ++i) {
        struct qemu_plugin_insn *insn = qemu_plugin_tb_get_insn(tb, i);
        uint64_t pc = qemu_plugin_insn_vaddr(insn);
        for (unsigned j = 0; j < state.nsites; ++j) {
            struct site *site = &state.sites[j];
            if (pc < state.bias || site->pc != pc - state.bias) {
                continue;
            }
            unsigned char bytes[MAX_INSTRUCTION];
            if (qemu_plugin_insn_size(insn) != site->size ||
                qemu_plugin_insn_data(insn, bytes, sizeof(bytes)) != site->size ||
                memcmp(bytes, site->bytes, site->size)) {
                stop("witness");
                return;
            }
            site->checked = true;
        }
        qemu_plugin_register_vcpu_insn_exec_cond_cb(
            insn, execute, QEMU_PLUGIN_CB_R_REGS, QEMU_PLUGIN_COND_NE,
            qemu_plugin_scoreboard_u64(state.enabled), 0, (void *)(uintptr_t)pc);
    }
}

static void initialize(qemu_plugin_id_t id, unsigned vcpu) {
    (void)id;
    if (vcpu) {
        stop("vcpu");
        return;
    }
    qemu_plugin_u64_set(qemu_plugin_scoreboard_u64(state.enabled), 0, 1);
    GArray *registers = qemu_plugin_get_registers();
    for (unsigned i = 0; i < registers->len; ++i) {
        qemu_plugin_reg_descriptor *reg =
            &g_array_index(registers, qemu_plugin_reg_descriptor, i);
        for (unsigned j = 0; j < NREGS; ++j) {
            if (!strcmp(reg->name, names[j])) {
                state.regs[j] = reg->handle;
            }
        }
    }
    g_array_free(registers, true);
    for (unsigned j = 0; j < NREGS; ++j) {
        if (!state.regs[j]) {
            stop("register");
        }
    }
}

static void finish(qemu_plugin_id_t id, void *userdata) {
    (void)id;
    (void)userdata;
    if (state.depth || state.pending.kind != NO_TRANSFER) {
        stop("pending");
    }
    fprintf(state.output, "END\t%u\t%s\t%s\n", state.seq,
            g_checksum_get_string(state.checksum),
            state.limited ? "limited"
            : state.gap   ? "gap"
                          : "complete");
    fclose(state.output);
    g_checksum_free(state.checksum);
    g_byte_array_free(state.scratch, true);
    qemu_plugin_scoreboard_free(state.enabled);
}

static bool load_binary(void) {
    const char *path = qemu_plugin_path_to_binary();
    FILE *file = path ? fopen(path, "rb") : NULL;
    g_free((void *)path);
    if (!file) {
        return false;
    }
    GChecksum *hash = g_checksum_new(G_CHECKSUM_SHA256);
    unsigned char buffer[4096];
    size_t size, total = 0;
    while ((size = fread(buffer, 1, sizeof(buffer), file))) {
        total += size;
        if (total > MAX_BINARY) {
            break;
        }
        g_checksum_update(hash, buffer, size);
    }
    bool ok = total <= MAX_BINARY && !ferror(file);
    if (ok) {
        ok = !strcmp(state.binary, g_checksum_get_string(hash));
    }
    g_checksum_free(hash);
    rewind(file);
    unsigned char header[ELF_HEADER];
    bool header_read = fread(header, 1, sizeof(header), file) == sizeof(header);
    bool elf64_le = header_read && !memcmp(header, "\177ELF\2\1\1", 7);
    bool x86_64 = header_read && header[18] == 62 && !header[19];
    bool program_width = header_read && header[54] == PROGRAM_HEADER && !header[55];
    unsigned program_count = header_read ? header[56] | (header[57] << 8) : 0;
    bool program_bounds = program_count > 0 && program_count <= MAX_PROGRAM_HEADERS;
    ok = ok && elf64_le && x86_64 && program_width && program_bounds;
    uint64_t table = 0;
    for (unsigned j = 0; ok && j < REGISTER_BYTES; ++j) {
        table |= (uint64_t)header[32 + j] << (8 * j);
    }
    state.start = UINT64_MAX;
    for (unsigned i = 0; ok && i < program_count; ++i) {
        unsigned char segment[PROGRAM_HEADER];
        uint64_t offset = table + i * sizeof(segment);
        bool within_file =
            offset >= table && offset <= total && total - offset >= sizeof(segment);
        ok = within_file && !fseek(file, offset, SEEK_SET) &&
             fread(segment, 1, sizeof(segment), file) == sizeof(segment);
        if (ok && segment[0] == 1 && !segment[1] && !segment[2] && !segment[3] &&
            (segment[4] & 1)) {
            uint64_t address = 0, file_size = 0;
            for (unsigned j = 0; j < REGISTER_BYTES; ++j) {
                address |= (uint64_t)segment[16 + j] << (8 * j);
                file_size |= (uint64_t)segment[32 + j] << (8 * j);
            }
            if (address > UINT64_MAX - file_size) {
                ok = false;
                break;
            }
            state.start = MIN(state.start, address);
            state.end = MAX(state.end, address + file_size);
        }
    }
    fclose(file);
    return ok && state.start < state.end;
}

QEMU_PLUGIN_EXPORT int qemu_plugin_install(qemu_plugin_id_t id, const qemu_info_t *info,
                                           int argc, char **argv) {
    if (info->system_emulation || strcmp(info->target_name, "x86_64") ||
        info->version.cur != 4 || argc != 2 || !g_str_has_prefix(argv[0], "plan=") ||
        !g_str_has_prefix(argv[1], "out=")) {
        return -1;
    }
    FILE *plan = fopen(argv[0] + 5, "rb");
    if (!plan) {
        return -1;
    }
    char bytes[MAX_PLAN + 1];
    size_t size = fread(bytes, 1, sizeof(bytes), plan);
    bool ok = !ferror(plan) && size && size < sizeof(bytes) && bytes[size - 1] == '\n';
    fclose(plan);
    if (!ok || memchr(bytes, 0, size)) {
        return -1;
    }
    char *hash = g_compute_checksum_for_data(G_CHECKSUM_SHA256, (guchar *)bytes, size);
    g_strlcpy(state.plan, hash, sizeof(state.plan));
    g_free(hash);
    bytes[size - 1] = 0;
    char **rows = g_strsplit(bytes, "\n", -1);
    ok = g_str_has_prefix(rows[0], "M2PLAN\t1\t") && strlen(rows[0]) == 73;
    for (unsigned j = 9; ok && j < 73; ++j) {
        ok = g_ascii_isdigit(rows[0][j]) || (rows[0][j] >= 'a' && rows[0][j] <= 'f');
    }
    if (ok) {
        g_strlcpy(state.binary, rows[0] + 9, sizeof(state.binary));
    }
    for (unsigned i = 1; ok && rows[i]; ++i) {
        char **fields = g_strsplit(rows[i], "\t", -1);
        ok = g_strv_length(fields) == 4 && !strcmp(fields[0], "S") &&
             state.nsites < NSITES;
        if (ok) {
            struct site *site = &state.sites[state.nsites++];
            unsigned kind;
            for (kind = 0; kind < G_N_ELEMENTS(kinds); ++kind) {
                if (!strcmp(fields[1], kinds[kind])) {
                    break;
                }
            }
            site->kind = kind;
            char *end;
            site->pc = g_ascii_strtoull(fields[2], &end, 16);
            ok = kind < G_N_ELEMENTS(kinds) && strlen(fields[2]) == 16 && !*end &&
                 strlen(fields[3]) && strlen(fields[3]) <= 2 * MAX_INSTRUCTION &&
                 !(strlen(fields[3]) & 1);
            site->size = strlen(fields[3]) / 2;
            for (unsigned j = 0; ok && j < site->size; ++j) {
                int a = g_ascii_xdigit_value(fields[3][j * 2]),
                    b = g_ascii_xdigit_value(fields[3][j * 2 + 1]);
                if (a < 0 || b < 0) {
                    ok = false;
                } else {
                    site->bytes[j] = a * 16 + b;
                }
            }
        }
        g_strfreev(fields);
    }
    g_strfreev(rows);
    if (!ok || !state.nsites) {
        return -1;
    }
    state.output = fopen(argv[1] + 4, "wb");
    if (!state.output) {
        return -1;
    }
    state.checksum = g_checksum_new(G_CHECKSUM_SHA256);
    state.scratch = g_byte_array_sized_new(SAMPLE);
    state.enabled = qemu_plugin_scoreboard_new(sizeof(uint64_t));
    qemu_plugin_register_vcpu_init_cb(id, initialize);
    qemu_plugin_register_vcpu_tb_trans_cb(id, translate);
    qemu_plugin_register_atexit_cb(id, finish, NULL);
    return 0;
}
