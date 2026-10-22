"""표가 가리킨 프레임 꼬리 f 뒤의 실제 승리 자막 6건을 편집 입력에 복원한다."""
import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HITS = {'LIPSYNC1.LIP': [(823, 0x20dd1), (1475, 0x2d13a)],
        'LIPSYNC2.LIP': [(2418, 0x51f21)],
        'LIPSYNC3.LIP': [(1044, 0x2d57d), (2133, 0x49ac4)],
        'LIPSYNC4.LIP': [(1710, 0x3818e)]}

def main():
    index_path = ROOT / 'assets/translation/index.json'
    index = json.loads(index_path.read_text(encoding='utf-8'))
    if index.get('schema'):
        raise SystemExit('이관 이전 일회성 경계 복원 도구입니다. 공유 문안과 사용처 등록을 함께 갱신하는 별도 이관이 필요합니다.')
    binding_path = ROOT / 'config/text-bindings.json'
    bindings = json.loads(binding_path.read_text(encoding='utf-8'))
    evidence = []
    for filename, entries in HITS.items():
        rel = 'ADVDATA/' + filename
        data = (ROOT / 'originals/v05' / rel).read_bytes()
        path = ROOT / 'assets/translation/segments' / (rel + '.jsonl')
        rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
        ids = {r['id'] for r in rows}
        for table_row, offset in entries:
            key = f'{rel}#{table_row:04d}'
            raw = '決め∈'.encode('cp932')
            assert data[offset:offset + len(raw) + 1] == raw + b'\0'
            off_b = struct.unpack_from('<I', data, 12 + table_row * 12 + 8)[0] - 1
            assert off_b == offset - 2 and data[off_b:offset] == b'f\0'
            assert not any(r['offset'] <= offset < r['offset'] + r['capacity'] + 1 for r in rows if r['id'] != key)
            existing = next((r for r in rows if r['id'] == key), None)
            if existing and existing['offset'] != offset:
                assert existing['offset'] == off_b and existing['raw_hex'] == '66' and existing['text'] == 'f'
                rows.remove(existing)
            if not existing or existing['offset'] != offset:
                row = {'id': key, 'file': rel, 'offset': offset, 'capacity': len(raw),
                       'raw_hex': raw.hex(), 'text': '결정∈', 'baseline_text': '決め∈',
                       'kind': 'fixed', 'review': '교차 검토 필요', 'source': '決め∈'}
                rows.append(row)
                bindings[key] = {k: v for k, v in row.items() if k not in ['text', 'review', 'source']}
            evidence.append({'id': key, 'offset': offset, 'table_off_b': off_b,
                             'original_hex': raw.hex(), 'text': '결정∈',
                             'reason': '기존 추출기가 off_b의 프레임 꼬리 f를 대사로 오인하고 NUL 뒤 실제 자막을 누락함'})
        rows.sort(key=lambda r: r['id'])
        path.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        for seg in index['segments']:
            if seg['path'] == path.relative_to(ROOT).as_posix():
                seg.update(rows=len(rows), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    binding_path.write_text(json.dumps(bindings, ensure_ascii=False), encoding='utf-8')
    (ROOT / 'research/victory-lipsync-recovery.json').write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('승리 자막 복원:', len(evidence), '개')

if __name__ == '__main__': main()
