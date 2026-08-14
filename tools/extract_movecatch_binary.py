"""MOVE.BIN, EYECATCH.BIN, CINEMA.BIN, ENDING.BIN 처럼 null(\\x00)로 구분된
Shift-JIS 문자열이 여기저기 흩어져 있는 데이터 파일에서 실제 텍스트만
골라내는 도구. scan_strings()의 2바이트 페어 검증만으로는 애니메이션/
스크립트 바이트코드가 우연히 유효한 SJIS로 디코딩되는 오탐이 너무 많아서
(예: CINEMA.BIN), 여기에 히라가나/가타카나 2글자 연속 조건을 추가로
요구해 노이즈를 걸러낸다. (조사 없이 명사만 나열되는 라벨류는 히라가나가
없을 수 있어 가타카나 2글자 연속도 함께 허용한다 - 캐릭터 이름 등)
"""
import re, os, sys
CONTROL_CODE_PATTERN = re.compile(
    r'@(?:fs[0-9]+,[0-9]+|fm[0-9]+,[0-9]+|lm[0-9]+,[0-9]+|c[0-9]+|x)')
KANA_RUN = re.compile(r'[぀-ヿ]{2,}')

def real_text_filter(text):
    # "@fs22,22@fm24,0" 같은 제어 코드로 시작하는 문자열은 UI 라벨
    # 목록(장소 이름 등)으로 의도적으로 배치된 것이라 가나가 없는
    # 순수 한자 단어(계단, 음악실 등)라도 노이즈일 확률이 낮다.
    if CONTROL_CODE_PATTERN.match(text):
        rest = CONTROL_CODE_PATTERN.sub('', text)
        # 뒤에 "@fi0,0" 같이 우리가 못 지운 제어 코드가 더 남아있으면
        # (전부 제어 코드뿐인 라인) 실제 라벨이 아니므로 제외한다.
        return 1 <= len(rest) <= 15 and '@' not in rest
    # 진짜 텍스트에는 \t, \x0b 같은 제어 문자가 섞여 나올 수 없다 -
    # 애니메이션/스크립트 바이트코드가 우연히 유효한 SJIS로 디코딩된
    # 노이즈를 걸러낸다.
    if any(ord(c) < 0x20 for c in text):
        return False
    return bool(KANA_RUN.search(text))

def find_real_strings(data):
    """null 구분 문자열 목록을 (offset, byte_len, text) 형태로 반환.

    맨 앞에 사설영역(PUA) 문자로 디코딩되는 아이콘 바이트가 붙어있는
    경우(예: ENDING.BIN의 0xF0 0x43)가 있는데, 이건 실제 텍스트가
    아니라 텍스트 앞에 찍히는 아이콘 그림 코드이므로 번역 대상에서
    빼고 pos/byte_len을 그만큼 밀어서 그 바이트는 그대로 보존한다."""
    results = []
    pos = 0
    for part in data.split(b'\x00'):
        if part:
            try:
                text = part.decode('cp932')
                skip_bytes = 0
                while text and 0xE000 <= ord(text[0]) <= 0xF8FF:
                    text = text[1:]
                    skip_bytes += 2
                if real_text_filter(text):
                    results.append((pos + skip_bytes, len(part) - skip_bytes, text))
            except UnicodeDecodeError:
                pass
        pos += len(part) + 1
    return results

if __name__ == '__main__':
    import json
    path = sys.argv[1]
    out_txt = sys.argv[2]
    out_manifest = sys.argv[3] if len(sys.argv) > 3 else out_txt.replace('.txt', '.manifest.json')

    with open(path, 'rb') as f:
        data = f.read()
    results = find_real_strings(data)

    lines_out = []
    manifest = []
    for idx, (pos, blen, text) in enumerate(results):
        lines_out.append(f"[{idx:04d}] {text}")
        manifest.append({'idx': idx, 'pos': pos, 'byte_len': blen})

    os.makedirs(os.path.dirname(out_txt) or '.', exist_ok=True)
    with open(out_txt, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines_out) + '\n')
    with open(out_manifest, 'w', encoding='utf-8') as f:
        json.dump(manifest, f)
    print(f"{len(results)}개 문자열 -> {out_txt}")
