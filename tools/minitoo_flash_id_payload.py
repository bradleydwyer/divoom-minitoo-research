#!/usr/bin/env python3
"""One pinned 1 KiB candidate block, for upload/readback only at this stage."""
import hashlib
import struct

ADDRESS = 0x120000
SIZE = 1024
RESULT_OFFSET = 0x3C0
RESULT_BYTES = 48
CODE = bytes.fromhex(
    "c0ffc0031200c0ea28007604442146218041061645e02940a5e10466c3ff001c"
    "fd00b560b162200061ac366056e8087ac42123ff0141f9ff40ea802b40205604"
    "a460b560b0e8009030620017302840e0000141e12110b16056047e0404164020"
    "c06041ea0140c062c063c06b49904220d8ec1b02c22182f8fb074a9c4120d8ec"
    "2b01c12181f8fb09c0ff28fc19000160c3ff0003008491e8000302ef01400161"
    "c3ff00366e0191e8000302ef02400062c1ff006cdc0290e8000102ef0440c0ff"
    "1460fd000060004202ef0840c8ff001cfd00d0ec8000a0e8000c02ef1040e0e0"
    "668c0160c3ff3400580191e8000302ef20400066004202ef4040e0e0148d0060"
    "004202ef804020e114840160014202ef804f0161b1e8310002ef004f41f04316"
    "006290e8000102ef804ee6e05c8d6760d0ec68e0d0ec6c90d0ec60b1d0ec64a1"
    "87f808208ef806de89f804fe8bf802300af8020002ef004e406280f884004ce1"
    "0870d0ec61c070e108e070f14fb0e06240e1460070f14fa0e06470f14fe0e065"
    "40e146004df02040e062d0ec81d041eaff8040ea2180200070e10870e0602000"
    "41ea02404020613f4520bfea2eff1045402102f12040c0634021793fbfea25ff"
    "005c59810017a07c588215d6c063c22481f9f20741ea00404064804440658042"
    "40660049406490f808fe406590f805fe406690f802fe41ea0440d0ec61c02000"
    "d0ec81d02000d0ec61b1d0ec65a1d0ec69e0e76040ea808c2000606090e80007"
    "0bef0140606290e8000e0bef0240606490e8000b0bef0440606590e8000a0bef"
    "0840606390e800090bef1040d0ec8000c1ffff3fffff10ea80010bef2040406b"
    "004241ea03402000c0ff4449544dc0605e04"
)
CODE_SHA256 = "ed31fb16017c17cb70abd458198e5d7d9c69b8d356c66427fa95279fee7bb55c"
BLOCK_SHA256 = "b7c492132e2645d7f28a7250e71d65cc4fb7fd7f70935bfe0edc691c60242c97"
COMPLETION = 0x4D544944
POLL_LIMIT = 65536


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def make_block(code=CODE):
    if ((ADDRESS, SIZE, RESULT_OFFSET, RESULT_BYTES) != (0x120000, 1024, 0x3C0, 48)
            or code != CODE or len(code) != 626 or len(code) > RESULT_OFFSET
            or sha256(code) != CODE_SHA256 or RESULT_OFFSET + RESULT_BYTES > SIZE):
        raise ValueError("Candidate code or memory bounds differ from the fixed pin")
    block = code + bytes(SIZE - len(code))
    if sha256(block) != BLOCK_SHA256:
        raise ValueError("Candidate block differs from the fixed pin")
    return block


def decode_result(data):
    """Validate a future result, offline. No helper currently executes this code.

    All bytes outside the 48-byte result must match the pinned initial block.
    A valid result may be a refusal, timeout, cleanup error or absent response;
    captured bytes alone do not identify a physical flash part.
    """
    initial = make_block()
    end = RESULT_OFFSET + RESULT_BYTES
    if (len(data) != SIZE or data[:RESULT_OFFSET] != initial[:RESULT_OFFSET]
            or data[end:] != initial[end:]):
        raise ValueError("Code or padding outside the fixed result changed")
    completion, status, preflight, count, *tail = struct.unpack_from("<12I", data, RESULT_OFFSET)
    ident, polls, cleanup = tail[:3], tail[3:7], tail[7]
    labels = ("captured", "preflight-refused", "transfer-timeout", "cleanup-failed", "no-response")
    if (completion != COMPLETION or status >= len(labels) or preflight & ~0xFFF
            or cleanup & ~0x3F or count > 4 or any(value > 255 for value in ident)):
        raise ValueError("Invalid result marker, status, count, flags or ID byte")
    if status == 1:
        if not preflight or count or cleanup or any(ident) or any(polls):
            raise ValueError("Inconsistent preflight refusal")
    else:
        if preflight or bool(cleanup) != (status == 3):
            raise ValueError("Inconsistent preflight/cleanup flags")
        if any(not 1 <= value <= POLL_LIMIT for value in polls[:count]):
            raise ValueError("Invalid completed-transfer poll count")
        received = max(count - 1, 0)
        if any(ident[received:]):
            raise ValueError("ID bytes present for unfinished receives")
        if count < 4:
            if status not in (2, 3) or polls[count] != POLL_LIMIT or any(polls[count + 1:]):
                raise ValueError("Inconsistent timeout stage or unused poll counts")
        else:
            no_response = ident in ([0, 0, 0], [255, 255, 255])
            if status not in (0, 3, 4) or (status != 3 and no_response != (status == 4)):
                raise ValueError("Inconsistent completed transaction status")
    return {"status": labels[status], "preflight_mismatches": preflight,
            "transfers_completed": count, "id_bytes": bytes(ident).hex(),
            "polls": polls, "cleanup_mismatches": cleanup,
            "id_captured": status == 0,
            "note": "Validated RAM result only; part identity, capacity and backup are not established"}
