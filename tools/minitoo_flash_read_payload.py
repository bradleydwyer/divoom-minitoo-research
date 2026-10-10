#!/usr/bin/env python3
"""Pinned two-pass 64-byte raw-flash reader; no arbitrary payload/range inputs."""
import struct
import minitoo_flash_identify_payload as identify

ADDRESS = identify.ADDRESS
SIZE = identify.SIZE
CHUNK_BYTES = identify.CHUNK_BYTES
RESULT_OFFSET = 0x700
RESULT_BYTES = 256
STACK_BOTTOM = identify.STACK_BOTTOM
STACK_TOP = identify.STACK_TOP
STACK_GUARD = identify.STACK_GUARD
COMPLETION = 0x4D544652
POLL_LIMIT = identify.POLL_LIMIT
FLASH_ADDRESS = 0
CAPTURE_BYTES = 64
READ_TRANSFERS = 68
CODE = bytes.fromhex(
    "64e0000ec1fff8071200906064e000039061c0ff00081200c1ff4b4154538160eeff0028"
    "1200c0ff0007120080ea4400c0ff000812000160c0fff00712008160c1fff80712001061"
    "64e08003106064e0800e8000e29f40208020002008ffff0f080088802000c0eb01000120"
    "23ff801df9ff02818000750444e1800cc3ff001cfd00b460b16220004121356055e8087a"
    "c12123ff0111f9ff40ea802b4120048aa16041f00001b46030ea808d316211173128b060"
    "101655047f04e29808164020d0ec810041ea0180d0ec8900d0ec8d00d0ec8d0301e11080"
    "4220d8ec1b02c22182f8fb0700e11c8041204220d8ec0b12c22182f8fb1100e140804220"
    "d8ec0b12c22182f8fb09402009e15080d0ec9100d0ec950104e1708002e1548003e15c80"
    "05e168804620d8ec2b06d8ec3b06d8ec5b0657204116900707eafdffc621d42086f8f105"
    "c0ff28fc19000160c2ff0003008491e8000202ef01800161c2ff00366e0191e8000202ef"
    "02800062c1ff006cdc0290e8000102ef0480c0ff1460fd000060004202ef0880caff001c"
    "fd00d0eca000a0e8000c02ef1080e0e066ac0160c2ff3400580191e8000202ef20800066"
    "004202ef4080e0e014ad0060004202ef808020e114a40160014202ef808f0161b1e83100"
    "02ef008f41f04316006290e8000102ef808ee7e05cad73607662d0ec7cb07564746583f8"
    "072086f805de8bf803fe85f80130044202ef008ec0fff8071200016061ff03100e00c2ff"
    "e0f7e7ff121803ff0128090042e000fca119e2e0d02902e8021002ef808d41f0bc4a0061"
    "90e8000102ef008dd0ec880001ff00007901d4e915b040e10830802670f10860f06070f1"
    "6f50f06240f16600852370f16f40f064842470f16f60f06540f16600862240f02058f062"
    "d0eca10041eaffa040e02118d0eca100200005f10c80832176e10830c614d4e9019042e0"
    "2110bee8010042e0211841e1802c40e02150bee803001016c0e1e210b4e08031d0eca100"
    "bfeac0fe706160e16600d0ec31044de02900bee803002d16d0ec300480f8e9cc8ef80706"
    "40e180dcd0eca1002000bfeaa9fef6602000bfeaa5fe04e101e0d0ec914049e00200d0ec"
    "85904024bee803004021bee801000916c2144be001004ce00100bee80300c4143ae80000"
    "ab1640e029101cea000bd016793f3ae80000613fbee80300793fd0ec8cf0c0e1f2208218"
    "c23cbfea88fe00f8ae0090e1c21b01430017d8ec5b0a00e101f00ae101a0d0ec8d0089e9"
    "d2a10026f06020004e166b16c6ff001cfd006a16b616d4e9009084f9840941ea0080d0ec"
    "80018046d0ec84018043d0ec8801004cd0ec800190f80afed0ec840190f806fed0ec8801"
    "90f802fe41ea0480d0ec840000f87508d0ec800190f8b80ad0ec840180f8b4c0d0ec8801"
    "80f8b02a0de16c8044204ee0215047e02940e6e05cadc3ff001cfd00d0ec31e040a2b4e0"
    "8020bfea1dfe606160e16600d0ec2906d0ec2806052080f896ccb7602000bfea0ffeb016"
    "e0602000bfea0afec421d46541ea078009e154204520da16482935e9040040e029104220"
    "822735e904007a3f4123054121168a9cbfea03fe0127d0ec982011ec0002d0ec99101043"
    "35e9040052eea000c521d0ec91500ae101a085f9dd890026e06020000de140d084f9b105"
    "4020d0ec8500b4e0801050ee102750ee101b81e85320c02180fcf57f048241ea0580c6ff"
    "0053fd000026e060200040e02040c1ff001cfd00906020000423e4640324e3650522e562"
    "0221e26040ea801c2000606090e800020fef01806062022590e800050fef0280606490e8"
    "00040fef0480606590e800030fef0880606390e800020fef10801060c1ffff3fffff10ea"
    "80010fef2080d0ec8c03004241ea03802000c0ff5246544dd0ec810002885f0441ea0680"
    "d79641ea0880d79341ea0980d790"
)
CODE_SHA256 = "f9c9d86b002ecd6aec11815ef2426a86fefac4974c53008f59822fd75d3359cb"
BLOCK_SHA256 = "a041be5d933b0533a829fe26428ce951e164886d0856024c925cbebadef1e121"
sha256 = identify.sha256


