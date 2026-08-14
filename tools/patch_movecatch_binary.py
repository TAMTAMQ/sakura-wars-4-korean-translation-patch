"""MOVE.BIN, EYECATCH.BIN, CINEMA.BIN, ENDING.BIN 재삽입 툴.

이 파일들은 1ST_READ.BIN/APPEND.BIN/MGJT.BIN과 달리 실행 코드가 아니라
데이터 파일이라, 문자열을 가리키는 절대주소 포인터가 코드 안에 있다는
보장이 없다. 그래서 리포인팅을 시도하지 않고, LIPSYNC/SLG_ESM과 같은
방식으로 원문 Shift-JIS 바이트 길이 이내로만 안전하게 제자리 교체한다
(넘치는 항목은 건너뛰고 목록으로 보고).

사용법:
  python patch_movecatch_binary.py <원본.BIN> <번역텍스트.txt> <출력.BIN> [폰트출력폴더]
"""
import sys, os
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from extract_movecatch_binary import find_real_strings
from hangul_font_map import load_map, save_map, assign_tiles, encode_mixed_fit, patch_skfont
from translation_io import parse_translation_file

def patch(bin_path, translation_path, out_path, out_font_dir=None):
    with open(bin_path, 'rb') as f:
        data = bytearray(f.read())

    strings = find_real_strings(bytes(data))
    translations = parse_translation_file(translation_path)

    hangul_map = load_map()
    for text in translations.values():
        if text:
            assign_tiles(text, hangul_map)
    save_map(hangul_map)

    applied = 0
    too_long = []

    for i, (start, orig_len, orig_text) in enumerate(strings):
        text = translations.get(i)
        if not text or text == orig_text:
            continue

        try:
            encoded = encode_mixed_fit(text, hangul_map, orig_len)
        except UnicodeEncodeError as e:
            raise SystemExit(f"[{i:04d}]번 인코딩 실패: {e}\n  텍스트: {text!r}")

        if len(encoded) > orig_len:
            too_long.append((i, orig_text, text, len(encoded), orig_len))
            continue

        data[start:start+len(encoded)] = encoded
        data[start+len(encoded):start+orig_len] = b'\x00' * (orig_len - len(encoded))
        applied += 1

    with open(out_path, 'wb') as f:
        f.write(data)

    if out_font_dir and hangul_map:
        patch_skfont(SCRIPT_DIR, out_font_dir, hangul_map)

    return applied, len(strings), len(hangul_map), too_long

if __name__ == '__main__':
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    out_font_dir = sys.argv[4] if len(sys.argv) > 4 else 'patched_fonts'
    applied, total, num_hangul, too_long = patch(sys.argv[1], sys.argv[2], sys.argv[3], out_font_dir)
    print(f"완료: {applied}/{total}개 문자열 번역 적용")
    if too_long:
        print(f"원문보다 길어서 건너뛴 항목: {len(too_long)}개")
        for i, orig, trans, enc_len, budget in too_long:
            print(f"  [{i:04d}] 원문 {budget}바이트, 번역 {enc_len}바이트: {trans!r}")
