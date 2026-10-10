/* Offline prototype only: not uploaded or executed on the MiniToo.
 * A future ROM-mode test would upload one 512-byte block at 0x120000.
 * Its last 16 bytes contain the result marker, initially zero.
 * No stack, peripheral, ROM-service, hook, or flash access is needed.
 */
typedef unsigned int u32;
_Static_assert(sizeof(u32) == 4, "Requires a 32-bit unsigned int");

void minitoo_ram_probe(void *rom_arguments)
{
    (void)rom_arguments;
    *(volatile u32 *)0x001201f0 = 0x4d544f4b;
}
