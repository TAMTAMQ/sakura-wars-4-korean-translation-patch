"""APPEND.BIN, MGJT.BIN 등 OVLM 실행 오버레이 파일 재삽입 툴 (리포인팅 지원).

이 게임의 OVLM 오버레이는 항상 같은 메모리 주소(0x8c6386c0)에 올려서
실행된다 (APPEND.BIN 문자열 252개 전부, MGJT.BIN 문자열 266개 중 255개가
이 주소 + 파일오프셋 값을 가리키는 절대 포인터를 파일 안에서 실제로
찾을 수 있어서 확인됨 - OVLM 헤더의 로드 주소 필드보다 32바이트 낮은
값이다. 1ST_READ.BIN(patch_1st_read_repoint.py)과 완전히 같은 원리:
포인터를 찾을 수 있는 문자열은 원문보다 길게 번역해도 파일 끝에 새로
붙이고 포인터만 바꿔치기해서 반영한다. 포인터를 못 찾은 소수(예:
디버그 전용이라 실제로 참조되지 않는 문자열)만 기존처럼 원문 길이
제약이 남는다.

사용법:
  python patch_ovlm_binary.py <원본.BIN> <번역텍스트.txt> <출력.BIN> [폰트출력폴더]
"""
import sys, os, struct
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from extract_ovlm_binary import find_real_strings
from hangul_font_map import load_map, save_map, assign_tiles, encode_mixed, encode_mixed_fit, patch_skfont
from translation_io import parse_translation_file

BASE_ADDR = 0x8c6386c0

def find_pointers(data, addr):
    target = struct.pack('<I', addr)
    idx, positions = 0, []
    while True:
        idx = data.find(target, idx)
        if idx == -1:
            break
        positions.append(idx)
        idx += 1
    return positions

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

    appended = bytearray()
    applied_inplace = 0
    applied_repoint = 0
    skipped_no_room = []

    for i, (start, orig_len, orig_text) in enumerate(strings):
        text = translations.get(i)
        if not text or text == orig_text:
            continue

        try:
            encoded = encode_mixed(text, hangul_map)
        except UnicodeEncodeError as e:
            raise SystemExit(f"[{i:04d}]번 인코딩 실패: {e}\n  텍스트: {text!r}")

        if len(encoded) <= orig_len:
            data[start:start+len(encoded)] = encoded
            data[start+len(encoded):start+orig_len] = b'\x00' * (orig_len - len(encoded))
            applied_inplace += 1
        else:
            pointer_positions = find_pointers(bytes(data), BASE_ADDR + start)
            if not pointer_positions:
                # 리포인팅할 포인터를 못 찾았을 때만 마지막으로 공백을
                # 없앤 버전으로 제자리에 들어가는지 한 번 더 시도한다.
                encoded_fit = encode_mixed_fit(text, hangul_map, orig_len)
                if len(encoded_fit) <= orig_len:
                    data[start:start+len(encoded_fit)] = encoded_fit
                    data[start+len(encoded_fit):start+orig_len] = b'\x00' * (orig_len - len(encoded_fit))
                    applied_inplace += 1
                    continue
                skipped_no_room.append((i, orig_text, text, orig_len))
                continue
            new_file_offset = len(data) + len(appended)
            new_addr = BASE_ADDR + new_file_offset
            appended.extend(encoded)
            appended.append(0)
            for pp in pointer_positions:
                struct.pack_into('<I', data, pp, new_addr)
            applied_repoint += 1

    data.extend(appended)

    with open(out_path, 'wb') as f:
        f.write(data)

    if out_font_dir and hangul_map:
        patch_skfont(SCRIPT_DIR, out_font_dir, hangul_map)

    applied = applied_inplace + applied_repoint
    return applied, len(strings), len(hangul_map), skipped_no_room

if __name__ == '__main__':
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    out_font_dir = sys.argv[4] if len(sys.argv) > 4 else 'patched_fonts'
    applied, total, num_hangul, skipped = patch(sys.argv[1], sys.argv[2], sys.argv[3], out_font_dir)
    print(f"완료: {applied}/{total}개 문자열 번역 적용")
    if skipped:
        print(f"포인터를 못 찾아서 원문 길이 제약이 남은 항목: {len(skipped)}개")
        for i, orig, trans, orig_len in skipped:
            print(f"  [{i:04d}] 원문 {orig_len}바이트: {trans!r}")
