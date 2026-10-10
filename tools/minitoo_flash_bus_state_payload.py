#!/usr/bin/env python3
"""Fixed BR28 bus/clock sampler and offline checks; no USB imports/access."""
import hashlib
import struct

ADDRESS = 0x120000
SIZE = 512
RESULT_OFFSET = 0x1B0
MARKER = 0x4D544253
CODE = bytes.fromhex(
    "c1ff28fc19001260c0ffb001120082611261826211628163"
    "c1ff1460fd0011608164c1ff001cfd0011608165"
    "c1ff0002fe001260826611668167c1ff0041fd0011608168"
    "c1ff1400fd00126082691261826a1162816b"
    "c1ff0053fd001260826c1262826d1263826e1264826f02f140001165a160"
    "c1ff0055fd001360a3611162a162c1ff5342544d81608000")
SAMPLES = (
    ("boot_arg_word", 0x19FC28),
    ("boot_arg_osc_hz", 0x19FC2C),
    ("boot_arg_sys_hz", 0x19FC30),
    ("iomap_con0", 0xFD6014),
    ("spi0_con", 0xFD1C00),
    ("sfc_con", 0xFE0200),
    ("sfc_enc_con", 0xFE0218),
    ("perienc_enccon", 0xFD4100),
    ("clock_sys_div", 0xFD0014),
    ("clock_con0", 0xFD0018),
    ("clock_con1", 0xFD001C),
    ("portd_out", 0xFD5300),
    ("portd_dir", 0xFD5308),
    ("portd_die", 0xFD530C),
    ("portd_pu", 0xFD5310),
    ("portd_pd", 0xFD5314),
    ("portg_out", 0xFD5500),
    ("portg_dir", 0xFD5508),
)
RESULT_BYTES = 4 * (1 + len(SAMPLES))
INSTRUCTIONS = 49
CODE_SHA256 = "23b208a4f4f6c2accd93fab2e7e703ef5d217e445970221da6fbcaf5942c6c5b"
BLOCK_SHA256 = "42a82dbb4da591e5adfec802b695d38068576373b9e1c4a7c1fbb6f31afd2348"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def audit_code(code, inputs):
    """Interpret this straight-line instruction subset, with no live MMIO.

    This checks exact source addresses, write bounds and order. It is not a
    general CPU/peripheral emulator, silicon side-effect model or recovery proof.
    """
    if code != CODE:
        raise ValueError("Code differs from the reviewed 140-byte bus sampler")
    registers = [None] * 4
    reads, writes = [], []
    pc = instructions = 0
    while pc < len(code):
        instructions += 1
        instruction = code[pc:pc + 2]
        if instruction in (b"\xc0\xff", b"\xc1\xff"):
            registers[instruction[0] - 0xC0] = struct.unpack_from("<I", code, pc + 2)[0]
            pc += 6
        elif instruction[0] in (0x11, 0x12, 0x13) and 0x60 <= instruction[1] <= 0x66:
            address = registers[1] + 4 * (instruction[1] - 0x60)
            expected = SAMPLES[len(reads)][1] if len(reads) < len(SAMPLES) else None
            if address != expected or address not in inputs:
                raise ValueError("Unexpected bus-sampler source address")
            reads.append(address)
            registers[instruction[0] - 0x10] = inputs[address]
            pc += 2
        elif code[pc:pc + 4] == b"\x02\xf1\x40\x00":
            registers[2] = registers[0] + 0x40
            pc += 4
        elif instruction[0] in (0x81, 0x82, 0xA1, 0xA3) and 0x60 <= instruction[1] <= 0x6F:
            base = 0 if instruction[0] < 0xA0 else 2
            address = registers[base] + 4 * (instruction[1] - 0x60)
            if not ADDRESS + RESULT_OFFSET <= address < ADDRESS + RESULT_OFFSET + RESULT_BYTES:
                raise ValueError("Bus sampler write outside its result buffer")
            writes.append((address, registers[instruction[0] & 0xF]))
            pc += 2
        elif instruction == b"\x80\x00" and pc + 2 == len(code):
            pc += 2
        else:
            raise ValueError("Unexpected bus-sampler instruction or control flow")
    expected_writes = [(ADDRESS + RESULT_OFFSET + 4 * (i + 1), inputs[a])
                       for i, (_, a) in enumerate(SAMPLES)]
    expected_writes.append((ADDRESS + RESULT_OFFSET, MARKER))
    if (instructions != INSTRUCTIONS or reads != [a for _, a in SAMPLES]
            or writes != expected_writes):
        raise ValueError("Bus sampler read/write sequence differs from the reviewed pin")
    return {"reads": reads, "writes": writes, "instructions": instructions}


def make_block(code=CODE):
    audit_code(code, {a: i for i, (_, a) in enumerate(SAMPLES)})
    block = code + bytes(SIZE - len(code))
    if sha256(code) != CODE_SHA256 or sha256(block) != BLOCK_SHA256:
        raise ValueError("Bus sampler code/block hash differs from the reviewed pin")
    return block


def decode_result(data):
    original = make_block()
    end = RESULT_OFFSET + RESULT_BYTES
    if (len(data) != SIZE or data[:RESULT_OFFSET] != original[:RESULT_OFFSET]
            or data[end:] != original[end:]):
        raise ValueError("Bus result changed code/padding outside the fixed result buffer")
    words = struct.unpack_from("<19I", data, RESULT_OFFSET)
    if words[0] != MARKER:
        raise ValueError("Bus-snapshot completion word is absent or wrong")
    values = dict(zip((name for name, _ in SAMPLES), words[1:]))
    iomap = values["iomap_con0"]
    return {
        "raw_values": {name: f"0x{value:08x}" for name, value in values.items()},
        "rom_shadow_selector": (values["boot_arg_word"] >> 16) & 255,
        "spi0_group_bit14": (iomap >> 14) & 1,
        "sfc_group_bit16": (iomap >> 16) & 1,
        "spi0_crossbar_bit13": (iomap >> 13) & 1,
        "spi0_enabled": bool(values["spi0_con"] & 1),
        "sfc_enabled": bool(values["sfc_con"] & 1),
        "clock_fields": {
            "hsb_divider_field": values["clock_sys_div"] & 255,
            "lsb_divider_field": (values["clock_sys_div"] >> 8) & 7,
            "sfc_divider_field": (values["clock_sys_div"] >> 12) & 7,
            "main_clock_selector": (values["clock_con1"] >> 8) & 7,
        },
        "note": "Sequential ROM-mode register samples; no flash-chip protocol, encryption state, geometry or backup is established by these fields alone",
    }
