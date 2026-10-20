"""낫표 「」『』의 글자 간격(advance)을 줄이는 1ST_READ.BIN 패치를 만든다.

배경: v0.5는 문자 출력 함수 포인터(0x13d854)를 자기 훅(0x8C0BE044)으로 바꿔
F0~F7 한글 코드를 원래 한자 칸 코드로 되돌려 찍은 뒤, 그 글자 칸 기록(14바이트)의
+8(advance)을 「크기 − 1~4」로 줄여 한글을 촘촘하게 찍는다. 낫표는 이 훅을 거치지
않아 전각 advance 그대로라 한글 사이에서 앞뒤가 벌어져 보인다.

패치:
  1) 0xAE1A0(빈 0 영역, v0.5 훅 바로 뒤)에 새 진입점. 코드가 0x8175~0x8178(「」『』)이
     아니면 v0.5 훅(0x8C0BE044)으로 그대로 넘긴다.
  2) 낫표면 v0.5 훅 본문(0xAE052~0xAE18B)의 사본을 실행한다. 사본은 원래와 같은
     주소 mod 4에 두어 PC 상대 리터럴이 그대로 맞는다. 바꾼 곳은 두 군데:
     - 코드 변환(extu.b r5 / or r0,r5)을 nop으로: 원래 SJIS 코드로 찍는다.
     - advance 계산: 여는 낫표(홀수 코드) = 크기 − 2, 닫는 낫표(짝수) = 크기×3/8.
       (tighten_brackets.py로 획을 칸 끝으로 옮긴 글리프 기준)
  3) 0x13D854의 출력 함수 포인터를 새 진입점으로.

출력: config/code-patches.json (build.py가 원본 byte를 확인하고 적용한다)
"""
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = 0x8C010000
ENTRY = 0xAE1A0
HOOK_SRC = (0xAE052, 0xAE18C)


def w16(*ops):
    return b''.join(struct.pack('<H', x) for x in ops)


def build():
    exe = (ROOT / 'originals/v05/1ST_READ.BIN').read_bytes()
    prefix = w16(
        0x6053,  # mov   r5,r0
        0x4028,  # shll16 r0
        0xD104,  # mov.l @(L1),r1      ; 0x81750000
        0x3018,  # sub   r1,r0
        0x4029,  # shlr16 r0
        0x4009,  # shlr2 r0            ; r0 = (code-0x8175)>>2
        0x2008,  # tst   r0,r0
        0x8907,  # bt    bracket       ; 0x8175~0x8178
        0xD002,  # mov.l @(L2),r0      ; v0.5 훅
        0x402B,  # jmp   @r0
        0x0009,  # nop
        0x0009,  # nop
    ) + struct.pack('<II', 0x81750000, 0x8C0BE044) + w16(0x0009)  # bracket: nop(정렬)
    assert len(prefix) == 0x22 and (ENTRY + 0x22) % 4 == HOOK_SRC[0] % 4
    body = bytearray(exe[HOOK_SRC[0]:HOOK_SRC[1]])
    at = lambda a: a - HOOK_SRC[0]
    assert body[at(0xAE0DC):at(0xAE0E0)] == bytes.fromhex('5c650b25')
    body[at(0xAE0DC):at(0xAE0E0)] = w16(0x0009, 0x0009)
    assert body[at(0xAE12C):at(0xAE152)].hex() == '16e112300e8912e1123008890ee1123002' '89ff7007a00900fe7004a00900fd7001a00900fc70'
    body[at(0xAE12C):at(0xAE152)] = w16(
        0x6203,  # mov   r0,r2    ; r2 = 칸 크기
        0x6093,  # mov   r9,r0    ; 코드
        0xC801,  # tst   #1,r0
        0x8903,  # bt    close    ; 짝수 = 닫는 낫표
        0x6023,  # mov   r2,r0
        0x70FE,  # add   #-2,r0   ; 여는 낫표: 크기-2
        0xA005,  # bra   end
        0x0009,
        0x6023,  # close: mov r2,r0
        0x4009,  # shlr2 r0
        0x6103,  # mov   r0,r1
        0x4101,  # shlr  r1
        0x301C,  # add   r1,r0    ; 크기×3/8
        *([0x0009] * 6))
    code = prefix + bytes(body)
    patches = [
        {'file': '1ST_READ.BIN', 'offset': ENTRY, 'original_hex': exe[ENTRY:ENTRY + len(code)].hex(),
         'new_hex': code.hex(), 'kind': 'machine-code', 'isa': 'SH-4 little-endian',
         'note': '낫표 advance 훅(make_bracket_patch.py 주석 참고)'},
        {'file': '1ST_READ.BIN', 'offset': 0x13D854, 'original_hex': exe[0x13D854:0x13D858].hex(),
         'new_hex': struct.pack('<I', BASE + ENTRY).hex(), 'kind': 'pointer',
         'note': '문자 출력 함수 포인터 → 낫표 훅'},
    ]
    assert set(exe[ENTRY:ENTRY + len(code)]) == {0}
    out = ROOT / 'config/code-patches.json'
    out.write_text(json.dumps({'patches': patches}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print('코드 패치', len(code), '바이트 →', out)


if __name__ == '__main__':
    build()
