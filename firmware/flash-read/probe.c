/* Fixed volatile-mode release, JEDEC ID and two fixed 64-byte reads. No persistent flash writes.
 * Separate from the original disabled candidate; see docs/flash-backup.md. */
#include "probe.h"

#ifdef MINITOO_READ_OFFLINE_TEST
extern id_u32 read_model_read(id_u32 address);
extern void read_model_write(id_u32 address, id_u32 value);
#define READ(a) read_model_read(a)
#define WRITE(a, v) read_model_write((a), (v))
#define SYNC() ((void)0)
#else
#define READ(a) (*(volatile const id_u32 *)(a))
#define WRITE(a, v) (*(volatile id_u32 *)(a) = (v))
#define SYNC() __asm__ volatile("csync" ::: "memory")
#endif

#define SPI_CON 0x00fd1c00u
#define SPI_BAUD 0x00fd1c04u /* Write-only: deliberately never read. */
#define SPI_BUF 0x00fd1c08u
#define OUT 0x00fd5300u
#define IN 0x00fd5304u
#define DIR 0x00fd5308u
#define DIE 0x00fd530cu
#define PU 0x00fd5310u
#define PD 0x00fd5314u
#define CS 8u
#define SIGNALS 0x67u /* Group-0 clock plus all four data pins. */
#define INPUTS 0x66u /* PD1/PD2 plus quad-only PD5/PD6, from power_sfc.c.o. */
#define PENDING 0x8000u
#define CLEAR_PENDING 0x4000u
#define SPI_BASE 0x21u /* ROM flash-clock setting 0x20, master + enable. */

static id_u32 transfer(id_u32 con, id_u32 byte, volatile id_u32 *polls)
{
    id_u32 receive = con & 0x1000u;
    WRITE(SPI_CON, con | CLEAR_PENDING);
    WRITE(SPI_BUF, byte);
    SYNC();
    for (id_u32 count = 1; count <= ID_POLL_LIMIT; ++count) {
        if (READ(SPI_CON) & PENDING) {
            *polls = count;
            WRITE(SPI_CON, con | CLEAR_PENDING);
            /* Return marker bit distinguishes byte 00 from timeout. */
            id_u32 value = receive ? READ(SPI_BUF) & 255u : 0u;
            WRITE(SPI_CON, con);
            return 0x100u | value;
        }
    }
    *polls = ID_POLL_LIMIT;
    return 0;
}

static void settle(void)
{
    /* Finite conservative CS-high/setup gap; compiler must retain the loop. */
    for (volatile id_u32 n = 0; n < 4096u; ++n) { SYNC(); }
}

