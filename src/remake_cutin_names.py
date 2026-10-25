"""합체 공격 컷인의 이름판(SLG/UNITS/*_S_N.BC)을 한국어로 다시 만든다.

이름판은 64×64 VQ 텍스처(ARGB4444)에 32px 높이 띠로 들어 있다. 한 줄 이름 띠(폭 64×조각 수)를
64px씩 잘라 텍스처 t1 위·아래, t0 위·아래 순서로 채운 구조다(텍스처가 하나면 t0 위·아래).
블록마다 「大神一郎」와 대원 이름이 하나씩 있다. 바탕은 검정 반투명(알파 136), 글자는 #EEE에
어두운 그림자. 원본 띠처럼 왼쪽부터 쓰고, 넘치면 가로로만 줄인다.

게임은 띠 전체를 그리지 않는다. 파일 안 NJSP 스프라이트 표가 조각마다 그릴 UV 폭과 화면 폭을 정한다.
- 「大神一郎」 판: t1 위·아래, t0 위(192px)까지 그리고, t0 아래 첫 8px 열을 80px로 늘려 꼬리로 쓴다.
- 대원 판: 이름 길이에 따라 128·192·224·272px. 꼬리 조각(UV 폭 ≠ 화면 폭)은 늘여 그린다.
그래서 글자는 그리는 폭 안에만 쓰고, 늘이는 꼬리 열은 원본 판 픽셀을 그대로 둔다.
(처음 판은 띠 256px 전체에 써서 「오오가미 이치로」 끝이 잘리고 꼬리에 줄무늬가 생길 뻔했다.)

출력: assets/images/remake/cutin/<파일>/<블록>_<텍스처>.png, index.json, 원본 비교 strips.png
"""
import json
import struct
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import export_images as E
from remake_ui import font_at

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets/images/remake/cutin'
OGAMI = '오오가미 이치로'
NAMES = {'SAKURA': '신구지 사쿠라', 'SUMIRE': '칸자키 스미레', 'MARIA': '마리아・타치바나', 'KANNA': '키리시마 칸나',
         'IRIS': '아이리스', 'KOURAN': '이 홍란', 'ORIHIME': '솔레타・오리히메', 'RENI': '레니・밀히슈트라세',
         'ERICA': '에리카・폰티느', 'GLYCINE': '글리신・블뢰메르', 'COQUELICOT': '코쿠리코',
         'LOBELIA': '로벨리아・카를리니', 'HANABI': '키타오지 하나비'}
BG = (0, 0, 0, 136)
INK = (238, 238, 238)
SS = 4


def name_blocks(raw):
    """(블록 번호, [텍스처 번호…], 원본 띠) — 알파 136 바탕의 64×64 텍스처만 가진 블록"""
    out = []
    for b, spec in enumerate(E.block_specs(raw)):
        if spec[0] != 'BPV1':
            continue
        dec = E.decompress(spec[2], spec[4]) if spec[3] else spec[2]
        try:
            texs = E.decode_bpv(dec)
        except ValueError:
            continue
        if not texs or any(m['width'] != 64 or m['height'] != 64 for _, _, m in texs):
            continue
        arrs = [np.asarray(im.convert('RGBA')) for _, im, _ in texs]
        if all((a[..., 3] == 136).mean() > 0.5 for a in arrs):
            chunks = [c for a in reversed(arrs) for c in (a[:32], a[32:])]
            out.append((b, [i for i, _, _ in texs], np.concatenate(chunks, axis=1)))
    return out


# 글리신 판은 「グリシーヌ・ブルーメール」의 두 「ー」를 같은 텍스처 조각 하나로 두 번 찍는다(t1 아래 0~16).
# 한국어에는 되풀이할 글자가 없어서, 그 조각을 쓰던 항목을 띠 순서대로 이어 그리게 고친다(크기·위치 그대로, UV만).
# 파일 위치: NJSP 항목 시작. 값: (텍스처, u0, v0, u1, v1) 픽셀
SPRITE_FIX = {
    'GLYCINE': {0x8D974: (0, 48, 0, 64, 32), 0x8D934: (0, 0, 32, 16, 64), 0x8D8F4: (0, 16, 32, 64, 64)},
}


