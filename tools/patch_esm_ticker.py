"""SMAPnn.ESM 안에 있는 "짧은 상태창 문구"(고정 24바이트 필드) 재삽입 툴.

이 필드는 일반 CTPA/ASCR 오프셋 표가 가리키는 지점보다 *앞쪽*에 있는
텍스트다 - 즉, 우리가 지금까지 번역해 온 "// 뒤쪽" 대사와 같은
null-종료 문자열의 앞부분인데, 그 앞부분 시작 지점을 가리키는 표 항목이
파일 안 어디에도 없다(확인 완료). 그런데도 실기에서 이 앞부분이 실제
화면(상태창/전투 시작 문구)에 표시되는 것으로 보아, ASCR 표가 아닌
다른 경로(실행 코드 안의 직접 참조 등, 아직 못 찾음)로 읽히는 것으로
추정된다.

정확한 참조 방식을 모르기 때문에 안전하게 "제자리 교체만" 한다:
  - 이 24바이트 구간의 시작 위치는 원문 텍스트를 파일 안에서 검색해서
    찾는다(하드코딩된 오프셋을 쓰지 않음 - 더 안전).
  - 번역문이 24바이트 이내면 그 자리에 덮어쓰고 나머지는 0으로 채운다.
  - 24바이트를 넘으면 건너뛴다(레이아웃을 밀거나 포인터를 바꾸는 시도를
    하지 않음 - 참조 방식을 모르는 상태에서 포인터를 함부로 바꾸면
    ESM 레이아웃을 밀어서 게임이 멈췄던 전례가 있음).

사용법:
  python patch_esm_ticker.py <원본.ESM> <번역텍스트.txt> <출력.ESM>
  (전용 원문 목록은 SMAP_ticker.txt 사용 - translation_io.parse_translation_file
   형식과 동일하게 [번호] 원문/번역문 한 줄씩)
"""
import sys, os
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from hangul_font_map import load_map, save_map, assign_tiles, encode_mixed
from translation_io import parse_translation_file

BUDGET = 24

def find_original_list(path):
    """SMAP_ticker.txt 형식([번호] 텍스트)에서 순서대로 원문 리스트 추출."""
    import re
    items = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            m = re.match(r'^\[(\d+)\]\s?(.*)$', line.rstrip('\n'))
            if m:
                items.append(m.group(1))
    return items

def patch(esm_path, orig_list_path, translation_path, out_path):
    with open(esm_path, 'rb') as f:
        data = bytearray(f.read())

    orig_texts = {}
    import re
    with open(orig_list_path, encoding='utf-8') as f:
        for line in f:
            m = re.match(r'^\[(\d+)\]\s?(.*)$', line.rstrip('\n'))
            if m:
                orig_texts[int(m.group(1))] = m.group(2)
    translations = parse_translation_file(translation_path)

    hangul_map = load_map()
    for text in translations.values():
        if text:
            assign_tiles(text, hangul_map)
    save_map(hangul_map)

    applied = 0
    too_long = []
    not_found = []
    search_from = 0
    for idx in sorted(orig_texts.keys()):
        orig_text = orig_texts[idx]
        orig_bytes = orig_text.encode('cp932')
        pos = bytes(data).find(orig_bytes, search_from)
        if pos == -1:
            not_found.append((idx, orig_text))
            continue
        search_from = pos + 1  # 같은 문구가 반복돼도 다음번엔 그다음 위치부터

        new_text = translations.get(idx)
        if not new_text or new_text == orig_text:
            continue
        try:
            encoded = encode_mixed(new_text, hangul_map)
        except UnicodeEncodeError as e:
            raise SystemExit(f"[{idx}]번 인코딩 실패: {e}\n  텍스트: {new_text!r}")
        if len(encoded) > BUDGET:
            too_long.append((idx, orig_text, new_text, len(encoded)))
            continue
        data[pos:pos+len(encoded)] = encoded
        data[pos+len(encoded):pos+BUDGET] = b'\x00' * (BUDGET - len(encoded))
        applied += 1

    with open(out_path, 'wb') as f:
        f.write(bytes(data))

    return applied, len(orig_texts), too_long, not_found

if __name__ == '__main__':
    if len(sys.argv) < 5:
        print(__doc__)
        sys.exit(1)
    applied, total, too_long, not_found = patch(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
    print(f"완료: {applied}/{total}개 상태창 문구 적용")
    if too_long:
        print(f"24바이트 초과로 건너뜀: {len(too_long)}개")
        for idx, orig, trans, enc_len in too_long:
            print(f"  [{idx}] {enc_len}B: {trans!r}")
    if not_found:
        print(f"원문을 못 찾음: {len(not_found)}개")
        for idx, orig in not_found:
            print(f"  [{idx}] {orig!r}")
