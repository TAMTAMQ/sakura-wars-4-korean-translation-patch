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

# 고정폭 필드(SMAP_ticker.txt 등)에서 번역문이 원문보다 짧을 때, 화면에
# 안 보이는 채로 맨 뒤에 채워 넣어 바이트 수를 원문과 정확히 맞추기
# 위한 전용 문자. 실제 번역문에는 절대 나오지 않는 코드포인트(Invisible
# Separator)라서 오탐지 걱정이 없다.
BLANK_PAD_CHAR = '⁣'

# 한글 타일은 "안 쓰는 한자" 자리를 빌려서 그리는데, 이 "안 쓰는"이라는
# 판단은 지금까지 번역해 온 대사(SBX/ESM/LIPSYNC 등) 안에서만 안 나온다는
# 뜻이었다. 그런데 전투 커맨드 메뉴, 시스템 메시지("了解!" 등)처럼 우리가
# 추출/번역하지 못한 곳(이미지이거나, 아직 못 찾은 하드코딩된 문자열)에서
# 여전히 원본 그대로의 한자가 그려지는 곳이 있고, 그 한자가 하필 한글이
# 배정된 타일과 겹치면 그 자리에 엉뚱한 한글이 대신 찍힌다(2026-08-15,
# 사용자가 "了解!"가 "了할!"로 깨져 보이는 것을 확인 - 解(かい) 글자의
# 타일에 '할'이 배정되어 있었음).
#
# 완전히 안전하다고 보장할 수는 없지만(하드코딩된 문자열을 전부 찾을 방법이
# 없음), 전투/시스템 메뉴에 흔히 쓰일 만한 상용 한자들을 미리 막아두면
# 위험을 크게 줄일 수 있다. 여기서 막은 한자들은 한글 타일로 절대 배정되지
# 않는다.
BLOCKED_KANJI = set(
    "了解決定中止続行選択承認取消戻終了開始情報通信隊長環境解除防御回復救出撃破成功失敗設定確認"
    "編隊出撃帰還戦闘勝利敗北移動攻撃継続一覧一時保存読込削除終戦開戦進行退却待機命令実行"
    "変更更新登録追加削除切替操作選出配置装備武器道具使用装填発射砲撃爆発着弾命中回避防御"
    "反撃援護支援補給修理修復強化弱体状態異常回復治療蘇生撤退撤収前進後退旋回停止発進着陸"
    "離陸出撃帰投接近接触離脱警戒索敵発見捕捉照準射撃格闘白兵近接遠距離中距離範囲全体単体"
    "自分味方敵対中立協力連携合体分離変形合流分岐終端始端継承相続決着勝敗引分中断再開再戦"
    "次回前回今回毎回全回半分全部一部全員全体個別単独複数多数少数最大最小増加減少上昇下降"
    "開幕終幕休止中休憩終業始業就業退勤出勤在籍除籍入隊退隊昇進降格任命解任配属異動転属"
    "戻情報通信除防復隊長速力体験験経値上限段階種類効果範囲判定確率計算表示画面音声設定終盤序盤中盤敵味方勝負点数評価難易度標準通常特殊限定期間経過残余不足充分完了未完途中最初最後直前直後付近周辺一帯領域境界線内外側面正面背面上部下部中央端末先頭最後尾間隔距離速度加速減速回転角度方向位置座標移送搬送輸送運搬牽引推進駆動制御操縦操作管理監視観測測定計測記録保存呼出転送受信送信通達伝達報告連絡指示命令指令司令幕僚参謀将校兵士部隊軍隊編成組織構成配分割当配置配備展開集結解散撤収帰投出発到着経由通過横断縦断突破包囲奇襲強襲急襲奇策戦術戦略作戦計画立案検討評議会議討論協議交渉調整仲裁裁定"
)

def _kanji_to_tile(ch):
    """한자 한 글자를 그 원본 폰트 타일 번호로 변환(assign_tiles가 새
    한글 타일을 고를 때 BLOCKED_KANJI와 겹치는지 확인하는 용도)."""
    try:
        b = ch.encode('cp932')
    except UnicodeEncodeError:
        return None
    if len(b) != 2:
        return None
    row = b[0] - 0x81 if b[0] <= 0x9F else b[0] - 0xC1
    col = b[1] - 0x40 if b[1] < 0x7F else b[1] - 0x41
    kuten = row * 188 + col
    tile = KANJI_START_TILE + (kuten - KANJI_BASE_KUTEN)
    if tile < KANJI_START_TILE or tile >= KANJI_START_TILE + MAX_KANJI_TILES:
        return None
    return tile

BLOCKED_TILES = set(t for t in (_kanji_to_tile(c) for c in BLOCKED_KANJI) if t is not None)

def assign_tiles(text, mapping):
    used = set(int(v) for v in mapping.values())
    next_tile = (max(used) + 1) if used else KANJI_START_TILE
    for ch in text:
        # 완성형 한글 음절(가,나,다...) + 단독 자모(ㅋ,ㅠ,ㅡ 등 강조/이모티콘용)
        is_hangul = ('가' <= ch <= '힣') or ('ㄱ' <= ch <= 'ㆎ')
        is_space = ch == ' ' and SPACE_MODE == 'tile'
        is_pad = ch == BLANK_PAD_CHAR
        if (is_hangul or is_space or is_pad) and ch not in mapping:
            while next_tile in BLOCKED_TILES:
                next_tile += 1
            if next_tile >= KANJI_START_TILE + MAX_KANJI_TILES:
                raise SystemExit("배정 가능한 타일이 부족합니다 (최대 2996자)")
            mapping[ch] = next_tile
            next_tile += 1
    return mapping

