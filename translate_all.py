"""
사쿠라 대전 4 번역 일괄 적용 툴
한 번 실행으로 모든 대사(SBX/SBN) + 1ST_READ.BIN 전체 문자열 +
한글 폰트(SKFONT.CG~4.CG)를 전부 만들어서 디스크에 바로 반영할 수 있는
폴더 구조로 출력합니다.

사용법 (korean_font_package 폴더에서):
  python3 translate_all.py

번역할 내용은 translation_templates/ 안의 파일들을 디스크 경로 그대로
편집해서 채워주세요 (예: translation_templates/ADVDATA/SCRIPT/S0120.txt,
translation_templates/MINIGAME/JT00SAKU.txt 등). 번역하지 않은 [번호]
줄은 자동으로 원문이 유지됩니다.

결과물은 output/ 폴더에 실제 디스크 경로 그대로 생성됩니다.
이 output 폴더를 그대로 zip으로 압축 -> 확장자 .dcp로 변경 ->
Universal Dreamcast Patcher의 Apply Patch에 사용하면 됩니다.
"""
import os, sys, argparse

# Windows 콘솔이 cp949 등이라 일본어/특수문자 출력 중 UnicodeEncodeError로
# 죽는 걸 방지 (2026-08-14) - 인코딩 안 되는 글자는 죽이지 않고 대체됨.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, 'reconfigure'):
        _stream.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # korean_font_package/
TOOLS_DIR = os.path.join(BASE_DIR, 'tools')
sys.path.insert(0, TOOLS_DIR)

from rebuild_sbx import rebuild as rebuild_sbx_file
from patch_1st_read_repoint import patch as patch_1st_read_file
from patch_esm import patch as patch_esm_file
from patch_esm_ticker import patch as patch_esm_ticker_file
from patch_lipsync import patch as patch_lipsync_file
from patch_ovlm_binary import patch as patch_ovlm_file
from patch_movecatch_binary import patch as patch_movecatch_file
from hangul_font_map import load_map, patch_skfont, set_space_mode
from auto_fill_lipsync import build_translation_dict, LINE_PATTERN as LIPSYNC_LINE_PATTERN

ORIGINAL_DIR = os.path.join(BASE_DIR, 'original_files')
TEMPLATES_DIR = os.path.join(BASE_DIR, 'translation_templates')
ORIGINAL_TXT_DIR = os.path.join(BASE_DIR, 'original_txt')
ORIGINAL_1ST_READ = os.path.join(TOOLS_DIR, '1ST_READ.BIN')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
ALL_STRINGS_TEMPLATE_REL = os.path.join('1ST_READ', 'all_1st_read_strings.txt')
ESM_NAMES = ['SMAP01', 'SMAP02', 'SMAP03', 'SMAP04', 'SMAP05']
ESM_GROUP = {'SMAP01': 'G01', 'SMAP02': 'G02', 'SMAP03': 'G03', 'SMAP04': 'G04', 'SMAP05': 'G05'}
LIPSYNC_NAMES = ['LIPSYNC1', 'LIPSYNC2', 'LIPSYNC3', 'LIPSYNC4']
OVLM_FILES = [('APPEND', 'ADVDATA/APPEND/APPEND.BIN'), ('MGJT', 'MINIGAME/MGJT.BIN')]
# 리포인팅 지원이 없는 데이터 파일들 (템플릿 경로, 디스크 상대 경로)
MOVECATCH_FILES = [
    ('ADVDATA/MOVE.txt', 'ADVDATA/MOVE.BIN'),
    ('ADVDATA/EYECATCH/EYECATCH.txt', 'ADVDATA/EYECATCH/EYECATCH.BIN'),
    ('ADVDATA/CINEMA/CINEMA.txt', 'ADVDATA/CINEMA/CINEMA.BIN'),
    ('ADVDATA/ENDING.txt', 'ADVDATA/ENDING.BIN'),
]

