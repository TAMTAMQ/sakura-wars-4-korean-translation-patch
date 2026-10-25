"""GRCT 앞머리의 NJSP 스프라이트 표를 읽고, 게임이 텍스처 조각을 화면에 놓는 모양을 그대로 합성한다.

NJSP 항목(64바이트): 플래그(하위 1비트 = 텍스처 번호), 화면 중심 x·y와 폭·높이(float),
스프라이트 번호(상위 16비트), 기준점 0.5·0.5, 색 4개, UV u0·v0·u1·v1(float, 0~1).
화면 폭이 UV 폭과 다르면 그 조각을 늘려 그린다(예: 이름판 x 80~88 판 조각을 40~68px로 늘려 줄 여백으로 쓴다).
글자가 이런 늘임 조각이나 UV 범위 밖에 걸리면 게임에서 잘리거나 줄무늬로 보인다.

usage: python src/grct_sprites.py <GRCT> [텍스처 PNG …]  → 화면 합성 PNG 저장
"""
import struct
import sys
from pathlib import Path

from PIL import Image


def groups(data):
    """[(NJSP 위치, [(번호, 텍스처, (x, y, w, h), (u0, v0, u1, v1)), …]), …]"""
    out = []
    i = data.find(b'NJSP')
    while i >= 0:
        n = struct.unpack_from('<I', data, i + 12)[0]
        items = []
        for k in range(n):
            e = i + 0x48 + k * 64
            flag = struct.unpack_from('<I', data, e)[0]
            x, y, w, h = struct.unpack_from('<4f', data, e + 4)
            sid = struct.unpack_from('<I', data, e + 20)[0] >> 16
            uv = struct.unpack_from('<4f', data, e + 48)
            items.append((sid, flag & 1, (x, y, w, h), uv))
        out.append((i, items))
        i = data.find(b'NJSP', i + 4)
    return out


def compose(items, textures, scale=2):
    """스프라이트 묶음 하나를 화면 좌표로 합성(보라 바탕, scale배 확대)"""
    boxes = [(x - w / 2, y - h / 2, x + w / 2, y + h / 2) for _, _, (x, y, w, h), _ in items]
    x0, y0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
    x1, y1 = max(b[2] for b in boxes), max(b[3] for b in boxes)
    canvas = Image.new('RGBA', (int(x1 - x0) * scale, int(y1 - y0) * scale), (90, 60, 120, 255))
    for (_, tex, (x, y, w, h), (u0, v0, u1, v1)), b in zip(items, boxes):
        img = textures[tex]
        tw, th = img.size
        piece = img.crop((round(u0 * tw), round(v0 * th), round(u1 * tw), round(v1 * th)))
        piece = piece.resize((int(w) * scale, int(h) * scale), Image.NEAREST)
        canvas.alpha_composite(piece, (int((b[0] - x0) * scale), int((b[1] - y0) * scale)))
    return canvas


if __name__ == '__main__':
    path = Path(sys.argv[1])
    for pos, items in groups(path.read_bytes()):
        print(pos, items)
