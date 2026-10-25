"""메뉴·표지판 등 개별 디자인 이미지를 원본 바탕으로 다시 만든다.

원본 텍스처에서 일본어 글자만 지우고(OpenCV 인페인팅·복제·채우기) 그 자리에
한국어를 원본과 비슷한 글꼴·색·테두리·그림자로 그린다. 결과는 텍스처의 픽셀
형식(ARGB4444 / RGB565 / ARGB1555) 단계로 양자화한다.

입력: assets/images/remake/ui.json
출력: assets/images/remake/ui/<컨테이너>/<블록>_<텍스처>.png, index.json

ui.json 항목: {"source", "block", "texture", "ops": [...]}
  {"op": "inpaint", "rect": [x0,y0,x1,y1], "select": "dark|light|all|near",
   "thr": 숫자, "color": [r,g,b], "dilate": 1, "radius": 3}
  {"op": "copy", "from": [x0,y0,x1,y1], "to": [x, y]}           영역 복제
  {"op": "fill", "rect": [...], "rgba": [r,g,b,a]}               단색 채우기
  {"op": "text", "rect": [...], "text": "...", "font": "sans|serif|gothic|batang",
   "weight": 700, "size": 픽셀, "fill": [r,g,b] 또는 {"top":[..],"bottom":[..]},
   "stroke": [[r,g,b], 폭], "shadow": [[r,g,b,a], dx, dy, blur],
   "glow": [[r,g,b], 반경, 세기], "align": "center|left|right", "vertical": false,
   "track": 0, "squeeze": 1.0}
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import export_images as E  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'assets/images/remake/ui.json'
OUT = ROOT / 'assets/images/remake/ui'
SS = 4
FONTS = {
    'sans': ('C:/Windows/Fonts/NotoSansKR-VF.ttf', True),
    'serif': ('C:/Windows/Fonts/NotoSerifKR-VF.ttf', True),
    'gothic': ('C:/Windows/Fonts/malgunbd.ttf', False),
    'batang': ('C:/Windows/Fonts/HANBatangB.ttf', False),
    'gungso': ('C:/Windows/Fonts/H2GSRB.TTF', False),       # HY궁서 B: 붓글씨
    'myeongjo': ('C:/Windows/Fonts/H2MJRE.TTF', False),     # HY견명조
}


def font_at(name, weight, px):
    path, variable = FONTS[name]
    f = ImageFont.truetype(path, px)
    if variable:
        f.set_variation_by_axes([weight])
    return f


def select_mask(arr, rect, op):
    x0, y0, x1, y1 = rect
    sub = arr[y0:y1, x0:x1].astype(np.int32)
    lum = sub[..., :3] @ np.array([299, 587, 114]) // 1000
    mode = op.get('select', 'dark')
    thr = op.get('thr', 90)
    if mode == 'dark':
        m = lum < thr
    elif mode == 'light':
        m = lum > thr
    elif mode == 'near':
        m = np.abs(sub[..., :3] - np.array(op['color'])).sum(-1) < thr
    elif mode == 'far':  # 바탕색에서 먼 픽셀(글자·테두리·번짐)을 모두 고른다
        m = np.abs(sub[..., :3] - np.array(op['color'])).sum(-1) > thr
    else:
        m = np.ones(lum.shape, bool)
    if 'alpha_min' in op:
        m &= sub[..., 3] >= op['alpha_min']
    full = np.zeros(arr.shape[:2], np.uint8)
    full[y0:y1, x0:x1] = m.astype(np.uint8) * 255
    d = op.get('dilate', 1)
    if d:
        import cv2
        full = cv2.dilate(full, np.ones((2 * d + 1, 2 * d + 1), np.uint8))
        clip = np.zeros_like(full)
        clip[y0:y1, x0:x1] = 255
        full &= clip
    return full


def inpaint(arr, op):
    import cv2
    if op.get('local'):  # rect 밖(다른 그림 칸)의 색을 끌어오지 않도록 rect만 잘라서 채운다
        x0, y0, x1, y1 = op['rect']
        sub = np.ascontiguousarray(arr[y0:y1, x0:x1])
        out = arr.copy()
        out[y0:y1, x0:x1] = inpaint(sub, {**op, 'local': False, 'rect': [0, 0, x1 - x0, y1 - y0]})
        return out
    mask = select_mask(arr, op['rect'], op)
    r = op.get('radius', 3)
    rgb = cv2.inpaint(np.ascontiguousarray(arr[..., :3]), mask, r, cv2.INPAINT_TELEA)
    out = arr.copy()
    out[..., :3] = rgb
    if op.get('alpha') != 'keep':  # 불투명 띠 가장자리에서는 바깥 투명값이 번지지 않게 keep
        out[..., 3] = cv2.inpaint(np.ascontiguousarray(arr[..., 3]), mask, r, cv2.INPAINT_TELEA)
    return out


def extend_vertical(arr, op):
    """판의 위·아래 끝을 유지하고 지정한 가로 단면을 반복해 세로로 늘린다."""
    x0, y0, x1, y1 = op['rect']
    at, extra = op['at'], op['extra']
    if not (0 <= x0 < x1 <= arr.shape[1] and 0 <= y0 < y1 <= arr.shape[0]
            and 0 < at < y1 - y0 and extra > 0 and y1 + extra <= arr.shape[0]):
        raise ValueError('세로 배경 연장 범위 오류')
    src = arr[y0:y1, x0:x1].copy()
    extended = np.concatenate((src[:at], np.repeat(src[at:at + 1], extra, axis=0), src[at:]), axis=0)
    out = arr.copy()
    out[y0:y1 + extra, x0:x1] = extended
    return out


def clear_panel(arr, op):
    """푸른 테두리를 침범하지 않고 반투명 검정 판의 글자·번짐만 지운다."""
    out = arr.copy()
    x0, y0, x1, y1 = op['rect']
    scan0, scan1 = op['edge_scan']
    for y in range(y0, y1):
        row = arr[y, scan0:scan1, :3].astype(np.int32)
        blue = np.flatnonzero(row[:, 2] - row[:, 0] >= 20)
        end = min(x1, scan0 + int(blue[0]) - 2) if len(blue) else x1
        if end > x0:
            out[y, x0:end] = op['rgba']
    return out


def layout_text(op):
    """op의 글자를 rect 크기 마스크(채움·테두리 분리)로 만든다."""
    x0, y0, x1, y1 = op['rect']
    W, H = (x1 - x0) * SS, (y1 - y0) * SS
    font = font_at(op.get('font', 'sans'), op.get('weight', 700), op['size'] * SS)
    stroke = op.get('stroke', [None, 0])[1] * SS
    track = op.get('track', 0) * SS
    chars = list(op['text'])
    fill = Image.new('L', (W * 3, H * 3), 0)
    edge = Image.new('L', (W * 3, H * 3), 0)
    df, de = ImageDraw.Draw(fill), ImageDraw.Draw(edge)
    if op.get('vertical'):
        y = 0
        asc = font.getbbox('한')
        step = (asc[3] - asc[1]) + track + op['size'] * SS * 0.12
        if op.get('justify'):  # 글자 간격을 늘려 rect 높이를 위에서 아래까지 채운다(원본 줄 길이 맞춤)
            units = sum(0.5 if c == ' ' else 1 for c in chars)
            step = (H - (asc[3] - asc[1])) / max(units - 1, 1)
        for c in chars:
            if c == ' ':
                y += step * 0.5
                continue
            b = font.getbbox(c)
            x = W * 1.5 - (b[2] + b[0]) / 2
            yy = H + y - asc[1]
            de.text((x, yy), c, font=font, fill=255, stroke_width=int(stroke))
            df.text((x, yy), c, font=font, fill=255)
            y += step
    else:
        x = 0
        asc = font.getbbox('한')
        for c in chars:
            yy = H * 1.5 - (asc[3] + asc[1]) / 2
            de.text((W + x, yy), c, font=font, fill=255, stroke_width=int(stroke))
            df.text((W + x, yy), c, font=font, fill=255)
            x += font.getlength(c) + track
    box = edge.getbbox()
    if not box:
        return np.zeros((H // SS, W // SS)), np.zeros((H // SS, W // SS))
    fill, edge = fill.crop(box), edge.crop(box)
    sq = op.get('squeeze', 1.0)
    w, h = edge.width * sq, edge.height
    if op.get('vertical'):
        scale = 1.0 if op.get('justify') else min(1.0, H / h, W / w)
    else:
        scale = min(1.0, W / w, H / h)
        if W / w < 1 and h * 1 <= H:  # 가로만 넘치면 가로로만 누른다
            sq *= W / w
            w, scale = W, min(1.0, H / h)
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    fill = fill.resize((nw, nh), Image.LANCZOS)
    edge = edge.resize((nw, nh), Image.LANCZOS)
    align = op.get('align', 'center')
    px = (W - nw) // 2 if align == 'center' else (0 if align == 'left' else W - nw)
    py = (H - nh) // 2 if not op.get('top') else 0
    cf, ce = Image.new('L', (W, H), 0), Image.new('L', (W, H), 0)
    cf.paste(fill, (px, py))
    ce.paste(edge, (px, py))
    size = (W // SS, H // SS)
    return (np.asarray(cf.resize(size, Image.BOX), float) / 255,
            np.asarray(ce.resize(size, Image.BOX), float) / 255)


def over(dst, color, alpha):
    """dst(float RGBA 0~1) 위에 단색 color를 alpha 마스크로 덮는다."""
    a = alpha[..., None]
    out_a = a + dst[..., 3:4] * (1 - a)
    rgb = (np.asarray(color, float)[None, None, :] * a + dst[..., :3] * dst[..., 3:4] * (1 - a)) / np.maximum(out_a, 1e-6)
    return np.concatenate([rgb, out_a], -1)


def draw_text(arr, op):
    """rect가 텍스처 밖으로 나가면(이웃 텍스처와 이어지는 글자) 겹치는 부분만 그린다."""
    if 'clip' in op:  # clip 사각형 밖은 원래 픽셀을 지킨다(텍스처 안 다른 그림 칸)
        cx0, cy0, cx1, cy1 = op['clip']
        keep = arr.copy()
        out = draw_text(arr, {k: v for k, v in op.items() if k != 'clip'})
        mask = np.ones(arr.shape[:2], bool)
        mask[cy0:cy1, cx0:cx1] = False
        out[mask] = keep[mask]
        return out
    x0, y0, x1, y1 = op['rect']
    h, w = arr.shape[:2]
    if x0 < 0 or y0 < 0 or x1 > w or y1 > h:
        pad = np.zeros((y1 - y0, x1 - x0, 4), np.uint8)
        cx0, cy0, cx1, cy1 = max(x0, 0), max(y0, 0), min(x1, w), min(y1, h)
        pad[cy0 - y0:cy1 - y0, cx0 - x0:cx1 - x0] = arr[cy0:cy1, cx0:cx1]
        pad = _draw_text(pad, {**op, 'rect': [0, 0, x1 - x0, y1 - y0]})
        arr[cy0:cy1, cx0:cx1] = pad[cy0 - y0:cy1 - y0, cx0 - x0:cx1 - x0]
        return arr
    return _draw_text(arr, op)


def _draw_text(arr, op):
    x0, y0, x1, y1 = op['rect']
    fill, edge = layout_text(op)
    if op.get('binary'):  # 아주 작은 글씨: 계단 없는 2단계로(중간 회색이 없어 압축 크기가 덜 는다)
        fill, edge = (fill > 0.45).astype(float), (edge > 0.45).astype(float)
    region = arr[y0:y1, x0:x1].astype(float) / 255
    if 'glow' in op:
        col, rad, k = op['glow']
        g = Image.fromarray((edge * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(2 * rad + 1)).filter(ImageFilter.GaussianBlur(rad))
        region = over(region, np.array(col) / 255, np.clip(np.asarray(g, float) / 255 * k, 0, 1))
    if 'shadow' in op:
        col, dx, dy, blur = op['shadow']
        s = np.zeros_like(edge)
        h, w = edge.shape
        s[max(dy, 0):h + min(dy, 0), max(dx, 0):w + min(dx, 0)] = edge[max(-dy, 0):h - max(dy, 0), max(-dx, 0):w - max(dx, 0)]
        if blur:
            s = np.asarray(Image.fromarray((s * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(blur)), float) / 255
        region = over(region, np.array(col[:3]) / 255, s * col[3] / 255)
    if op.get('stroke', [None, 0])[1]:
        region = over(region, np.array(op['stroke'][0]) / 255, edge)
    fc = op.get('fill', [0, 0, 0])
    if isinstance(fc, dict):  # 위→아래 그라데이션
        t = np.linspace(0, 1, fill.shape[0])[:, None, None]
        ys = np.where(fill.max(1) > 0.1)[0]
        if len(ys):
            t = np.clip((np.arange(fill.shape[0]) - ys.min()) / max(1, ys.max() - ys.min()), 0, 1)[:, None, None]
        grad = np.array(fc['top'])[None, None, :] * (1 - t) + np.array(fc['bottom'])[None, None, :] * t
        a = fill[..., None]
        out_a = a + region[..., 3:4] * (1 - a)
        rgb = (grad / 255 * a + region[..., :3] * region[..., 3:4] * (1 - a)) / np.maximum(out_a, 1e-6)
        region = np.concatenate([rgb, out_a], -1)
    else:
        region = over(region, np.array(fc) / 255, fill)
    arr[y0:y1, x0:x1] = np.clip(np.round(region * 255), 0, 255).astype(np.uint8)
    return arr


def quantize(arr, pf):
    a = arr.astype(np.int32)
    if pf == 2:
        return (np.round(a / 17) * 17).clip(0, 255).astype(np.uint8)
    if pf == 1:
        q = a.copy()
        q[..., 0] = np.round(a[..., 0] * 31 / 255) * 255 // 31
        q[..., 1] = np.round(a[..., 1] * 63 / 255) * 255 // 63
        q[..., 2] = np.round(a[..., 2] * 31 / 255) * 255 // 31
        q[..., 3] = 255
        return q.astype(np.uint8)
    if pf == 0:
        q = (np.round(a * 31 / 255) * 255 // 31)
        q[..., 3] = np.where(a[..., 3] >= 128, 255, 0)
        return q.astype(np.uint8)
    return arr


def disc_texture(source, block, texture):
    """추출 색인에 없는 텍스처(v0.5가 손대지 않은 파일)를 원본에서 직접 디코딩한다."""
    path = ROOT / 'originals/v05' / source
    if not path.exists():
        path = ROOT / 'originals/disc' / source
    sig, off, packed, comp, exp = E.block_specs(path.read_bytes())[block]
    dec = E.decompress(packed, exp) if comp else packed
    _, img, meta = (E.decode_bpv(dec) if sig == 'BPV1' else E.decode_adcg(dec))[texture]
    out = ROOT / 'assets/extracted/images' / source / f'{block:04d}_{sig}' / f'{texture:04d}_original.png'
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    rel = out.relative_to(ROOT).as_posix()
    return {'original_png': rel, 'png': rel, 'pixel_format': meta['pixel_format']}


def main():
    cfg = json.loads(CONFIG.read_text(encoding='utf-8'))
    index = json.loads((ROOT / 'assets/extracted/images/index.json').read_text(encoding='utf-8'))
    tex = {(t['source'], t['block'], t['texture']): t for t in index['textures']}
    rows = []
    for item in cfg['items']:
        key = (item['source'], item['block'], item['texture'])
        t = tex[key] if key in tex else disc_texture(*key)
        base = t['png'] if item.get('base') == 'patched' else t['original_png']
        arr = np.asarray(Image.open(ROOT / base).convert('RGBA')).copy()
        for op in item['ops']:
            if op['op'] == 'extend_vertical':
                arr = extend_vertical(arr, op)
            elif op['op'] == 'clear_panel':
                arr = clear_panel(arr, op)
            elif op['op'] == 'inpaint':
                arr = inpaint(arr, op)
            elif op['op'] == 'rowfill':
                # 가로줄 무늬 바탕: 글자 픽셀을 같은 줄의 나머지 픽셀 중앙값으로 채운다
                mask = select_mask(arr, op['rect'], op) > 0
                x0, y0, x1, y1 = op['rect']
                for y in range(y0, y1):
                    keep = ~mask[y, x0:x1]
                    if keep.any():
                        med = np.median(arr[y, x0:x1][keep], axis=0)
                        row = arr[y, x0:x1]
                        row[~keep] = med.astype(np.uint8)
            elif op['op'] == 'rowref':
                # 가로줄 무늬 바탕: 글자 없는 기준 열(ref_x)의 색으로 줄마다 통째로 칠한다
                x0, y0, x1, y1 = op['rect']
                for y in range(y0, y1):
                    arr[y, x0:x1] = arr[y, op['ref_x']]
            elif op['op'] == 'overlay':
                # 다른 이미지(예: v0.5의 투명 배경 한국어 로고)를 rect 안에 비율 유지로 얹는다
                src = Image.open(ROOT / op['image']).convert('RGBA')
                if 'crop' in op:
                    src = src.crop(tuple(op['crop']))
                x0, y0, x1, y1 = op['rect']
                s = min((x1 - x0) / src.width, (y1 - y0) / src.height)
                src = src.resize((max(1, round(src.width * s)), max(1, round(src.height * s))), Image.LANCZOS)
                base = Image.fromarray(arr)
                base.alpha_composite(src, (x0 + (x1 - x0 - src.width) // 2, y0 + (y1 - y0 - src.height) // 2))
                arr = np.asarray(base).copy()
            elif op['op'] == 'patched_sel':
                # v0.5 이미지에서 바탕색과 먼 픽셀(한국어 글자)만 가져온다
                pt = np.asarray(Image.open(ROOT / t['png']).convert('RGBA'))
                m = select_mask(pt, op['rect'], op) > 0
                arr[m] = pt[m]
            elif op['op'] == 'patched':
                # v0.5 결과가 괜찮은 영역은 그대로 가져온다
                pt = np.asarray(Image.open(ROOT / t['png']).convert('RGBA'))
                x0, y0, x1, y1 = op['rect']
                arr[y0:y1, x0:x1] = pt[y0:y1, x0:x1]
            elif op['op'] == 'copy':
                fx0, fy0, fx1, fy1 = op['from']
                tx, ty = op['to']
                arr[ty:ty + fy1 - fy0, tx:tx + fx1 - fx0] = arr[fy0:fy1, fx0:fx1].copy()
            elif op['op'] == 'replace_gray':
                # 단색 반투명 바탕 위 회색·흰 글자만 바탕값으로 바꾼다(무채색 판정, 청록 모눈선은 남긴다).
                # 번짐 메움(inpaint)은 바탕에 잡음이 생겨 압축 크기가 커졌다(b844).
                x0, y0, x1, y1 = op['rect']
                sub = arr[y0:y1, x0:x1].astype(int)
                gray = (sub[..., :3].max(-1) - sub[..., :3].min(-1) <= op.get('tol', 8)) & (sub[..., :3].max(-1) >= op.get('min', 20))
                sub[gray] = op['rgba']
                arr[y0:y1, x0:x1] = sub.astype(np.uint8)
            elif op['op'] == 'grid_bg':
                # 모눈 바탕(설계도 b652): 바탕 = 줄별 값 + 열별 값 - 전체 값. 줄 값은 row_ref 가로 구간의 중앙값,
                # 열 값은 col_ref 세로 구간의 중앙값. 글자 없는 구간에서 재므로 모눈선이 이어진다.
                x0, y0, x1, y1 = op['rect']
                rx0, rx1 = op['row_ref']
                cy0, cy1 = op['col_ref']
                f = arr.astype(float)
                row = np.median(f[y0:y1, rx0:rx1], axis=1)
                col = np.median(f[cy0:cy1, x0:x1], axis=0)
                base = np.median(f[cy0:cy1, rx0:rx1].reshape(-1, 4), axis=0)
                arr[y0:y1, x0:x1] = np.clip(row[:, None] + col[None, :] - base, 0, 255).round().astype(np.uint8)
            elif op['op'] == 'fill':
                x0, y0, x1, y1 = op['rect']
                arr[y0:y1, x0:x1] = op['rgba']
            elif op['op'] == 'text':
                arr = draw_text(arr, op)
        arr = quantize(arr, t.get('pixel_format', 2))
        out = OUT / item['source'] / f"{item['block']:04d}_{item['texture']:04d}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(arr).save(out)
        rows.append({'source': item['source'], 'block': item['block'], 'texture': item['texture'],
                     'original': t['original_png'], 'patched': t['png'], 'remake': out.relative_to(ROOT).as_posix()})
    (OUT / 'index.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding='utf-8')
    print('UI 재제작', len(rows))


if __name__ == '__main__':
    main()
