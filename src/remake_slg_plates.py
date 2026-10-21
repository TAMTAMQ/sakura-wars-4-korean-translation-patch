"""SLG 컷인 이름판을 원본 디자인으로 다시 그린다.

v0.5 개선판은 이름판의 반투명 검은 판·명조체·그림자·검은 상자를 지우고
투명 배경에 고딕체를 넣었다. 원본 텍스처를 바탕으로 글자 띠만 판 색으로
다시 칠한 뒤, 개선판의 한국어 문구를 원본과 같은 방식(흰 명조 + 오른쪽 아래
그림자, 상자는 불투명 검정)으로 그린다. 결과는 ARGB4444 단계로 양자화한다.

입력: assets/images/remake/slg_plates.json, assets/extracted/images/index.json
출력: assets/images/remake/slg/<컨테이너>/<블록>_<텍스처>.png 와 비교 시트
게임 파일 재삽입은 하지 않는다.
"""
import base64
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageFont, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'assets/images/remake/slg_plates.json'
OUT = ROOT / 'assets/images/remake/slg'
SS = 4                 # 슈퍼샘플링 배율
PLATE_ALPHA = 136 / 255
TEXT_GRAY = 238
SHADOW_ALPHA = 0.85


def load_font(cfg, px):
    font = ImageFont.truetype(cfg['path'], px)
    try:
        font.set_variation_by_axes([cfg['weight']])
    except Exception:
        pass
    return font


def glyph_px(height):
    """원본 글자 높이: 24px 띠에 약 20px, 32px 띠에 약 27px."""
    return round(height * 0.84)


def place(ink, starts, W, cuts, align, x_off):
    """글자 잉크 구간(ink: 글자 원점 기준 [l, r])을 조각 경계(cuts)를 넘지 않게 배치한다.
    경계에 걸린 글자는 다음 조각 시작으로 민다. 넘치면 None."""
    def run(x0):
        out, shift = [], 0.0
        for (l, r), s in zip(ink, starts):
            x = x0 + s + shift
            for c in cuts:
                if x + l < c < x + r:
                    shift += c - (x + l) + SS
                    x = x0 + s + shift
            out.append(x)
        end = max(x + r for x, (l, r) in zip(out, ink)) if out else x0
        return out, end
    lo = x_off * SS + 2 * SS
    pos, end = run(lo)
    if end > W - 2 * SS:
        return None
    if align == 'center':
        for k in range(40):  # 가운데로 옮겨 보되 경계 때문에 넘치면 덜 옮긴다
            off = (W - (end - lo)) / 2 - lo
            p2, e2 = run(lo + off * (1 - k / 40))
            if e2 <= W - 2 * SS:
                return p2
    return pos


def render_mask(text, width, height, layout, track, x_off, font_cfg, cuts=()):
    """chain 전체 폭의 글자 마스크(0~1)를 만든다."""
    if cuts and layout != 'spaced':
        return render_chain(text, width, height, layout, track, x_off, font_cfg, cuts)
    W, H = width * SS, height * SS
    size = glyph_px(height) * SS
    font = load_font(font_cfg, size)
    # '한'의 잉크 높이를 목표 글자 높이에 맞춘다.
    box = font.getbbox('한')
    scale = size / (box[3] - box[1])
    font = load_font(font_cfg, round(size * scale))
    box = font.getbbox('한')
    ink_h = box[3] - box[1]
    top = (H - ink_h) / 2 - box[1] - SS  # 그림자 몫으로 1px 위로
    chars = list(text)
    adv = [font.getlength(c) for c in chars]
    margin = 2 * SS
    if layout == 'spaced':
        glyphs = [c for c in chars if c != ' ']
        pitch = W / max(1, len(glyphs))
        pos = [(i + 0.5) * pitch - font.getlength(c) / 2 for i, c in enumerate(glyphs)]
        chars = glyphs
        natural = W
    else:
        t = track * SS
        natural = sum(adv) + t * (len(chars) - 1)
        pos, x = [], 0.0
        for a in adv:
            pos.append(x)
            x += a + t
    layer = Image.new('L', (max(W, int(natural) + 4 * SS), H), 0)
    draw = ImageDraw.Draw(layer)
    for c, x in zip(chars, pos):
        draw.text((x, top), c, font=font, fill=255)
    if layout != 'spaced':
        avail = W - 2 * margin - x_off * SS
        span = int(np.ceil(natural))
        layer = layer.crop((0, 0, span, H))
        if span > avail:  # 넘치면 가로로만 줄인다
            layer = layer.resize((int(avail), H), Image.LANCZOS)
            span = int(avail)
        canvas = Image.new('L', (W, H), 0)
        if layout == 'center':
            x0 = (W - span) // 2
        else:
            x0 = x_off * SS
        canvas.paste(layer, (int(x0), 0))
        layer = canvas
    layer = layer.crop((0, 0, W, H)).resize((width, height), Image.BOX)
    return np.asarray(layer, dtype=np.float64) / 255