def sprite_entries(raw, fix=None):
    """화면 y 384·높이 32인 NJSP 묶음 [[(위치, 텍스처, 화면 x0, 화면 폭, (u0, v0, u1, v1)), …], …]"""
    fix = fix or {}
    out = []
    i = raw.find(b'NJSP')
    while i >= 0:
        n = struct.unpack_from('<I', raw, i + 12)[0]
        items = []
        for k in range(n):
            e = i + 0x48 + k * 64
            tex = struct.unpack_from('<I', raw, e)[0] & 0xff
            x, y, w, h = struct.unpack_from('<4f', raw, e + 4)
            uv = tuple(round(v * 64) for v in struct.unpack_from('<4f', raw, e + 48))
            if e in fix:
                tex, uv = fix[e][0], fix[e][1:]
            items.append((e, tex, x - w / 2, w, h, y, uv))
        if items and all(it[5] == 384 and it[4] == 32 for it in items):
            out.append(sorted([(e, t, x0, w, uv) for e, t, x0, w, h, y, uv in items], key=lambda it: it[2]))
        i = raw.find(b'NJSP', i + 4)
    return out


def layout(entries, texs):
    """(글자를 쓸 수 있는 띠 폭, 원본 판으로 둘 띠 구간 [(x0, x1, y0, y1)…])

    띠 0부터 화면에 한 번씩 그대로 이어 그리는 조각까지만 글자를 쓴다. 늘이거나(UV 폭 ≠ 화면 폭, 높이 ≠ 32)
    두 번 찍는 조각이 가리키는 띠 구간은 원본 판 그대로 두고, 그 앞에서 글자를 끝낸다."""
    if any(tex not in texs for _, tex, _, _, _ in entries):  # 다른 블록(텍스처 수가 다른 판)의 묶음
        return 0, []
    width = len(texs) * 128
    count = np.zeros((32, width), int)
    plain = np.zeros((32, width), bool)
    pos = 0
    for e, tex, x0, w, (u0, v0, u1, v1) in entries:
        sx, y0 = strip_x(texs, tex, u0, v0), v0 % 32
        count[y0:y0 + v1 - v0, sx:sx + u1 - u0] += 1
        if u1 - u0 != w or v1 - v0 != 32:
            plain[y0:y0 + v1 - v0, sx:sx + u1 - u0] = True
        elif sx == pos:  # 띠 0부터 화면에 차례로 이어지는 조각
            pos += w
    plain |= count > 1
    cols = np.nonzero(plain.any(0))[0]
    if len(cols):
        pos = min(pos, int(cols.min()))
    keep = []
    for x in cols:
        ys = np.nonzero(plain[:, x])[0]
        keep.append((int(x), int(x) + 1, int(ys.min()), int(ys.max()) + 1))
    return int(pos), keep


def sprite_patch(rel, raw, fix):
    """SPRITE_FIX를 build.py 코드 패치 형식으로"""
    out = []
    for e, (tex, u0, v0, u1, v1) in sorted(fix.items()):
        old = raw[e:e + 64]
        new = bytearray(old)
        new[0] = (new[0] & 0xfe) | tex
        struct.pack_into('<4f', new, 48, u0 / 64, v0 / 64, u1 / 64, v1 / 64)
        out.append({'file': rel, 'offset': e, 'original_hex': old.hex(), 'new_hex': bytes(new).hex(),
                    'kind': 'sprite-uv', 'note': f'{rel} 컷인 이름판 NJSP 항목 0x{e:X} UV (remake_cutin_names.py)'})
    return out


def strip_x(texs, tex, u, v):
    """텍스처 좌표 → 띠 x. 띠는 t1 위·아래, t0 위·아래 순서(텍스처가 하나면 t0 위·아래)"""
    order = list(reversed(texs))
    return (order.index(tex) * 2 + (1 if v >= 32 else 0)) * 64 + u


def render(text, width):
    """폭 width×32 이름 띠"""
    font = font_at('serif', 800, 28 * SS)
    canvas = Image.new('L', (width * SS * 2, 32 * SS), 0)
    d = ImageDraw.Draw(canvas)
    x = 0
    for c in text:
        if c == ' ':
            x += 12 * SS
            continue
        if c == '・':  # 전각 가운뎃점은 좌우 여백이 커서 좁게 찍는다
            d.text((x - 6 * SS, 16 * SS), c, font=font, fill=255, anchor='lm')
            x += font.getlength(c) - 12 * SS
            continue
        d.text((x, 16 * SS), c, font=font, fill=255, anchor='lm')
        x += font.getlength(c) + 3 * SS
    box = canvas.getbbox()
    glyph = canvas.crop((0, 0, box[2], 32 * SS))
    room = (width - 4) * SS
    if glyph.width > room:  # 넘치면 가로로만 누른다
        glyph = glyph.resize((room, glyph.height), Image.LANCZOS)
    mask = Image.new('L', (width * SS, 32 * SS), 0)
    mask.paste(glyph, (2 * SS, 0))
    mask = mask.resize((width, 32), Image.BOX)
    shadow = Image.new('L', mask.size, 0)
    shadow.paste(mask, (2, 2))
    shadow = shadow.filter(ImageFilter.GaussianBlur(1.0))
    m = np.asarray(mask, float) / 255
    s = np.asarray(shadow, float) / 255 * 0.9
    alpha_bg = BG[3] / 255
    a = s + alpha_bg * (1 - s)  # 그림자(검정) 위
    a = m + a * (1 - m)          # 글자
    rgb = (np.asarray(INK, float)[None, None, :] * m[..., None]) / np.maximum(a[..., None], 1e-6)
    return np.concatenate([np.clip(rgb, 0, 255), a[..., None] * 255], -1).round().astype(np.uint8)


