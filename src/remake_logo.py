"""『サクラ大戦』 로고를 한글 로고로 다시 만든다.

참고 이미지(한글 디자인 참고용 로고.png) 방식: 가타카나 「サクラ」만 같은
느낌의 한글 「사쿠라」로 바꾸고, 「大戦」 한자는 그대로 둔 채 아래에 작은
「대」「전」 이름표를 붙인다. 부제는 한국어로 다시 쓴다.

「사쿠라」 채움은 원본 サクラ 글자의 붉은 대리석 무늬를 늘려 쓰고, 검은
테두리·밝은 바깥선·그림자를 원본처럼 겹친다.

입력: assets/images/remake/logo.json
출력: assets/images/remake/logo/<컨테이너>/<블록>_<텍스처>.png, index.json
"""
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'assets/images/remake/logo.json'
OUT = ROOT / 'assets/images/remake/logo'
SS = 4
BRUSH = 'C:/Windows/Fonts/H2GSRB.TTF'      # HY궁서 B: 붓글씨
SANS = 'C:/Windows/Fonts/NotoSansKR-VF.ttf'
WORD_MASK = ROOT / 'assets/images/remake/logo_sakura_mask.png'


def font(path, px, weight=None):
    f = ImageFont.truetype(path, px)
    if weight:
        f.set_variation_by_axes([weight])
    return f


def text_mask(text, w, h, path, bold, weight=None, shear=0.0, track=0.0):
    """rect(w×h)에 꽉 차게 그린 글자 마스크(0~1). bold는 rect 높이 대비 굵기 보강 비율."""
    W, H = w * SS, h * SS
    f = font(path, H, weight)
    layer = Image.new('L', (W * 3, H * 3), 0)
    d = ImageDraw.Draw(layer)
    x = W * 0.2
    for c in text:
        d.text((x, H), c, font=f, fill=255)
        x += f.getlength(c) + track * H
    if bold:
        r = max(1, int(bold * H)) | 1
        layer = layer.filter(ImageFilter.MaxFilter(r))
    if shear:
        layer = layer.transform(layer.size, Image.AFFINE, (1, shear, -shear * H * 1.5, 0, 1, 0), Image.BICUBIC)
    layer = layer.crop(layer.getbbox())
    layer = layer.resize((W, H), Image.LANCZOS)
    return np.asarray(layer.resize((w, h), Image.BOX), float) / 255


def red_field(arr, rect):
    """rect 안의 원본 붉은 글자 픽셀 색을 rect 전체로 번지게 한 채움 무늬."""
    x0, y0, x1, y1 = rect
    sub = arr[y0:y1, x0:x1, :3].copy()
    r, g, b = [sub[..., i].astype(int) for i in range(3)]
    red = (r > g + 60) & (r > b + 30) & (g < 100) & (b < 130) & (arr[y0:y1, x0:x1, 3] > 200)  # 주황·분홍 제외
    sub[~red] = 0
    filled = cv2.inpaint(sub, (~red).astype(np.uint8) * 255, 9, cv2.INPAINT_TELEA)
    return filled.astype(float) / 255


def shift(m, dx, dy):
    out = np.zeros_like(m)
    h, w = m.shape
    out[max(dy, 0):h + min(dy, 0), max(dx, 0):w + min(dx, 0)] = m[max(-dy, 0):h - max(dy, 0), max(-dx, 0):w - max(dx, 0)]
    return out


def grow(m, px):
    if px <= 0:
        return m
    k = np.ones((2 * px + 1, 2 * px + 1), np.uint8)
    return cv2.dilate((m * 255).astype(np.uint8), k).astype(float) / 255


def blur(m, s):
    return np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(s)), float) / 255


def over(dst, rgb, a):
    a = np.clip(a, 0, 1)[..., None]
    out_a = a + dst[..., 3:4] * (1 - a)
    col = (rgb * a + dst[..., :3] * dst[..., 3:4] * (1 - a)) / np.maximum(out_a, 1e-6)
    return np.concatenate([col, out_a], -1)


