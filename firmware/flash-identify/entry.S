    .section .entry,"ax",@progbits
    .global minitoo_flash_identify_entry
minitoo_flash_identify_entry:
    r0 = sp
    r1 = 0x001207f8
    [r1] = r0
    r0 = rets
    [r1+4] = r0
    r0 = 0x00120800
    r1 = 0x5354414b
    [r0] = r1
    sp = 0x00122800
    r0 = 0x00120740
    call minitoo_flash_identify
    r0 = 0x00120800
    r1 = [r0]
    r0 = 0x00120794
    [r0] = r1
    r1 = 0x001207f8
    r0 = [r1+4]
    rets = r0
    r0 = [r1]
    sp = r0
    rts