def main():
    rows, previews, patches, layouts = [], [], [], []
    for key, name in NAMES.items():
        rel = f'SLG/UNITS/{key}_S_N.BC'
        raw = (ROOT / 'originals/disc' / rel).read_bytes()
        blocks = name_blocks(raw)
        if len(blocks) != 2:
            raise SystemExit(f'{rel}: 이름판 블록 {len(blocks)}개')
        ogami_ref = None
        fix = SPRITE_FIX.get(key, {})
        patches += sprite_patch(rel, raw, fix)
        sets = sprite_entries(raw, fix)
        if len(sets) != 2:
            raise SystemExit(f'{rel}: 이름판 스프라이트 묶음 {len(sets)}개')
        for b, texs, strip in blocks:
            # 「大神一郎」 블록: 첫 띠 조각의 글자 위치가 모든 파일에서 같다
            ref = (ROOT / 'assets/images/remake/cutin/_ogami_ref.npy')
            if ogami_ref is None and ref.exists():
                ogami_ref = np.load(ref)
            is_ogami = ogami_ref is not None and strip.shape == ogami_ref.shape and np.abs(strip.astype(int) - ogami_ref).max() == 0
            if key == 'SAKURA' and b == blocks[0][0]:
                ref.parent.mkdir(parents=True, exist_ok=True)
                np.save(ref, strip)
                ogami_ref, is_ogami = strip, True
            text = OGAMI if is_ogami else name
            # 묶음 둘 중 하나는 「大神一郎」, 하나는 대원. 원본 글자 끝이 그리는 폭 안에 드는 쪽을 고른다
            fits = [layout(es, texs) for es in sets]
            end = int(np.nonzero(((strip[..., 3] > 150) & (strip[..., :3].max(-1) > 120)).any(0))[0].max()) + 1
            cand = [f for f in fits if f[0] >= end]
            limit, keep = (min(cand) if is_ogami else max(cand)) if cand else max(fits)
            limit = min(limit, strip.shape[1])
            new = strip.copy()
            new[:, :limit] = render(text, limit)
            # 글자 폭 뒤는 판 바탕만 남긴다. 원본 글자 꼬리(「ーセ」 등)가 화면에 그려지는 조각이나
            # 늘여 그리는 조각에 남지 않게 한다(바탕 단색이라 늘여도 줄무늬가 없다).
            new[:, limit:] = BG
            layouts.append({'source': rel, 'block': b, 'text': text, 'limit': limit, 'plain': keep})
            chunks = [new[:, i * 64:(i + 1) * 64] for i in range(strip.shape[1] // 64)]
            order = list(reversed(texs))
            for k, t in enumerate(order):
                tile = np.concatenate([chunks[2 * k], chunks[2 * k + 1]], axis=0)
                path = OUT / rel / f'{b:04d}_{t:04d}.png'
                path.parent.mkdir(parents=True, exist_ok=True)
                Image.fromarray(tile, 'RGBA').save(path)
                rows.append({'source': rel, 'block': b, 'texture': t, 'text': text,
                             'remake': path.relative_to(ROOT).as_posix()})
            previews.append((strip, new))
    (OUT / 'index.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    (OUT / 'layout.json').write_text(json.dumps(layouts, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    (ROOT / 'config/code-patches-cutin-sprites.json').write_text(
        json.dumps({'patches': patches}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    width = max(s.shape[1] for s, _ in previews)
    sheet = Image.new('RGBA', (width * 2 + 16, 36 * len(previews)), (120, 60, 140, 255))
    for i, (old, new) in enumerate(previews):
        sheet.alpha_composite(Image.fromarray(old, 'RGBA'), (0, i * 36))
        sheet.alpha_composite(Image.fromarray(new, 'RGBA'), (width + 16, i * 36))
    sheet.save(OUT / 'strips.png')
    print('이름판', len(previews), '텍스처', len(rows))


if __name__ == '__main__':
    main()
