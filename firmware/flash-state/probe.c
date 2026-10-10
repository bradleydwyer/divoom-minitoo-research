/* Fixed configuration snapshot, built and reviewed offline before use.
 * No flash transactions, peripheral writes, calls, loops or runtime services.
 * Results occupy 0x1201d0..0x1201ef in the uploaded 512-byte RAM block.
 * The completion word is written last. These are sequential samples, not an
 * atomic snapshot; the ROM boot-argument selector is not wiring detection.
 */
typedef unsigned int u32;
_Static_assert(sizeof(u32) == 4, "Requires 32-bit unsigned int");

#define READ32(address) (*(volatile const u32 *)(address))

void minitoo_flash_state(void *rom_arguments)
{
    (void)rom_arguments;
    volatile u32 *result = (volatile u32 *)0x001201d0;
    result[1] = READ32(0x0019fc28); /* ROM boot_arg_list, first word */
    result[2] = READ32(0x00fd6014); /* IOMAP.CON0 */
    result[3] = READ32(0x00fd1c00); /* SPI0.CON, no BUF/FIFO read */
    result[4] = READ32(0x00fd5300); /* PORTD.OUT */
    result[5] = READ32(0x00fd5308); /* PORTD.DIR */
    result[6] = READ32(0x00fd5500); /* PORTG.OUT */
    result[7] = READ32(0x00fd5508); /* PORTG.DIR */
    result[0] = 0x4d545350;
}
