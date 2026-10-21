"""낫표 「」『』 글리프를 안쪽 글자 쪽으로 붙인다.

전각 칸의 advance는 고정이라 여는 낫표는 칸 오른쪽, 닫는 낫표는 칸 왼쪽에
획이 있다. 원본 획은 칸 끝에서 6~7px 떨어져 있어 한글과 붙으면 한글끼리보다
간격이 2~3px 넓다(예: 「미카사」). 가로 막대의 가운데 열을 빼고 세로획을
칸 끝 쪽으로 옮겨, 획과 다음 글자 사이 간격을 한글 글자 간격에 맞춘다.
막대 끝(캡) 모양은 그대로 남긴다.

같은 김에 전각 ？(타일 8)·！(타일 9)·０~９(147~156)·Ａ~Ｚ(157~182)·ａ~ｚ(183~208)를
한글과 같은 Noto Sans KR, 같은 크기 비율로 다시 그린다(원래 글리프는 한글 옆에서 굵고 커
보였고, v0.5 영문 일부에는 빗금 얼룩도 있었다).

항상 originals/v05 기준선에서 다시 계산하므로 여러 번 실행해도 결과가 같다.
"""
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FONTS = [('SKFONT.CG', 26), ('SKFONT2.CG', 24), ('SKFONT3.CG', 22), ('SKFONT4.CG', 22)]
OPENING = {53: '「', 55: '『'}
CLOSING = {54: '」', 56: '』'}
HANGUL_TILES = range(492, 700)
REDRAW = {8: '?', 9: '!', **{147 + i: str(i) for i in range(10)},  # ？！, 전각 ０~９
          **{157 + i: chr(65 + i) for i in range(26)}, **{183 + i: chr(97 + i) for i in range(26)}}  # Ａ~Ｚ, ａ~ｚ
# 한자 유지 표기(광무・改): 改(0x89FC) 칸은 한글 「망」이 쓰고 있어, 원문에 한 번도 안 나오는
# 岐(0x8AF2) 칸에 改를 그린다. config/encoding.json 「改」 = f2f2. 원본 일본어 글리프는 한글보다
# 훨씬 굵어서, 한자가 들어 있는 맑은 고딕으로 한글과 같은 방식으로 그린다.
KANJI_DRAW = {0x8AF2: '改'}
HANJA_FONT = 'C:/Windows/Fonts/malgun.ttf'


def kanji_tile(code):
    hi, lo = code >> 8, code & 255
    return 398 + (hi - 0x88) * 188 + (lo - 0x40 - (1 if lo > 0x7F else 0))
NOTO = ROOT / 'assets/fonts/NotoSansKR-subset.ttf'
MIN_BAR = 3  # 막대가 이보다 짧아지면 낫표로 읽히지 않는다


def decode(raw, s):
    src = np.frombuffer(raw, dtype=np.uint8).reshape(s // 2, s)
    v = np.empty((s, s), dtype=np.uint8)
    v[::2] = src & 15
    v[1::2] = src >> 4
    return v


def encode(v):
    return ((v[1::2] << 4) | v[::2]).astype(np.uint8).tobytes()


def tighten(v, closing, gap_target, next_margin):
    """여는 낫표 기준으로 처리한다. 닫는 낫표는 좌우 반전해서 넘긴다."""
    if closing:
        return tighten(v[:, ::-1], False, gap_target, next_margin)[:, ::-1]
    s = v.shape[0]
    counts = (v > 3).sum(0)
    stroke = [c for c in range(s) if counts[c] > s // 2]
    bar = [c for c in range(stroke[-1] + 1, s) if counts[c] > 0]
    excess = (s - 1 - stroke[-1]) + next_margin - gap_target
    k = max(0, min(len(bar) - MIN_BAR, excess))
    if k == 0:
        return v.copy()
    # 세로획 바로 옆 막대 열 k개를 빼고 그 왼쪽 전체를 k칸 오른쪽으로 민다.
    cut = stroke[-1] + 1
    out = np.zeros_like(v)
    out[:, k:cut + k] = v[:, :cut]
    out[:, cut + k:] = v[:, cut + k:]
    return out


def main():
    for name, s in FONTS:
        stride = s * s // 2
        data = bytearray((ROOT / 'originals/v05' / name).read_bytes())
        lm, rm = [], []
        for t in HANGUL_TILES:
            cols = np.where(decode(data[t * stride:(t + 1) * stride], s).max(0) > 0)[0]
            if len(cols):
                lm.append(cols.min()); rm.append(s - 1 - cols.max())
        lm, rm = int(np.median(lm)), int(np.median(rm))
        for t, closing in [(t, False) for t in OPENING] + [(t, True) for t in CLOSING]:
            v = decode(data[t * stride:(t + 1) * stride], s)
            # 여는 낫표 뒤에는 다음 글자의 왼쪽 여백, 닫는 낫표 앞에는 앞 글자의 오른쪽 여백
            new = tighten(v, closing, lm + rm, rm if closing else lm)
            data[t * stride:(t + 1) * stride] = encode(new)
        draws = [(t, ch, NOTO) for t, ch in REDRAW.items()]
        draws += [(kanji_tile(code), ch, HANJA_FONT) for code, ch in KANJI_DRAW.items()]
        for t, ch, path in draws:
            # hangul_font_map.render_hangul_tile과 같은 방식(크기 0.85, 칸 가운데)
            font = ImageFont.truetype(str(path), int(s * 0.85))
            img = Image.new('L', (s, s), 0)
            d = ImageDraw.Draw(img)
            bb = d.textbbox((0, 0), ch, font=font)
            # 영문·숫자는 기준선을 맞춘다(「H」 높이로 세로 위치 고정). 글자마다 가운데 정렬하면 소문자 높이가 들쭉날쭉하다
            vb = d.textbbox((0, 0), 'H', font=font) if ch.isascii() and ch.isalnum() else bb
            d.text(((s - bb[2] + bb[0]) // 2 - bb[0], (s - vb[3] + vb[1]) // 2 - vb[1]), ch, fill=255, font=font)
            data[t * stride:(t + 1) * stride] = encode((np.asarray(img) >> 4).astype(np.uint8))
        (ROOT / 'assets/fonts/native' / name).write_bytes(bytes(data))
        print(name, '한글 여백', lm, rm)


if __name__ == '__main__':
    main()