def make_block(code=None):
    code = CODE if code is None else code
    if (code != CODE or not code or len(code) > RESULT_OFFSET
            or sha256(code) != CODE_SHA256
            or RESULT_OFFSET + RESULT_BYTES != SIZE
            or ADDRESS + SIZE != STACK_BOTTOM or STACK_TOP > 0x125400):
        raise ValueError('Fixed small-read code or RAM bounds changed')
    block = code + bytes(SIZE-len(code))
    if sha256(block) != BLOCK_SHA256:
        raise ValueError('Fixed small-read block hash changed')
    return block


def decode_result(data):
    initial = make_block()
    if len(data) != SIZE or data[:RESULT_OFFSET] != initial[:RESULT_OFFSET]:
        raise ValueError('Small-read code/padding changed outside result')
    words = struct.unpack_from('<64I',data,RESULT_OFFSET)
    completion,status,preflight,count = words[:4]
    if completion != COMPLETION or status > 9 or words[60] != STACK_GUARD or words[61]:
        raise ValueError('Invalid small-read completion, status, guard or reserved word')
    # Reuse the existing strict ID-stage field validator, with its own pinned
    # block layout. Actual new-code bytes and the new guard were checked above.
    stage = bytearray(identify.make_block())
    stage_words = [*words[:21], words[60], *([0]*24), *words[62:64]]
    stage_words[0] = identify.COMPLETION
    stage_words[1] = status if status <= 5 else 0
    struct.pack_into('<48I',stage,identify.RESULT_OFFSET,*stage_words)
    capture = identify.decode_result(bytes(stage))
    counts, maxima, frames, idle = list(words[21:23]), list(words[23:25]), words[25], list(words[26:28])
    copies = (data[RESULT_OFFSET+112:RESULT_OFFSET+176],data[RESULT_OFFSET+176:RESULT_OFFSET+240])
    if (any(v > READ_TRANSFERS for v in counts) or any(v > POLL_LIMIT for v in maxima)
            or frames > 2 or any(v & ~0x66 for v in idle)):
        raise ValueError('Invalid small-read counts or idle samples')
    for n in range(2):
        received = max(0,counts[n]-4)
        if any(copies[n][received:]):
            raise ValueError('Read bytes present before their receive completed')
    no_read = not any(counts+maxima+idle) and frames == 0 and not any(copies[0]+copies[1])
    expected_id = capture['id_bytes'] == identify.EXPECTED_ID
    if status in (1,2,4,5,6) or (status == 3 and (count != 8 or not expected_id)):
        if not no_read or (status == 6 and (expected_id or capture['id_bytes'] in ('000000','ffffff'))):
            raise ValueError('A data read followed an unsuccessful ID stage')
    else:
        if not expected_id or count != 8 or preflight:
            raise ValueError('Small read requires complete expected ID')
        complete = True
        for n in range(2):
            if counts[n] == READ_TRANSFERS:
                if frames < n+1 or idle[n] != 0x66 or not 1 <= maxima[n] <= POLL_LIMIT:
                    raise ValueError('Invalid completed small read')
                continue
            complete = False
            if any(counts[n+1:]+maxima[n+1:]+idle[n+1:]) or any(b for c in copies[n+1:] for b in c):
                raise ValueError('Read continued after failure')
            if maxima[n]:
                if (frames != n+1 or idle[n] != 0x66 or maxima[n] != POLL_LIMIT
                        or status not in (3,7)):
                    raise ValueError('Inconsistent small-read timeout')
            elif counts[n] or frames != n or idle[n] == 0x66 or status not in (3,8):
                raise ValueError('Inconsistent small-read idle refusal')
            break
        if complete:
            if status not in (0,3,9) or (status != 3 and (copies[0] != copies[1]) != (status == 9)):
                raise ValueError('Inconsistent small-read comparison')
    labels = ('captured','preflight-refused','id-transfer-timeout','cleanup-failed',
              'id-no-response','id-idle-refused','unexpected-id','read-timeout',
              'read-idle-refused','read-mismatch')
    capture['status'] = labels[status]
    capture.update(read_transactions_started=frames,read_transfers_completed=counts,
                   read_max_polls=maxima,read_idle_inputs=[f'0x{v:02x}' for v in idle],
                   read_pass_sha256=[sha256(c) for c in copies],
                   read_copies_match=counts == [READ_TRANSFERS]*2 and copies[0] == copies[1],
                   read_is_all_zero_or_ff=copies[0] in (bytes(64),bytes([255])*64),
                   small_read_confirmed=status == 0 and expected_id)
    return capture,copies
