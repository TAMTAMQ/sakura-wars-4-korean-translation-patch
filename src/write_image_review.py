"""이미지 검수표(assets/images/review/image_review.json)를 비교 시트 HTML로 만든다.

원본 · v0.5 · (있으면) 재제작본을 나란히 놓고 판정·메모로 거를 수 있다. 이미지는
HTML 안에 넣어 파일 하나로 열린다.
"""
import base64
import html
import io
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / 'assets/images/review'
MAX_W = 320  # 시트에 넣을 때 가로 최대 폭(원본 비율 유지, 확대는 브라우저에서)


def data_uri(path):
    im = Image.open(path).convert('RGBA')
    if im.width >= 512:  # 640×480 등 큰 화면은 절반으로
        im = im.resize((im.width // 2, im.height // 2), Image.NEAREST)
    buf = io.BytesIO()
    im.save(buf, 'PNG', optimize=True)
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode(), im.width


def main():
    rows = json.loads((REVIEW / 'image_review.json').read_text(encoding='utf-8'))
    remake = {}
    # 뒤 단계가 앞 단계를 덮는다(로고는 UI 결과 위에 만든다)
    for idx in [ROOT / 'assets/images/remake' / d / 'index.json' for d in ('slg', 'staffroll', 'ui', 'logo')]:
        if not idx.exists():
            continue
        for r in json.loads(idx.read_text(encoding='utf-8')):
            remake[(r['source'], r['block'], r['texture'])] = r['remake']
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
           '.imgs{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-start}',
           '.imgs figure{margin:0;font-size:12px;text-align:center}',
           '.imgs img{image-rendering:pixelated;width:calc(var(--w)*var(--z)*1px);display:block;',
           'background:repeating-conic-gradient(#aaa 0 25%,#ccc 0 50%) 0 0/16px 16px}',
           'h3{margin:0 0 4px;font-size:14px}.note{margin:2px 0 6px}.m{color:#777;font-size:11px}',
           '</style></head><body>',
           '<h1>v0.5 개선판 변경 이미지 검수표</h1>',
           f'<p>서로 다른 변경 이미지 {len(rows)}종(사본 포함 {sum(r["copies"] for r in rows)}장). '
           + ' · '.join(f'{k} {v}' for k, v in sorted(counts.items(), key=lambda kv: order[kv[0]])) + '</p>',
           '<div class="bar">판정 <select id="f"><option value="">전체</option>'
           + ''.join(f'<option>{k}</option>' for k in order) + '</select> 배율 <select id="z">'
           '<option>1</option><option>2</option><option>3</option></select></div>']
    for r in rows:
        cls = '재제작' if r['verdict'] == '재제작 완료' else r['verdict']
        out.append(f'<div class="row {cls}" data-v="{r["verdict"]}">')
        out.append(f'<h3>#{r["id"]} [{r["verdict"]}{" · " + r["category"] if r["category"] else ""}] '
                   f'{html.escape(r["source"])} b{r["block"]} t{r["texture"]} ({r["size"][0]}×{r["size"][1]})</h3>')
        if r['note']:
            out.append(f'<div class="note">{html.escape(r["note"])}</div>')
        out.append('<div class="imgs">')
        imgs = [('원본', r['original']), ('v0.5', r['patched'])]
        key = (r['source'], r['block'], r['texture'])
        if key in remake:
            imgs.append(('재제작', remake[key]))
        for label, p in imgs:
            uri, w = data_uri(ROOT / p)
            out.append(f'<figure style="--w:{w}"><img src="{uri}" title="{html.escape(p)}">{label}</figure>')
        out.append('</div>')
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