def styled(dst, mask, fill_rgb, s, light=(0.86, 0.92, 0.95), thin=1.0):
    """원본 로고 글자 효과: 그림자 → 밝은 바깥선 → 검은 테두리 → 채움."""
    black = grow(mask, max(1, round(1.6 * s * thin)))
    lightm = grow(mask, max(2, round(2.6 * s * thin)))
    sh = blur(shift(lightm, round(2.5 * s), round(2.5 * s)), 1.2 * s) * 0.75
    dst = over(dst, np.zeros(3), sh)
    dst = over(dst, np.array(light), lightm)
    dst = over(dst, np.zeros(3), black)
    if fill_rgb.ndim == 1:
        fill_rgb = np.broadcast_to(fill_rgb, mask.shape + (3,))
    a = mask[..., None]
    out_a = a + dst[..., 3:4] * (1 - a)
    col = (fill_rgb * a + dst[..., :3] * dst[..., 3:4] * (1 - a)) / np.maximum(out_a, 1e-6)
    return np.concatenate([col, out_a], -1)


def gloss(field, mask, s):
    """채움에 위쪽 광택을 조금 넣는다."""
    edge = mask - shift(mask, 0, max(1, round(2 * s)))
    hi = np.clip(blur(np.clip(edge, 0, 1), s), 0, 1)[..., None] * 0.45
    return field * (1 - hi) + hi


def tag(dst, rect, text, s):
    """「大」「戦」 아래 작은 이름표: 테두리 있는 어두운 상자 + 흰 글자."""
    x0, y0, x1, y1 = rect
    h, w = dst.shape[:2]
    box = np.zeros((h, w))
    im = Image.new('L', (w * SS, h * SS), 0)
    ImageDraw.Draw(im).rounded_rectangle((x0 * SS, y0 * SS, x1 * SS, y1 * SS), radius=int(3 * s * SS), fill=255)
    box = np.asarray(im.resize((w, h), Image.BOX), float) / 255
    sh = blur(shift(grow(box, 1), round(2 * s), round(2 * s)), s) * 0.6
    dst = over(dst, np.zeros(3), sh)
    dst = over(dst, np.array([0.97, 0.97, 1.0]), grow(box, max(1, round(1.2 * s))))
    dst = over(dst, np.zeros(3), grow(box, max(1, round(0.5 * s))))
    dst = over(dst, np.array([0.20, 0.10, 0.38]), box)
    pad = max(1, round(1.5 * s))
    m = np.zeros((h, w))
    m[y0 + pad:y1 - pad, x0 + pad:x1 - pad] = text_mask(text, x1 - x0 - 2 * pad, y1 - y0 - 2 * pad, SANS, 0, 900)
    return over(dst, np.array([1.0, 0.92, 0.96]), m)


# CG_ALL1 #733(640×480 투명 로고, 배율 1) 기준 좌표. 다른 사본은 transform [배율, x, y]로 옮긴다.
MASTER = {
    'kana_rect': [4, 48, 206, 200],
    'letters': [['사', [6, 54, 76, 188]], ['쿠', [74, 64, 142, 172]], ['라', [140, 60, 210, 168]]],
    # 참고 로고에서 뽑은 「사쿠라」 글자 모양(사의 ㅏ는 라의 ㅏ를 늘려 기본 길이로)
    'word_rect': [11, 44, 224, 182],  # x=0에서 시작하면 사의 테두리가 텍스처 밖으로 잘렸다
    'tags': [[[290, 148, 322, 176], '대'], [[360, 148, 392, 176], '전']],
    'protect': [70, 160, 330, 202],  # 「Sakura Wars」 자리: 붉은 サ 획만 지운다
}


_LAYER = None

# 원본 サクラ 안쪽 색(#733 측정): 바탕 진홍 (238,17,85), 밝은 광택 (255,102,187)
FILL_BASE = np.array([238, 17, 85]) / 255
FILL_DARK = np.array([170, 0, 60]) / 255
FILL_SHINE = np.array([255, 110, 190]) / 255


