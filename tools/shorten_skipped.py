"""길이초과_건너뜀_목록.txt 를 읽어서, 원문 바이트 길이를 넘긴 번역문들을
아래 규칙을 순서대로 적용해 줄인 뒤 translation_templates/ 의 해당
줄에 다시 써넣는다.

  1) 원문이 "る。//" 로 시작하면(앞줄에서 이어지는 조각) 번역문도
     그 조각을 어설프게 옮긴 "루.//" 같은 앞부분이 붙는 경우가 많다.
     번역문의 첫 "//" 까지(포함) 잘라낸다.
  2) 번역문 안의 반각 공백(' ')을 전부 제거한다.
  3) "단어(한자)" 형태로 덧붙은 한자 풀이 괄호를 제거한다.
  4) 그래도 넘치면 말줄임표(…)를 제거한다.

각 단계 뒤에 실제 인코딩 바이트 길이(encode_mixed, 프로젝트 표준 인코더)를
원문 바이트 길이와 비교해서, 맞으면 그 단계에서 멈춘다.

사용법:
  python shorten_skipped.py            # 미리보기만, 파일 변경 없음
  python shorten_skipped.py --apply    # 실제로 템플릿 파일에 반영
"""
import sys, os, re, json, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from hangul_font_map import load_map, encode_mixed

BASE = os.path.join(HERE, '..')
SKIP_LIST_PATH = os.path.join(BASE, '길이초과_건너뜀_목록.txt')
TEMPLATES_DIR = os.path.join(BASE, 'translation_templates')

ESM_NAMES = {f'SMAP0{n}.ESM': os.path.join(TEMPLATES_DIR, 'SLG_ESM', f'SMAP0{n}.txt') for n in range(1, 6)}
LIP_NAMES = {f'LIPSYNC{n}.LIP': os.path.join(TEMPLATES_DIR, 'LIPSYNC', f'LIPSYNC{n}.txt') for n in range(1, 5)}

def template_path_for(category, filename):
    if category == 'SRPG 전투대사(ESM)':
        return ESM_NAMES.get(filename)
    if category == '립싱크 음성대사(LIPSYNC)':
        return LIP_NAMES.get(filename)
    if category == '기타 오버레이':
        name = filename.split(' (')[0]
        return os.path.join(TEMPLATES_DIR, 'OVLM', name + '.txt')
    if category == '시스템 메시지(1ST_READ.BIN)':
        return os.path.join(TEMPLATES_DIR, '1ST_READ', 'all_1st_read_strings.txt')
    return None

ENTRY_HEADER = re.compile(r'^\[(.+?)\] \[(\d+)\] 원문 (\d+)바이트$')
LINE_IDX = re.compile(r'^\[(\d+)\]\s?(.*)$')
HANJA_PAREN = re.compile(r'[ 　]*\(([一-鿿々〻]+)\)')

def parse_skip_list(path):
    entries = []
    category = None
    with open(path, encoding='utf-8') as f:
        lines = f.readlines()
    i = 0
    while i < len(lines):
        line = lines[i].rstrip('\n')
        if line.startswith('--- ') and line.endswith(' ---'):
            category = line[4:-4]
            i += 1
            continue
        m = ENTRY_HEADER.match(line)
        if m and category:
            filename, idx, orig_len = m.group(1), int(m.group(2)), int(m.group(3))
            orig_line = lines[i+1].rstrip('\n')
            trans_line = lines[i+2].rstrip('\n')
            orig = orig_line[len('  원문: '):] if orig_line.startswith('  원문: ') else ''
            trans = trans_line[len('  지금 번역(너무 김): '):] if trans_line.startswith('  지금 번역(너무 김): ') else ''
            entries.append({'category': category, 'filename': filename, 'idx': idx,
                             'orig_len': orig_len, 'orig': orig, 'trans': trans})
            i += 4
            continue
        i += 1
    return entries

