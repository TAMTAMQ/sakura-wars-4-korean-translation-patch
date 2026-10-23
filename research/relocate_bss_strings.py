"""v0.5가 1ST_READ.BIN 끝(원본 파일 끝 = BSS 시작 0x8C231064) 뒤에 덧붙여 옮긴 문자열을
원래 자리로 되돌린다.

원본 파일 끝 뒤는 실행 시 BSS(0으로 지워지는 전역 변수 영역)다. 실제로 원본 코드가
0x8C231064를 전역 변수로 쓴다. 그 자리로 옮긴 문자열은 게임에서 빈칸으로 나왔다
(옵션 진동팩 「비활성」 등). 이 스크립트는
- 문안 위치(text-bindings·segments)를 원본 문자열 자리·길이로 옮기고
- config/code-patches-bss-relocate.json에 포인터 복원과 덧붙은 영역 0 채우기를 쓴다.
한 번만 실행한다(이미 옮긴 행은 건너뛴다).
"""
import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = 0x8C010000
FILE = '1ST_READ.BIN'


def main():
    orig = (ROOT / 'originals/disc' / FILE).read_bytes()
    v05 = (ROOT / 'originals/v05' / FILE).read_bytes()
    end = len(orig)
    codes = json.loads((ROOT / 'config/encoding.json').read_text(encoding='utf-8'))
    rev = {bytes.fromhex(v): k for k, v in codes.items()}

    def decode(b):
        out, i = '', 0
        while i < len(b):
            if b[i] == 0:
                break
            if b[i] >= 0xF0:
                c = bytes([b[i] & ~8, b[i + 1]])
                out += rev.get(c, '?') + (' ' if b[i] & 8 else '')
                i += 2
            elif 0x81 <= b[i] <= 0x9F or b[i] >= 0xE0:
                out += b[i:i + 2].decode('cp932', 'replace')
                i += 2
            else:
                out += chr(b[i])
                i += 1
        return out

    bindings_path = ROOT / 'config/text-bindings.json'
    bindings = json.loads(bindings_path.read_text(encoding='utf-8'))
    seg_path = ROOT / 'assets/translation/segments' / (FILE + '.jsonl')
    seg = [json.loads(line) for line in seg_path.read_text(encoding='utf-8').splitlines() if line]
    patches, moved = [], []
    for row in seg:
        if row['offset'] < end:
            continue
        old = row['offset']
        ptrs = [i for i in range(0, end - 3, 4) if v05[i:i + 4] == struct.pack('<I', BASE + old)]
        ptrs = [i for i in ptrs if struct.unpack_from('<I', orig, i)[0] != BASE + old]
        targets = {struct.unpack_from('<I', orig, i)[0] - BASE for i in ptrs}
        assert len(targets) == 1, (row['id'], targets)
        slot = targets.pop()
        length = orig.index(b'\0', slot) - slot
        for i in ptrs:
            patches.append({'file': FILE, 'offset': i, 'original_hex': v05[i:i + 4].hex(),
                            'new_hex': orig[i:i + 4].hex(), 'kind': 'pointer',
                            'note': f"BSS로 옮겨진 {row['id']} 포인터를 원본 문자열 자리로 복원"})
        raw = v05[slot:slot + length]
        row.update(offset=slot, capacity=length, raw_hex=raw.hex(), baseline_text=decode(raw))
        bindings[row['id']].update({k: row[k] for k in ['offset', 'capacity', 'raw_hex', 'baseline_text']})
        moved.append({'id': row['id'], 'from': old, 'to': slot, 'capacity': length})
    if not moved:
        print('이미 옮김')
        return
    patches.append({'file': FILE, 'offset': end, 'original_hex': v05[end:].hex(),
                    'new_hex': '00' * (len(v05) - end), 'kind': 'data',
                    'note': 'v0.5가 원본 파일 끝(BSS 시작) 뒤에 덧붙인 문자열 영역을 0으로 비움'})
    seg_path.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in seg), encoding='utf-8')
    bindings_path.write_text(json.dumps(bindings, ensure_ascii=False), encoding='utf-8')
    index_path = ROOT / 'assets/translation/index.json'
    index = json.loads(index_path.read_text(encoding='utf-8'))
    for item in index['segments']:
        item['sha256'] = hashlib.sha256((ROOT / item['path']).read_bytes()).hexdigest()
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (ROOT / 'config/code-patches-bss-relocate.json').write_text(
        json.dumps({'patches': patches}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps(moved, ensure_ascii=False))
    print('포인터', len(patches) - 1, '곳, 0 채우기', len(v05) - end, '바이트')


if __name__ == '__main__':
    main()
