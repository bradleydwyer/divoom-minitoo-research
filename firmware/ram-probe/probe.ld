OUTPUT_FORMAT("elf32-pi32v2")
ENTRY(minitoo_ram_probe)
SECTIONS
{
    . = 0x00120000;
    .text : { *(.text*) }
    ASSERT(SIZEOF(.text) <= 0x1f0, "Code overlaps result marker")
    .unexpected : { *(.data*) *(.bss*) *(COMMON) *(.rodata*) }
    ASSERT(SIZEOF(.unexpected) == 0, "Unexpected data or runtime dependency")
    /DISCARD/ : { *(.comment) *(.note*) *(.llvm_addrsig) }
}
