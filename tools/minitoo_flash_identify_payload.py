#!/usr/bin/env python3
"""Pinned fixed volatile-mode release/ID program; no arbitrary payload inputs."""
import hashlib
import struct

ADDRESS = 0x120000
SIZE = 2048
CHUNK_BYTES = 1024
RESULT_OFFSET = 0x740
RESULT_BYTES = 192
STACK_BOTTOM = 0x120800
STACK_TOP = 0x122800
STACK_GUARD = 0x5354414B
COMPLETION = 0x4D54494D
POLL_LIMIT = 65536
EXPECTED_ID = "856015"
CODE = bytes.fromhex(
    "64e0000ec1fff8071200906064e000039061c0ff00081200c1ff4b4154538160eeff00281200"
    "c0ff4007120080ea2300c0ff000812000160c0ff940712008160c1fff8071200106164e08003"
    "106064e0800e8000e29f40208020002008ffff0f080088802000c0eb0100012023ff801df9ff"
    "028180007f04e29702164020a06041ea0120a062a063a06f2c904120d8ec4b01c12181f8fb07"
    "289c41204320d8ec0b13c32183f8fb1100e140204320d8ec0b13c32183f8fb0954ea0020c0ff"
    "28fc19000160c3ff0003008491e8000302ef01200161c3ff00366e0191e8000302ef02200062"
    "c1ff006cdc0290e8000102ef0420c0ff1460fd000060004202ef0820c3ff001cfd003060a0e8"
    "000c02ef1020e0e0663c0160c5ff3400580191e8000502ef20200066004202ef4020e0e0143d"
    "0060004202ef802020e114340160014202ef802f0161b1e8310002ef002f41f04316006290e8"
    "000102ef802eede05c3dd0ecd070d0ecd8b0d0ecdc60d0ecd091d0ecd48187f808208bf806de"
    "86f804fe89f8023008f8020002ef002ec0fff8071200016061ff03100e00c5ffe0f7e7ff1518"
    "03ff0158090045e000fcd119e5e0d05905e8021002ef802d41f0bc4a006190e8000102ef002d"
    "206201ff00001d0140f1087086268027d0ecd10070e108b0d0ecd90070e16f9040e16600d0ec"
    "d10170e16f80d0ecd50170e16fb040e16600d0ecd90040e02058b06041eaff3040e02118b060"
    "200070f108708725802447204ae02110b7e801004ae0211841e180ac40e02150b7e803001016"
    "71a22d1cb060bfea08ffd0ecd40060e16600d0ec51044e29b7e80300a616d0ec500480f8dccc"
    "87f8060640e1806cb0602000bfeaf2fe0024d0ecd1002000bfeaecfe78818020d0ec21054122"
    "40228028a1614024b7e803004021d4e905b0d4e90990d4e90d80b7e80100802840204be00100"
    "48e00100b7e80300c01449e00100804109164ee0291018ea00096e166a16d0ec2cc04fe180ec"
    "d0ec31f0793f8041613fb7e80300793fb162200090e18219c0e1c2502518366056e8067a0be1"
    "01b023ff01b1f8ff149dd0ec5db1d0ec31f045e000013eea808d356255173528d0ec31e00145"
    "511735e1fc4fd8ec5b1001e101c0c021a6d6a163012881e9b8010027d0ecd100200000200716"
    "d4e90c80d4e90890d4e904b080f9660941ea0020206480442065804220660049206490f811fe"
    "206590f80efe206690f80bfe41ea0420048847ea805bd4e90c80d4e90890d4e904b00027d0ec"
    "d100200040e02040b0602000d0ecd191d0ecd581d0ecd9b00425d0ecd14040ea803c2000d0ec"
    "d000012690e800040fef0120d0ecd80090e8000b0fef0220d0ecd00190e800090fef0420d0ec"
    "d40190e800080fef0820d0ecdc0090e800010fef10203060c1ffff3fffff10ea80010fef2020"
    "206f004241ea03202000c0ff4d49544da06002895f0441ea0520d797")
