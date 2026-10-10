/* Fixed retained-application SRAM copy. No peripherals, flash, services or
 * caller arguments. FD07 must read the copy, never the source: it temporarily
 * transforms its source in place. This is a sequential ROM-mode capture.
 */
typedef unsigned int u32;
_Static_assert(sizeof(u32) == 4, "Requires 32-bit unsigned int");

void minitoo_sram_snapshot(void *rom_arguments)
{
    (void)rom_arguments;
    volatile const u32 *source = (volatile const u32 *)0x0010b000;
    volatile u32 *destination = (volatile u32 *)0x00120400;
    for (u32 words = 0x1400; words != 0; --words) {
        *destination++ = *source++;
    }
    *(volatile u32 *)0x001203f0 = 0x4d545352;
}
