"""NC_ALL1.DAT b728~b748의 시 구절과 스태프 크레딧(640×480 ADCG)을 한국어로 다시 만든다.

- 시(b728~b741): 「花の命は 短くて…」 세로쓰기 구절 하나가 텍스처 하나다. 흰 붓글씨, 번짐 없음.
  b738·b739는 b740·b741과 같은 글자를 어두운 갈색(102,85,68)으로 칠한 사본이다.
- 크레딧(b742~b748): 직함(작은 글자)과 이름(큰 글자, 자간 넓음). 흰 글자에 갈색 번짐.
b749(저작권 표기)는 라틴 문자라 그대로 둔다. 이미지 목록 밖이라 v0.8.5까지 일본어로 남아 있었다.

열·줄 위치는 원본 알파에서 잰다. 글자가 원본 타일 밖으로 나가면 config/image-expansions.json에
타일 추가를 등록한다(remake_quotes.py와 같은 방식).
출력: assets/images/remake/nc/ADVDATA/NC_ALL1.DAT/<블록>_0000.png, index.json, compare.png
"""
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import export_images as E
from remake_quotes import SUBST, decoded, extra_tiles, glyph, tokens
from remake_ui import font_at

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets/images/remake/nc'
REL = 'ADVDATA/NC_ALL1.DAT'
GLOW = (102, 85, 68)
SS = 4
EXPANSION_REASON = ('NC_ALL1 시·크레딧(remake_nc_titles.py): 한국어 글자가 원본 글자 타일 밖으로 나가는 칸에 64×64 타일을 더한다. '
                    '캔버스 640×480과 기존 타일 좌표는 유지한다.')
POEM = {728: '꽃의 목숨', 729: '짧고', 730: '꿈꾸는 세월은', 731: '달음질쳐 지나가네', 732: '아아',
        733: '잔혹한 시간이여', 734: '무자비한 것이여', 735: '허나', 736: '내 가슴에', 737: '피어나는',
        738: '그대여', 739: '꽃이여', 740: '그대여', 741: '꽃이여'}
CREDITS = {742: ['제작 총지휘', '카야마 테츠'], 743: ['총괄 프로듀서', '히로이 오지'],
           744: ['캐릭터 원안', '후지시마 코스케'], 745: ['캐릭터 디자인', '총작화 감독', '마츠바라 히데노리'],
           746: ['작곡・음악 감독', '다나카 코헤이'], 747: ['구성・각본', '아카호리 사토루'],
           748: ['각본', '카와사키 히로유키']}


def original(raw, specs, b):
    return np.asarray(E.decode_adcg(decoded(raw, specs, b))[0][1].convert('RGBA'))


def runs(mask, gap):
    idx = np.nonzero(mask)[0]
    out, s, p = [], idx[0], idx[0]
    for i in idx[1:]:
        if i > p + gap:
            out.append((s, p))
            s = i
        p = i
    out.append((s, p))
    return out


def poem(old, text):
    """세로 한 줄: 원본 글자 칸 크기·가운데 x·위 y를 그대로 쓴다"""
    a = old[..., 3] > 60
    ys, xs = np.nonzero(a)
    cx = (xs.min() + xs.max()) / 2
    cell = xs.max() - xs.min() + 1
    pitch = cell * 0.9
    color = old[old[..., 3] >= 200][:, :3].mean(0) if (old[..., 3] >= 200).any() else old[a][:, :3].mean(0)
    font = font_at('gungso', 0, int(cell * 0.82) * SS)
    mask = Image.new('L', (640 * SS, 480 * SS), 0)
    y = ys.min()
    for t in tokens(text):
        if t == ' ':
            y += pitch * 0.4
            continue
        g = glyph(font, t)
        mask.paste(255, (int(cx * SS - g.width / 2), int((y + pitch / 2) * SS - g.height / 2)), g)
        y += pitch
    m = np.asarray(mask.resize((640, 480), Image.BOX), float) / 255
    out = np.zeros((480, 640, 4), np.uint8)
    out[..., :3] = np.round(color).astype(np.uint8)
    out[..., 3] = np.round(m * 255).astype(np.uint8)
    out[out[..., 3] < 8] = 0
    return out