void minitoo_flash_read(volatile struct id_result *result)
{
    result->completion = 0;
    result->status = ID_PREFLIGHT_REFUSED;
    result->preflight_mismatches = 0;
    result->transfers_completed = 0;
    result->cleanup_mismatches = 0;
    for (id_u32 i = 0; i < 3; ++i) result->id_bytes[i] = 0;
    for (id_u32 i = 0; i < 8; ++i) result->polls[i] = 0;
    for (id_u32 i = 0; i < 4; ++i) result->idle_inputs[i] = 0;
    result->transactions_started = 0;
    result->read_transactions_started = 0;
    for (id_u32 pass = 0; pass < 2; ++pass) {
        result->read_completed[pass] = 0;
        result->read_max_polls[pass] = 0;
        result->read_idle_inputs[pass] = 0;
        for (id_u32 i = 0; i < 64; ++i) result->data[pass][i] = 0;
    }

    /* Exact previously sampled baseline, before any peripheral write.
     * Mode zero here does not establish the physical chip's retained mode.
     */
#define CHECK(a, expected, bit) \
    if (READ(a) != (expected)) result->preflight_mismatches |= 1u << (bit)
    CHECK(0x0019fc28u, 0x84000300u, 0);
    CHECK(0x0019fc2cu, 24000000u, 1);
    CHECK(0x0019fc30u, 48000000u, 2);
    CHECK(0x00fd6014u, 0u, 3); /* Includes group/crossbar/bit-19 checks. */
    CHECK(SPI_CON, 0x8000u, 4);
    CHECK(0x00fe0200u, 0x01580034u, 5);
    CHECK(0x00fe0218u, 0u, 6);
    CHECK(0x00fd4100u, 0u, 7);
    CHECK(0x00fd0014u, 0u, 8);
    CHECK(0x00fd0018u, 0x31u, 9);
    CHECK(0x00fd001cu, 0x1643u, 10);
    id_u32 out = READ(OUT), dir = READ(DIR), die = READ(DIE);
    id_u32 pu = READ(PU), pd = READ(PD);
    if (out != 0x10u || dir != 0x6fu || die != 0x7fu || pu != 0x18u || pd != 0)
        result->preflight_mismatches |= 1u << 11;
    id_u32 caller_sp = READ(0x001207f8u);
    if ((caller_sp & 3u) || !((caller_sp >= 0x00180820u && caller_sp <= 0x00181020u)
        || (caller_sp >= 0x0019fc00u && caller_sp < 0x001a0000u)))
        result->preflight_mismatches |= 1u << 12;
    CHECK(0x001207fcu, 0x00004abcu, 13);
    if (result->preflight_mismatches) goto finish;

    /* CS latch high before output enable. Preserve PD4 flash power.
     * Keep IOMAP unchanged: group 0, crossbar off, bit 19 already clear.
     * GPIO masks follow ROM group-0 setup without naming unproven pin roles.
     */
    WRITE(OUT, out | CS);
    WRITE(DIR, dir & ~CS);
    WRITE(PU, ((pu & ~(SIGNALS | CS)) | INPUTS));
    WRITE(PD, pd & ~(SIGNALS | CS));
    WRITE(DIR, (dir & ~(CS | SIGNALS)) | INPUTS);
    /* Never drive a data output during mode release. SPI unidirectional
     * receive releases its data pins; bit 3 is clear, DIR_IN is set before
     * enable. Weak GPIO pull-ups supply ones without strong-driver contention.
     */
    WRITE(SPI_CON, 0x1820u | CLEAR_PENDING);
    WRITE(SPI_BAUD, 255u);
    WRITE(SPI_CON, 0x1821u);
    SYNC();
    for (id_u32 frame = 0; frame < 4; ++frame) {
        /* 2 clocks, 16 clocks, 2 clocks, then ordinary 9F + 24 clocks.
         * Frames 0/2 exit ordinary QPI; frame 1 covers continuous dual/quad
         * and DTR mode bits. No data pin is actively driven in frames 0..2.
         */
        id_u32 con = (frame == 1u) ? 0x1021u : 0x1821u;
        if (frame == 3u) con = 0x29u;
        WRITE(SPI_CON, (frame == 3u ? 0x1021u : con) | CLEAR_PENDING);
        settle();
        result->idle_inputs[frame] = READ(IN) & INPUTS;
        if (result->idle_inputs[frame] != INPUTS) {
            result->status = ID_IDLE_REFUSED;
            goto cleanup;
        }
        if (frame == 3u) {
            WRITE(SPI_CON, con | CLEAR_PENDING);
            SYNC();
            settle();
        }
        WRITE(OUT, out & ~CS);
        SYNC();
        settle();
        result->transactions_started = frame + 1u;
        result->status = ID_TRANSFER_TIMEOUT;
        id_u32 transfers = frame == 1u ? 2u : (frame == 3u ? 4u : 1u);
        for (id_u32 i = 0; i < transfers; ++i) {
            id_u32 index = result->transfers_completed;
            id_u32 tx_con = frame == 3u && i ? 0x1029u : con;
            id_u32 byte = frame == 3u && !i ? 0x9fu : 255u;
            id_u32 value = transfer(tx_con, byte, &result->polls[index]);
            if (!value) goto cleanup;
            if (frame == 3u && i) result->id_bytes[i - 1u] = value & 255u;
            result->transfers_completed = index + 1u;
        }
        WRITE(OUT, out | CS);
        SYNC();
    }
    result->status = ID_CAPTURED;
    if ((result->id_bytes[0] == 0 && result->id_bytes[1] == 0 && result->id_bytes[2] == 0)
        || (result->id_bytes[0] == 255 && result->id_bytes[1] == 255 && result->id_bytes[2] == 255))
        result->status = ID_NO_RESPONSE;

    if (result->status == ID_NO_RESPONSE) goto cleanup;
    if (result->id_bytes[0] != 0x85u || result->id_bytes[1] != 0x60u
        || result->id_bytes[2] != 0x15u) {
        result->status = ID_UNEXPECTED;
        goto cleanup;
    }
    for (id_u32 pass = 0; pass < 2; ++pass) {
        WRITE(SPI_CON, 0x1021u | CLEAR_PENDING);
        settle();
        result->read_idle_inputs[pass] = READ(IN) & INPUTS;
        if (result->read_idle_inputs[pass] != INPUTS) {
            result->status = ID_READ_IDLE_REFUSED;
            goto cleanup;
        }
        WRITE(SPI_CON, 0x29u | CLEAR_PENDING);
        SYNC();
        settle();
        WRITE(OUT, out & ~CS);
        SYNC();
        settle();
        result->read_transactions_started = pass + 1u;
        result->status = ID_READ_TIMEOUT;
        for (id_u32 i = 0; i < 68; ++i) {
            /* Exactly 03 00 00 00, then 64 input bytes. No dummy byte. */
            id_u32 polls = 0;
            id_u32 value = transfer(i < 4u ? 0x29u : 0x1029u,
                                   i == 0u ? 3u : (i < 4u ? 0u : 255u), &polls);
            if (polls > result->read_max_polls[pass]) result->read_max_polls[pass] = polls;
            if (!value) goto cleanup;
            if (i >= 4u) result->data[pass][i - 4u] = (unsigned char)value;
            result->read_completed[pass] = i + 1u;
        }
        WRITE(OUT, out | CS);
        SYNC();
    }
    result->status = ID_CAPTURED;
    for (id_u32 i = 0; i < 64; ++i) {
        if (result->data[0][i] != result->data[1][i]) {
            result->status = ID_READ_MISMATCH;
            break;
        }
    }

cleanup:
    WRITE(OUT, out | CS); /* Deselect first, including after incomplete transfer. */
    SYNC();
    WRITE(SPI_CON, 0x20u | CLEAR_PENDING); /* Disable before releasing GPIO. */
    SYNC();
    WRITE(PU, pu); /* Original CS pull-up before returning CS to input. */
    WRITE(PD, pd);
    WRITE(DIR, dir);
    WRITE(OUT, out); /* Original low latch only after CS has become an input. */
    WRITE(SPI_CON, CLEAR_PENDING); /* Restore config zero, not sampled pending. */
    SYNC();
    if (READ(OUT) != out) result->cleanup_mismatches |= 1u;
    if (READ(DIR) != dir) result->cleanup_mismatches |= 2u;
    if (READ(PU) != pu) result->cleanup_mismatches |= 4u;
    if (READ(PD) != pd) result->cleanup_mismatches |= 8u;
    if (READ(DIE) != die) result->cleanup_mismatches |= 16u;
    if (READ(SPI_CON) & ~(CLEAR_PENDING | PENDING)) result->cleanup_mismatches |= 32u;
    if (result->cleanup_mismatches) result->status = ID_CLEANUP_FAILED;
finish:
    SYNC();
    result->completion = ID_COMPLETION;
}