def shorten(orig, text, orig_len, hangul_map):
    def blen(s):
        return len(encode_mixed(s, hangul_map))

    was_already_fitting = blen(text) <= orig_len

    # 1~3단계는 "어차피 불필요한 내용"이라 길이 확인 없이 순서대로 전부
    # 적용한다(목록에 있던 항목이면 지금 당장 딱 맞더라도 정리). 4단계
    # (말줄임표 제거)만 그래도 넘칠 때의 최후 수단이라 조건부로 적용한다.
    applied = []

    if orig.startswith('る。//'):
        p = text.find('//')
        if p != -1:
            candidate = text[p+2:]
            if candidate != text:
                text = candidate
                applied.append('rule1_ru_slash')

    candidate = text.replace(' ', '')
    if candidate != text:
        text = candidate
        applied.append('rule2_space')

    candidate = HANJA_PAREN.sub('', text)
    if candidate != text:
        text = candidate
        applied.append('rule3_hanja')

    if blen(text) > orig_len:
        candidate = text.replace('…', '')
        if candidate != text:
            text = candidate
            applied.append('rule4_ellipsis')

    if applied:
        step = '+'.join(applied)
    else:
        step = 'already_fits_no_change' if was_already_fitting else 'no_rule_matched_still_long'
    return text, step

def load_template_lines(path):
    with open(path, encoding='utf-8') as f:
        return f.readlines()

def write_template_lines(path, lines):
    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(lines)

def main():
    apply_changes = '--apply' in sys.argv
    hangul_map = load_map()
    entries = parse_skip_list(SKIP_LIST_PATH)
    print(f"건너뜀 목록 {len(entries)}개 항목 로드")

    by_path = collections.defaultdict(list)
    skipped_no_template = []
    for e in entries:
        path = template_path_for(e['category'], e['filename'])
        if not path or not os.path.exists(path):
            skipped_no_template.append(e)
            continue
        by_path[path].append(e)

    stats = collections.Counter()
    still_too_long = []
    fixed_report_lines = []

    for path, es in by_path.items():
        lines = load_template_lines(path)
        idx_to_lineno = {}
        for lineno, line in enumerate(lines):
            m = LINE_IDX.match(line.rstrip('\n'))
            if m:
                idx_to_lineno[int(m.group(1))] = lineno

        changed = 0
        for e in es:
            idx = e['idx']
            lineno = idx_to_lineno.get(idx)
            if lineno is None:
                stats['idx_not_found_in_template'] += 1
                continue
            cur_line = lines[lineno].rstrip('\n')
            m = LINE_IDX.match(cur_line)
            prefix_end = m.start(2)
            current_text = m.group(2)

            new_text, step = shorten(e['orig'], current_text, e['orig_len'], hangul_map)
            stats[step] += 1
            new_blen = len(encode_mixed(new_text, hangul_map))
            if new_blen > e['orig_len']:
                still_too_long.append((path, idx, e['orig_len'], new_blen, e['orig'], new_text))

            if new_text != current_text:
                lines[lineno] = cur_line[:prefix_end] + new_text + '\n'
                changed += 1

        if changed and apply_changes:
            write_template_lines(path, lines)
        fixed_report_lines.append(f"{path}: {changed}/{len(es)}줄 수정")

    print("\n=== 파일별 수정 현황 ===")
    for l in fixed_report_lines:
        print(" ", l)

    print("\n=== 규칙별 적용 횟수 ===")
    for k, v in stats.most_common():
        print(f"  {k}: {v}")

    print(f"\n템플릿 파일을 못 찾은 항목: {len(skipped_no_template)}개")
    print(f"규칙을 다 적용해도 여전히 긴 항목: {len(still_too_long)}개")

    if not apply_changes:
        print("\n(--apply 없이 실행: 미리보기만, 파일은 변경하지 않았습니다)")
    else:
        print("\n템플릿 파일에 반영 완료")

    report_path = os.path.join(HERE, 'shorten_report.txt')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"수정 대상 {len(entries)}개, 여전히 김 {len(still_too_long)}개\n\n")
        for path, idx, orig_len, new_blen, orig, new_text in still_too_long:
            f.write(f"[{os.path.basename(path)}] [{idx:04d}] 원문 {orig_len}바이트 -> 지금 {new_blen}바이트\n")
            f.write(f"  원문: {orig}\n  줄인 번역: {new_text}\n\n")
    print(f"상세 리포트: {report_path}")

if __name__ == '__main__':
    main()
