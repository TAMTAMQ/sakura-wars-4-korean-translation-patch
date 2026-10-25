"""재제작했지만 이미지 검수표(assets/images/review/image_review.json)에 없는 텍스처를 행으로 추가한다.

검수표는 v0.5가 바꾼 이미지에서 출발해서, v0.5가 손대지 않은 원본 이미지(명대사·컷인 이름판 등)를
새로 번역하면 빠져 있었다. 이런 행은 v0.5 칸 없이 원본과 재제작본만 보인다(patched = null).
이미 있는 행은 건드리지 않는다. 다시 실행해도 같은 행을 두 번 넣지 않는다.
"""
import json
from pathlib import Path

from PIL import Image

from remake_ui import disc_texture

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / 'assets/images/review/image_review.json'
STAGES = {  # 단계 → 행 메모 머리말
    'slg': 'SLG 이름판', 'staffroll': '스태프롤', 'ui': 'UI', 'logo': '로고',
    'cutin': '합체 공격 컷인 이름판', 'quotes': '명대사 이미지', 'nc': '시 구절·스태프 크레딧',
    'combo': '합체 공격 기술 이름판', 'kumi': '부대 이름판',
}


def ui_notes():
    cfg = json.loads((ROOT / 'assets/images/remake/ui.json').read_text(encoding='utf-8'))
    out = {}
    for it in cfg['items']:
        texts = [op['text'] for op in it['ops'] if op['op'] == 'text' and op.get('text')]
        out[(it['source'], it['block'], it['texture'])] = (it.get('note', ''), texts)
    return out


def text_of(row):
    t = row.get('text')
    if isinstance(t, dict):
        return ' / '.join(v for v in t.values() if v)
    return t or ''


def main():
    rows = json.loads(REVIEW.read_text(encoding='utf-8'))
    have = {(r['source'], r['block'], r['texture']) for r in rows}
    for r in rows:
        for m in r['members']:
            src, b, t = m.rsplit(' ', 2)
            have.add((src, int(b[1:]), int(t[1:])))
    notes = ui_notes()
    next_id = max(r['id'] for r in rows) + 1
    added = 0
    for stage, label in STAGES.items():
        idx = ROOT / 'assets/images/remake' / stage / 'index.json'
        if not idx.exists():
            continue
        for item in json.loads(idx.read_text(encoding='utf-8')):
            key = (item['source'], item['block'], item['texture'])
            if key in have:
                continue
            original = disc_texture(*key)['original_png']
            size = list(Image.open(ROOT / original).size)
            if stage == 'ui':
                note, texts = notes.get(key, ('', []))
                desc = f'{label} · {note}' if note else label
                text = ' / '.join(dict.fromkeys(texts))
            else:
                desc, text = label, text_of(item).replace('/', ' / ')
            rows.append({'id': next_id, 'verdict': '재제작 완료', 'category': '미번역',
                         'note': f'v0.5가 손대지 않은 원본 이미지. {desc}. 한국어: {text}',
                         'source': key[0], 'block': key[1], 'texture': key[2], 'size': size,
                         'copies': 1, 'members': [f'{key[0]} b{key[1]} t{key[2]}'],
                         'original': original, 'patched': None})
            have.add(key)
            next_id += 1
            added += 1
    REVIEW.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print('검수표 행 추가', added, '전체', len(rows))


if __name__ == '__main__':
    main()
