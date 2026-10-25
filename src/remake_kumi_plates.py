"""부대 이름판(SLG/UNITS/KUMI_01~20.GRCT, 「大神華撃団・花組」 등 20종)을 한국어로 다시 만든다.

64×64 ARGB4444 텍스처 두 장에 24px 높이 띠 하나가 들어 있다. NJSP 표대로 t1 위(0~24)·t1 아래(24~48)·
t0 위(0~24)·t0 아래 앞 16px을 차례로 이어 그린다 → 화면 폭 208px. 바탕은 검정 알파 136, 글자는 #EEE에
그림자(remake_slg_plates.py의 plate 양식과 같다). 이미지 목록 밖이라 v0.8.6까지 일본어로 남아 있었다.
조 이름 표기는 대사 번역(「화조」, 퀴즈의 「미니조」, 「절대 정의 오오가미 화격단」)에 맞췄다.

출력: assets/images/remake/kumi/<파일>/0000_<텍스처>.png, index.json, 대조 시트 compare.png
"""
import json
from pathlib import Path

import numpy as np
from PIL import Image

import export_images as E
from remake_slg_plates import compose, render_mask

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets/images/remake/kumi'
FONT = {'path': 'C:/Windows/Fonts/NotoSerifKR-VF.ttf', 'weight': 600}  # slg_plates.json과 같은 글꼴
PIECES = [(1, 0, 64), (1, 24, 64), (0, 0, 64), (0, 24, 16)]  # (텍스처, 띠 y, 그리는 폭) 화면 왼쪽부터
WIDTH = sum(w for _, _, w in PIECES)
HEAD = '오오가미 화격단'
NAMES = ['화조', '홍조', '창조', '수조', '전조', '제도조', '파리조', '동양조', '어른조', '미니조',
         '기라성조', '귀족조', '금은조', '라이벌조', '벚꽃조', '미식조', '도조', '멋쟁이조', '개그조']
LAST = '오오가미 화격단 ~절대 정의~'  # KUMI_20: 「大神華撃団～絶対正義～」


def textures(raw):
    spec = E.block_specs(raw)[0]
    dec = E.decompress(spec[2], spec[4]) if spec[3] else spec[2]
    return {t: np.asarray(im.convert('RGBA')).copy() for t, im, m in E.decode_bpv(dec)}


def strip_of(texs):
    return np.concatenate([texs[t][y:y + 24, :w] for t, y, w in PIECES], axis=1)


def main():
    rows, pairs = [], []
    for i in range(1, 21):
        rel = f'SLG/UNITS/KUMI_{i:02d}.GRCT'
        old = textures((ROOT / 'originals/disc' / rel).read_bytes())
        text = LAST if i == 20 else f'{HEAD}・{NAMES[i - 1]}'
        mask = render_mask(text, WIDTH, 24, 'center', 1, 0, FONT, (), shadow_guard=3)
        strip = compose(mask, 'plate')
        new = {t: a.copy() for t, a in old.items()}
        x = 0
        for t, y, w in PIECES:
            new[t][y:y + 24, :w] = strip[:, x:x + w]
            x += w
        for t, arr in new.items():
            path = OUT / rel / f'0000_{t:04d}.png'
            path.parent.mkdir(parents=True, exist_ok=True)
            Image.fromarray(arr, 'RGBA').save(path)
            rows.append({'source': rel, 'block': 0, 'texture': t, 'text': text,
                         'remake': path.relative_to(ROOT).as_posix()})
        pairs.append((strip_of(old), strip_of(new)))
    (OUT / 'index.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    sheet = Image.new('RGBA', (WIDTH * 2 + 16, 28 * len(pairs)), (120, 60, 140, 255))
    for k, (o, n) in enumerate(pairs):
        sheet.alpha_composite(Image.fromarray(o, 'RGBA'), (0, k * 28))
        sheet.alpha_composite(Image.fromarray(n, 'RGBA'), (WIDTH + 16, k * 28))
    sheet.resize((sheet.width * 2, sheet.height * 2), Image.NEAREST).save(OUT / 'compare.png')
    print('부대 이름판', len(pairs))


if __name__ == '__main__':
    main()
