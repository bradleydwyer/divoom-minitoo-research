OUTPUT_FORMAT("elf32-pi32v2")
ENTRY(minitoo_sram_snapshot)
SECTIONS
{
    . = 0x00120000;
    .text : { *(.text*) }
    ASSERT(SIZEOF(.text) <= 0x3f0, "Code overlaps completion marker")
    .unexpected : { *(.data*) *(.bss*) *(COMMON) *(.rodata*) }
    ASSERT(SIZEOF(.unexpected) == 0, "Unexpected data or runtime dependency")
    /DISCARD/ : { *(.comment) *(.note*) *(.llvm_addrsig) }
}
