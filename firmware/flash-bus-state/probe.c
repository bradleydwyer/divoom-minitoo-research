/* Fixed read-only bus-state sample. No flash transaction or peripheral write.
 * All results are in the same uploaded 512-byte RAM block. Sequential reads;
 * register state does not identify the flash or prove its physical protocol.
 */
typedef unsigned int u32;
_Static_assert(sizeof(u32) == 4, "Requires 32-bit unsigned int");
#define READ32(address) (*(volatile const u32 *)(address))

void minitoo_flash_bus_state(void *rom_arguments)
{
    (void)rom_arguments;
    volatile u32 *result = (volatile u32 *)0x001201b0;
    result[1] = READ32(0x0019fc28); /* ROM boot arguments / port shadow */
    result[2] = READ32(0x0019fc2c); /* ROM oscillator-frequency word */
    result[3] = READ32(0x0019fc30); /* ROM system-frequency word */
    result[4] = READ32(0x00fd6014); /* IOMAP.CON0 */
    result[5] = READ32(0x00fd1c00); /* SPI0.CON; no BUF/BAUD access */
    result[6] = READ32(0x00fe0200); /* Main SFC.CON */
    result[7] = READ32(0x00fe0218); /* Main SFC.ENC_CON; no key access */
    result[8] = READ32(0x00fd4100); /* PERIENC.ENCCON; no key access */
    result[9] = READ32(0x00fd0014); /* CLOCK.SYS_DIV */
    result[10] = READ32(0x00fd0018); /* CLOCK.CLK_CON0 */
    result[11] = READ32(0x00fd001c); /* CLOCK.CLK_CON1 */
    result[12] = READ32(0x00fd5300); /* PORTD.OUT */
    result[13] = READ32(0x00fd5308); /* PORTD.DIR */
    result[14] = READ32(0x00fd530c); /* PORTD.DIE */
    result[15] = READ32(0x00fd5310); /* PORTD.PU */
    result[16] = READ32(0x00fd5314); /* PORTD.PD */
    result[17] = READ32(0x00fd5500); /* PORTG.OUT */
    result[18] = READ32(0x00fd5508); /* PORTG.DIR */
    result[0] = 0x4d544253;
}
