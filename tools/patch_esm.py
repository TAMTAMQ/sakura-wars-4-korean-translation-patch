"""SMAPnn.ESM (SRPG 전투 대사) 재삽입 툴.

이전 버전은 청크(CTPA/ASCR) 전체를 오프셋 표까지 다시 계산해서 통째로
재조립했는데(청크가 커지면 뒤 데이터가 전부 밀림), 실제 게임에서 첫
전투 진입과 동시에 멈추는 문제가 확인됐다(2026-08-14). 그래서
esm_format.rebuild_repoint() 방식으로 교체했다: 모든 청크가 원래 파일
위치·크기 그대로 유지되고(아무 바이트도 안 밀림), 번역문이 원래 자리에
안 들어가는 항목만 파일 맨 끝에 새로 추가하고 그 항목의 오프셋 표 값
하나만 그쪽을 가리키게 바꾼다. ASCR/CTPA 포맷 자체가 이미 표를 통한
간접 참조 구조라서 이 값만 바꾸면 되고, 그 무엇도 옮길 필요가 없다.

사용법:
  python patch_esm.py <원본.ESM> <번역텍스트.txt> <출력.ESM> [폰트출력폴더]
"""
import sys, os
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import esm_format as ef
from hangul_font_map import load_map, save_map, assign_tiles, encode_mixed, patch_skfont
from translation_io import parse_translation_file

def is_real_text(t):
    return bool(t) and any(ord(c) >= 0x3000 for c in t)

def patch(esm_path, translation_path, out_path, out_font_dir=None):
    with open(esm_path, 'rb') as f:
        data = f.read()
    chunks = ef.scan_esm(data)
    translations = parse_translation_file(translation_path)

    hangul_map = load_map()
    for text in translations.values():
        if text:
            assign_tiles(text, hangul_map)
    save_map(hangul_map)

    translations_by_chunk = {}
    total = 0
    idx = 0
    for c in chunks:
        chunk_trans = {}
        for li, t in enumerate(c['texts']):
            if not is_real_text(t):
                continue
            new_text = translations.get(idx)
            if new_text and new_text != t:
                chunk_trans[li] = new_text
            idx += 1
        if chunk_trans:
            translations_by_chunk[c['offset']] = chunk_trans
    total = idx

    rebuilt, applied_inplace, applied_repoint, encode_failed = ef.rebuild_repoint(
        data, chunks, translations_by_chunk, hangul_map)
    with open(out_path, 'wb') as f:
        f.write(rebuilt)

    if out_font_dir and hangul_map:
        patch_skfont(SCRIPT_DIR, out_font_dir, hangul_map)

    applied = applied_inplace + applied_repoint
    return applied, total, len(hangul_map), encode_failed

if __name__ == '__main__':
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    out_font_dir = sys.argv[4] if len(sys.argv) > 4 else 'patched_fonts'
    applied, total, num_hangul, failed = patch(sys.argv[1], sys.argv[2], sys.argv[3], out_font_dir)
    print(f"완료: {applied}/{total}개 대사 번역 적용 (길이 제한 없음, 레이아웃 안 밀림)")
    if failed:
        print(f"인코딩 실패: {len(failed)}개")
