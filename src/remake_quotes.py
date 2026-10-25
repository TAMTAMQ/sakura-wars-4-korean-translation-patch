"""CG_ALL1.DAT b923~b1048의 세로쓰기 명대사 이미지(640×480 ADCG)를 한국어로 다시 만든다.

원본은 투명 바탕에 흰 붓글씨 세로줄 1~3개, 어두운 적갈색(85,51,51) 번짐이 둘러싼 구조다.
대사는 대화 데이터에 없고 그림으로만 있다. 이미지 목록 밖이라 v0.8.5까지 일본어로 남아 있었다.

열 위치(가운데 x)와 열마다 시작 높이는 원본 글자 알파에서 잰다. 한국어 열이 원본보다 길어
아래(BOTTOM)를 넘으면 위로 올리고, 그래도 넘으면 블록 전체 글자 간격을 줄인다.

입력: assets/images/remake/quotes/text.json (블록 → 열을 '/'로 나눈 한국어)
출력: assets/images/remake/quotes/ADVDATA/CG_ALL1.DAT/<블록>_0000.png, index.json, 대조 시트 compare_XX.png
"""
import json
import struct
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import export_images as E
from remake_ui import font_at

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets/images/remake/quotes'
REL = 'ADVDATA/CG_ALL1.DAT'
GLOW = (85, 51, 51)
INK = (255, 255, 255)
SIZE = 22       # 원본 글자 폭 22~24px
PITCH = 22.0    # 원본 세로 간격 약 21.5px
TOP_MIN, BOTTOM = 24, 462
SS = 4
EXPANSION_REASON = ('명대사 이미지(remake_quotes.py): 한국어 세로줄이 원본 글자 타일 밖으로 나가는 칸에 64×64 타일을 더한다. '
                    '캔버스 640×480과 기존 타일 좌표는 유지한다.')
ROTATE = set('…~―「」()-')
SUBST = str.maketrans({'—': '―', '・': '·'})  # 궁서에 없는 글자
SMALL = set(',.')


def original(raw, specs, block):
    return np.asarray(E.decode_adcg(decoded(raw, specs, block))[0][1].convert('RGBA'))


def decoded(raw, specs, block):
    sig, off, packed, compressed, expected = specs[block]
    return E.decompress(packed, expected) if compressed else packed


def extra_tiles(dec, img):
    """ADCG는 그림이 있는 타일만 갖고 있다. 한국어 글자가 걸치는데 타일이 없는 칸 [(x, y)…]"""
    count = E.u32(dec, 4)
    tw, th = struct.unpack_from('<HH', dec, 8)
    table = E.u32(dec, 12)
    have = set()
    for i in range(count):
        xy = E.u32(dec, table + i * 16 + 8)
        have.add((xy & 65535, xy >> 16))
    need = []
    for y in range(0, img.shape[0], th):
        for x in range(0, img.shape[1], tw):
            if (x, y) not in have and (img[y:y + th, x:x + tw, 3] >= 8).any():  # 4444로 줄이면 알파 8 미만은 0
                need.append((x, y))
    return need


def columns(arr):
    """[(가운데 x, 위 y)…] 오른쪽 열부터"""
    core = arr[..., 3] >= 238
    xs = np.nonzero(core.any(0))[0]
    runs, s, p = [], xs[0], xs[0]
    for x in xs[1:]:
        if x > p + 3:
            runs.append((s, p))
            s = x
        p = x
    runs.append((s, p))
    out = []
    for a, b in runs:
        if b - a < 8:  # 점·쉼표 조각은 옆 열에 붙인다
            continue
        ys = np.nonzero(core[:, a:b + 1].any(1))[0]
        out.append(((a + b) / 2, int(ys.min())))
    return sorted(out, reverse=True)


def tokens(text):
    text = text.translate(SUBST)
    out, i = [], 0
    while i < len(text):
        c = text[i]
        if text[i:i + 2] in ('!!', '!?', '?!'):
            out.append(text[i:i + 2])
            i += 2
            continue
        out.append(c)
        i += 1
    return out


def advance(t):
    if t == ' ':
        return 0.4
    if t in SMALL:
        return 0.5
    return 1.0


def draw_column(mask, font, text, cx, top, pitch):
    """mask(L, SS배)에 세로줄 하나"""
    y = top
    for t in tokens(text):
        a = advance(t)
        cy = y + pitch * a / 2
        if t == ' ':
            pass
        elif t in SMALL:  # 세로쓰기 쉼표·마침표는 반 칸 오른쪽 위
            g = glyph(font, t)
            g = g.resize((int(g.width * 1.3), int(g.height * 1.3)), Image.LANCZOS)
            mask.paste(255, (int((cx + pitch * 0.3) * SS - g.width / 2), int((y - pitch * 0.05) * SS)), g)
        else:
            g = glyph(font, t)
            if t in ROTATE:
                g = g.rotate(-90, expand=True)
            mask.paste(255, (int(cx * SS - g.width / 2), int(cy * SS - g.height / 2)), g)
        y += pitch * a
    return y


