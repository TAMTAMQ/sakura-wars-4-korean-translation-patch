"""합체 공격 컷인의 기술 이름판(SLG/UNITS/*_S.GRCT)을 한국어로 다시 만든다.

「大神 & さくら」「狼虎滅却 桜花絢爛」을 담은 128×128 ARGB4444 텍스처다. 대원 이름판(*_K2/F2.GRCT,
remake_slg_plates.py의 member 틀)과 띠 배치가 같다. 이름 띠(N)·기술 띠(A)는 두 조각을 이어 쓰고,
B 자리(대원 이름판이면 검은 상자 속 짧은 이름)에는 「双」「武」가 한 글자씩 판 위에 적혀 있다.

화면 배치는 GRCT 앞머리의 NJSP 스프라이트 표가 정한다(src/grct_sprites.py로 합성 확인).
- 이름 줄: [0,0,128,24] + [0,24,80,48]. 둘째 조각은 80px까지만 그린다(88이 아니다).
- 둘째 줄: [80,24,88,48] 판 조각을 양쪽 68px로 늘린 여백 사이에 「双」[88,24,128,48]과 「武」[96,72,128,96]를
  붙여 그린다 → 한 단어 「双武」(합체 광무 이름, 설계도 b652 「名称 双武」) → 「쌍무」.
  늘이는 x 80~88 칸에 글자 획이 남으면 줄무늬로 보이므로 원본 판 픽셀을 그대로 둔다.
- 기술 줄: [0,48,128,72] + [0,72,96,96].
v0.5가 손대지 않아 이미지 목록에 없었고 일본어로 남아 있었다.

판 텍스처는 대부분 1번, 스미레만 0번이다(픽셀 형식 4444인 쪽).
출력: assets/images/remake/combo/<파일>/<블록>_<텍스처>.png, index.json, 대조 시트 compare.png
"""
import json
from pathlib import Path

import numpy as np
from PIL import Image

import export_images as E
from remake_slg_plates import compose, render_mask

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets/images/remake/combo'
FONT = {'path': 'C:/Windows/Fonts/NotoSerifKR-VF.ttf', 'weight': 600}  # slg_plates.json과 같은 글꼴
# member 틀과 같은 자리. 텍스처 번호는 파일마다 판 텍스처로 바꿔 쓴다
CHAINS = [
    {'key': 'N', 'rects': [(0, 0, 128, 24), (0, 24, 80, 48)], 'track': 5},
    # 두 조각이 화면에서 붙어 「双武」 한 단어가 된다 → 원본 글자 자리마다 한 글자씩
    {'key': 'B1', 'rects': [(88, 24, 128, 48)], 'track': 0},
    {'key': 'B2', 'rects': [(96, 72, 128, 96)], 'track': 0},
    {'key': 'A', 'rects': [(0, 48, 128, 72), (0, 72, 96, 96)], 'track': 2},
]
B_TEXT = ('쌍', '무')  # 원문 「双」「武」
PLATES = {
    'SAKURA': ('사쿠라', '낭호멸각 앵화현란'),
    'SUMIRE': ('스미레', '낭호멸각 아훔의 춤'),
    'MARIA': ('마리아', '낭호멸각 부두시시이'),
    'KANNA': ('칸나', '낭호멸각 백랑권'),
    'IRIS': ('아이리스', '낭호멸각 판타스티크 베제'),
    'KOURAN': ('홍란', '낭호멸각 천지풍운'),
    'ORIHIME': ('오리히메', '낭호멸각 두에토'),
    'RENI': ('레니', '낭호멸각 글뤽클리히카이트'),
    'ERICA': ('에리카', '낭호멸각 베네딕시옹'),
    'GLYCINE': ('글리신', '낭호멸각 에테르넬 아무르'),
    'COQUELICOT': ('코쿠리코', '낭호멸각 아무르 소르시에르'),
    'LOBELIA': ('로벨리아', '낭호멸각 아모레 센차 피네'),
    'HANABI': ('하나비', '낭호멸각 화조풍월'),
}


def plate_texture(raw):
    """(블록, 텍스처 번호, RGBA 배열) — 4444 판 텍스처"""
    spec = E.block_specs(raw)[0]
    dec = E.decompress(spec[2], spec[4]) if spec[3] else spec[2]
    texs = E.decode_bpv(dec)
    plates = [(i, im) for i, im, m in texs if m['pixel_format'] == 2]
    if len(plates) != 1:
        raise SystemExit('판 텍스처를 하나로 정할 수 없음')
    i, im = plates[0]
    return 0, i, np.asarray(im.convert('RGBA')).copy()


def draw(img, text, chain):
    h = 24
    width = sum(x1 - x0 for x0, _, x1, _ in chain['rects'])
    cuts, acc = [], 0
    for x0, _, x1, _ in chain['rects'][:-1]:
        acc += x1 - x0
        cuts.append(acc)
    mask = render_mask(text, width, h, 'center', chain['track'], 0, FONT, cuts, shadow_guard=3)
    rgba = compose(mask, 'plate')
    off = 0
    for x0, y0, x1, y1 in chain['rects']:
        img[y0:y1, x0:x1] = rgba[:, off:off + x1 - x0]
        off += x1 - x0


def main():
    rows, pairs = [], []
    for key, (short, attack) in PLATES.items():
        rel = f'SLG/UNITS/{key}_S.GRCT'
        b, t, old = plate_texture((ROOT / 'originals/disc' / rel).read_bytes())
        new = old.copy()
        texts = {'N': f'오오가미 & {short}', 'B1': B_TEXT[0], 'B2': B_TEXT[1], 'A': attack}
        for chain in CHAINS:
            draw(new, texts[chain['key']], chain)
        new[24:48, 80:88] = old[24:48, 80:88]  # 늘여 그리는 여백 조각은 원본 판 그대로
        path = OUT / rel / f'{b:04d}_{t:04d}.png'
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(new, 'RGBA').save(path)
        rows.append({'source': rel, 'block': b, 'texture': t, 'text': texts,
                     'remake': path.relative_to(ROOT).as_posix()})
        pairs.append((old, new))
    (OUT / 'index.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    sheet = Image.new('RGBA', (2 * 3 * 128 + 24, len(pairs) * 3 * 100), (120, 60, 140, 255))
    for k, (old, new) in enumerate(pairs):
        for j, arr in enumerate((old, new)):
            im = Image.fromarray(arr[:96], 'RGBA').resize((384, 288), Image.NEAREST)
            sheet.alpha_composite(im, (j * (384 + 24), k * 300))
    sheet.save(OUT / 'compare.png')
    print('합체 기술판', len(rows))


if __name__ == '__main__':
    main()