def credit(old, lines):
    """직함·이름 줄: 원본 줄마다 왼쪽 x·가운데 y·글자 높이를 잰다(이름은 마지막 줄)"""
    a = old[..., 3] >= 136
    rows = runs(a.any(1), 3)
    if len(rows) != len(lines):
        raise SystemExit(f'줄 수 불일치 {len(rows)} != {len(lines)}')
    plan = []
    for k, ((y0, y1), text) in enumerate(zip(rows, lines)):
        xs = np.nonzero(a[y0:y1 + 1].any(0))[0]
        h = y1 - y0 + 1
        font = font_at('gothic', 0, int(round(h * 1.05)) * SS)
        track = (3 if k == len(lines) - 1 else 1) * SS  # 이름 줄은 원본처럼 자간을 넓힌다
        text = text.translate(SUBST)
        width = sum(font.getlength(c) + track for c in text) - track
        span = (xs.max() - xs.min() + 1) * SS
        if width > span and track > SS:  # 원본 줄보다 길면 자간을 줄여 원본 타일 안에 머물게 한다
            width -= (track - SS) * (len(text) - 1)
            track = SS
        if width > span * 1.15:  # 그래도 많이 넘치면 글자를 줄인다(원본 높이의 85%까지)
            scale = max(0.85, span * 1.15 / width)
            font = font_at('gothic', 0, int(round(h * 1.05 * scale)) * SS)
            width = sum(font.getlength(c) + track for c in text) - track
        plan.append((xs.min() * SS, (y0 + y1 + 1) / 2 * SS, font, track, text, width))
    # 한국어가 길어 오른쪽 끝(632px)을 넘으면 블록 전체를 왼쪽으로 옮긴다(줄 머리 정렬 유지)
    shift = max(0, max(x + w for x, _, _, _, _, w in plan) - 632 * SS)
    shift = min(shift, min(x for x, *_ in plan) - 4 * SS)
    mask = Image.new('L', (640 * SS, 480 * SS), 0)
    d = ImageDraw.Draw(mask)
    for x, y, font, track, text, width in plan:
        x -= shift
        for c in text:
            if c != ' ':
                d.text((x, y), c, font=font, fill=255, anchor='lm')
            x += font.getlength(c) + track
    m = mask.resize((640, 480), Image.BOX)
    glow = m.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(1.2))
    mf = np.asarray(m, float) / 255
    gf = np.clip(np.asarray(glow, float) / 255 * 1.4, 0, 1)
    al = mf + gf * (1 - mf)
    rgb = (255 * mf[..., None] + np.asarray(GLOW, float) * (gf * (1 - mf))[..., None]) / np.maximum(al[..., None], 1e-6)
    out = np.concatenate([np.clip(rgb, 0, 255), al[..., None] * 255], -1).round().astype(np.uint8)
    out[out[..., 3] < 8] = 0
    return out


def main():
    raw = (ROOT / 'originals/disc' / REL).read_bytes()
    specs = E.block_specs(raw)
    rows, pairs, grown = [], [], []
    for b, text in {**POEM, **CREDITS}.items():
        old = original(raw, specs, b)
        new = poem(old, text) if b in POEM else credit(old, text)
        dec = decoded(raw, specs, b)
        extra = extra_tiles(dec, new)
        if extra:
            grown.append({'source': REL, 'block': b, 'original_decoded_size': len(dec),
                          'additional_tiles': [list(t) for t in extra], 'reason': EXPANSION_REASON})
        path = OUT / REL / f'{b:04d}_0000.png'
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(new, 'RGBA').save(path)
        rows.append({'source': REL, 'block': b, 'texture': 0, 'text': text if isinstance(text, str) else '/'.join(text),
                     'remake': path.relative_to(ROOT).as_posix()})
        pairs.append((b, old, new))
    conf_path = ROOT / 'config/image-expansions.json'
    conf = json.loads(conf_path.read_text(encoding='utf-8'))
    conf['blocks'] = [r for r in conf['blocks'] if r.get('reason') != EXPANSION_REASON] + grown
    conf_path.write_text(json.dumps(conf, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    (OUT / 'index.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    # 대조 시트: 블록마다 글자 영역만 원본 | 한국어
    tiles = []
    for b, old, new in pairs:
        al = (old[..., 3] > 0) | (new[..., 3] > 0)
        ys, xs = np.nonzero(al)
        box = (max(xs.min() - 6, 0), max(ys.min() - 6, 0), min(xs.max() + 7, 640), min(ys.max() + 7, 480))
        ims = []
        for arr in (old, new):
            im = Image.new('RGBA', (box[2] - box[0], box[3] - box[1]), (40, 40, 90, 255))
            im.alpha_composite(Image.fromarray(arr, 'RGBA').crop(box))
            ims.append(im.resize((im.width * 2, im.height * 2), Image.NEAREST))
        tiles.append((b, ims))
    W = 1800
    x = y = rowh = 0
    pos = []
    for b, (o, n) in tiles:
        w = o.width + n.width + 30
        if x + w > W:
            x, y, rowh = 0, y + rowh + 16, 0
        pos.append((x, y, b, o, n))
        x += w
        rowh = max(rowh, o.height)
    sheet = Image.new('RGBA', (W, y + rowh + 16), (90, 90, 90, 255))
    for x, y, b, o, n in pos:
        sheet.alpha_composite(o, (x, y + 14))
        sheet.alpha_composite(n, (x + o.width + 6, y + 14))
        ImageDraw.Draw(sheet).text((x, y), f'b{b}', fill=(255, 255, 0, 255))
    sheet.save(OUT / 'compare.png')
    print('NC 시·크레딧', len(rows), '타일 추가 블록', len(grown))


if __name__ == '__main__':
    main()