def find_original(base_no_ext):
    for ext in ('.SBX', '.SBN'):
        p = base_no_ext + ext
        if os.path.exists(p):
            return p
    return None

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spacing', choices=['skip', 'tile'], default='skip',
                         help="공백 처리 방식. skip=공백을 아예 안 넣고 붙여씀"
                              " / tile(기본값)=빈 한자 타일 자리를 빌려 공백을 그림(게임에서"
                              " 2칸 폭으로 보일 수 있음, 아직 원인 미해결)")
    args = parser.parse_args()
    set_space_mode(args.spacing)
    print(f"(공백 처리 방식: {args.spacing})\n")

    all_skipped = []  # (분류, 파일, 번호, 원문바이트길이, 번역시도) 전부 모아서 나중에 파일로 저장

    print("=== 1) 대사 스크립트(SBX/SBN) 처리 중 ===")
    sbx_files_done = 0
    total_sbx_lines = 0
    if os.path.isdir(TEMPLATES_DIR):
        for root, dirs, files in os.walk(TEMPLATES_DIR):
            rel_root = os.path.relpath(root, TEMPLATES_DIR)
            if rel_root.split(os.sep)[0] == '1ST_READ':
                continue  # 아래에서 별도 처리
            for fname in sorted(files):
                if not fname.endswith('.txt'):
                    continue
                rel_path = os.path.join(rel_root, fname) if rel_root != '.' else fname
                base_no_ext = os.path.join(ORIGINAL_DIR, rel_path[:-4])
                src = find_original(base_no_ext)
                if not src:
                    continue
                template_path = os.path.join(root, fname)
                out_path = os.path.join(OUTPUT_DIR, os.path.dirname(rel_path),
                                         os.path.basename(src))
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                stats = rebuild_sbx_file(src, template_path, out_path, out_font_dir=None)
                if stats['translated_count'] > 0:
                    print(f"  {rel_path}: {stats['translated_count']}/{stats['real_total']}줄 번역 적용")
                    sbx_files_done += 1
                    total_sbx_lines += stats['translated_count']
                else:
                    os.remove(out_path)
    if sbx_files_done == 0:
        print("  번역된 대사가 없습니다 (건너뜀)")

    print("\n=== 2) SRPG 전투 대사(ESM) 처리 중 ===")
    esm_files_done = 0
    total_esm_lines = 0
    for esm_name in ESM_NAMES:
        template_path = os.path.join(TEMPLATES_DIR, 'SLG_ESM', esm_name + '.txt')
        src_esm = os.path.join(ORIGINAL_DIR, 'SLG_ESM', esm_name + '.ESM')
        if not (os.path.exists(template_path) and os.path.exists(src_esm)):
            continue
        out_esm = os.path.join(OUTPUT_DIR, 'SLG', ESM_GROUP[esm_name], esm_name + '.ESM')
        os.makedirs(os.path.dirname(out_esm), exist_ok=True)
        applied, total, _, _ = patch_esm_file(src_esm, template_path, out_esm, out_font_dir=None)

        # 오프셋 표로 참조되지 않는 "상태창 짧은 문구"(고정 24바이트) 추가 반영
        ticker_orig = os.path.join(ORIGINAL_TXT_DIR, 'SLG_ESM', 'SMAP_ticker.txt')
        ticker_tpl = os.path.join(TEMPLATES_DIR, 'SLG_ESM', 'SMAP_ticker.txt')
        ticker_applied = 0
        if os.path.exists(ticker_orig) and os.path.exists(ticker_tpl) and os.path.exists(out_esm):
            ticker_applied, ticker_total, ticker_too_long, _ = patch_esm_ticker_file(
                out_esm, ticker_orig, ticker_tpl, out_esm)
            if ticker_too_long:
                print(f"    {esm_name}.ESM 상태창 문구 24바이트 초과로 건너뜀: {len(ticker_too_long)}개")

        if applied > 0 or ticker_applied > 0:
            print(f"  {esm_name}.ESM: {applied}/{total}개 대사 번역 적용, 상태창 문구 {ticker_applied}개 추가 적용 (길이 제한 없음)")
            esm_files_done += 1
            total_esm_lines += applied + ticker_applied
        else:
            os.remove(out_esm)

    print("\n=== 3) 립싱크 음성 대사(LIPSYNC) 자동 채움 + 처리 중 ===")
    lip_dir = os.path.join(TEMPLATES_DIR, 'LIPSYNC')
    if os.path.isdir(lip_dir):
        known = build_translation_dict()
        total_autofilled = 0
        for fname in sorted(os.listdir(lip_dir)):
            if not fname.endswith('.txt'):
                continue
            path = os.path.join(lip_dir, fname)
            with open(path, encoding='utf-8') as f:
                lines = f.readlines()
            filled = 0
            new_lines = []
            for line in lines:
                stripped = line.rstrip('\n')
                m = LIPSYNC_LINE_PATTERN.match(stripped)
                if m:
                    idx, text = m.group(1), m.group(2)
                    if text in known:
                        new_lines.append(f"[{idx}] {known[text]}\n")
                        filled += 1
                        continue
                new_lines.append(line if line.endswith('\n') else line + '\n')
            if filled:
                with open(path, 'w', encoding='utf-8') as f:
                    f.writelines(new_lines)
                print(f"  {fname}: 이미 번역된 대사 {filled}줄 자동으로 가져옴")
            total_autofilled += filled
        if total_autofilled == 0:
            print("  자동으로 가져올 만한 기존 번역이 없습니다 (건너뜀)")

    lip_files_done = 0
    total_lip_lines = 0
    for lip_name in LIPSYNC_NAMES:
        template_path = os.path.join(TEMPLATES_DIR, 'LIPSYNC', lip_name + '.txt')
        src_lip = os.path.join(ORIGINAL_DIR, 'ADVDATA', lip_name + '.LIP')
        if not (os.path.exists(template_path) and os.path.exists(src_lip)):
            continue
        out_lip = os.path.join(OUTPUT_DIR, 'ADVDATA', lip_name + '.LIP')
        os.makedirs(os.path.dirname(out_lip), exist_ok=True)
        applied, total, _, encode_failed, too_long = patch_lipsync_file(src_lip, template_path, out_lip, out_font_dir=None)
        if applied > 0:
            print(f"  {lip_name}.LIP: {applied}/{total}개 대사 번역 적용 (표 값 불변, pre+text 합친 공간 안에서만)")
            if too_long:
                print(f"    주의: 공간 부족으로 원문 유지 {len(too_long)}개")
                for i, orig, trans, need, have in too_long:
                    print(f"      [{i:04d}] 필요 {need}바이트 > 가용 {have}바이트: {trans!r}")
                    all_skipped.append(('립싱크 음성대사(LIPSYNC)', f'{lip_name}.LIP', i, orig, trans, have))
            if encode_failed:
                print(f"    주의: 인코딩 실패 {len(encode_failed)}개 (한글 매핑 문제 등)")
                for i, orig, trans in encode_failed:
                    print(f"      [{i:04d}] 원문: {orig!r} 번역: {trans!r}")
                    all_skipped.append(('립싱크 음성대사(LIPSYNC)', f'{lip_name}.LIP', i, orig, trans, 0))
            lip_files_done += 1
            total_lip_lines += applied
        else:
            os.remove(out_lip)

    print("\n=== 4) 기타 실행 오버레이(APPEND/MGJT 등) 처리 중 ===")
    ovlm_files_done = 0
    total_ovlm_lines = 0
    for name, rel_disc_path in OVLM_FILES:
        template_path = os.path.join(TEMPLATES_DIR, 'OVLM', name + '.txt')
        src_bin = os.path.join(ORIGINAL_DIR, rel_disc_path)
        if not (os.path.exists(template_path) and os.path.exists(src_bin)):
            continue
        out_bin = os.path.join(OUTPUT_DIR, rel_disc_path)
        os.makedirs(os.path.dirname(out_bin), exist_ok=True)
        applied, total, _, skipped = patch_ovlm_file(src_bin, template_path, out_bin, out_font_dir=None)
        if applied > 0:
            print(f"  {name}: {applied}/{total}개 문자열 번역 적용 (리포인팅 지원)")
            if skipped:
                print(f"    주의: 포인터를 못 찾아 원문보다 길게 못 넣은 항목 {len(skipped)}개")
                for i, orig, trans, orig_len in skipped:
                    print(f"      [{i:04d}] 원문 {orig_len}바이트: {trans!r}")
                    all_skipped.append(('기타 오버레이', f'{name} ({rel_disc_path})', i, orig, trans, orig_len))
            ovlm_files_done += 1
            total_ovlm_lines += applied
        else:
            os.remove(out_bin)

    print("\n=== 4-1) 장소 이동/상태 표시 데이터(MOVE/EYECATCH/CINEMA/ENDING.BIN) 처리 중 ===")
    movecatch_files_done = 0
    total_movecatch_lines = 0
    for template_rel, rel_disc_path in MOVECATCH_FILES:
        template_path = os.path.join(TEMPLATES_DIR, template_rel)
        src_bin = os.path.join(ORIGINAL_DIR, rel_disc_path)
        if not (os.path.exists(template_path) and os.path.exists(src_bin)):
            continue
        out_bin = os.path.join(OUTPUT_DIR, rel_disc_path)
        os.makedirs(os.path.dirname(out_bin), exist_ok=True)
        applied, total, _, too_long = patch_movecatch_file(src_bin, template_path, out_bin, out_font_dir=None)
        if applied > 0:
            name = os.path.basename(rel_disc_path)
            print(f"  {name}: {applied}/{total}개 문자열 번역 적용")
            if too_long:
                print(f"    주의: 원문보다 길어서 못 넣은 항목 {len(too_long)}개")
                for i, orig, trans, enc_len, orig_len in too_long:
                    print(f"      [{i:04d}] 원문 {orig_len}바이트: {trans!r}")
                    all_skipped.append(('장소이동/상태(MOVE 등)', f'{name}', i, orig, trans, orig_len))
            movecatch_files_done += 1
            total_movecatch_lines += applied
        else:
            os.remove(out_bin)

    print("\n=== 5) 1ST_READ.BIN 전체 문자열 처리 중 ===")
    applied_msgs, total_msgs = 0, 0
    all_strings_template = os.path.join(TEMPLATES_DIR, ALL_STRINGS_TEMPLATE_REL)
    if os.path.exists(all_strings_template) and os.path.exists(ORIGINAL_1ST_READ):
        out_1st_read = os.path.join(OUTPUT_DIR, '1ST_READ.BIN')
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        try:
            stats1st = patch_1st_read_file(
                ORIGINAL_1ST_READ, all_strings_template, out_1st_read, out_font_dir=None)
        except SystemExit as e:
            print(f"  {e}")
            print("  1ST_READ.BIN 처리를 건너뛰고 나머지는 계속 진행합니다.")
            stats1st = None

        if stats1st is None:
            if os.path.exists(out_1st_read):
                os.remove(out_1st_read)
        else:
            applied_msgs = stats1st['applied_inplace'] + stats1st['applied_repoint']
            total_msgs = stats1st['real_total']
            if applied_msgs > 0:
                print(f"  1ST_READ.BIN: {applied_msgs}/{total_msgs}개 문자열 번역 적용"
                      f" (제자리 {stats1st['applied_inplace']}개, 리포인팅 {stats1st['applied_repoint']}개)")
                if stats1st['skipped_no_room']:
                    print(f"  주의: 포인터를 못 찾아 원문보다 길게 못 넣은 항목 {len(stats1st['skipped_no_room'])}개"
                          " (아래 번호를 원문 길이 이내로 줄이면 반영됩니다)")
                    for i, orig, trans, orig_len in stats1st['skipped_no_room']:
                        budget = orig_len // 2
                        print(f"    [{i:03d}] 원문 {orig_len}바이트(한글 약 {budget}자까지) - "
                              f"지금 번역: {trans!r}")
                        all_skipped.append(('시스템 메시지(1ST_READ.BIN)', '1ST_READ.BIN', i, orig, trans, orig_len))
            else:
                print("  번역된 내용이 없습니다 (건너뜀)")
                os.remove(out_1st_read)
    else:
        print("  translation_templates/1ST_READ/all_1st_read_strings.txt 또는 1ST_READ.BIN을 찾을 수 없어 건너뜀")

    print("\n=== 6) 한글 폰트 생성 중 ===")
    hangul_map = load_map()
    num_hangul = len(hangul_map)
    if num_hangul > 0:
        patch_skfont(TOOLS_DIR, OUTPUT_DIR, hangul_map)
        print(f"  한글 {num_hangul}자 -> output/ 에 SKFONT.CG, SKFONT2.CG, SKFONT3.CG, SKFONT4.CG 생성")
    else:
        print("  번역된 한글이 없어 폰트는 생성하지 않았습니다.")

    print("\n=== 완료 ===")
    print(f"대사 파일 {sbx_files_done}개 ({total_sbx_lines}줄), "
          f"ESM 전투대사 {esm_files_done}개 파일({total_esm_lines}줄), "
          f"립싱크 대사 {lip_files_done}개 파일({total_lip_lines}줄), "
          f"기타 오버레이 {ovlm_files_done}개 파일({total_ovlm_lines}개), "
          f"장소이동/상태 {movecatch_files_done}개 파일({total_movecatch_lines}개), "
          f"1ST_READ.BIN 문자열 {applied_msgs}개, 한글 {num_hangul}자")
    print(f"결과물 폴더: {OUTPUT_DIR}")
    print("이 폴더 안의 내용을 그대로 zip으로 압축한 뒤 확장자를 .dcp로 바꿔서")
    print("Universal Dreamcast Patcher의 Apply Patch에 사용하세요.")

    skipped_report_path = os.path.join(BASE_DIR, '길이초과_건너뜀_목록.txt')
    if all_skipped:
        with open(skipped_report_path, 'w', encoding='utf-8') as f:
            f.write(f"번역문이 원문보다 길어서 이번 실행에서 건너뛴 항목 목록 (총 {len(all_skipped)}개)\n")
            f.write("이 항목들은 현재 output/ 안에서 원문(일본어) 그대로 남아 있습니다.\n")
            f.write("번역문을 원문 바이트 길이 이내로 줄인 뒤 translate_all.py를 다시 실행하면 반영됩니다.\n")
            f.write("=" * 70 + "\n\n")
            last_category = None
            for category, filename, i, orig, trans, orig_len in all_skipped:
                if category != last_category:
                    f.write(f"\n--- {category} ---\n")
                    last_category = category
                f.write(f"[{filename}] [{i:04d}] 원문 {orig_len}바이트\n")
                f.write(f"  원문: {orig}\n")
                f.write(f"  지금 번역(너무 김): {trans}\n\n")
        print(f"\n주의: 원문보다 길어서 건너뛴 항목이 총 {len(all_skipped)}개 있습니다.")
        print(f"목록 파일: {skipped_report_path}")
        print("이 파일을 열어보시면 어느 파일의 몇 번 줄을 줄여야 하는지 한눈에 보입니다.")
    else:
        if os.path.exists(skipped_report_path):
            os.remove(skipped_report_path)

if __name__ == '__main__':
    main()
