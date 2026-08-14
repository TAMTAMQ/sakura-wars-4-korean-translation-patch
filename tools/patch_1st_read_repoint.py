"""
1ST_READ.BIN 재삽입 툴 (리포인팅 지원 버전)
포인터를 찾을 수 있는 메시지는 원문보다 길게 번역해도 됩니다
(새 텍스트를 파일 끝에 추가하고, 그걸 가리키도록 포인터를 바꿔치기).
포인터를 못 찾은 일부 메시지는 기존처럼 원문 길이 제약이 적용됩니다.

사용법:
  python3 patch_1st_read_repoint.py <원본 1ST_READ.BIN> <번역텍스트.txt> <출력 1ST_READ.BIN> [출력 폰트폴더]
"""
import sys, re, os, struct
from extract_1st_read_all import scan_strings, is_excluded
from hangul_font_map import load_map, save_map, assign_tiles, encode_mixed, encode_mixed_fit, patch_skfont
from translation_io import parse_translation_file

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_ADDR = 0x8c010000

def find_all_messages(data):
    results = scan_strings(data, start=2100000)
    return [(s, blen, text) for s, blen, text in results if not is_excluded(s)]

def find_pointers(data, file_offset):
    mem_addr = BASE_ADDR + file_offset
    target = struct.pack('<I', mem_addr)
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

    messages = find_all_messages(bytes(data))
    translations = parse_translation_file(translation_path)

    # 번역 템플릿은 [번호]가 곧 이 1ST_READ.BIN을 스캔했을 때의 순번이라고
    # 가정하고 매칭한다 (아래 for 루프의 translations.get(i)). 그런데
    # bin_path로 들어온 파일이 번역 템플릿을 만들 때 쓴 파일과 다르면
    # (예: 추출 중 일부가 깨진 다른 복사본), 스캔 결과 개수/순서가
    # 어긋나서 "원문"과 "번역"이 서로 다른 문장을 가리키는 상태로 조용히
    # 패치가 진행되고, 엉뚱한 길이초과 보고서까지 나온다. 이런 사고를
    # 막기 위해 개수가 다르면 그 자리에서 바로 멈춘다.
    expected = max(translations.keys()) + 1 if translations else 0
    if len(messages) != expected:
        raise SystemExit(
            f"[1ST_READ.BIN 불일치] 지금 스캔한 문자열 개수({len(messages)}개)가 "
            f"번역 템플릿의 항목 개수({expected}개)와 다릅니다.\n"
            f"  -> '{bin_path}' 파일이 translation_templates/1ST_READ/"
            f"all_1st_read_strings.txt를 만들 때 쓴 파일과 다른 것으로 보입니다.\n"
            f"  이 상태로 진행하면 원문과 번역이 서로 다른 문장으로 잘못 짝지어질 "
            f"수 있어 안전하게 중단합니다. 원본 디스크에서 1ST_READ.BIN을 다시 "
            f"확인해서 넣어주세요.")

    hangul_map = load_map()
    for text in translations.values():
        if text:
            assign_tiles(text, hangul_map)
    save_map(hangul_map)

    appended = bytearray()
    applied_inplace = 0
    applied_repoint = 0
    skipped_no_room = []

    for i, (start, orig_len, orig_text) in enumerate(messages):
        text = translations.get(i)
        if not text or text == orig_text:
            continue

        try:
            encoded = encode_mixed(text, hangul_map)
        except UnicodeEncodeError as e:
            raise SystemExit(f"[{i:03d}]번 인코딩 실패: {e}\n  텍스트: {text!r}")

        if len(encoded) <= orig_len:
            # 원문 자리에 그대로 들어감 (제자리 교체)
            data[start:start+len(encoded)] = encoded
            data[start+len(encoded):start+orig_len] = b'\x00' * (orig_len - len(encoded))
            applied_inplace += 1
        else:
            # 원문보다 길다 -> 포인터를 찾아서 새 위치로 리포인팅 시도
            pointer_positions = find_pointers(bytes(data), start)
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

    return {
        'applied_inplace': applied_inplace,
        'applied_repoint': applied_repoint,
        'skipped_no_room': skipped_no_room,
        'total': len(messages),
        'hangul_count': len(hangul_map),
        'appended_bytes': len(appended),
    }

if __name__ == '__main__':
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    out_font_dir = sys.argv[4] if len(sys.argv) > 4 else 'patched_fonts'
    stats = patch(sys.argv[1], sys.argv[2], sys.argv[3], out_font_dir)
    print(f"완료: 제자리교체 {stats['applied_inplace']}개, 리포인팅 {stats['applied_repoint']}개")
    print(f"파일 끝에 추가된 바이트: {stats['appended_bytes']}")
    if stats['skipped_no_room']:
        print(f"경고: 포인터를 못 찾아서 적용 못한 항목 {len(stats['skipped_no_room'])}개:")
        for i, orig, trans, orig_len in stats['skipped_no_room']:
            print(f"  [{i:03d}] 원문 {orig_len}바이트(한글 약 {orig_len//2}자까지) 원문보다 길어서 실패: {trans!r}")
    print(f"한글 {stats['hangul_count']}자 -> {out_font_dir}/ 에 폰트 생성됨")