CODE_SHA256 = "b0f480cfc21f43ae8e50993e1765eadaa94980808aa1fb94fd4ec854bab9bed3"
BLOCK_SHA256 = "e75fdc94f426aa6879b58dbdbf7dedf409339d0405983ca5d648e99d7cc8866e"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def make_block(code=CODE):
    if (code != CODE or len(code) != 1054 or sha256(code) != CODE_SHA256
            or len(code) > RESULT_OFFSET or RESULT_OFFSET + RESULT_BYTES != SIZE
            or ADDRESS + SIZE != STACK_BOTTOM or STACK_TOP > 0x125400):
        raise ValueError("Mode-release/ID code or reviewed RAM bounds changed")
    block = code + bytes(SIZE - len(code))
    if sha256(block) != BLOCK_SHA256:
        raise ValueError("Mode-release/ID block hash changed")
    return block


def decode_result(data):
    initial = make_block()
    if len(data) != SIZE or data[:RESULT_OFFSET] != initial[:RESULT_OFFSET]:
        raise ValueError("ID code/padding changed outside the result")
    words = struct.unpack_from("<48I", data, RESULT_OFFSET)
    completion, status, preflight, count = words[:4]
    ident, polls, cleanup = list(words[4:7]), list(words[7:15]), words[15]
    idle, frames, guard = list(words[16:20]), words[20], words[21]
    caller_sp, caller_return = words[46:48]
    labels = ("captured", "preflight-refused", "transfer-timeout", "cleanup-failed",
              "no-response", "idle-inputs-refused")
    if (completion != COMPLETION or status >= len(labels) or preflight & ~0x3FFF
            or cleanup & ~0x3F or count > 8 or frames > 4
            or any(v > 255 for v in ident) or any(v & ~0x66 for v in idle)
            or guard != STACK_GUARD or any(words[22:46])):
        raise ValueError("Invalid mode-release/ID result fields, guard or reserved bytes")
    sp_valid = caller_sp % 4 == 0 and (0x180820 <= caller_sp <= 0x181020
                                     or 0x19FC00 <= caller_sp < 0x1A0000)
    if bool(preflight & 0x1000) == sp_valid or bool(preflight & 0x2000) == (caller_return == 0x4ABC):
        raise ValueError("Caller context and its preflight flags disagree")
    if status == 1:
        if not preflight or count or frames or cleanup or any(ident + polls + idle):
            raise ValueError("Inconsistent preflight refusal")
    else:
        if preflight or bool(cleanup) != (status == 3):
            raise ValueError("Inconsistent preflight/cleanup flags")
        if any(not 1 <= v <= POLL_LIMIT for v in polls[:count]):
            raise ValueError("Invalid completed-transfer poll count")
        if any(ident[max(0, count - 5):]):
            raise ValueError("ID bytes present before their receives completed")
        # A failure is either a pending timeout in the next transfer, or a
        # refusal at one of the four CS-high input checks. No continuation.
        boundaries = (0, 1, 3, 4)
        timed_out = count < 8 and polls[count] == POLL_LIMIT
        if count == 8:
            expected_frames, checked = 4, 4
            no_response = ident in ([0, 0, 0], [255, 255, 255])
            if status not in (0, 3, 4) or (status != 3 and no_response != (status == 4)):
                raise ValueError("Inconsistent completed identification")
        elif timed_out:
            expected_frames = sum(count >= n for n in boundaries)
            checked = expected_frames
            if status not in (2, 3) or any(polls[count + 1:]):
                raise ValueError("Inconsistent timeout result")
        else:
            if count not in boundaries or status not in (3, 5) or any(polls[count:]):
                raise ValueError("Inconsistent idle-input refusal")
            expected_frames = boundaries.index(count)
            checked = expected_frames + 1
            if idle[expected_frames] == 0x66:
                raise ValueError("Idle refusal has no failed input check")
        if frames != expected_frames or any(idle[checked:]):
            raise ValueError("Invalid chip-select count or unused input samples")
        good_checks = checked - int(count < 8 and not timed_out)
        if any(v != 0x66 for v in idle[:good_checks]):
            raise ValueError("A transfer followed a failed input check")
    raw_id = bytes(ident).hex()
    return {
        "status": labels[status], "preflight_mismatches": preflight,
        "transfers_completed": count, "transactions_started": frames,
        "mode_release_transactions_started": min(frames, 3),
        "id_bytes": raw_id, "polls": polls, "cleanup_mismatches": cleanup,
        "idle_inputs": [f"0x{v:02x}" for v in idle],
        "private_stack_guard_confirmed": True,
        "caller_sp": f"0x{caller_sp:08x}", "caller_return": f"0x{caller_return:08x}",
        "id_captured": status == 0,
        "matches_cached_id": status == 0 and raw_id == EXPECTED_ID,
    }
