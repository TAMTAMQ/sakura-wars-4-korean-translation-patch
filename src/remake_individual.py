"""직접 비교해 확인한 이미지에만 개별 수정층을 만든다. 기존 재제작본은 쓰지 않는다.

기준: review/remake_baseline.json에 보존한 재제작본. 글꼴은 균일 배율로만
래스터화하며, 폭에 맞추려고 글자 모양을 가로 압축하지 않는다.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from remake_slg_plates import SS, compose, load_font

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets/images/remake/individual'

# 이 목록은 원본과 재제작을 각각 눈으로 대조해 결정한 수정 범위다.
PLANS = {
    120: {'copy': [[0, 0, 128, 24]], 'note': '상단 ???는 번역 대상이 아니므로 원본 글자·크기·위치를 그대로 복원.'},
    121: {'none_vertical': True, 'note': '녹귀: 원본 오른쪽 세로 な/し 위치에 없/음을 세로 배치. 아래 기병 증귀도 왼쪽 96px 영역에 배치하여 겹침 방지. 가로 압축 없음.'},
    122: {'none_vertical': True, 'note': '적귀: 원본 오른쪽 세로 な/し 위치에 없/음을 세로 배치. 아래 기병 증귀도 왼쪽 96px 영역에 배치하여 겹침 방지. 가로 압축 없음.'},
    123: {'none_vertical': True, 'note': '청귀: 원본 오른쪽 세로 な/し 위치에 없/음을 세로 배치. 아래 기병 증귀도 왼쪽 96px 영역에 배치하여 겹침 방지. 가로 압축 없음.'},
    127: {'copy': [[64, 96, 128, 120]], 'note': '에리카 이름판: 일본어 광무 부분의 번역은 유지하고, 번역 대상이 아닌 F2 두 칸은 원본 복원.'},
    132: {'copy': [[0, 0, 128, 24]], 'hakushiki': True, 'note': '상단 ??? 원본 복원. 마조기병 하쿠시키는 원래 24px 행에 자연 비율로 배치. 검은 이름칸은 원본 가나의 작은 글자 높이에 맞춰 하쿠시키를 다시 배치. 가로 압축 없음.'},
    134: {'copy': [[64, 96, 128, 120]], 'note': '글리신 이름판: 번역 대상이 아닌 F2 두 칸을 원본 복원.'},
    136: {'copy': [[64, 96, 128, 120]], 'note': '코쿠리코 이름판: 번역 대상이 아닌 F2 두 칸을 원본 복원.'},
    138: {'copy': [[64, 96, 128, 120]], 'note': '로벨리아 이름판: 번역 대상이 아닌 F2 두 칸을 원본 복원.'},
    140: {'copy': [[64, 96, 128, 120]], 'note': '하나비 이름판: 번역 대상이 아닌 F2 두 칸을 원본 복원.'},
}


def lettering(text, width, height, ink_height, pitch, x=1, space=8, vertical=False):
    """명시한 크기·자간으로만 그린다. 한글의 가로/세로 배율은 같다."""
    cfg = json.loads((ROOT / 'assets/images/remake/slg_plates.json').read_text(encoding='utf-8'))['font']
    size = ink_height * SS
    f = load_font(cfg, size)
    bbox = f.getbbox('한')
    f = load_font(cfg, round(size * size / (bbox[3] - bbox[1])))
    ink = f.getbbox('한')
    mask = Image.new('L', (width * SS, height * SS), 0)
    draw = ImageDraw.Draw(mask)
    cursor = x * SS
    for i, char in enumerate(text):
        if char == ' ':
            cursor += space * SS
            continue
        box = f.getbbox(char)
        if vertical:
            left = (width * SS - (box[2] - box[0])) / 2 - box[0]
            top = i * pitch * SS + ((pitch * SS - (ink[3] - ink[1])) / 2) - ink[1] - SS
        else:
            left = cursor
            top = (height * SS - (ink[3] - ink[1])) / 2 - ink[1] - SS
        if left + box[0] < 0 or left + box[2] > width * SS or top + box[3] > height * SS:
            raise ValueError(f'개별 배치 범위 초과: {text}, {char}')
        draw.text((left, top), char, font=f, fill=255)
        cursor += pitch * SS
    return np.asarray(mask.resize((width, height), Image.Resampling.BOX), dtype=float) / 255


def strip(image, text, rects, ink_height, pitch, style='plate', **kwargs):
    width = sum(r[2] - r[0] for r in rects)
    height = rects[0][3] - rects[0][1]
    rgba = Image.fromarray(compose(lettering(text, width, height, ink_height, pitch, **kwargs), style))
    offset = 0
    for x0, y0, x1, y1 in rects:
        image.paste(rgba.crop((offset, 0, offset + x1 - x0, height)), (x0, y0))
        offset += x1 - x0


def main():
    review = ROOT / 'assets/images/review'
    rows = json.loads((review / 'image_review.json').read_text(encoding='utf-8'))
    baseline = json.loads((review / 'remake_baseline.json').read_text(encoding='utf-8'))
    results = []
    for row in rows:
        plan = PLANS.get(row['id'])
        if not plan:
            continue
        key = f"{row['source']}|{row['block']}|{row['texture']}"
        frozen = ROOT / baseline[key]['path']
        assert hashlib.sha256(frozen.read_bytes()).hexdigest() == baseline[key]['sha256'], key
        image = Image.open(frozen).convert('RGBA')
        original = Image.open(ROOT / row['original']).convert('RGBA')
        for rect in plan.get('copy', []):
            image.paste(original.crop(rect), rect[:2])
        if plan.get('none_vertical'):
            strip(image, '기병 증귀', [(0, 96, 96, 120)], 20, 21)
            # 게임은 아래 띠(96~120행)를 x≈112에서 갈라 왼쪽은 「기병 증귀」 줄, 오른쪽은 필살 칸에 붙인다.
            # 원본 し도 112~120에 있다. 「음」이 그 경계를 넘으면 반쪽씩 두 줄에 찍혔다.
            strip(image, '', [(96, 96, 113, 120)], 15, 24)  # 기존 재제작의 글자 그림자 잔여분 제거
            strip(image, '없', [(96, 72, 124, 96)], 15, 24, vertical=True)
            strip(image, '음', [(113, 96, 128, 120)], 15, 24, vertical=True)
        if plan.get('hakushiki'):
            strip(image, '마조기병 하쿠시키', [(0, 24, 128, 48), (0, 48, 80, 72)], 20, 24, x=0)
            strip(image, '하쿠시키', [(80, 48, 128, 72), (96, 96, 120, 120)], 16, 16, style='box', x=0)
        target = OUT / row['source'] / f"{row['block']:04d}_{row['texture']:04d}.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        image.save(target)
        if plan.get('none_vertical'):
            scope = '부분 수정: 아래쪽 기병 증귀·세로 없음만 재배치. 다른 한글 영역은 기존 재제작과 동일.'
        elif plan.get('hakushiki'):
            scope = '부분 수정: 물음표 복원, 제목·검은 이름칸 재배치. 아래 필살기 문구는 기존 재제작과 동일.'
        else:
            scope = '기호만 복원: 한글 글꼴·크기·배치는 이번 수정에 포함되지 않음.'
        results.append({k: row[k] for k in ['source', 'block', 'texture', 'original', 'patched']} |
                       {'id': row['id'], 'remake': target.relative_to(ROOT).as_posix(), 'note': plan['note'], 'scope': scope})
    (OUT / 'index.json').write_text(json.dumps(results, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print('개별 수정', len(results), '종. 기존 재제작본 보존.')


if __name__ == '__main__':
    main()
