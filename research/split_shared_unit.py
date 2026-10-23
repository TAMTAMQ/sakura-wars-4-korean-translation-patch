"""원문이 다른데 번역이 같아 하나의 공유 문안으로 묶인 사용처를 별도 문안으로 떼어 낸다.

usage: python research/split_shared_unit.py <사용처 ID> [...]
떼어 낸 문안은 원래 문안의 번역·검수 상태를 그대로 물려받는다.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]


def write_jsonl(path, rows):
    path.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')


def main(ids):
    index_path = ROOT / 'assets/translation/index.json'
    index = json.loads(index_path.read_text(encoding='utf-8'))
    for oid in ids:
        rel = oid.split('#')[0]
        seg_path = ROOT / 'assets/translation/segments' / (rel + '.jsonl')
        seg = jsonl(seg_path)
        row = next(r for r in seg if r['id'] == oid)
        unit_files = list((ROOT / 'assets/translation/units').rglob('*.jsonl'))
        for up in unit_files:
            units = jsonl(up)
            owner = next((u for u in units if u['id'] == row['unit']), None)
            if owner:
                break
        if len(owner['occurrences']) < 2:
            raise SystemExit('이미 단독 문안: ' + oid)
        if any(o.get('form') for o in owner['occurrences'] if o['id'] == oid) or 'text' not in owner:
            raise SystemExit('변형·조합 문안은 지원하지 않음: ' + oid)
        uid = 'dialogue:' + hashlib.sha256((oid + row['source']).encode()).hexdigest()[:16]
        new = {'id': uid, 'source': row['source'], 'text': owner['text'], 'review': owner.get('review', '교차 검토 필요'),
               'occurrences': [{'id': oid}]}
        owner['occurrences'] = [o for o in owner['occurrences'] if o['id'] != oid]
        units.insert(units.index(owner) + 1, new)
        write_jsonl(up, units)
        row['unit'] = uid
        write_jsonl(seg_path, seg)
        print(oid, '→', uid)

    def rehash(o):
        if isinstance(o, dict):
            if 'path' in o and 'sha256' in o and (ROOT / o['path']).exists():
                o['sha256'] = hashlib.sha256((ROOT / o['path']).read_bytes()).hexdigest()
            for v in o.values():
                rehash(v)
        elif isinstance(o, list):
            for v in o:
                rehash(v)
    rehash(index)
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main(sys.argv[1:])
