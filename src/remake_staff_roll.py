"""스태프롤 큰 글자를 원본 디자인으로 다시 그린다.

원본: 칸 가장자리 10~12px 안을 꽉 채운 굵은 명조, 글자색 (238,238,238),
바깥쪽 약 10px에 걸쳐 갈색 (85,51,17) 번짐이 투명도 0→약 190으로 퍼진다.
v0.5의 한국어 음절을 같은 방식으로 그리고 ARGB4444 단계로 양자화한다.

입력: assets/images/remake/staffroll.json
출력: assets/images/remake/staffroll/<블록>_0000.png, index.json
"""
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'assets/images/remake/staffroll.json'
OUT = ROOT / 'assets/images/remake/staffroll'
SS = 4
INK = 238
GLOW = (85, 51, 17)
GLOW_MAX = 190 / 255
MIN_ASPECT = 0.62  # 두 음절일 때 가로를 이 비율까지 좁혀 칸을 더 채운다


def font_at(cfg, px):
    f = ImageFont.truetype(cfg['path'], px)
    try:
        f.set_variation_by_axes([cfg['weight']])
    except Exception:
        pass
    return f


def ink_box(arr):
    ys, xs = np.where(arr[..., 3] > 200)
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1


def glyph_mask(text, box_w, box_h, font_cfg):
    """text를 box에 맞춘 마스크(0~1, box 크기)."""
    size = box_h * SS
    font = font_at(font_cfg, size)
    l, t, r, b = font.getbbox(text)
    layer = Image.new('L', (r - l + 8, b - t + 8), 0)
    ImageDraw.Draw(layer).text((4 - l, 4 - t), text, font=font, fill=255)
    layer = layer.crop(layer.getbbox())
    tw, th = box_w * SS, box_h * SS
    scale = min(tw / layer.width, th / layer.height)
    w, h = layer.width * scale, layer.height * scale
    if w < tw and h >= th - 1:
        pass
    elif h < th:
        # 가로가 꽉 찼으면 세로를 키우고 가로를 MIN_ASPECT까지 눌러 칸을 채운다
        grow = min(th / h, 1 / MIN_ASPECT)
        h *= grow
    layer = layer.resize((max(1, round(w)), max(1, round(h))), Image.LANCZOS)
    canvas = Image.new('L', (tw, th), 0)
    canvas.paste(layer, ((tw - layer.width) // 2, (th - layer.height) // 2))
    return np.asarray(canvas.resize((box_w, box_h), Image.BOX), dtype=np.float64) / 255


def render(text, w, h, box, font_cfg):
    x0, y0, x1, y1 = box
    mask = np.zeros((h, w))
    mask[y0:y1, x0:x1] = glyph_mask(text, x1 - x0, y1 - y0, font_cfg)
    m = Image.fromarray((mask * 255).astype(np.uint8))
    halo = m.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(4))
    glow = np.clip(np.asarray(halo, dtype=np.float64) / 255 * 1.6, 0, 1) * GLOW_MAX
    a = mask + glow * (1 - mask)
    rgba = np.zeros((h, w, 4))
    for c in range(3):
        rgba[..., c] = np.where(a > 0, (INK * mask + GLOW[c] * glow * (1 - mask)) / np.maximum(a, 1e-6), GLOW[c])
    rgba[..., 3] = a * 255
    return np.clip(np.round(rgba / 17) * 17, 0, 255).astype(np.uint8)


# 압축 크기를 줄이는 단계. 원래 2048 자리에 들어갈 때까지 순서대로 시도한다.
#   0: 그대로 / 1: 색을 흰 글자·갈색 번짐 두 색으로 / 2~5: 번짐 투명도를 6~… 단계로 줄임
LEVELS = [None, 0, 34, 51, 68, 85]


def simplify(arr, level):
    if LEVELS[level] is None:
        return arr
    a = arr.astype(int).copy()
    glyph = a[..., 0] > 160
    a[..., :3] = np.where(glyph[..., None], [INK] * 3, list(GLOW))
    step = LEVELS[level]
    if step:
        a[..., 3] = np.where(glyph, 255, np.round(a[..., 3] / step) * step)
    return np.clip(a, 0, 255).astype(np.uint8)


def fit(block, arr):
    """CG_ALL1의 원래 레코드 자리에 들어가는 가장 덜 단순화한 이미지를 고른다."""
    import struct
    import export_images as E
    import inject_images as I
    from prs_compress import compress_optimal
    raw = (ROOT / 'originals/v05/ADVDATA/CG_ALL1.DAT').read_bytes()
    specs = E.block_specs(raw)
    off = specs[block][1]
    _, _, b = struct.unpack_from('<III', raw, off + 4)
    tail = raw[off + 16 + b:specs[block + 1][1]]
    room = b + tail.find(b'AGR1') - 16  # 페이로드(4정렬) + CPRS/EOFC 16바이트
    dec, _ = I.decode_block(specs[block])
    for level in range(len(LEVELS)):
        cand = simplify(arr, level)
        size = len(compress_optimal(I.rebuild_adcg(dec, cand)))
        if size + (-size % 4) <= room:
            return cand, level, size, room
    raise ValueError(f'블록 {block}: 가장 단순화해도 {size} > {room}')


def keep_inside(arr, orig):
    """글자(빛 포함)를 원본 글자 범위 안으로 넣는다(넘치면 줄이고 원본 범위 가운데로).
    원본보다 1~2px 넓게 퍼져 텍스처 가장자리에 닿는 것이 있었다."""
    def box(a):
        m = a[..., 3] > 20
        ys, xs = np.where(m.any(1))[0], np.where(m.any(0))[0]
        return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
    ox0, oy0, ox1, oy1 = box(orig)
    rx0, ry0, rx1, ry1 = box(arr)
    s = min(1.0, (ox1 - ox0) / (rx1 - rx0), (oy1 - oy0) / (ry1 - ry0))
    im = Image.fromarray(arr).crop((rx0, ry0, rx1, ry1))
    if s < 1:
        im = im.resize((max(1, int((rx1 - rx0) * s)), max(1, int((ry1 - ry0) * s))), Image.LANCZOS)
    out = Image.new('RGBA', (arr.shape[1], arr.shape[0]), (0, 0, 0, 0))
    out.paste(im, (ox0 + (ox1 - ox0 - im.width) // 2, oy0 + (oy1 - oy0 - im.height) // 2))
    return np.asarray(out).copy()


def main():
    cfg = json.loads(CONFIG.read_text(encoding='utf-8'))
    index = json.loads((ROOT / 'assets/extracted/images/index.json').read_text(encoding='utf-8'))
    tex = {(t['source'], t['block'], t['texture']): t for t in index['textures']}
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for block, text in cfg['blocks'].items():
        t = tex[(cfg['source'], int(block), 0)]
        orig = np.asarray(Image.open(ROOT / t['original_png']).convert('RGBA'))
        h, w = orig.shape[:2]
        arr = render(text, w, h, ink_box(orig), cfg['font'])
        arr, level, size, room = fit(int(block), arr)
        arr = keep_inside(arr, orig)
        out = OUT / f'{int(block):04d}_0000.png'
        Image.fromarray(arr).save(out)
        rows.append({'source': cfg['source'], 'block': int(block), 'texture': 0, 'text': text,
                     'original': t['original_png'], 'patched': t['png'], 'remake': out.relative_to(ROOT).as_posix(),
                     'simplify_level': level, 'compressed': size, 'room': room})
    (OUT / 'index.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding='utf-8')
    print('스태프롤 재제작', len(rows))


if __name__ == '__main__':
    main()