# 인코딩 안 되는 서양식 문장부호 -> 일본어(JIS)에 실제로 있는 비슷한 문자로 자동 치환
PUNCT_SUBSTITUTES = {
    '·': '・',  # · (가운뎃점) -> ・ (일본어 나카구로)
    '–': '―',  # – (en dash) -> ― (일본어 장음 대시)
    '—': '―',  # — (em dash) -> ―
    '‑': '―',  # ‑ (non-breaking hyphen) -> ―
    '‒': '―',  # ‒ (figure dash) -> ―
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


def _encode_mixed_raw(text, mapping):
    out = bytearray()
    pos = 0
    for m in CONTROL_CODE_PATTERN.finditer(text):
        out += _encode_plain(text[pos:m.start()], mapping)
        out += m.group(0).encode('ascii')  # 제어 코드는 반각 그대로 통과
        pos = m.end()
    out += _encode_plain(text[pos:], mapping)
    return bytes(out)


# 게임 자체 텍스트박스가 정확히 전각 16자(32바이트)마다 자동 줄바꿈을 하는데,
# 우리가 넣는 '//' 강제 개행이 하필 그 경계와 같은 지점(직전 조각이 정확히
# 32바이트)에 오면 "자동 줄바꿈 + 강제 개행"이 겹쳐서 빈 줄이 생긴다
# (2026-08-15 확인, SPACE_MODE='skip'일 때 특히 잘 발생 - 공백이 0바이트라
# 폭이 안 흔들려서 정확히 32의 배수가 되기 쉬움).
#
# 처음엔 안 보이는 패딩 글자를 끼워 넣어 32바이트 배수 자체를 피해보려
# 했지만, 게임이 16글자를 딱 채우는 순간 커서를 다음 줄로 선점 이동시켜
# 버려서 패딩 글자가(안 보이는 글자라도) 그 다음 줄에 혼자 남게 되어
# 여전히 빈 줄처럼 보이는 문제가 있었다.
#
# 그래서 대신 그 경계에 걸리는 '//' 자체를 지운다(사용자 요청,
# 2026-08-15) - 자동 줄바꿈이 이미 그 자리에서 줄을 나눠줄 것이므로,
# 강제 개행을 또 넣을 필요가 없다.
LINE_WRAP_BYTES = 32


def _strip_wrap_boundary_breaks(text, mapping):
    """'//'로 끝나는(뒤에 강제 개행이 오는) 조각의 인코딩 바이트 길이가
    LINE_WRAP_BYTES(32, 전각 16자) 이상이면, 그 '//'를 지워서 자동
    줄바꿈에게 개행을 맡긴다. 맨 마지막 조각(뒤에 '//'가 없어 강제
    개행이 없는 부분)은 애초에 대상이 아니다.

    2026-08-15: 원래는 정확히 32의 배수(32, 64, 96...)일 때만 지웠는데,
    사용자 요청으로 32바이트 "이상"이면 배수 여부와 상관없이 무조건
    지우는 것으로 완화했다 - 어차피 그 정도 길이면 자동 줄바꿈이 이미
    한 번 이상 줄을 나눴을 것이므로. 단, 이 때문에 16자보다 긴 대부분의
    대사에서 의도적으로 넣은 '//' 줄바꿈이 함께 지워진다는 점을
    사용자도 인지하고 선택함."""
    if '//' not in text:
        return text
    segs = text.split('//')
    out_parts = [segs[0]]
    changed = False
    for i in range(1, len(segs)):
        prev_seg = segs[i - 1]
        encoded_len = len(_encode_mixed_raw(prev_seg, mapping)) if prev_seg else 0
        if encoded_len >= LINE_WRAP_BYTES:
            # 이 '//'를 지운다 - 바로 앞뒤 조각을 그냥 이어붙인다.
            out_parts[-1] = out_parts[-1] + segs[i]
            changed = True
        else:
            out_parts.append(segs[i])
    return '//'.join(out_parts) if changed else text


def encode_mixed(text, mapping):
    text = _strip_wrap_boundary_breaks(text, mapping)
    return _encode_mixed_raw(text, mapping)


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

    if ch == ' ' or ch == BLANK_PAD_CHAR:
        # 완전히 빈 타일(픽셀 전부 0)이면 게임 렌더러가 "잘라낼 잉크가
        # 없다"고 판단해 폭을 줄이지 못하고 칸 전체(2칸 크기)로 표시하는
        #것으로 보임. 거의 안 보이는 아주 작은 점 하나를 중앙에 남겨서
        # "내용이 있는 좁은 글자"로 인식되게 한다. (BLANK_PAD_CHAR도 같은
        # 이유로 동일하게 처리 - 화면에 실질적으로 안 보여야 함)
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
