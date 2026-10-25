"""이미지 검수표(assets/images/review/image_review.json)를 비교 시트 HTML로 만든다.

원본 · v0.5 · (있으면) 재제작본을 나란히 놓고 판정·메모로 거를 수 있다. 이미지는
HTML 안에 넣어 파일 하나로 열린다.
"""
import base64
import html
import io
import json
from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / 'assets/images/review'
MAX_W = 320  # 시트에 넣을 때 가로 최대 폭(원본 비율 유지, 확대는 브라우저에서)


def data_uri(path, crop=None):
    im = Image.open(path).convert('RGBA')
    if crop:
        im = im.crop(crop)
        im = im.resize((im.width * 4, im.height * 4), Image.NEAREST)
    elif im.width >= 512:  # 640×480 등 큰 화면은 절반으로
        im = im.resize((im.width // 2, im.height // 2), Image.NEAREST)
    buf = io.BytesIO()
    im.save(buf, 'PNG', optimize=True)
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode(), im.width


def changed_bounds(before, after):
    a = Image.open(before).convert('RGBA')
    b = Image.open(after).convert('RGBA')
    if a.size != b.size:
        raise ValueError('비교 이미지 크기가 다름')
    channels = ImageChops.difference(a, b).split()
    diff = channels[0]
    for channel in channels[1:]:
        diff = ImageChops.lighter(diff, channel)
    box = diff.getbbox()
    if not box:
        return None, 0
    count = sum(n for value, n in enumerate(diff.histogram()) if value)
    x0, y0, x1, y1 = box
    return (max(0, x0 - 2), max(0, y0 - 2), min(a.width, x1 + 2), min(a.height, y1 + 2)), count


def main():
    rows = json.loads((REVIEW / 'image_review.json').read_text(encoding='utf-8'))
    remake = {}
    # 뒤 단계가 앞 단계를 덮는다(로고는 UI 결과 위에 만든다)
    for idx in [ROOT / 'assets/images/remake' / d / 'index.json' for d in ('slg', 'staffroll', 'ui', 'logo', 'cutin', 'quotes', 'nc', 'combo')]:
        if not idx.exists():
            continue
        for r in json.loads(idx.read_text(encoding='utf-8')):
            remake[(r['source'], r['block'], r['texture'])] = r['remake']
    baseline = REVIEW / 'remake_baseline.json'
    if baseline.exists():
        for key, item in json.loads(baseline.read_text(encoding='utf-8')).items():
            source, block, texture = key.rsplit('|', 2)
            remake[(source, int(block), int(texture))] = item['path']
    individual = {}
    individual_index = ROOT / 'assets/images/remake/individual/index.json'
    if individual_index.exists():
        for item in json.loads(individual_index.read_text(encoding='utf-8')):
            individual[(item['source'], item['block'], item['texture'])] = item
    order = {'결함': 0, '경미': 1, '재제작 완료': 2, '정상': 3}
    rows.sort(key=lambda r: (order[r['verdict']], r['id']))
    counts = {}
    for r in rows:
        counts[r['verdict']] = counts.get(r['verdict'], 0) + 1
    out = ['<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>이미지 검수표</title><style>',
           ':root{--z:1}body{font-family:sans-serif;background:#f3f3f3;margin:16px;color:#222}',
           '.bar{position:sticky;top:0;background:#f3f3f3;padding:8px 0;z-index:1}',
           '.row{background:#fff;margin:0 0 10px;padding:8px;border-left:6px solid #999}',
           '.결함{border-color:#d33}.경미{border-color:#e90}.정상{border-color:#3a3}.재제작{border-color:#36c}',
           '.imgs{display:flex;gap:10px;flex-wrap:nowrap;align-items:flex-start;overflow-x:auto}',
           '.imgs figure{flex-shrink:0}.individual{border-top:2px solid #28734b;padding-top:4px}',
           '.imgs figure{margin:0;font-size:12px;text-align:center}',
           '.imgs img{image-rendering:pixelated;width:calc(var(--w)*var(--z)*1px);display:block;',
           'background:repeating-conic-gradient(#aaa 0 25%,#ccc 0 50%) 0 0/16px 16px}',
           'h3{margin:0 0 4px;font-size:14px}.note{margin:2px 0 6px}.m{color:#777;font-size:11px}',
           '</style></head><body>',
           '<h1>이미지 검수표</h1>',
           '<p>원본 → v0.5 → 재제작(보존본) → 개별 수정 순서입니다. v0.5가 손대지 않아 새로 번역한 이미지는 '
           '원본 → 재제작 두 칸만 있습니다. 기존 재제작본은 보존하며, '
           '추가 수정이 있는 이미지에만 오른쪽 비교 칸을 표시합니다.</p>',
           '<p>개별 수정은 표시된 부분만 바꾼 결과이며 이미지 전체의 검수 완료를 뜻하지 않습니다. '
           '제목의 기존 판정과 별도로, 아래에 이번 수정 범위와 수정부 확대 비교를 표시합니다.</p>',
           f'<p>서로 다른 변경 이미지 {len(rows)}종(사본 포함 {sum(r["copies"] for r in rows)}장). '
           + ' · '.join(f'{k} {v}' for k, v in sorted(counts.items(), key=lambda kv: order[kv[0]])) + '</p>',
           '<div class="bar">판정 <select id="f"><option value="">전체</option>'
           + ''.join(f'<option>{k}</option>' for k in order) + '</select> 배율 <select id="z">'
           '<option>1</option><option>2</option><option>3</option></select></div>']
    updates = REVIEW / 'image_review_updates.json'
    if updates.exists():
        out.append('<section class="row"><h2>후속 이슈 수정 기록</h2>')
        for update in json.loads(updates.read_text(encoding='utf-8')):
            out.append(f'<h3>{html.escape(update["date"])} — {html.escape(update["title"])}</h3>')
            for note in update['notes']:
                out.append(f'<p>{html.escape(note)}</p>')
            if update.get('comparison'):
                uri, w = data_uri(ROOT / update['comparison'])
                label = html.escape(update.get('comparison_label', '수정 전 / 수정 후'))
                out.append(f'<div class="imgs"><figure style="--w:{w}"><img src="{uri}">{label}</figure></div>')
        out.append('</section>')
    for r in rows:
        cls = '재제작' if r['verdict'] == '재제작 완료' else r['verdict']
        out.append(f'<div class="row {cls}" data-v="{r["verdict"]}">')
        out.append(f'<h3>#{r["id"]} [{r["verdict"]}{" · " + r["category"] if r["category"] else ""}] '
                   f'{html.escape(r["source"])} b{r["block"]} t{r["texture"]} ({r["size"][0]}×{r["size"][1]})</h3>')
        if r['note']:
            out.append(f'<div class="note">{html.escape(r["note"])}</div>')
        out.append('<div class="imgs">')
        imgs = [('원본', r['original'])]
        if r['patched']:  # v0.5가 손대지 않은 원본 이미지 행은 v0.5 칸이 없다
            imgs.append(('v0.5', r['patched']))
        key = (r['source'], r['block'], r['texture'])
        if key in remake:
            imgs.append(('재제작 (보존본)' if r['patched'] else '재제작', remake[key]))
        correction = individual.get(key)
        if correction:
            imgs.append(('개별 수정', correction['remake']))
        for label, p in imgs:
            uri, w = data_uri(ROOT / p)
            out.append(f'<figure style="--w:{w}"><img src="{uri}" title="{html.escape(p)}">{label}</figure>')
        out.append('</div>')
        if correction:
            out.append(f'<div class="note individual"><strong>{html.escape(correction.get("scope", "부분 수정"))}</strong><br>'
                       f'변경 내용: {html.escape(correction["note"])}</div>')
            bounds, count = changed_bounds(ROOT / remake[key], ROOT / correction['remake'])
            out.append(f'<div class="m">재제작 보존본 대비 변경 픽셀: {count}개</div>')
            if bounds:
                out.append('<details><summary>실제 수정부 4배 확대 비교</summary><div class="imgs">')
                for label, path in [('수정부 확대 · 재제작 보존본', remake[key]), ('수정부 확대 · 개별 수정', correction['remake'])]:
                    uri, w = data_uri(ROOT / path, bounds)
                    out.append(f'<figure style="--w:{w}"><img src="{uri}">{label}</figure>')
                out.append('</div></details>')
        if r['copies'] > 1:
            out.append(f'<div class="m">같은 이미지 {r["copies"]}곳: {html.escape(", ".join(r["members"]))}</div>')
        out.append('</div>')
    out.append('<script>'
               'const f=document.getElementById("f"),z=document.getElementById("z");'
               'f.onchange=()=>document.querySelectorAll(".row").forEach(e=>e.style.display=!f.value||e.dataset.v==f.value?"":"none");'
               'z.onchange=()=>document.body.style.setProperty("--z",z.value);'
               '</script></body></html>')
    (REVIEW / 'image_review.html').write_text('\n'.join(out), encoding='utf-8')
    print('검수표', REVIEW / 'image_review.html')


if __name__ == '__main__':
    main()