def render_chain(text, width, height, layout, track, x_off, font_cfg, cuts):
    """여러 조각으로 나뉘는 띠: 글자가 조각 경계를 가로지르지 않게 배치한다.
    (경계에 걸린 글자는 두 조각에 나뉘어 들어가, 게임이 조각을 따로 그리는 화면에서
    남은 획이 그림자처럼 보였다.)"""
    W, H = width * SS, height * SS
    size = glyph_px(height) * SS
    font = load_font(font_cfg, size)
    box = font.getbbox('한')
    font = load_font(font_cfg, round(size * size / (box[3] - box[1])))
    box = font.getbbox('한')
    top = (H - (box[3] - box[1])) / 2 - box[1] - SS
    chars = list(text)
    cuts = [c * SS for c in cuts]
    for k in range(51):
        s = 1 - k * 0.01
        starts, x, ink = [], 0.0, []
        for c in chars:
            b = font.getbbox(c) if c != ' ' else (0, 0, 0, 0)
            starts.append(x)
            ink.append((b[0] * s, b[2] * s + 3 * SS))  # 오른쪽 아래 그림자 몫 3px
            x += (font.getlength(c) + track * SS) * s
        pos = place(ink, starts, W, cuts, layout, x_off)
        if pos is not None:
            break
    else:
        print('  경계 맞춤 실패(기존 배치 사용):', text, width, cuts)
        return render_mask(text, width, height, layout, track, x_off, font_cfg)
    layer = Image.new('L', (W, H), 0)
    for c, x in zip(chars, pos):
        if c == ' ':
            continue
        gw = int(np.ceil(font.getlength(c))) + 2 * SS
        g = Image.new('L', (gw, H), 0)
        ImageDraw.Draw(g).text((0, top), c, font=font, fill=255)
        g = g.resize((max(1, round(gw * s)), H), Image.LANCZOS)
        layer.paste(g, (int(round(x)), 0), g)
    layer = layer.resize((width, height), Image.BOX)
    return np.asarray(layer, dtype=np.float64) / 255


def compose(mask, style):
    h, w = mask.shape
    base = 1.0 if style == 'box' else PLATE_ALPHA
    shift = 2 if h >= 30 else 1
    sh = np.zeros_like(mask)
    sh[shift:, shift + 1:] = mask[:-shift, :-(shift + 1)] if style != 'box' else 0
    sh = np.asarray(Image.fromarray((sh * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.5)),
                    dtype=np.float64) / 255 * SHADOW_ALPHA
    a1 = sh + base * (1 - sh)
    a2 = mask + a1 * (1 - mask)
    color = np.where(a2 > 0, TEXT_GRAY * mask / np.maximum(a2, 1e-6), 0)
    rgba = np.zeros((h, w, 4))
    rgba[..., 0] = rgba[..., 1] = rgba[..., 2] = color
    rgba[..., 3] = a2 * 255
    return np.clip(np.round(rgba / 17) * 17, 0, 255).astype(np.uint8)