def sakura_fill(mask, seed=4):
    """「사쿠라」 글자 안 채움: 진홍 바탕 + 가장자리 어둡게 + 원본처럼 비스듬한 그라데이션 광택 줄."""
    h, w = mask.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(float)
    field = np.broadcast_to(FILL_BASE, (h, w, 3)).copy()
    # 가장자리 쪽 어둡게(획 안쪽 그림자)
    inside = (mask > 0.5).astype(np.uint8)
    dist = cv2.distanceTransform(inside, cv2.DIST_L2, 3)
    edge = np.clip(1 - dist / 4, 0, 1)[..., None] * 0.55
    field = field * (1 - edge) + FILL_DARK * edge
    # 원본처럼 오른쪽 위→왼쪽 아래로 흐르는 광택 줄
    rng = np.random.default_rng(seed)
    t = xx * 0.6 + yy * 0.8
    shine = np.zeros((h, w))
    for c in rng.uniform(t[mask > 0.5].min(), t[mask > 0.5].max(), 7):
        width = rng.uniform(2.5, 6)
        shine = np.maximum(shine, np.exp(-((t - c) / width) ** 2) * rng.uniform(0.35, 0.7))
    shine *= np.clip(dist / 3, 0, 1)
    field = field * (1 - shine[..., None]) + FILL_SHINE * shine[..., None]
    return field



def master_layer():
    """#733 원본의 붉은 무늬로 칠한 「사쿠라」를 투명 바탕(640×480)에 그린 RGBA(0~1)."""
    global _LAYER
    if _LAYER is not None:
        return _LAYER
    index = json.loads((ROOT / 'assets/extracted/images/index.json').read_text(encoding='utf-8'))
    t = next(t for t in index['textures'] if (t['source'], t['block'], t['texture']) == ('ADVDATA/CG_ALL1.DAT', 733, 0))
    arr = np.asarray(Image.open(ROOT / t['original_png']).convert('RGBA'))
    h, w = arr.shape[:2]
    kr, wr = MASTER['kana_rect'], MASTER['word_rect']
    fr = [max(0, min(kr[0], wr[0])), max(0, min(kr[1], wr[1])), min(w, max(kr[2], wr[2])), min(h, max(kr[3], wr[3]))]
    wx0, wy0, wx1, wy1 = wr
    wm = Image.open(WORD_MASK).convert('L').filter(ImageFilter.GaussianBlur(2))
    wm = wm.resize((wx1 - wx0, wy1 - wy0), Image.LANCZOS)
    wm = np.clip((np.asarray(wm, float) / 255 - 0.62) * 4 + 0.5, 0, 1)
    mask = np.zeros((h, w))
    mask[wy0:wy1, wx0:wx1] = wm
    # 원본 サクラ의 무늬를 옮기면 옛 획 경계가 흔적으로 남는다 → 채움을 새로 그린다
    field = sakura_fill(mask)
    _LAYER = styled(np.zeros((h, w, 4)), mask, gloss(field, mask, 1.0), 1.0, thin=0.6)
    Image.fromarray((_LAYER * 255).astype(np.uint8)).save(ROOT / 'assets/images/remake/logo_sakura_layer.png')
    return _LAYER


def footprints(transform, h, w):
    """#733 기준 サクラ 자리와 새 「사쿠라」 층의 불투명 자리를 대상 텍스처 좌표로 옮긴다(0/255)."""
    k, ox, oy = transform
    index = json.loads((ROOT / 'assets/extracted/images/index.json').read_text(encoding='utf-8'))
    t = next(t for t in index['textures'] if (t['source'], t['block'], t['texture']) == ('ADVDATA/CG_ALL1.DAT', 733, 0))
    src = np.asarray(Image.open(ROOT / t['original_png']).convert('RGBA'))
    kx0, ky0, kx1, ky1 = MASTER['kana_rect']
    kana = np.zeros(src.shape[:2], np.uint8)
    kana[ky0:ky1, kx0:kx1] = (src[ky0:ky1, kx0:kx1, 3] > 0) * 255
    cover = (master_layer()[..., 3] > 0.85).astype(np.uint8) * 255
    cover = cv2.erode(cover, np.ones((3, 3), np.uint8))
    M = np.float32([[k, 0, ox], [0, k, oy]])
    f = lambda m: cv2.warpAffine(m, M, (w, h), flags=cv2.INTER_LINEAR)
    return (f(kana) > 40).astype(np.uint8) * 255, (f(cover) > 200).astype(np.uint8) * 255


