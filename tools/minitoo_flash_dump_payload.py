#!/usr/bin/env python3
"""Pinned 4 KiB reader for the fixed two-pass, 2 MiB main-flash plan."""
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
COMPLETION = 0x4D544644
POLL_LIMIT = identify.POLL_LIMIT
READ_POLL_BUDGET = 2097152
DATA_ADDRESS = 0x122800
CAPTURE_BYTES = 4096
FLASH_BYTES = 2097152
CHUNKS_PER_PASS = FLASH_BYTES // CAPTURE_BYTES
TOTAL_CHUNKS = 2 * CHUNKS_PER_PASS
READ_TRANSFERS = CAPTURE_BYTES + 4
REQUEST_OFFSET = 0x7D0
sha256 = identify.sha256
CODE = bytes.fromhex(
    "64e0000ec1fff8071200906064e000039061c0ff00081200c1ff4b4154538160eeff0028"
    "1200c0ff0007120080ea4400c0ff000812000160c0fff00712008160c1fff80712001061"
    "64e08003106064e0800e8000e29f40208020002008ffff0f080088802000c0eb01000120"
    "23ff801df9ff02818000750444e1800cc3ff001cfd00b460b16220004121356055e8087a"
    "c12123ff0111f9ff40ea802b4120048aa16041f00001b46030ea808d316211173128b060"
    "101655047f04e29704164020c06041ea0140c062c063c06f49904220d8ec1b02c22182f8"
    "fb07489c41204220d8ec0b12c22182f8fb1100e140404220d8ec0b12c22182f8fb094020"
    "05e15040d060d063d061d062d064d065c1ff002812004220d8ee2101c22121ff802dfaff"
    "c0ffd0071200016008ffff13b1019bd9026141ff0023ac01c2ff28fc19002360c6ff0003"
    "008493e8000602ef01402361c6ff00366e0193e8000602ef02402262c3ff006cdc0292e8"
    "000302ef0440c2ff1460fd00266012acc3ff00f01f00064202ef084090e1228342210141"
    "4220caff001cfd00d0eca01022af91e8000202ef1040e1e066ac1260c3ff3400580192e8"
    "000302ef20401166014202ef4040e1e014ad1160014202ef804021e114a41260024202ef"
    "804f1261b2e8310002ef004f42f04316116291e8000202ef804ee7e05cadd0ec70c07662"
    "d0ec7c907364d0ec74b18cf8082086f806de89f804fe83f802300bf8020002ef004e016a"
    "61ff03100e00c2ffe0f7e7ff121803ff0128090042e000fca119e2e0d02902e8021002ef"
    "804d41f0bc4a006b90e8000102ef004d406201ff00001e01d4e91990d4e9018040e108c0"
    "802770f10860f06070f16f30f06240f16600832470f16fb0f064d4e915b070f16f60f065"
    "40f16600862340f02058f062d0eca10041eaffa040e02118d0eca100200008e10c40d4e9"
    "09c076e108c0c6d4862142e02110bee8010042e0211841e1802c40e02150bee803001016"
    "c0e1e2104b1cd0eca100bfeabbfe706160e16600d0ec31044fe02900bee803002f16d0ec"
    "300480f8d4cc8ef8070640e180fcd0eca1002000bfeaa4fef6602000bfeaa0fe09e101e0"
    "d0ec51904ae00200d0ec45a04024bee803004021bee801000a16c3144ce001004de00100"
    "bee80300c5143be80000bc1640e029101dea000cf016793f3be80000613fbee80300793f"
    "466362a24218c23cbfea85fe00f89b0090e1d21c01430017d8ec8b0b68810be101b0c063"
    "8ae9d6b10027f0602000c6ff001cfd006a169ed6062189f98c0941ea0040406480444065"
    "804240660049406490f808fe406590f805fe406690f802fe41ea0440406100f86e084064"
    "90f8a80a406580f8a5c0406680f8a22a40e02150a216a060bfea36fe7316306160e16600"
    "d064506480f897cc40e02940a0602000bfea28fe0021b0602000bfea23fe43ea015041ea"
    "0740c01449e01800cafffc271200c314412309f80730793fbbec03800020c8e102090117"
    "d4e9218048293be9040040e02910aa80bfea15fe012868e86441526211ec0002d1621045"
    "3be90400d8eeb10a0be101b0d0ec55b0506522ff00095c00c0e1b20839e1f89f03ff0104"
    "d1ff70d601278160200041ea0040048b41ea09402000c0ff4446544dc06002895f0441ea"
    "054075d60027d060200040e02040c1ff001cfd00906020000624d6640325d3650723d762"
    "0222d26040ea801c2000506090e800020fef01405062022690e800070fef0240506490e8"
    "00060fef0440506590e800030fef0840506390e800020fef10401060c1ffff3fffff10ea"
    "80010fef2040406f505d41ea0340d79a41ea0640e78041ea0840d79d41ea0a40d79a"
)
CODE_SHA256 = '540b48b994fca003c35c5422b32f10de1c4a262cd44ef53d6cb13510ef0a3218'
BLOCK_ZERO_SHA256 = 'e672aa1b6b31d93416fee911bface186df537203089aacf85284e23899ad97df'