def main():
    cfg = json.loads(CONFIG.read_text(encoding='utf-8'))
    index = json.loads((ROOT / 'assets/extracted/images/index.json').read_text(encoding='utf-8'))
    tex = {(t['source'], t['block'], t['texture']): t for t in index['textures']}
    results = []
    for blk in cfg['blocks']:
        chains = cfg['templates'][blk['template']]
        images = {}
        for chain in chains:
            for r in chain['rects']:
                key = (blk['source'], blk['block'], r[0])
                if r[0] not in images:
                    t = tex[key]
                    images[r[0]] = np.asarray(Image.open(ROOT / t['original_png']).convert('RGBA')).copy()
        if blk.get('use_v05'):
            # 게임이 조각을 어떻게 그리는지 확실하지 않은 띠는 v0.5 개선판 배치를 그대로 쓴다
            for t in images:
                images[t] = np.asarray(Image.open(ROOT / tex[(blk['source'], blk['block'], t)]['png']).convert('RGBA')).copy()
            chains = []
        for chain in chains:
            text = blk['text'].get(chain['key'], '')
            if isinstance(text, dict):  # 블록별로 배치를 바꿀 때 {"text", "layout", "x", "track"}
                chain = {**chain, **{k: v for k, v in text.items() if k != 'text'}}
                text = text['text']
            heights = {r[4] - r[2] for r in chain['rects']}
            assert len(heights) == 1, chain
            h = heights.pop()
            width = sum(r[3] - r[1] for r in chain['rects'])
            used = width
            if chain.get('fit_original'):
                # 전투 컷인 이름 띠: 게임은 원본 글자가 쓴 조각까지만, 마지막 조각은 원본 글자 끝까지만 그린다.
                # (넘친 한글이 잘리고 잘린 획이 줄무늬처럼 보였다) → 그 폭 안에만 쓰고 끝 2px은 비운다.
                used, off = 0, 0
                for t, x0, y0, x1, y1 in chain['rects']:
                    a = images[t][y0:y1, x0:x1]
                    xs = np.where(((a[..., 3] > 60) & (a[..., :3].max(-1) > 120)).any(0))[0]
                    if len(xs):
                        used = off + xs.max() + 1
                    off += x1 - x0
                used -= 2
            cuts, acc = [], 0
            for r in chain['rects'][:-1]:
                acc += r[3] - r[1]
                if acc < used:
                    cuts.append(acc)
            mask = render_mask(text, used, h, chain['layout'], chain.get('track', 0), chain.get('x', 0), cfg['font'],
                               cuts) if text else np.zeros((h, used))
            mask = np.pad(mask, ((0, 0), (0, width - used)))
            rgba = compose(mask, chain['style'])
            off = 0
            for t, x0, y0, x1, y1 in chain['rects']:
                images[t][y0:y1, x0:x1] = rgba[:, off:off + x1 - x0]
                off += x1 - x0
        for t, arr in images.items():
            meta = tex[(blk['source'], blk['block'], t)]
            out = OUT / blk['source'] / f"{blk['block']:04d}_{t:04d}.png"
            out.parent.mkdir(parents=True, exist_ok=True)
            Image.fromarray(arr).save(out)
            results.append({'source': blk['source'], 'block': blk['block'], 'texture': t,
                            'original': meta['original_png'], 'patched': meta['png'],
                            'remake': out.relative_to(ROOT).as_posix()})
    (OUT / 'index.json').write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding='utf-8')
    print('재제작', len(results))