def place(item):
    if 'transform' not in item:
        return item
    k, ox, oy = item['transform']
    f = lambda r: [round(ox + r[0] * k), round(oy + r[1] * k), round(ox + r[2] * k), round(oy + r[3] * k)]
    out = dict(item)
    out['kana_rect'] = f(MASTER['kana_rect'])
    out['letters'] = [[c, f(r)] for c, r in MASTER['letters']]
    out['word_rect'] = f(MASTER['word_rect'])
    out['tags'] = [[f(r), c] for r, c in MASTER['tags']]
    out['protect'] = f(MASTER['protect'])
    out['scale'] = k
    return out


def run(item):
    item = place(item)
    index = json.loads((ROOT / 'assets/extracted/images/index.json').read_text(encoding='utf-8'))
    t = next(t for t in index['textures'] if (t['source'], t['block'], t['texture']) == (item['source'], item['block'], item['texture']))
    # base_image: 다른 재제작 단계(예: 대원 명단 글자) 결과 위에 로고만 다시 만든다
    arr = np.asarray(Image.open(ROOT / item.get('base_image', t['original_png'])).convert('RGBA')).copy()
    s = item.get('scale', 1.0)
    h, w = arr.shape[:2]
    kx0, ky0, kx1, ky1 = item['kana_rect']
    field = np.zeros((h, w, 3))
    fr = list(item['kana_rect'])
    if 'word_rect' in item:  # 새 글자가 kana 영역 밖으로 나가도 채움 무늬가 닿게 넓힌다
        fr = [max(0, min(fr[0], item['word_rect'][0])), max(0, min(fr[1], item['word_rect'][1])),
              min(w, max(fr[2], item['word_rect'][2])), min(h, max(fr[3], item['word_rect'][3]))]
    field[fr[1]:fr[3], fr[0]:fr[2]] = red_field(arr, fr)
    # サクラ 지우기: 투명 바탕이면 투명하게, 그림 바탕이면 인페인팅
    erase = np.zeros((h, w), np.uint8)
    sub = arr[ky0:ky1, kx0:kx1].astype(int)
    m = sub[..., 3] > 0
    r, g, b = sub[..., 0], sub[..., 1], sub[..., 2]
    glyph = m & (((r > g + 50) & (r > b + 20)) | (sub[..., :3].max(-1) < 60) | ((sub[..., :3].min(-1) > 170) & (np.ptp(sub[..., :3], -1) < 40)))
    if 'dark_below' in item:  # 그림 바탕: 원본 글자의 회색 그림자·외곽까지 지운다
        lum = sub[..., :3] @ np.array([0.299, 0.587, 0.114])
        glyph |= m & (lum < item['dark_below'])
    if item.get('erase_all', True):
        glyph = m
    orange = (r > 200) & (g > 100) & (g < 200) & (b < 80)  # 「Sakura Wars」 주황 글자는 남긴다
    glyph &= ~orange
    erase[ky0:ky1, kx0:kx1] = glyph
    erase = cv2.dilate(erase * 255, np.ones((3, 3), np.uint8))
    erase[ky0:ky1, kx0:kx1][orange] = 0
    if 'protect' in item:
        x0, y0, x1, y1 = item['protect']
        sub = arr[y0:y1, x0:x1].astype(int)
        red = (sub[..., 0] > sub[..., 1] + 50) & (sub[..., 0] > sub[..., 2] + 20)
        keep = np.zeros(arr.shape[:2], bool)
        keep[y0:y1, x0:x1] = ~cv2.dilate(red.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
        erase[keep] = 0
    if 'blue_erase' in item:  # 파란 글자(ジャン)와 그 테두리
        x0, y0, x1, y1 = item['blue_erase']
        sub = arr[y0:y1, x0:x1].astype(int)
        blue = (sub[..., 2] > sub[..., 0] + 60) | (sub[..., :3].max(-1) < 70)
        m2 = np.zeros(arr.shape[:2], np.uint8)
        m2[y0:y1, x0:x1] = blue
        blue_mask = cv2.dilate(m2 * 255, np.ones((7, 7), np.uint8))
        erase |= blue_mask
    for ex in item.get('erase_extra', []):
        x0, y0, x1, y1 = ex
        erase[y0:y1, x0:x1] = 255
    if 'transform' in item:
        # 지울 곳 = #733에서 잰 サクラ 자리(그림자 포함)만. 사각형으로 넓게 지우면 배경이 번진다.
        foot, cover = footprints(item['transform'], h, w)
        k = item['transform'][0]
        foot = cv2.dilate(foot, np.ones((3, 3), np.uint8)) if k >= 0.5 else foot
        sub = arr.astype(int)
        orange_all = (sub[..., 0] > 200) & (sub[..., 1] > 100) & (sub[..., 1] < 200) & (sub[..., 2] < 80)
        keep = blue_mask if 'blue_erase' in item else np.zeros_like(erase)
        # 덮일 자리까지 함께 지워야 인페인팅이 옛 붉은 획을 끌어오지 않는다(새 글자가 그 위를 덮는다)
        erase = ((foot > 0) & ~orange_all).astype(np.uint8) * 255 | keep
    if item.get('background') == 'transparent':
        arr[erase > 0] = 0
    else:
        rgb = cv2.inpaint(np.ascontiguousarray(arr[..., :3]), erase, 3, cv2.INPAINT_TELEA)
        a = cv2.inpaint(np.ascontiguousarray(arr[..., 3]), erase, 3, cv2.INPAINT_TELEA)
        arr[..., :3] = rgb
        arr[..., 3] = a
    dst = arr.astype(float) / 255
    # 사쿠라
    mask = np.zeros((h, w))
    if item.get('word_mask', True) and 'word_rect' in item:
        # 한 번 만든 「사쿠라」 층(#733 배율 1)을 그대로 줄여 붙인다: 크기만 다르고 모양·테두리 비율이 같다
        k, ox, oy = item.get('transform', [1, 0, 0])
        layer = master_layer()
        mx0, my0, mx1, my1 = MASTER['word_rect']
        pad = 10
        bx0, by0, bx1, by1 = max(mx0 - pad, 0), max(my0 - pad, 0), mx1 + pad, my1 + pad
        crop = Image.fromarray((layer[by0:by1, bx0:bx1] * 255).astype(np.uint8))
        nw, nh = max(1, round((bx1 - bx0) * k)), max(1, round((by1 - by0) * k))
        crop = crop.resize((nw, nh), Image.LANCZOS) if k != 1 else crop
        base = Image.fromarray((np.clip(dst, 0, 1) * 255).astype(np.uint8))
        base.alpha_composite(crop, (round(ox + bx0 * k), round(oy + by0 * k)))
        dst = np.asarray(base).astype(float) / 255
        letters = []
    else:
        letters = item.get('letters') or [['사쿠라', item['sakura_rect']]]
    for ch, (lx0, ly0, lx1, ly1) in letters:  # 글자마다 따로 효과를 입혀 겹친 곳도 테두리로 갈린다
        mask = np.zeros((h, w))
        mask[ly0:ly1, lx0:lx1] = text_mask(ch, lx1 - lx0, ly1 - ly0, item.get('font', BRUSH), item.get('bold', 0.03), shear=item.get('shear', 0.0))
        dst = styled(dst, mask, gloss(field, mask, s), s)
    for ex in item.get('extra', []):  # 예: 미니게임 로고 「ジャン」 → 「장」(파란 그라데이션)
        ch, (lx0, ly0, lx1, ly1), top, bot = ex['text'], ex['rect'], np.array(ex['top']) / 255, np.array(ex['bottom']) / 255
        mask = np.zeros((h, w))
        mask[ly0:ly1, lx0:lx1] = text_mask(ch, lx1 - lx0, ly1 - ly0, item.get('font', BRUSH), item.get('bold', 0.03), shear=item.get('shear', 0.0))
        tt = np.clip((np.arange(h) - ly0) / max(1, ly1 - ly0), 0, 1)[:, None, None]
        grad = np.broadcast_to(top * (1 - tt) + bot * tt, (h, w, 3))
        dst = styled(dst, mask, gloss(grad.copy(), mask, s), s)
    for rect, txt in item.get('tags', []):
        dst = tag(dst, rect, txt, s)
    for op in item.get('subtitle', []):
        x0, y0, x1, y1 = op['erase']
        # 띠 안쪽 줄 전체를 그 줄의 띠 색 하나로 칠한다(옅은 획 가장자리까지 남지 않게).
        # 지정한 범위 위아래로 띠 색 줄이 이어지면 거기까지 넓힌다.
        band = np.array(op['band'])
        img = (dst * 255).astype(int)
        def row_ok(y):
            row = img[y, x0:x1, :3]
            near = np.abs(row - band).sum(-1) < 60
            return near.mean() > 0.5
        while y0 > 0 and row_ok(y0 - 1):
            y0 -= 1
        while y1 < h and row_ok(y1):
            y1 += 1
        for y in range(y0, y1):
            row = img[y, x0:x1]
            near = np.abs(row[:, :3] - band).sum(-1) < 40
            col = np.median(row[near], 0) if near.any() else np.append(band, 255)
            dst[y, x0:x1] = col / 255
        tx0, ty0, tx1, ty1 = op['rect']
        f = font(op.get('font', 'C:/Windows/Fonts/NotoSerifKR-VF.ttf'), op['size'] * SS, op.get('weight', 700))
        L = Image.new('L', ((tx1 - tx0) * SS, (ty1 - ty0) * SS), 0)
        dd = ImageDraw.Draw(L)
        total = sum(f.getlength(c) for c in op['text']) + op.get('track', 0) * SS * (len(op['text']) - 1)
        x = ((tx1 - tx0) * SS - total) / 2
        bb = f.getbbox('한')
        y = ((ty1 - ty0) * SS - (bb[3] - bb[1])) / 2 - bb[1]
        for c in op['text']:
            dd.text((x, y), c, font=f, fill=255)
            x += f.getlength(c) + op.get('track', 0) * SS
        mm = np.zeros((h, w))
        mm[ty0:ty1, tx0:tx1] = np.asarray(L.resize((tx1 - tx0, ty1 - ty0), Image.BOX), float) / 255
        dst = over(dst, np.array(op['color']) / 255, mm)
    out = np.clip(np.round(dst * 255), 0, 255).astype(np.uint8)
    pf = t.get('pixel_format', 2)
    if pf == 2:
        out = (np.round(out.astype(int) / 17) * 17).clip(0, 255).astype(np.uint8)
    elif pf == 1:
        q = out.astype(int)
        q[..., 0] = np.round(q[..., 0] * 31 / 255) * 255 // 31
        q[..., 1] = np.round(q[..., 1] * 63 / 255) * 255 // 63
        q[..., 2] = np.round(q[..., 2] * 31 / 255) * 255 // 31
        q[..., 3] = 255
        out = q.astype(np.uint8)
    path = OUT / item['source'] / f"{item['block']:04d}_{item['texture']:04d}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(out).save(path)
    return {'source': item['source'], 'block': item['block'], 'texture': item['texture'],
            'original': t['original_png'], 'patched': t['png'], 'remake': path.relative_to(ROOT).as_posix()}


def main():
    cfg = json.loads(CONFIG.read_text(encoding='utf-8'))
    rows = [run(item) for item in cfg['items']]
    (OUT / 'index.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding='utf-8')
    print('로고 재제작', len(rows))


if __name__ == '__main__':
    main()
