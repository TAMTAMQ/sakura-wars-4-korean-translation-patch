"""마작 미니게임(MINIGAME/MGJT.BIN)의 인물 이름·「リーチ」 문자열을 한국어로 바꾸는 패치를 만든다.

배경: 승자·패자 표시와 점수표에 쓰는 짧은 문자열(さくら·大神·リーチ 등)은 대사 추출에서 빠져
일본어로 남았다. 문자열 칸은 원문 길이에 꼭 맞아(さくら 7바이트, 織姫 5바이트 …) 「오리히메」
「카야마」 같은 이름은 제자리에 들어가지 않는다. 이름은 모두 포인터로만 참조되므로
(MGJT.BIN은 0x8C6386C0에 올라간다), 이름 문자열 영역을 다시 채우고 포인터를 새 위치로 고친다.

  - 이름 표 1(0x36AB0, 붙여 쓴 이름)·표 2(0x36B18, 두 글자 이름은 전각 공백으로 띄움)
  - 대전 상대 기록(0x3AC00부터 0x54바이트 간격)의 이름 포인터
  - 대사 바인딩이 관리하는 칸(아이리스·글리신·코쿠리코·로벨리아·그란 마)은 건드리지 않는다
  - 「リーチ」 두 곳(0x3D75B, 0x40BFB)은 제자리에 「리치」

출력: config/code-patches-mgjt-names.json (build.py가 원본 byte를 확인하고 적용한다)
"""
import json
import struct
from pathlib import Path

from build import encode, readjson

ROOT = Path(__file__).resolve().parents[1]
REL = 'MINIGAME/MGJT.BIN'
BASE = 0x8C6386C0
# 다시 채울 문자열 영역(시작, 끝). 바인딩 칸 사이의 빈틈만 쓴다.
CHUNKS = [(0x36BB3, 0x36BCF), (0x36BD8, 0x36BEE), (0x36C0B, 0x36C4B), (0x36C56, 0x36CA3),
          (0x3DB59, 0x3DB75), (0x3DB7E, 0x3DB94), (0x3DBB1, 0x3DBCA)]
# 원문 문자열 → 한국어. 키는 v0.5 기준선에 있는 원문(또는 v0.5가 잘못 바꾼 「만분」).
PLAIN = {'さくら': '사쿠라', 'すみれ': '스미레', 'マリア': '마리아', 'カンナ': '칸나', '紅蘭': '홍란',
         '織姫': '오리히메', 'レニ': '레니', 'エリカ': '에리카', '花火': '하나비', 'メル': '멜', 'シー': '시',
         '加山': '카야마', '米田': '요네다', 'かえで': '카에데', 'かすみ': '카스미', '由里': '유리',
         '椿': '츠바키', '琴音': '코토네', '斧彦': '요키히코', '菊之丞': '키쿠노조', '大神': '오오가미'}
# 표 2의 띄어 쓴 이름: 두 글자 한국어 이름은 원문처럼 가운데에 전각 공백을 둔다
SPACED = {'紅　蘭': '홍　란', '織　姫': '오리히메', 'レ　ニ': '레　니', '花　火': '하나비',
          'メ　ル': '멜', 'シ　ー': '시', '加　山': '카야마', '米　田': '요네다',
          '由　里': '유　리', '琴　音': '코토네', '斧　彦': '요키히코'}
REACH = [0x3D75B, 0x40BFB]


def cstr(data, off):
    return data[off:data.index(0, off)]


def main():
    codes = readjson(ROOT / 'config/encoding.json')
    rev = {bytes.fromhex(v): k for k, v in codes.items()}
    data = (ROOT / 'originals/v05' / REL).read_bytes()

    def text(off):
        raw, out, i = cstr(data, off), '', 0
        while i < len(raw):
            c = raw[i]
            if 0x81 <= c <= 0x9F or c >= 0xE0:
                g = raw[i:i + 2]
                out += rev.get(g) or g.decode('cp932')
                i += 2
            else:
                out += chr(c)
                i += 1
        return out

    fixes = {'만분': '하나비', '만　분': '하나비'}  # v0.5가 花火를 잘못 바꿔 둔 것
    table = {**PLAIN, **SPACED, **fixes}
    inside = lambda a: any(s <= a < e for s, e in CHUNKS)
    words = len(data) // 4
    ptrs = []
    for i, v in enumerate(struct.unpack_from('<%dI' % words, data)):
        a = v - BASE
        if 0 <= a < len(data) and inside(a):
            src = text(a)
            if src not in table:
                raise SystemExit(f'번역 없는 이름 {hex(a)} {src!r}')
            ptrs.append((i * 4, a, table[src]))
    # 같은 문자열은 한 번만 두고, 긴 것부터 빈 영역에 채운다
    need = sorted({t for _, _, t in ptrs}, key=lambda t: -len(encode(t, codes)))
    free = [[s, e] for s, e in CHUNKS]
    place = {}
    for t in need:
        b = encode(t, codes) + b'\0'
        slot = next((f for f in free if f[1] - f[0] >= len(b)), None)
        if slot is None:
            raise SystemExit('자리 부족: ' + t)
        place[t] = (slot[0], b)
        slot[0] += len(b)
    patched = bytearray(data)
    for s, e in CHUNKS:
        patched[s:e] = bytes(e - s)
    for t, (a, b) in place.items():
        patched[a:a + len(b)] = b
    for off, _, t in ptrs:
        struct.pack_into('<I', patched, off, BASE + place[t][0])
    for a in REACH:
        if text(a) != 'リーチ':
            raise SystemExit('リーチ 위치 불일치')
        n = len(cstr(data, a))
        b = encode('리치', codes)
        patched[a:a + n] = b + bytes(n - len(b))
    patches, i = [], 0
    while i < len(data):  # 바뀐 연속 구간마다 패치 하나
        if patched[i] == data[i]:
            i += 1
            continue
        j = i
        while j < len(data) and patched[j] != data[j]:
            j += 1
        patches.append({'file': REL, 'offset': i, 'original_hex': data[i:j].hex(),
                        'new_hex': bytes(patched[i:j]).hex(), 'note': 'MGJT 이름·리치 (make_mgjt_names_patch.py)'})
        i = j
    out = ROOT / 'config/code-patches-mgjt-names.json'
    out.write_text(json.dumps({'patches': patches}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print('포인터', len(ptrs), '문자열', len(place), '패치', len(patches))


if __name__ == '__main__':
    main()
