OUTPUT_FORMAT("elf32-pi32v2")
ENTRY(minitoo_flash_bus_state)
SECTIONS
{
    . = 0x00120000;
    .text : { *(.text*) }
    ASSERT(SIZEOF(.text) <= 0x1b0, "Code overlaps bus-state results")
    .unexpected : { *(.data*) *(.bss*) *(COMMON) *(.rodata*) }
    ASSERT(SIZEOF(.unexpected) == 0, "Unexpected data or runtime dependency")
    /DISCARD/ : { *(.comment) *(.note*) *(.llvm_addrsig) }
}
