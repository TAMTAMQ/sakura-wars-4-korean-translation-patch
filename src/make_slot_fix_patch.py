"""v0.5 실행 파일의 지연 슬롯 문제를 고치는 1ST_READ.BIN 패치를 만든다.

v0.5는 원본 코드 사이의 NOP 빈칸에 함수 두 개를 넣었는데, 두 빈칸 모두 바로 앞 명령이
`bra`라서 빈칸의 첫 NOP이 그 분기의 지연 슬롯이었다. 새 함수의 첫 명령
`mov.l @(disp,PC),r1`이 지연 슬롯에서 같이 실행되어(PC 상대 로드 + r1 덮어쓰기) 에뮬레이터에서는
돌지만 실기에서는 멈춘다(릴리스 「실기 실행을 위한 수정본 v2」가 이 패치들을 롤백했던 이유).
  0x9275E bra → 슬롯 0x92760 = 새 함수 A(32바이트, 함수 포인터 0x13B888이 가리킴)
  0x9363E bra → 슬롯 0x93640 = 새 함수 B(32바이트, 0x943C0의 bra가 가리킴)

수정: 두 함수를 빈 0 영역(낫표 훅 뒤 0xAE300, 0xAE320)으로 그대로 옮긴다(주소 mod 4가 같아
PC 상대 리터럴이 그대로 맞는다). 원래 빈칸은 원본 NOP으로 되돌린다. A는 포인터만 고친다.
B는 0x943C0의 bra가 멀리 닿지 않으므로, 슬롯이 아닌 0x93642에 점프대를 두고 bra를 거기로 돌린다
(B는 진입하자마자 r0을 덮어쓰므로 점프대가 r0을 써도 된다).

출력: config/code-patches-slotfix.json (build.py가 원본 byte를 확인하고 적용한다)
"""
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = 0x8C010000
A_OLD, B_OLD, SIZE = 0x92760, 0x93640, 0x20
A_NEW, B_NEW = 0xAE300, 0xAE320
A_PTR = 0x13B888
B_BRA = 0x943C0
TRAMP = 0x93642


def w16(*ops):
    return b''.join(struct.pack('<H', x) for x in ops)


def patch(exe, off, new, note):
    return {'file': '1ST_READ.BIN', 'offset': off, 'original_hex': exe[off:off + len(new)].hex(),
            'new_hex': bytes(new).hex(), 'kind': 'machine-code', 'isa': 'SH-4 little-endian', 'note': note}


def build():
    exe = (ROOT / 'originals/v05/1ST_READ.BIN').read_bytes()
    org = (ROOT / 'originals/disc/1ST_READ.BIN').read_bytes()  # 원본 디스크와 같은 파일
    assert A_OLD % 4 == A_NEW % 4 and B_OLD % 4 == B_NEW % 4
    assert set(exe[A_NEW:B_NEW + SIZE]) == {0}
    assert struct.unpack_from('<I', exe, A_PTR)[0] == BASE + A_OLD
    assert exe[B_BRA:B_BRA + 2] == w16(0xA93E)  # bra 0x93640
    nop = w16(*[0x0009] * (SIZE // 2))
    assert org[A_OLD:A_OLD + SIZE] == nop and org[B_OLD:B_OLD + SIZE] == nop

    tramp = nop[:2] + w16(0xD001, 0x402B, 0x0009) + struct.pack('<I', BASE + B_NEW)  # 0x93640: nop(슬롯)
    assert (TRAMP + 2) % 4 == 0 and len(tramp) <= SIZE  # mov.l @(1,PC) → (0x93644&~3)+4+4 = 0x93648
    tramp += nop[len(tramp):]
    disp = (TRAMP - (B_BRA + 4)) // 2 & 0xFFF
    patches = [
        patch(exe, A_NEW, exe[A_OLD:A_OLD + SIZE] + exe[B_OLD:B_OLD + SIZE], 'v0.5 함수 A·B를 지연 슬롯 밖으로 이동'),
        patch(exe, A_OLD, nop, '함수 A 자리 원본 NOP 복원(0x9275E bra의 지연 슬롯)'),
        patch(exe, B_OLD, tramp, '함수 B 자리: 슬롯 NOP 복원 + 0x93642 점프대'),
        patch(exe, A_PTR, struct.pack('<I', BASE + A_NEW), '함수 A 포인터 → 0xAE300'),
        patch(exe, B_BRA, w16(0xA000 | disp), 'bra → 0x93642 점프대'),
    ]
    out = ROOT / 'config/code-patches-slotfix.json'
    out.write_text(json.dumps({'patches': patches}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print('지연 슬롯 수정 패치', len(patches), '개 →', out)


if __name__ == '__main__':
    build()
