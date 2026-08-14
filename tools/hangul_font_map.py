"""
한자 타일 자리를 빌려서 한글을 표시하기 위한 매핑 도구.
SKFONT.CG(26x26), SKFONT2.CG(24x24), SKFONT3/4.CG(22x22) 네 파일 모두
같은 타일 번호 체계를 공유하므로, 동시에 패치해야 게임 내 모든 화면
(대사창/메뉴/상태창 등)에서 한글이 정상적으로 보입니다.
"""
import json, os, re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

FONT_CONFIGS = [
    ("SKFONT.CG",  338, 26),
    ("SKFONT2.CG", 288, 24),
    ("SKFONT3.CG", 242, 22),
    ("SKFONT4.CG", 242, 22),
]
# 사용자 컴퓨터에 어떤 폰트가 깔려있든 상관없도록, 필요한 한글
# 음절 글자만 추려낸 폰트 파일을 tools/ 폴더 안에 함께 넣어서 사용
FONT_PATH = os.path.join(SCRIPT_DIR, "NotoSansKR-subset.ttf")
MAP_FILE = os.path.join(SCRIPT_DIR, "hangul_map.json")

KANJI_START_TILE = 492          # 0x28998 / 338 (모든 폰트 파일 공통)
KANJI_BASE_KUTEN = 1410         # 0x889F 의 ku-ten 순번
MAX_KANJI_TILES = 2996          # 3488(전체) - 492

# 공백 처리 방식
#   'skip' (기본값): 공백 자체를 안 넣고 건너뜀 -> 확실히 폭 문제가
#                    없지만 단어가 다 붙어서 나옴
#   'tile': 한글처럼 빈 한자 타일 자리를 빌려서 공백 글자를 그려넣음
#           -> 안 붙지만, 게임에서 그 칸이 2칸 폭으로 보일 수 있음
#              (아직 원인 미해결)
SPACE_MODE = 'skip'

def set_space_mode(mode):
    global SPACE_MODE
    if mode not in ('skip', 'tile'):
        raise ValueError("space_mode는 'skip' 또는 'tile'만 가능합니다")
    SPACE_MODE = mode

def kuten_index_to_sjis(idx):
    row, col = divmod(idx, 188)
    b1 = row + 0x81 if row <= 0x1E else row + 0xC1
    b2 = col + 0x40 if col < 0x3F else col + 0x41
    return bytes([b1, b2])

