#!/usr/bin/env python3
"""Fixed BR28 configuration sampler and offline checks; no USB imports/access."""
import hashlib
import struct

ADDRESS = 0x120000
SIZE = 512
RESULT_OFFSET = 0x1D0
RESULT_BYTES = 32
INSTRUCTIONS = 23
MARKER = 0x4D545350
CODE = bytes.fromhex(
    "c0ff28fc19000060c1ffd00112009061c0ff1460fd0000609062"
    "c0ff001cfd0000609063c0ff0053fd000260926400629065"
    "c0ff0055fd000260926600629067c0ff5053544d90608000")
CODE_SHA256 = "59ad6306222544f666b82bf3429b28627dab02e5271af656ed4bb1d59d4ec8a8"
BLOCK_SHA256 = "6e625218e18f9265099bc7c32edb814fc46e5fb7a16cf14697747a0efea4cc63"
SAMPLES = (
    ("boot_arg_word", 0x19FC28),
    ("iomap_con0", 0xFD6014),
    ("spi0_con", 0xFD1C00),
    ("portd_out", 0xFD5300),
    ("portd_dir", 0xFD5308),
    ("portg_out", 0xFD5500),
    ("portg_dir", 0xFD5508),
)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def audit_code(code, inputs):
    """Execute only the sampler's tiny instruction subset against synthetic data.

    Unknown instructions, reads, writes and control flow fail closed. This is a
    byte-level bounds check, not a PI32v2 CPU/peripheral emulator or hardware proof.
    """
    if code != CODE:
        raise ValueError("Code differs from the reviewed 74-byte sampler")
    registers = [None] * 3
    reads, writes = [], []
    pc = 0
    instructions = 0
    loads = {b"\x00\x60": (0, 0), b"\x02\x60": (2, 0), b"\x00\x62": (0, 8)}
    while pc < len(code):
        instructions += 1
        instruction = code[pc:pc + 2]
        if instruction in (b"\xc0\xff", b"\xc1\xff"):
            registers[instruction[0] - 0xC0] = struct.unpack_from("<I", code, pc + 2)[0]
            pc += 6
        elif instruction in loads:
            dest, offset = loads[instruction]
            address = registers[0] + offset
            expected = SAMPLES[len(reads)][1] if len(reads) < len(SAMPLES) else None
            if address != expected or address not in inputs:
                raise ValueError("Unexpected sampler source address")
            reads.append(address)
            registers[dest] = inputs[address]
            pc += 2
        elif instruction[0] in (0x90, 0x92) and 0x60 <= instruction[1] <= 0x67:
            address = registers[1] + (instruction[1] - 0x60) * 4
            if not ADDRESS + RESULT_OFFSET <= address < ADDRESS + RESULT_OFFSET + 32:
                raise ValueError("Sampler write outside its result buffer")
            writes.append((address, registers[instruction[0] - 0x90]))
            pc += 2
        elif instruction == b"\x80\x00" and pc + 2 == len(code):
            pc += 2
        else:
            raise ValueError("Unexpected sampler instruction or control flow")
    expected_writes = [(ADDRESS + RESULT_OFFSET + 4 * (i + 1), inputs[a])
                       for i, (_, a) in enumerate(SAMPLES)]
    expected_writes.append((ADDRESS + RESULT_OFFSET, MARKER))
    if instructions != 23 or reads != [a for _, a in SAMPLES] or writes != expected_writes:
        raise ValueError("Sampler read/write order differs from the reviewed sequence")
    return {"reads": reads, "writes": writes, "instructions": instructions}


def make_block(code=CODE):
    audit_code(code, {a: i for i, (_, a) in enumerate(SAMPLES)})
    block = code + bytes(SIZE - len(code))
    if sha256(code) != CODE_SHA256 or sha256(block) != BLOCK_SHA256:
        raise ValueError("Sampler code/block hash differs from the reviewed pin")
    return block


def decode_result(data):
    """Accept the full pinned block, with changes confined to eight result words."""
    original = make_block()
    end = RESULT_OFFSET + 32
    if (len(data) != SIZE or data[:RESULT_OFFSET] != original[:RESULT_OFFSET]
            or data[end:] != original[end:]):
        raise ValueError("Result changed code/padding outside the fixed result buffer")
    words = struct.unpack_from("<8I", data, RESULT_OFFSET)
    if words[0] != MARKER:
        raise ValueError("Snapshot completion word is absent or wrong")
    values = dict(zip((name for name, _ in SAMPLES), words[1:]))
    selector = (values["boot_arg_word"] >> 16) & 255
    iomap_group = (values["iomap_con0"] >> 14) & 1
    return {
        "raw_values": {name: f"0x{value:08x}" for name, value in values.items()},
        "rom_shadow_selector": selector,
        "iomap_group_bit14": iomap_group,
        "shadow_matches_group_bit": selector == iomap_group,
        "portd_bit3_out": (values["portd_out"] >> 3) & 1,
        "portd_bit3_dir": (values["portd_dir"] >> 3) & 1,
        "portg_bit4_out": (values["portg_out"] >> 4) & 1,
        "portg_bit4_dir": (values["portg_dir"] >> 4) & 1,
        "note": "Sequential ROM-mode configuration samples; not flash identification, wiring proof, or installed firmware backup",
    }
