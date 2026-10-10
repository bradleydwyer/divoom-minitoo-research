/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Offline PI32v2 RAM fixture. This is not a BR28 board or ROM model. */
#include "qemu/osdep.h"
#include "qapi/error.h"
#include "qemu/bswap.h"
#include "qemu/error-report.h"
#include "qemu/module.h"
#include "qemu/units.h"
#include "hw/core/boards.h"
#include "system/address-spaces.h"
#include "cpu.h"

#define RAM_BASE 0x00120000u
#define RAM_BYTES 8192u
#define BLOCK_BYTES 512u
#define CODE_BYTES 16u
#define RESULT_OFFSET 0x1f0u
#define RETURN_PC (RAM_BASE + 0x300u)
#define INITIAL_SP (RAM_BASE + 0xff0u)

static void fixture_reset(CPUPi32v2State *env)
{
    /* A synthetic caller, not a reconstruction of the mask ROM's state. */
    env->spr[RETS] = RETURN_PC;
    env->spr[SP] = INITIAL_SP;
    for (unsigned i = 0; i < 2; i++) {
        env->stack_low[i] = RAM_BASE;
        env->stack_high[i] = RAM_BASE + RAM_BYTES - 1;
    }
    for (unsigned i = 0; i < 3; i++) {
        env->write_low[i] = UINT32_MAX;
        env->write_high[i] = 0;
    }
    /* Keep the loaded instructions read-only during the experiment. */
    env->write_low[0] = RAM_BASE;
    env->write_high[0] = RAM_BASE + CODE_BYTES - 1;
}

static int fixture_fetch(CPUPi32v2State *env, uint32_t addr, unsigned size)
{
    if (addr >= RAM_BASE && addr < RAM_BASE + CODE_BYTES &&
        size <= RAM_BASE + CODE_BYTES - addr) {
        return -1;
    }
    return PI32V2_GUARD_PC;
}

static const Pi32v2MachineOps fixture_ops = {
    .reset_state = fixture_reset,
    .fetch_fault = fixture_fetch,
};

static void fixture_finish(CPUPi32v2State *env)
{
    MachineState *ms = MACHINE(env_archcpu(env)->machine);
    const uint8_t *ram = memory_region_get_ram_ptr(ms->ram);
    g_autofree char *ram_hash = g_compute_checksum_for_data(
        G_CHECKSUM_SHA256, ram, RAM_BYTES);
    g_autofree char *block_hash = g_compute_checksum_for_data(
        G_CHECKSUM_SHA256, ram, BLOCK_BYTES);
    printf("{\"machine\":\"minitoo-ram-check\",\"pc\":%u,"
           "\"sp\":%u,\"rets\":%u,\"instructions\":%" PRIu64 ","
           "\"irq_entries\":%" PRIu64 ",\"result_word\":%u,"
           "\"ram_sha256\":\"%s\",\"block_sha256\":\"%s\","
           "\"registers\":[",
           env->pc, env->spr[SP], env->spr[RETS], env->instructions,
           env->irq_entries, ldl_le_p(ram + RESULT_OFFSET), ram_hash, block_hash);
    for (unsigned i = 0; i < 16; i++) {
        printf("%s%u", i ? "," : "", env->gpr[i]);
    }
    printf("]}\n");
    fflush(stdout);
    exit(EXIT_SUCCESS);
}

static const Pi32v2ObserverOps fixture_observers = {
    .finish = fixture_finish,
};

static void fixture_init(MachineState *ms)
{
    g_autofree char *image = NULL;
    g_autoptr(GError) err = NULL;
    gsize bytes = 0;
    if (ms->ram_size != RAM_BYTES || !ms->kernel_filename) {
        error_report("minitoo-ram-check needs exactly 8 KiB RAM and a 512-byte -kernel fixture");
        exit(EXIT_FAILURE);
    }
    if (!g_file_get_contents(ms->kernel_filename, &image, &bytes, &err)) {
        error_report("cannot load RAM fixture: %s", err->message);
        exit(EXIT_FAILURE);
    }
    if (bytes != BLOCK_BYTES) {
        error_report("RAM fixture must contain exactly 512 bytes");
        exit(EXIT_FAILURE);
    }
    memory_region_add_subregion(get_system_memory(), RAM_BASE, ms->ram);
    memcpy(memory_region_get_ram_ptr(ms->ram), image, bytes);
    Pi32v2CPU *cpu = PI32V2_CPU(cpu_create(TYPE_PI32V2_CPU));
    cpu->machine = ms;
    cpu->ops = &fixture_ops;
    cpu->observer_ops = &fixture_observers;
    cpu->boot_pc = RAM_BASE;
    cpu->stop_pc = RETURN_PC;
    cpu->instruction_limit = 64;
    cpu_reset(CPU(cpu));
}

static void fixture_class_init(ObjectClass *oc, const void *data)
{
    MachineClass *mc = MACHINE_CLASS(oc);
    mc->desc = "Offline MiniToo RAM-marker fixture (no ROM or peripherals)";
    mc->init = fixture_init;
    mc->default_cpu_type = TYPE_PI32V2_CPU;
    mc->default_ram_id = "minitoo-ram-check.ram";
    mc->default_ram_size = RAM_BYTES;
    mc->max_cpus = 1;
}

static const TypeInfo fixture_type = {
    .name = MACHINE_TYPE_NAME("minitoo-ram-check"),
    .parent = TYPE_MACHINE,
    .class_init = fixture_class_init,
};

static void fixture_register(void)
{
    type_register_static(&fixture_type);
}
type_init(fixture_register)