def load_map():
    if os.path.exists(MAP_FILE):
        with open(MAP_FILE, encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_map(m):
    with open(MAP_FILE, 'w', encoding='utf-8') as f:
        json.dump(m, f, ensure_ascii=False, indent=2)

def assign_tiles(text, mapping):
    used = set(int(v) for v in mapping.values())
    next_tile = (max(used) + 1) if used else KANJI_START_TILE
    for ch in text:
        # 완성형 한글 음절(가,나,다...) + 단독 자모(ㅋ,ㅠ,ㅡ 등 강조/이모티콘용)
        is_hangul = ('\uAC00' <= ch <= '\uD7A3') or ('\u3131' <= ch <= '\u318E')
        is_space = ch == ' ' and SPACE_MODE == 'tile'
        if (is_hangul or is_space) and ch not in mapping:
            if next_tile >= KANJI_START_TILE + MAX_KANJI_TILES:
                raise SystemExit("배정 가능한 타일이 부족합니다 (최대 2996자)")
            mapping[ch] = next_tile
            next_tile += 1
    return mapping

# 인코딩 안 되는 서양식 문장부호 -> 일본어(JIS)에 실제로 있는 비슷한 문자로 자동 치환
PUNCT_SUBSTITUTES = {
    '\u00b7': '\u30fb',  # · (가운뎃점) -> ・ (일본어 나카구로)
    '\u2013': '\u2015',  # – (en dash) -> ― (일본어 장음 대시)
    '\u2014': '\u2015',  # — (em dash) -> ―
    '\u2011': '\u2015',  # ‑ (non-breaking hyphen) -> ―
    '\u2012': '\u2015',  # ‒ (figure dash) -> ―
}

def to_fullwidth_char(ch):
    """이 게임 렌더러는 1바이트(반각) 코드를 처리하지 못하므로,
    영숫자/문장부호 등은 2바이트 전각 코드로 바꿔서 넣는다.
    단, '/' 는 게임이 줄바꿈 명령으로 특수 처리하는 문자라서
    반각 그대로(0x2F) 유지해야 한다 — 전각으로 바꾸면 줄바꿈이
    깨지고 문자 그대로 화면에 찍힌다.
    '!' 도 특수 케이스: 표준 전각느낌표(0x8149) 자리가 이 게임에서
    실제로 무엇을 표시하는지 검증되지 않았고, 원문 대사 1,651곳에서
    실제로 쓰이는 건 다른 바이트(0x81b8, 표준 Shift-JIS로는 '∈')이므로
    이쪽을 사용한다."""
    if ch == '/':
        return ch
    if ch == '!':
        return '∈'  # 실제 인코딩시 0x81b8 (이 게임의 진짜 느낌표)
    if ch in PUNCT_SUBSTITUTES:
        return PUNCT_SUBSTITUTES[ch]
    if 0x21 <= ord(ch) <= 0x7E:  # 반각 영숫자/기호
        return chr(0xFF00 + (ord(ch) - 0x20))
    return ch

# 글자 크기·폰트·줄 위치·색상을 지정하는 제어 코드. 게임이 이 반각(ASCII)
# 바이트 시퀀스를 그대로 스캔해서 제어 코드로 인식하므로, 절대 전각으로
# 바꾸면 안 된다 - 전각으로 바뀌면 제어 코드로 인식되지 않고 화면에
# 글자 그대로("＠ｃ９" 등) 찍혀버린다.
CONTROL_CODE_PATTERN = re.compile(
    r'@(?:fs[0-9]+,[0-9]+|fm[0-9]+,[0-9]+|lm[0-9]+,[0-9]+|c[0-9]+|x)')


def _encode_plain(text, mapping):
    """제어 코드가 아닌 일반 텍스트 구간을 기존 규칙대로 인코딩."""
    out = bytearray()
    for ch in text:
        if ch == ' ' and SPACE_MODE == 'skip':
            # 공백 자체를 넣지 않고 건너뛴다(0바이트) - 폭 문제가
            # 원천적으로 생기지 않는 안전한 기본값.
            continue
        if ch in mapping:
            tile = mapping[ch]
            kuten = KANJI_BASE_KUTEN + (tile - KANJI_START_TILE)
            out += kuten_index_to_sjis(kuten)
        else:
            ch = to_fullwidth_char(ch)
            out += ch.encode('cp932')
    return bytes(out)


def encode_mixed(text, mapping):
    out = bytearray()
    pos = 0
    for m in CONTROL_CODE_PATTERN.finditer(text):
        out += _encode_plain(text[pos:m.start()], mapping)
        out += m.group(0).encode('ascii')  # 제어 코드는 반각 그대로 통과
        pos = m.end()
    out += _encode_plain(text[pos:], mapping)
    return bytes(out)


def encode_mixed_fit(text, mapping, budget):
    """현재 SPACE_MODE(보통 tile)로 먼저 인코딩해보고, budget(바이트)을
    넘으면 그 줄 하나만 공백을 없애는 skip 모드로 다시 인코딩해서 그게
    들어가면 그걸 쓴다. (전역 SPACE_MODE 자체는 안 바꿈 - 이 줄만 예외
    적용) 2026-08-14: tile 모드에서 "너무 길어서 못 넣음"으로 밀리던
    줄들을 공백만 없애서 구제하기 위해 추가.

    둘 다 budget을 넘으면 더 짧은 쪽을 반환한다(호출부의 길이초과 판정/
    보고 로직은 그대로 두고, 최대한 가까운 결과를 주기 위함)."""
    global SPACE_MODE
    encoded = encode_mixed(text, mapping)
    if len(encoded) <= budget or SPACE_MODE == 'skip':
        return encoded
    original_mode = SPACE_MODE
    SPACE_MODE = 'skip'
    try:
        encoded_noSpace = encode_mixed(text, mapping)
    finally:
        SPACE_MODE = original_mode
    if len(encoded_noSpace) <= budget:
        return encoded_noSpace
    return encoded_noSpace if len(encoded_noSpace) < len(encoded) else encoded

def render_hangul_tile(ch, size, font_size=None):
    from PIL import Image, ImageDraw, ImageFont
    if font_size is None:
        font_size = int(size * 0.85)
    font = ImageFont.truetype(FONT_PATH, font_size)
    img = Image.new('L', (size, size), 0)
    draw = ImageDraw.Draw(img)

    if ch == ' ':
        # 완전히 빈 타일(픽셀 전부 0)이면 게임 렌더러가 "잘라낼 잉크가
        # 없다"고 판단해 폭을 줄이지 못하고 칸 전체(2칸 크기)로 표시하는
        #것으로 보임. 거의 안 보이는 아주 작은 점 하나를 중앙에 남겨서
        # "내용이 있는 좁은 글자"로 인식되게 한다.
        cx, cy = size // 2, size // 2
        img.putpixel((cx, cy), 1)
        return img

    bbox = draw.textbbox((0,0), ch, font=font)
    w = bbox[2]-bbox[0]
    h = bbox[3]-bbox[1]
    x = (size - w)//2 - bbox[0]
    y = (size - h)//2 - bbox[1]
    draw.text((x,y), ch, fill=255, font=font)
    return img

def img_to_tile_bytes(img, size, tile_bytes):
    tile = bytearray(tile_bytes)
    rows = size // 2
    for row in range(rows):
        for col in range(size):
            upper = img.getpixel((col, row*2)) >> 4
            lower = img.getpixel((col, row*2+1)) >> 4
            tile[row*size+col] = (lower << 4) | upper
    return bytes(tile)

def patch_skfont(src_dir, out_dir, mapping):
    """FONT_CONFIGS의 4개 폰트 파일을 전부 패치. src_dir/out_dir는 폴더 경로."""
    import os
    os.makedirs(out_dir, exist_ok=True)
    for fname, tile_bytes, size in FONT_CONFIGS:
        src_path = os.path.join(src_dir, fname)
        out_path = os.path.join(out_dir, fname)
        with open(src_path, 'rb') as f:
            data = bytearray(f.read())
        for ch, tile_idx in mapping.items():
            img = render_hangul_tile(ch, size)
            tb = img_to_tile_bytes(img, size, tile_bytes)
            offset = tile_idx * tile_bytes
            data[offset:offset+tile_bytes] = tb
        with open(out_path, 'wb') as f:
            f.write(data)