def write_sheet():
    """원본 / v0.5 / 재제작 3단 비교 시트(HTML·PNG)를 만든다."""
    rows = json.loads((OUT / 'index.json').read_text(encoding='utf-8'))
    index = json.loads((ROOT / 'assets/extracted/images/index.json').read_text(encoding='utf-8'))
    # 같은 원본·개선판 쌍을 쓰는 다른 컨테이너(UNITS의 GRCT 등)도 함께 표시한다.
    pair = {}
    for t in index['textures']:
        if t.get('original_png'):
            k = (Path(ROOT / t['original_png']).read_bytes(), Path(ROOT / t['png']).read_bytes())
            pair.setdefault(k, []).append(f"{t['source']} b{t['block']} t{t['texture']}")
    base = ROOT / 'assets/images/remake'
    html = ['<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>SLG 이름판 비교</title><style>',
            'body{font-family:sans-serif;background:#f4f4f4;margin:16px}',
            '.row{display:flex;gap:12px;align-items:flex-start;background:#fff;padding:8px;margin-bottom:10px;flex-wrap:wrap}',
            '.cell{text-align:center;font-size:12px}',
            '.cell img{image-rendering:pixelated;width:calc(var(--z)*var(--w)*1px);display:block;',
            'background:repeating-conic-gradient(#bbb 0 25%,#ddd 0 50%) 0 0/16px 16px}',
            'h3{margin:0 0 4px;font-size:13px;width:100%}.m{color:#666;font-size:11px;width:100%}',
            '</style></head><body><h1>SLG 컷인 이름판: 원본 / v0.5 / 재제작</h1>',
            '<p>배율 <select id="z" onchange="document.body.style.setProperty(\'--z\',this.value)">',
            '<option>2</option><option selected>3</option><option>4</option></select> ',
            '체크무늬는 투명한 부분이다. 문구는 v0.5 그대로이고 판·글꼴·그림자·검은 상자를 원본대로 되돌렸다.</p>']
    sheet = []
    for r in rows:
        o, p, m = (ROOT / r['original'], ROOT / r['patched'], ROOT / r['remake'])
        w = Image.open(o).width
        members = pair.get((o.read_bytes(), p.read_bytes()), [])
        rp = lambda q: Path(q).relative_to(ROOT).as_posix()
        html.append(f'<div class="row" style="--w:{w}"><h3>{r["source"]} b{r["block"]} t{r["texture"]}</h3>')
        for label, q in (('원본', o), ('v0.5', p), ('재제작', m)):
            data = base64.b64encode(q.read_bytes()).decode()
            html.append(f'<div class="cell"><img src="data:image/png;base64,{data}" title="{rp(q)}">{label}</div>')
        if len(members) > 1:
            html.append(f'<div class="m">같은 이미지: {", ".join(members)}</div>')
        html.append('</div>')
        sheet.append((r, [Image.open(q).convert('RGBA') for q in (o, p, m)]))
    html.append('<script>document.body.style.setProperty("--z",3)</script></body></html>')
    (base / 'slg_compare.html').write_text('\n'.join(html), encoding='utf-8')

    # PNG 시트: 한 줄에 원본·v0.5·재제작, 2배
    z, gap = 2, 8
    def tile(im):
        bg = Image.new('RGBA', im.size, (120, 140, 170, 255))
        bg.alpha_composite(im)
        return bg.resize((im.width * z, im.height * z), Image.NEAREST).convert('RGB')
    lines = []
    for r, ims in sheet:
        ts = [tile(i) for i in ims]
        line = Image.new('RGB', (sum(t.width for t in ts) + gap * 2, ts[0].height + 14), 'white')
        for j, t in enumerate(ts):
            line.paste(t, (j * (t.width + gap), 14))
        ImageDraw.Draw(line).text((0, 1), f"{r['source']} b{r['block']} t{r['texture']}", fill='black')
        lines.append(line)
    cols = 3
    colw = max(l.width for l in lines) + 16
    per = (len(lines) + cols - 1) // cols
    colh = [sum(l.height + 6 for l in lines[c * per:(c + 1) * per]) for c in range(cols)]
    out = Image.new('RGB', (colw * cols, max(colh) + 30), 'white')
    ImageDraw.Draw(out).text((4, 4), '원본 | v0.5 | 재제작  (배경 회청색 = 투명)', fill='black',
                             font=load_font({'path': 'C:/Windows/Fonts/malgun.ttf', 'weight': 400}, 16))
    for c in range(cols):
        y = 30
        for l in lines[c * per:(c + 1) * per]:
            out.paste(l, (c * colw, y))
            y += l.height + 6
    out.save(base / 'slg_compare.png')
    print('비교 시트', base / 'slg_compare.html', base / 'slg_compare.png')


if __name__ == '__main__':
    main()
    write_sheet()
