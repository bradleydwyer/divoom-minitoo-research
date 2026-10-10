OUTPUT_FORMAT("elf32-pi32v2")
ENTRY(minitoo_flash_id_entry)
SECTIONS
{
    . = 0x00120000;
    .text : { *(.entry) *(.text*) }
    ASSERT(SIZEOF(.text) <= 0x3c0, "Code overlaps fixed ID results")
    .unexpected : { *(.data*) *(.bss*) *(COMMON) *(.rodata*) }
    ASSERT(SIZEOF(.unexpected) == 0, "Unexpected data or runtime dependency")
    /DISCARD/ : { *(.comment) *(.note*) *(.llvm_addrsig) }
}