def glyph(font, t):
    w = int(font.getlength(t)) + 8
    h = font.size + 8
    im = Image.new('L', (w, h), 0)
    ImageDraw.Draw(im).text((w / 2, h / 2), t, font=font, fill=255, anchor='mm')
    box = im.getbbox()
    if not box:
        return im
    if t in ROTATE or t in SMALL:
        return im.crop(box)
    # 글자 칸 가로 가운데는 유지하고 세로만 잘라 가운데 정렬
    return im.crop((0, box[1], w, box[3]))


def column_length(text, pitch):
    return sum(advance(t) for t in tokens(text)) * pitch


def layout(cols_ja, texts):
    """열마다 (x, 위 y)와 블록 간격"""
    n = len(texts)
    if len(cols_ja) >= n:
        place = cols_ja[:n]
    else:  # 열이 늘면 원본 간격으로 왼쪽에 덧붙인다
        step = (cols_ja[0][0] - cols_ja[-1][0]) / max(len(cols_ja) - 1, 1) or 33
        place = cols_ja + [(cols_ja[-1][0] - step * (k + 1), cols_ja[-1][1]) for k in range(n - len(cols_ja))]
    pitch = PITCH
    while True:
        tops = []
        for (x, top), t in zip(place, texts):
            length = column_length(t, pitch)
            top = min(top, BOTTOM - length)
            tops.append(top)
        if min(tops) >= TOP_MIN or pitch < 15:
            break
        pitch -= 0.5
    # 원본에서 열끼리 맞춰 있던 머리는 그대로 맞춘다
    shift = [t0 - t for (_, t0), t in zip(place, tops)]
    if max(shift) > 0:
        common = max(shift)
        tops = [t0 - common if abs(t0 - place[0][1]) < 6 else t for (_, t0), t in zip(place, tops)]
        tops = [max(t, TOP_MIN) for t in tops]
    return [(x, t) for (x, _), t in zip(place, tops)], pitch


def render(cols, texts, pitch):
    size = int(round(SIZE * pitch / PITCH))
    font = font_at('gungso', 0, size * SS)
    mask = Image.new('L', (640 * SS, 480 * SS), 0)
    for (x, top), t in zip(cols, texts):
        draw_column(mask, font, t, x, top, pitch)
    m = mask.resize((640, 480), Image.BOX)
    glow = m.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(2.2))
    mf = np.asarray(m, float) / 255
    gf = np.clip(np.asarray(glow, float) / 255 * 1.6, 0, 1)
    a = mf + gf * (1 - mf)
    rgb = (np.asarray(INK, float) * mf[..., None] + np.asarray(GLOW, float) * (gf * (1 - mf))[..., None]) / np.maximum(a[..., None], 1e-6)
    out = np.concatenate([np.clip(rgb, 0, 255), a[..., None] * 255], -1).round().astype(np.uint8)
    out[out[..., 3] < 8] = 0  # 4444로 0이 되는 번짐 끝은 완전 투명으로(타일 없는 칸에 색이 남지 않게)
    return out


def main():
    text = json.loads((OUT / 'text.json').read_text(encoding='utf-8'))
    raw = (ROOT / 'originals/disc' / REL).read_bytes()
    specs = E.block_specs(raw)
    rows, pairs, grown = [], [], []
    for key, item in text.items():
        if key.startswith('_'):
            continue
        b = int(key)
        old = original(raw, specs, b)
        texts = item['ko'].split('/')
        cols, pitch = layout(columns(old), texts)
        new = render(cols, texts, pitch)
        dec = decoded(raw, specs, b)
        extra = extra_tiles(dec, new)
        if extra:
            grown.append({'source': REL, 'block': b, 'original_decoded_size': len(dec),
                          'additional_tiles': [list(t) for t in extra], 'reason': EXPANSION_REASON})
        path = OUT / REL / f'{b:04d}_0000.png'
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(new, 'RGBA').save(path)
        rows.append({'source': REL, 'block': b, 'texture': 0, 'text': item['ko'],
                     'remake': path.relative_to(ROOT).as_posix()})
        pairs.append((b, old, new, pitch))
    path = ROOT / 'config/image-expansions.json'
    conf = json.loads(path.read_text(encoding='utf-8'))
    keep = [r for r in conf['blocks'] if r.get('reason') != EXPANSION_REASON]
    conf['blocks'] = keep + grown
    path.write_text(json.dumps(conf, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    (OUT / 'index.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    # 대조 시트: 한 장에 4블록, 원본 | 한국어
    bg = Image.new('RGBA', (640, 480), (40, 30, 40, 255))
    for s in range(0, len(pairs), 4):
        sheet = Image.new('RGBA', (1290, 484 * len(pairs[s:s + 4])), (90, 90, 90, 255))
        for k, (b, old, new, pitch) in enumerate(pairs[s:s + 4]):
            for j, arr in enumerate((old, new)):
                im = bg.copy()
                im.alpha_composite(Image.fromarray(arr, 'RGBA'))
                ImageDraw.Draw(im).text((6, 4), f'b{b} p{pitch:g}', fill=(255, 255, 0, 255))
                sheet.paste(im, (j * 650, k * 484))
        sheet.save(OUT / f'compare_{s // 4:02d}.png')
    print('명대사', len(rows), '타일 추가 블록', len(grown), '추가 타일', sum(len(g['additional_tiles']) for g in grown))


if __name__ == '__main__':
    main()