def make_block(ordinal=0, code=None):
    code = CODE if code is None else code
    if (type(ordinal) is not int or not 0 <= ordinal < TOTAL_CHUNKS
            or code != CODE or not code or len(code) > RESULT_OFFSET
            or sha256(code) != CODE_SHA256 or ADDRESS + SIZE != STACK_BOTTOM
            or DATA_ADDRESS != STACK_TOP or DATA_ADDRESS + CAPTURE_BYTES > 0x125400):
        raise ValueError('Changed code, request or reviewed RAM bounds')
    block = bytearray(code + bytes(SIZE-len(code)))
    struct.pack_into('<2I',block,REQUEST_OFFSET,ordinal,ordinal ^ 0xFFFFFFFF)
    check = bytearray(block)
    struct.pack_into('<2I',check,REQUEST_OFFSET,0,0xFFFFFFFF)
    if sha256(check) != BLOCK_ZERO_SHA256:
        raise ValueError('Changed pinned block layout')
    return bytes(block)


def decode_result(data, ordinal):
    initial = make_block(ordinal)
    if len(data) != SIZE or data[:RESULT_OFFSET] != initial[:RESULT_OFFSET]:
        raise ValueError('Dump code/padding changed')
    words = list(struct.unpack_from('<64I',data,RESULT_OFFSET))
    completion,status,preflight,count = words[:4]
    if (completion != COMPLETION or status > 10 or words[60] != STACK_GUARD
            or any(words[26:52]+words[54:60]+[words[61]])
            or data[REQUEST_OFFSET:REQUEST_OFFSET+8] != initial[REQUEST_OFFSET:REQUEST_OFFSET+8]):
        raise ValueError('Invalid dump completion, request, guard or reserved fields')
    if status == 9:
        if any(words[2:26]) or words[62] % 4 or words[63] != 0x4ABC:
            raise ValueError('Inconsistent request refusal')
        return {'status':'request-refused','chunk_confirmed':False,
                'transactions_started':0,'read_transactions_started':0}
    stage = bytearray(identify.make_block())
    stage_words = [*words[:21],words[60],*([0]*24),*words[62:64]]
    stage_words[0] = identify.COMPLETION
    stage_words[1] = status if status <= 5 else 0
    struct.pack_into('<48I',stage,identify.RESULT_OFFSET,*stage_words)
    capture = identify.decode_result(bytes(stage))
    completed,maximum,frames,idle,total = words[21:26]
    if (completed > READ_TRANSFERS or maximum > POLL_LIMIT or frames > 1
            or idle & ~0x66 or total >= READ_POLL_BUDGET + POLL_LIMIT):
        raise ValueError('Invalid read counters')
    expected_id = capture['id_bytes'] == identify.EXPECTED_ID
    if status in (1,2,4,5,6) or (status == 3 and (count != 8 or not expected_id)):
        if any(words[21:26]) or (status == 6 and (expected_id or capture['id_bytes'] in ('000000','ffffff'))):
            raise ValueError('Data read followed a failed ID stage')
    else:
        if not expected_id or count != 8 or preflight:
            raise ValueError('Data read requires expected ID and valid preflight')
        if frames == 0:
            if completed or maximum or total or idle == 0x66 or status not in (3,8):
                raise ValueError('Invalid read idle refusal')
        else:
            if idle != 0x66 or not 1 <= maximum <= POLL_LIMIT or total < maximum:
                raise ValueError('Invalid started read')
            if status == 10 or (status == 3 and total >= READ_POLL_BUDGET and completed):
                if not completed or total < READ_POLL_BUDGET or total > completed * maximum:
                    raise ValueError('Invalid whole-read budget refusal')
            elif completed == READ_TRANSFERS:
                if status not in (0,3) or not completed <= total < READ_POLL_BUDGET or total > completed*maximum:
                    raise ValueError('Invalid completed read')
            elif status not in (3,7) or maximum != POLL_LIMIT or total < POLL_LIMIT or total > (completed+1)*maximum:
                raise ValueError('Invalid read timeout')
    labels = ('captured','preflight-refused','id-timeout','cleanup-failed','id-no-response',
              'id-idle-refused','unexpected-id','read-timeout','read-idle-refused','request-refused','read-budget')
    capture.update(status=labels[status],ordinal=ordinal,
                   flash_address=f'0x{(ordinal % CHUNKS_PER_PASS)*CAPTURE_BYTES:06x}',
                   read_transfers_completed=completed,read_max_polls=maximum,
                   read_transactions_started=frames,read_idle_inputs=f'0x{idle:02x}',
                   read_poll_total=total,chunk_confirmed=status == 0)
    return capture


def validate_data(data, metadata):
    if len(data) != CAPTURE_BYTES:
        raise ValueError('Wrong flash chunk size')
    completed = metadata.get('read_transfers_completed',0)
    if any(data[max(0,completed-4):]):
        raise ValueError('Read buffer changed beyond completed receives')
    return sha256(data)
