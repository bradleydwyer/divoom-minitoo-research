/* Experimental implementation, NOT cleared for device execution.
 * See docs/technical-notes.md for unresolved hardware
 * assumptions. The separate fixed entry adapter is for offline review and the
 * upload-only check; no host tool permits execution of this candidate yet.
 * No SDK/ROM helper is called; the only proposed chip transaction is 9F.
 */
#include "candidate.h"

#ifdef MINITOO_ID_OFFLINE_TEST
extern id_u32 id_model_read(id_u32 address);
extern void id_model_write(id_u32 address, id_u32 value);
#define READ(a) id_model_read(a)
#define WRITE(a, v) id_model_write((a), (v))
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
#define DIR 0x00fd5308u
#define DIE 0x00fd530cu
#define PU 0x00fd5310u
#define PD 0x00fd5314u
#define CS 8u
#define SIGNALS 0x47u /* ROM group-0 setup: PD0, PD1, PD2, PD6. */
#define INPUTS 0x46u
#define PENDING 0x8000u
#define CLEAR_PENDING 0x4000u
#define SPI_BASE 0x21u /* ROM flash-clock setting 0x20, master + enable. */

static id_u32 transfer(id_u32 receive, id_u32 byte, volatile id_u32 *polls)
{
    id_u32 con = SPI_BASE | 8u | (receive ? 0x1000u : 0u);
    WRITE(SPI_CON, con | CLEAR_PENDING);
    WRITE(SPI_BUF, byte);
    SYNC();
    for (id_u32 count = 1; count <= ID_POLL_LIMIT; ++count) {
        if (READ(SPI_CON) & PENDING) {
            *polls = count;
            WRITE(SPI_CON, con | CLEAR_PENDING);
            /* Return marker bit distinguishes byte 00 from timeout. */
            id_u32 value = receive ? READ(SPI_BUF) & 255u : 0u;
            WRITE(SPI_CON, SPI_BASE | (receive ? 0x1000u : 0u));
            return 0x100u | value;
        }
    }
    *polls = ID_POLL_LIMIT;
    return 0;
}

void minitoo_flash_id_candidate(volatile struct id_result *result)
{
    result->completion = 0;
    result->status = ID_PREFLIGHT_REFUSED;
    result->preflight_mismatches = 0;
    result->transfers_completed = 0;
    result->cleanup_mismatches = 0;
    for (id_u32 i = 0; i < 3; ++i) result->id_bytes[i] = 0;
    for (id_u32 i = 0; i < 4; ++i) result->polls[i] = 0;

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
    WRITE(SPI_CON, 0x20u | CLEAR_PENDING); /* Disabled during setup. */
    WRITE(SPI_BAUD, 255u); /* Candidate divider; exact encoding still under review. */
    WRITE(SPI_CON, SPI_BASE);
    SYNC();
    WRITE(OUT, out & ~CS);
    SYNC();

    result->status = ID_TRANSFER_TIMEOUT;
    if (!transfer(0, 0x9fu, &result->polls[0])) goto cleanup;
    result->transfers_completed = 1;
    for (id_u32 i = 0; i < 3; ++i) {
        id_u32 value = transfer(1, 255u, &result->polls[i + 1]);
        if (!value) goto cleanup;
        result->id_bytes[i] = value & 255u;
        result->transfers_completed = i + 2;
    }
    result->status = ID_CAPTURED;
    if ((result->id_bytes[0] == 0 && result->id_bytes[1] == 0 && result->id_bytes[2] == 0)
        || (result->id_bytes[0] == 255 && result->id_bytes[1] == 255 && result->id_bytes[2] == 255))
        result->status = ID_NO_RESPONSE;

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
