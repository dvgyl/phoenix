/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#include "qemu-plugin.h"

QEMU_PLUGIN_EXPORT int qemu_plugin_version = QEMU_PLUGIN_VERSION;

static uint64_t start;
static uint64_t end;
static uint64_t entry;
static uint8_t *hits;
static bool initialized;

static void hit(unsigned int vcpu, void *data) {
    (void)vcpu;
    hits[(uintptr_t)data - 1] = 1;
}

static void translate(qemu_plugin_id_t id, struct qemu_plugin_tb *block) {
    (void)id;
    if (!initialized) {
        start = qemu_plugin_start_code();
        end = qemu_plugin_end_code();
        entry = qemu_plugin_entry_code();
        if (end <= start || end - start > 16 * 1024 * 1024 || entry < start || entry >= end) {
            return;
        }
        initialized = true;
        hits = calloc(end - start, sizeof(*hits));
    }
    if (hits == NULL) {
        return;
    }
    for (size_t index = 0; index < qemu_plugin_tb_n_insns(block); index++) {
        struct qemu_plugin_insn *instruction = qemu_plugin_tb_get_insn(block, index);
        uint64_t address = qemu_plugin_insn_vaddr(instruction);
        if (address >= start && address < end) {
            qemu_plugin_register_vcpu_insn_exec_cb(
                instruction, hit, QEMU_PLUGIN_CB_NO_REGS,
                (void *)(uintptr_t)(address - start + 1));
        }
    }
}

static void finish(qemu_plugin_id_t id, void *data) {
    (void)id;
    (void)data;
    if (hits == NULL) {
        return;
    }
    char line[128];
    snprintf(line, sizeof(line), "image %" PRIx64 " %" PRIx64 " %" PRIx64 "\n", start, end, entry);
    qemu_plugin_outs(line);
    unsigned int count = 0;
    for (uint64_t offset = 0; offset < end - start; offset++) {
        if (hits[offset]) {
            snprintf(line, sizeof(line), "hit %" PRIx64 "\n", start + offset);
            qemu_plugin_outs(line);
            count++;
        }
    }
    snprintf(line, sizeof(line), "done %u\n", count);
    qemu_plugin_outs(line);
    free(hits);
}

QEMU_PLUGIN_EXPORT int qemu_plugin_install(qemu_plugin_id_t id,
    const qemu_info_t *info, int argc, char **argv) {
    (void)argv;
    if (info->system_emulation || argc != 0) {
        return -1;
    }
    qemu_plugin_register_vcpu_tb_trans_cb(id, translate);
    qemu_plugin_register_atexit_cb(id, finish, NULL);
    return 0;
}
