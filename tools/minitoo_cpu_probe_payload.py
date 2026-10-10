#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Fixed CPU-behaviour experiment. Pure offline code: no USB or MMIO access.

The model's answers are predictions, not requirements for a valid capture.
Only r0-r3, ordinary arithmetic flags and the fixed result words are changed.
"""
import hashlib
import itertools
import struct

ADDRESS = 0x120000
SIZE = 512
RESULT_OFFSET = 0x180
RESULT_WORDS = 19
RESULT_BYTES = RESULT_WORDS * 4
CENTER = ADDRESS + RESULT_OFFSET + 40
MARKER = 0x43505531  # CPU1
COMPARISONS = (14, 15, 16, 0x80000000, 0xFFFFFFFF)
PARALLEL = ((0x11223344, 0x015B), (0xAABBCCDD, 0xFFFE))
ARITHMETIC = (("add_carry", 0xFFFFFFFF, 1, False),
              ("add_overflow", 0x7FFFFFFF, 1, False),
              ("sub_borrow", 0, 1, True),
              ("sub_equal", 1, 1, True))


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def _fixed_program():
    """Explicit instruction encodings, also decoded by vendor objdump."""
    words = []

    def emit(*values):
        words.extend(values)

    def literal(reg, value):
        emit(0xFFC0 | reg, value & 0xFFFF, value >> 16)

    def store(reg, word):
        offset = word * 4 - 40
        assert -64 <= offset <= 60 and offset % 4 == 0
        emit(0x6090 | reg | (((offset // 4) & 31) << 8))

    literal(1, CENTER)
    emit(0xE064, 0x3500)  # r3 = PSR; never write a special register.
    store(3, 1)
    for i, value in enumerate(COMPARISONS):
        literal(0, value)
        literal(2, 1)
        emit(0xFC80, 0x1E03)  # if unsigned r0 <= 15, skip one 6-byte literal.
        literal(2, 0)
        store(2, i + 2)
    for i, (incoming, immediate) in enumerate(PARALLEL):
        word = 7 + i * 2
        literal(0, incoming)
        literal(1, ADDRESS + RESULT_OFFSET + word * 4)
        emit(0xF040, immediate, 0x6090)  # r0 = signed imm16 # [r1] = incoming r0.
        emit(0x6190)  # [r1+4] = r0; records the head's result.
        literal(1, CENTER)
    for i, (_, left, right, subtract) in enumerate(ARITHMETIC):
        literal(0, left)
        literal(2, right)
        emit(0x1E80 if subtract else 0x1820)  # r0=r0-r2 or r0+=r2.
        emit(0xE064, 0x3500)  # Capture immediately, before any other arithmetic.
        store(0, 11 + i * 2)
        store(3, 12 + i * 2)
    literal(0, MARKER)
    store(0, 0)  # Completion written last.
    emit(0x0080)  # rts, using caller RETS; no calls or stack operations.
    return struct.pack("<" + "H" * len(words), *words)


CODE = _fixed_program()
CODE_SHA256 = "44a635183d3a492d3ce48e296d2017a7952e7d4b290981bbb54fa889c4306483"
BLOCK_SHA256 = "df44ee774ed51e8017e5ab97afe41f9f2381e91a1909b8aae40e0d0e4b0f59fd"


def audit_code(code=CODE):
    """Explore both sides of every branch, ignoring predicted CPU outcomes.

    This deliberately tiny decoder checks the whole fixed code, all 32 paths,
    every write address/order, and register destinations. It is a bounds audit,
    not an independent implementation of the CPU's arithmetic semantics.
    """
    if code != CODE or len(code) > RESULT_OFFSET:
        raise ValueError("CPU probe differs from fixed program or overlaps results")
    paths = []
    for choices in itertools.product((False, True), repeat=len(COMPARISONS)):
        registers = [None] * 4
        pc = count = branch = 0
        writes = []

        def write(base, offset):
            address = registers[base]
            if address is None:
                raise ValueError("Unknown write base")
            address += offset
            if address % 4 or not ADDRESS + RESULT_OFFSET <= address <= ADDRESS + RESULT_OFFSET + RESULT_BYTES - 4:
                raise ValueError("Write outside fixed results")
            writes.append(address)

        while pc < len(code):
            count += 1
            if count > 128:
                raise ValueError("Unexpected loop")
            op = struct.unpack_from("<H", code, pc)[0]
            if 0xFFC0 <= op <= 0xFFC3:
                registers[op & 3] = struct.unpack_from("<I", code, pc + 2)[0]
                pc += 6
            elif code[pc:pc + 4] == bytes.fromhex("64e00035"):
                registers[3] = None  # PSR read only, no special-register writes.
                pc += 4
            elif op == 0xFC80 and code[pc + 2:pc + 4] == bytes.fromhex("031e"):
                pc += 10 if choices[branch] else 4
                branch += 1
            elif op == 0xF040 and struct.unpack_from("<H", code, pc + 4)[0] == 0x6090:
                write(1, 0)  # Safe under either incoming or newly moved data semantics.
                value = struct.unpack_from("<h", code, pc + 2)[0]
                registers[0] = value & 0xFFFFFFFF
                pc += 6
            elif op & 0xE0F8 == 0x6090 and (op & 7) < 4:
                offset = (op >> 8) & 31
                offset = offset - 32 if offset & 16 else offset
                write(1, offset * 4)
                pc += 2
            elif op in (0x1820, 0x1E80):
                registers[0] = None  # No arithmetic answer assumed for address safety.
                pc += 2
            elif op == 0x0080 and pc + 2 == len(code):
                pc += 2
            else:
                raise ValueError(f"Unreviewed instruction at +0x{pc:x}")
        expected = [ADDRESS + RESULT_OFFSET + 4 * i for i in (*range(1, RESULT_WORDS), 0)]
        if writes != expected or branch != 5:
            raise ValueError("Unexpected write sequence or control flow")
        paths.append(count)
    return {"paths_checked": len(paths), "instructions_min": min(paths),
            "instructions_max": max(paths), "result_words_written": RESULT_WORDS,
            "gpr_writes": [0, 1, 2, 3], "explicit_special_register_writes": [],
            "data_reads": 0, "stack_accesses": 0, "calls": 0, "loops": 0,
            "peripheral_accesses": 0, "flash_transactions": 0}


def make_block(code=CODE):
    audit_code(code)
    block = code + bytes(SIZE - len(code))
    if sha256(code) != CODE_SHA256 or sha256(block) != BLOCK_SHA256:
        raise ValueError("CPU probe code/block differs from reviewed hash pins")
    return block


def decode_result(data):
    original = make_block()
    end = RESULT_OFFSET + RESULT_BYTES
    if len(data) != SIZE or data[:RESULT_OFFSET] != original[:RESULT_OFFSET] or data[end:] != original[end:]:
        raise ValueError("CPU probe changed code/padding outside fixed results")
    words = struct.unpack_from("<19I", data, RESULT_OFFSET)
    if words[0] != MARKER:
        raise ValueError("CPU probe completion word missing or wrong")
    comparisons = [{"input": f"0x{value:08x}", "unsigned_le_15": words[2 + i],
                    "model_prediction": int(value <= 15)} for i, value in enumerate(COMPARISONS)]
    parallel = [{"incoming": f"0x{incoming:08x}", "stored": f"0x{words[7 + 2*i]:08x}",
                 "head_result": f"0x{words[8 + 2*i]:08x}",
                 "model_stored": f"0x{incoming:08x}",
                 "model_head_result": f"0x{(imm if imm < 0x8000 else imm - 0x10000) & 0xFFFFFFFF:08x}"}
                for i, (incoming, imm) in enumerate(PARALLEL)]
    arithmetic = []
    for i, (name, left, right, sub) in enumerate(ARITHMETIC):
        result = ((left - right) if sub else (left + right)) & 0xFFFFFFFF
        carry = left >= right if sub else left + right > 0xFFFFFFFF
        overflow = bool(((left ^ right) if sub else ~(left ^ right)) & (left ^ result) & 0x80000000)
        flags = int(overflow) | (int(carry) << 1) | (int(result == 0) << 2) | ((result >> 31) << 3)
        arithmetic.append({"case": name, "result": f"0x{words[11 + 2*i]:08x}",
                           "psr": f"0x{words[12 + 2*i]:08x}", "flags_low4": words[12 + 2*i] & 15,
                           "model_result": f"0x{result:08x}", "model_flags_low4": flags})
    agreement = (all(c["unsigned_le_15"] == c["model_prediction"] for c in comparisons)
                 and all(c["stored"] == c["model_stored"] and c["head_result"] == c["model_head_result"] for c in parallel)
                 and all(c["result"] == c["model_result"] and c["flags_low4"] == c["model_flags_low4"] for c in arithmetic))
    return {"initial_psr": f"0x{words[1]:08x}", "comparisons": comparisons,
            "parallel": parallel, "arithmetic": arithmetic, "agrees_with_model": agreement,
            "note": "Structural capture validity is independent of model agreement. Only low four PSR bits compared."}
