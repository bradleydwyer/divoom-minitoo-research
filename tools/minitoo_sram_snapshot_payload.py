#!/usr/bin/env python3
"""Fixed retained-SRAM copy program and offline instruction/bounds checks."""
import hashlib
import struct

ADDRESS = 0x120000
SIZE = 1024
SOURCE = 0x10B000
CAPTURE_BYTES = 0x5000
DESTINATION = ADDRESS + SIZE
RESULT_OFFSET = 0x3F0
MARKER = 0x4D545352
CODE = bytes.fromhex(
    "4020c1ff00b01000e2e0aa1bd8ec1a30d8ec2b30c02121ffa00df8ff"
    "30e1f02fc1ff5253544d81608000")
CODE_SHA256 = "8ca2b4fc60c2e0b63e8205b58dbdf2a1b8c677545631045635db2d33929760e7"
BLOCK_SHA256 = "eb8a9f863cb261212703ecab9738bcacd7aeed6adf5e3df012b371234d9c6baa"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def audit_code(code, source_bytes):
    """Interpret the exact reviewed subset, including every loop iteration.

    Checks the linked bytes' reads, writes, branch target, iteration count and
    final marker. This is an offline instruction model, not a silicon emulator
    or a guarantee about SRAM retention or physical memory configuration.
    """
    if code != CODE or len(source_bytes) != CAPTURE_BYTES:
        raise ValueError("Expected the pinned 42-byte program and fixed source range")
    registers = [None] * 4
    output = bytearray(CAPTURE_BYTES)
    reads, writes = [], []
    pc = instructions = 0
    while pc < len(code):
        instructions += 1
        if instructions > 4 * (CAPTURE_BYTES // 4) + 7:
            raise ValueError("SRAM-copy instruction bound exceeded")
        instruction = code[pc:pc + 2]
        if instruction == b"\x40\x20":  # r0 = 0
            registers[0] = 0
            pc += 2
        elif instruction == b"\xc1\xff":  # r1 = immediate32
            registers[1] = struct.unpack_from("<I", code, pc + 2)[0]
            pc += 6
        elif code[pc:pc + 4] == b"\xe2\xe0\xaa\x1b":  # r2 = r1 + 0x15400
            registers[2] = registers[1] + 0x15400
            pc += 4
        elif code[pc:pc + 4] == b"\xd8\xec\x1a\x30":  # r3 = [r1 + r0 << 2]
            address = registers[1] + (registers[0] << 2)
            if address != SOURCE + 4 * len(reads) or address + 4 > SOURCE + CAPTURE_BYTES:
                raise ValueError("Unexpected source load or copy-loop ordering")
            registers[3] = struct.unpack_from("<I", source_bytes, address - SOURCE)[0]
            reads.append(address)
            pc += 4
        elif code[pc:pc + 4] == b"\xd8\xec\x2b\x30":  # [r2 + r0 << 2] = r3
            address = registers[2] + (registers[0] << 2)
            if address != DESTINATION + 4 * len(writes) or address + 4 > DESTINATION + CAPTURE_BYTES:
                raise ValueError("Unexpected destination store or copy-loop ordering")
            struct.pack_into("<I", output, address - DESTINATION, registers[3])
            writes.append((address, registers[3]))
            pc += 4
        elif instruction == b"\xc0\x21":  # r0 += 1
            registers[0] += 1
            pc += 2
        elif code[pc:pc + 6] == b"\x21\xff\xa0\x0d\xf8\xff":
            # Compare 0x1400; relative branch is from the end of this instruction.
            pc = pc + 6 - 0x10 if registers[0] != 0x1400 else pc + 6
        elif code[pc:pc + 4] == b"\x30\xe1\xf0\x2f":  # r0 = r2 - 0x10
            registers[0] = registers[2] - 0x10
            pc += 4
        elif instruction == b"\x81\x60":  # [r0] = r1, completion last
            if (len(reads) != CAPTURE_BYTES // 4 or len(writes) != CAPTURE_BYTES // 4
                    or registers[0] != ADDRESS + RESULT_OFFSET or registers[1] != MARKER):
                raise ValueError("Unexpected or premature completion store")
            writes.append((registers[0], registers[1]))
            pc += 2
        elif instruction == b"\x80\x00" and pc + 2 == len(code):
            pc += 2
        else:
            raise ValueError("Unexpected SRAM-copy instruction")
    if (instructions != 4 * (CAPTURE_BYTES // 4) + 7 or bytes(output) != source_bytes
            or len(writes) != CAPTURE_BYTES // 4 + 1):
        raise ValueError("Incomplete or changed SRAM copy")
    return {"reads": reads, "writes": writes, "instructions": instructions, "output": bytes(output)}


def make_block(code=CODE):
    if (code != CODE or sha256(code) != CODE_SHA256
            or not SOURCE + CAPTURE_BYTES <= ADDRESS
            or DESTINATION + CAPTURE_BYTES > 0x125C00):
        raise ValueError("SRAM-copy code or reviewed memory bounds changed")
    block = code + bytes(SIZE - len(code))
    if sha256(block) != BLOCK_SHA256:
        raise ValueError("SRAM-copy block hash changed")
    return block


def result_block():
    block = bytearray(make_block())
    struct.pack_into("<I", block, RESULT_OFFSET, MARKER)
    return bytes(block)


def validate_result(data):
    if data != result_block():
        raise ValueError("SRAM-copy completion/code/padding differs from the fixed expected result")
