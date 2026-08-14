"""LIPSYNC*.LIP (음성 립싱크 대사) 재삽입 툴.

원본 파일 안에서 항목 하나의 실제 원문은 표의 pre 구간에 있는 텍스트
(있는 경우) + text(off_b) 구간을 합친 것이다 (자세한 내용은
lipsync_format.py 참고). 번역 템플릿은 이 합쳐진 전체 문장을 표 행
번호(row) 기준으로 담고 있다 (build_lipsync_full_templates.py로 생성).

표(off_a/off_b) 값은 절대 바꾸지 않는다 - 파일 끝에 번역문을 추가하고
표 값만 그쪽을 가리키게 바꾸는 repoint 방식을 썼더니 실제 게임에서
자막이 앞부분 몇 글자만 나오고 멈추는 현상이 확인됐다(2026-08-14).
대신 pre_text+text를 합친 공간 안에서만 번역문을 채워넣고, 그 공간에
안 들어가는 긴 번역문은 원문을 그대로 유지한다(건너뜀). 자세한 이유는
lipsync_format.rebuild_repoint() 참고.

사용법:
  python patch_lipsync.py <원본.LIP> <번역텍스트.txt> <출력.LIP> [폰트출력폴더]
"""
import sys, os
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import lipsync_format as lf
from hangul_font_map import load_map, save_map, assign_tiles, encode_mixed, patch_skfont
from translation_io import parse_translation_file

def patch(lip_path, translation_path, out_path, out_font_dir=None):
    with open(lip_path, 'rb') as f:
        data = f.read()
    parsed = lf.parse(data)
    translations = parse_translation_file(translation_path)

    hangul_map = load_map()
    for text in translations.values():
        if text:
            assign_tiles(text, hangul_map)
    save_map(hangul_map)

    rebuilt, applied, too_long, encode_failed = lf.rebuild_repoint(
        data, parsed, translations, hangul_map)
    with open(out_path, 'wb') as f:
        f.write(rebuilt)

    if out_font_dir and hangul_map:
        patch_skfont(SCRIPT_DIR, out_font_dir, hangul_map)

    return applied, parsed['count'], len(hangul_map), encode_failed, too_long

if __name__ == '__main__':
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    out_font_dir = sys.argv[4] if len(sys.argv) > 4 else 'patched_fonts'
    applied, total, num_hangul, failed, too_long = patch(sys.argv[1], sys.argv[2], sys.argv[3], out_font_dir)
    print(f"완료: {applied}/{total}개 대사 번역 적용 (레이아웃 안 밀림, 표 값 불변)")
    if too_long:
        print(f"공간 부족으로 원문 유지(건너뜀): {len(too_long)}개")
        for k, orig, trans, need, have in too_long:
            print(f"  [{k:04d}] 필요 {need}바이트 > 가용 {have}바이트: {trans!r}")
    if failed:
        print(f"인코딩 실패(한글 매핑 문제 등): {len(failed)}개")
        for k, orig, trans in failed:
            print(f"  [{k:04d}] 원문: {orig!r} 번역: {trans!r}")
