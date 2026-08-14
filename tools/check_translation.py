#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
번역 검증 툴 (확장판)
1) 원본/번역본 텍스트를 정리 (빈 줄(엔터)만 제거, 줄 안의 공백은 그대로 보존)
2) 라인 번호([0001] 형식) 비교 -> 누락/순서 어긋난 곳 검출
3) 번역본에 일본어(히라가나/가타카나/한자)가 남아있는지 검출
4) 특수문자(∈, 〓) 누락/추가 검출 + 자동 복구
5) 이모지/이모티콘 임의 추가 검출 + 자동 제거
6) 원문이 라벨(_sub_, _MV_, _SET_, _BGA_ 등, 일본어 없는 줄)인데
   번역본에서 내용이 바뀐 경우 검출 (LLM이 라벨을 엉뚱하게 "번역"한 사고 방지)
7) "//" 조각 경계에서 원문에 있던 공백(반각 스페이스 또는 전각 스페이스 　)이
   번역본에서 사라진 경우 검출 + 자동 복구 (원문의 의도적인 공백/뜸 연출 보존)

*** 4), 5), 7)의 자동 복구는 기본으로 항상 실행되며, 번역본 파일을 직접
    덮어씁니다 (별도의 _fixed.txt 파일을 만들지 않습니다) ***

사용법:
    python3 check_translation.py 원본.txt 번역본.txt
    python3 check_translation.py --dir 원본폴더 번역본폴더
        (폴더 단위 일괄 검사, 파일명이 같은 것끼리 매칭. 이 명령 하나로
         검사 + 특수문자 복구 + 이모지 제거까지 폴더 안의 모든 파일에
         한 번에 적용됩니다.)

출력: 문제 있는 파일명 + 라인 번호 목록만 간단히 출력 (토큰/시간 절약용)
자동 복구가 하나라도 반영되면 번역본 파일 자체가 바로 수정됩니다
(별도의 _fixed.txt 파일을 만들지 않습니다. 필요하면 실행 전에 미리
백업해두세요).
--no-fix 옵션을 주면 자동 복구 없이 검사만 하고 끝냅니다.
"""

import re
import sys
import os
import argparse

LINE_TAG_RE = re.compile(r'^\[(\d+)\](.*)$')

# 화면 출력과 동시에 파일로도 저장하기 위한 로그 버퍼
_LOG_BUFFER = []

def log(msg=""):
    print(msg)
    _LOG_BUFFER.append(str(msg))

# 일본어 판정용 유니코드 범위: 히라가나, 가타카나, CJK 통합 한자(한중일 공용 한자 포함)
JAPANESE_RE = re.compile(
    r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF\u31F0-\u31FF\uFF66-\uFF9F]'
)

# 이 게임 전용 특수문자. 번역 중 임의로 사라지거나(가장 흔함) 다른 기호로
# 바뀌면 안 되는 문자들이라 개수/위치를 원문과 정확히 비교한다.
SPECIAL_CHARS = ['∈', '〓']

# 특수문자를 복구할 때, 번역문에 이미 붙어있으면 지워야 할 "중복 문장부호".
# ∈는 실제로 느낌표(!)라고 검증됐지만, 〓는 아직 정체가 확정되지 않았다.
# (물음표는 표준 바이트 그대로도 잘 동작하는 게 이미 확인됐어서, 〓가
# 단순히 물음표와 같다고 단정할 근거는 약하다. 다만 혹시 번역가가 물음표를
# 대신 넣었을 경우를 대비해 안전하게 같은 방식으로 처리해둔다.)
REDUNDANT_PUNCT = {
    '∈': ['!', '！'],
    '〓': ['?', '？'],
}

# 원문이 이 접두어로 시작하면(그리고 일본어가 없으면) 대사가 아니라 내부
# 라벨이므로 번역본에서도 100% 동일해야 정상이다.
LABEL_PREFIXES = ('_sub_', '_SUB_', '_MV_', '_SET_', '_BGA_')

# 이모지/이모티콘 판정용 유니코드 범위. 이 게임(2002년 드림캐스트, Shift-JIS)
# 원문에는 절대 나올 수 없는 문자대이므로, 번역본에서 발견되면 100% LLM이
# 임의로 추가한 것 -> 무조건 제거 대상으로 판단해도 안전하다.
EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"  # 각종 기호/그림문자, 이모티콘, 보충 기호 등
    "\U00002600-\U000027BF"  # 기타 기호 및 딩뱃
    "\U0001F1E6-\U0001F1FF"  # 국기(지역 표시 문자)
    "\U00002190-\U000021FF"  # 화살표(★같은 별도 강조 화살표 오남용 방지)
    "\U00002B00-\U00002BFF"  # 기타 화살표/기호
    "\U0000FE0F"             # variation selector(이모지 표시 강제 기호)
    "\U0000200D"             # zero-width joiner(합성 이모지 연결자)
    "]"
)


def clean_lines(raw_text):
    """
    1차 정리:
    - 완전히 빈 줄(엔터로만 이루어진 줄)만 제거
    - 줄 안의 공백(스페이스)은 그대로 보존
    반환: [(line_no:int, text:str, original_line_index:int), ...]
    번호 태그가 없는 줄은 line_no=None 으로 표시하고 별도 이슈로 취급
    """
    result = []
    for idx, line in enumerate(raw_text.splitlines(), start=1):
        if line == '' or line.strip('\r') == '':
            continue  # 빈 줄(엔터)만 제거, 내용 있는 줄의 공백은 건드리지 않음
        m = LINE_TAG_RE.match(line)
        if m:
            line_no = int(m.group(1))
            text = m.group(2)  # 공백 보존
            result.append((line_no, text, idx))
        else:
            # [0001] 형식이 아닌 줄 -> 번호 없음으로 기록
            result.append((None, line, idx))
    return result


def check_line_numbers(entries, label):
    """
    라인 번호 검증:
    - 번호가 없는 줄
    - 번호가 1씩 증가하지 않고 건너뛴 곳(누락)
    - 번호가 중복되거나 역순인 곳
    """
    issues = []
    prev_no = None
    seen = set()

    for line_no, text, orig_idx in entries:
        if line_no is None:
            issues.append(f"  [번호 없음] 원본 파일 {orig_idx}번째 줄: \"{text[:30]}\"")
            continue

        if line_no in seen:
            issues.append(f"  [중복] [{line_no:04d}] (원본 파일 {orig_idx}번째 줄)")
        seen.add(line_no)

        if prev_no is not None:
            if line_no < prev_no:
                issues.append(f"  [역순] [{prev_no:04d}] 다음에 [{line_no:04d}] 등장 (원본 파일 {orig_idx}번째 줄)")
            elif line_no > prev_no + 1:
                missing = list(range(prev_no + 1, line_no))
                missing_str = ', '.join(f"[{n:04d}]" for n in missing)
                issues.append(f"  [누락] {missing_str} (앞뒤: [{prev_no:04d}] -> [{line_no:04d}])")

        prev_no = line_no

    return issues


def check_japanese_remaining(entries):
    """번역본에 일본어가 남아있는 줄 검출"""
    issues = []
    for line_no, text, orig_idx in entries:
        if JAPANESE_RE.search(text):
            tag = f"[{line_no:04d}]" if line_no is not None else f"(번호없음, 원본 {orig_idx}번째 줄)"
            issues.append(f"  {tag} \"{text[:40]}\"")
    return issues


def check_emoji(tgt_map):
    """
    번역본에 이모지/이모티콘이 있는지 검출.
    원문(2002년 Shift-JIS 게임 텍스트)에는 절대 나올 수 없는 문자대이므로,
    발견되면 전부 LLM이 임의로 추가한 것으로 간주하고 무조건 제거 대상.

    반환: issues(문자열 리스트), fixes({line_no: 이모지 제거된 텍스트})
    """
    issues = []
    fixes = {}

    for line_no, tgt_text in tgt_map.items():
        found = EMOJI_RE.findall(tgt_text)
        if not found:
            continue
        cleaned = EMOJI_RE.sub('', tgt_text)
        issues.append(f"  [{line_no:04d}] 이모지/이모티콘 {len(found)}개 발견: {' '.join(found)}")
        issues.append(f"       번역: \"{tgt_text[:50]}\"")
        issues.append(f"       -> 자동복구(제거): \"{cleaned[:50]}\"")
        fixes[line_no] = cleaned

    return issues, fixes


def check_special_chars(src_map, tgt_map):
    """
    특수문자(∈, 〓) 개수 불일치 검출.
    "//"로 문장을 조각내서 조각 단위로 비교한다 -> 한 문장 안에 ∈가
    여러 번 나와도 어느 조각에서 사라졌는지까지 짚어낼 수 있다.

    반환: issues(문자열 리스트), fixes({line_no: 복구된 텍스트})
    복구 규칙: 원문 조각이 특수문자로 "끝나는데" 번역 조각이 그 문자로
    끝나지 않으면, 번역 조각 끝에 그 문자를 그대로 붙여서 복구한다.
    (문장 끝에 오는 경우가 대부분이라 이 방식으로 대부분 해결되지만,
    문장 중간에 있는 경우는 자동복구가 안 될 수 있어 issue로만 표시된다.)
    """
    issues = []
    fixes = {}

    for line_no, src_text in src_map.items():
        if line_no not in tgt_map:
            continue
        tgt_text = tgt_map[line_no]

        src_total = {c: src_text.count(c) for c in SPECIAL_CHARS}
        tgt_total = {c: tgt_text.count(c) for c in SPECIAL_CHARS}
        if src_total == tgt_total:
            continue  # 개수 다 일치하면 문제 없음

        src_segs = src_text.split('//')
        tgt_segs = tgt_text.split('//')

        mismatch_detail = []
        fixed_segs = list(tgt_segs) if len(tgt_segs) == len(src_segs) else None

        for c in SPECIAL_CHARS:
            if src_total[c] == tgt_total[c]:
                continue
            mismatch_detail.append(f"'{c}' 원문 {src_total[c]}개 vs 번역 {tgt_total[c]}개")

            # "//" 조각 개수가 같을 때만 조각 단위 자동복구 시도
            if fixed_segs is not None:
                for i, (ss, ts) in enumerate(zip(src_segs, fixed_segs)):
                    if ss.endswith(c) and not ts.endswith(c):
                        # 이미 번역문에 (중복되는) 문장부호가 붙어있으면
                        # 지우고 그 자리(공백은 유지)에 특수문자를 붙인다.
                        # 예: "군! " -> "군 " + '∈' = "군 ∈"
                        redundant = REDUNDANT_PUNCT.get(c, [])
                        if redundant:
                            pattern = '[' + re.escape(''.join(redundant)) + r']+(\s*)$'
                            ts = re.sub(pattern, r'\1', ts)
                        fixed_segs[i] = ts + c

        tag = f"[{line_no:04d}]"
        issues.append(f"  {tag} 특수문자 개수 불일치: {', '.join(mismatch_detail)}")
        issues.append(f"       원문: \"{src_text[:50]}\"")
        issues.append(f"       번역: \"{tgt_text[:50]}\"")

        if fixed_segs is not None:
            fixed_text = '//'.join(fixed_segs)
            fixed_total = {c: fixed_text.count(c) for c in SPECIAL_CHARS}
            if fixed_total == src_total:
                fixes[line_no] = fixed_text
                issues.append(f"       -> 자동복구: \"{fixed_text[:50]}\" (문장 끝 기준)")
            else:
                issues.append(f"       -> 자동복구 실패 (문장 중간에 있는 것으로 보임, 수동 확인 필요)")
        else:
            issues.append(f"       -> 자동복구 불가 (\"//\" 조각 개수가 원문과 달라서 대응 위치를 알 수 없음)")

    return issues, fixes


# 원문에서 의도적인 공백으로 취급하는 문자: 반각 스페이스, 전각 스페이스(　).
# 원문은 대사 중간의 "뜸"이나 대사 잇기를 이 공백들로 표현하는 경우가 많아서,
# 번역 과정에서 아예 사라지면 원래의 호흡/리듬이 사라진다.
SPACE_CHARS = (' ', '　')


def check_spacing(src_map, tgt_map):
    """
    "//"로 나눈 조각 단위로, 원문 조각이 공백으로 시작/끝나는데 번역 조각은
    그렇지 않은 경우(공백이 사라진 경우)를 검출한다.
    "//" 조각 개수가 원문과 다르면(이미 특수문자 체크에서도 쓰는 기준과 동일)
    조각별 대응 위치를 알 수 없으므로 자동복구 없이 이슈로만 남긴다.

    복구 규칙: 사라진 자리에 반각 스페이스 1개를 채워 넣는다(전각/반각 구분 없이
    "공백이 있었다"는 사실만 복원 - 이미 번역본 전반에서 전각 공백은 반각
    공백으로 정규화해서 쓰는 관례를 따름).
    """
    issues = []
    fixes = {}

    for line_no, src_text in src_map.items():
        if line_no not in tgt_map:
            continue
        tgt_text = tgt_map[line_no]
        if src_text == tgt_text:
            continue

        src_segs = src_text.split('//')
        tgt_segs = tgt_text.split('//')

        if len(src_segs) != len(tgt_segs):
            # 조각 개수가 다르면 대응 위치를 알 수 없음 -> 특수문자 체크와
            # 동일한 사유로 자동복구 대상에서 제외 (다른 체크 항목에서 이미
            # "// 조각 개수 불일치"로 잡히므로 여기서 중복 보고하지 않는다)
            continue

        fixed_segs = list(tgt_segs)
        seg_issues = []

        for i, (ss, ts) in enumerate(zip(src_segs, fixed_segs)):
            if not ss:
                continue
            if ss[:1] in SPACE_CHARS and ts[:1] not in SPACE_CHARS:
                seg_issues.append(f"조각[{i}] 앞쪽 공백 소실")
                fixed_segs[i] = ' ' + ts
                ts = fixed_segs[i]
            if ss[-1:] in SPACE_CHARS and ts[-1:] not in SPACE_CHARS:
                seg_issues.append(f"조각[{i}] 뒤쪽 공백 소실")
                fixed_segs[i] = ts + ' '

        if not seg_issues:
            continue

        tag = f"[{line_no:04d}]"
        issues.append(f"  {tag} 공백 소실: {', '.join(seg_issues)}")
        issues.append(f"       원문: \"{src_text[:50]}\"")
        issues.append(f"       번역: \"{tgt_text[:50]}\"")

        fixed_text = '//'.join(fixed_segs)
        fixes[line_no] = fixed_text
        issues.append(f"       -> 자동복구: \"{fixed_text[:50]}\"")

    return issues, fixes


def check_label_lines(src_map, tgt_map):
    """
    원문이 라벨(_sub_ 등으로 시작 + 일본어 없음)인데 번역본에서 내용이
    달라진 줄 검출. LLM이 이런 줄을 엉뚱하게 "번역"해버리는 사고를 잡아낸다.
    """
    issues = []
    for line_no, src_text in src_map.items():
        if line_no not in tgt_map:
            continue
        is_label = src_text.startswith(LABEL_PREFIXES) and not JAPANESE_RE.search(src_text)
        if not is_label:
            continue
        tgt_text = tgt_map[line_no]
        if tgt_text != src_text:
            issues.append(f"  [{line_no:04d}] 라벨 줄인데 내용이 바뀜")
            issues.append(f"       원문: \"{src_text[:50]}\"")
            issues.append(f"       번역: \"{tgt_text[:50]}\"")
    return issues


def run_check(src_path, tgt_path, do_fix=False):
    with open(src_path, encoding='utf-8') as f:
        src_raw = f.read()
    with open(tgt_path, encoding='utf-8') as f:
        tgt_raw = f.read()

    src_entries = clean_lines(src_raw)
    tgt_entries = clean_lines(tgt_raw)

    # 이 파일에 실제 문제가 하나라도 있을 때만 헤더+내용을 최종 로그에
    # 남긴다 ("이상 없음"만 잔뜩 나열되는 걸 방지 - 검증결과.txt에는
    # 문제 있는 파일만 남는다).
    buf = [f"\n===== {os.path.basename(tgt_path)} ====="]
    has_issue = False

    # 1. 번역본 라인 번호 검증
    num_issues = check_line_numbers(tgt_entries, "번역본")
    if num_issues:
        has_issue = True
        buf.append(f"[라인 번호 문제] {len(num_issues)}건")
        buf.extend(num_issues)
    else:
        buf.append("[라인 번호] 이상 없음")

    # 2. 원본 대비 번역본 라인 개수/번호셋 비교
    src_nos = {e[0] for e in src_entries if e[0] is not None}
    tgt_nos = {e[0] for e in tgt_entries if e[0] is not None}
    missing_in_tgt = sorted(src_nos - tgt_nos)
    extra_in_tgt = sorted(tgt_nos - src_nos)
    if missing_in_tgt:
        has_issue = True
        buf.append(f"[원본에는 있는데 번역본에 없는 번호] {len(missing_in_tgt)}건")
        buf.append('  ' + ', '.join(f"[{n:04d}]" for n in missing_in_tgt))
    if extra_in_tgt:
        has_issue = True
        buf.append(f"[번역본에만 있는 번호] {len(extra_in_tgt)}건")
        buf.append('  ' + ', '.join(f"[{n:04d}]" for n in extra_in_tgt))
    if not missing_in_tgt and not extra_in_tgt:
        buf.append("[원본-번역본 번호 대조] 이상 없음")

    # 3. 일본어 잔존 검출
    jp_issues = check_japanese_remaining(tgt_entries)
    if jp_issues:
        has_issue = True
        buf.append(f"[일본어 잔존] {len(jp_issues)}건")
        buf.extend(jp_issues)
    else:
        buf.append("[일본어 잔존] 없음")

    # 번호 -> 텍스트 맵 (4~6번 검사용, 양쪽에 공통으로 존재하는 번호만 비교)
    src_map = {e[0]: e[1] for e in src_entries if e[0] is not None}
    tgt_map = {e[0]: e[1] for e in tgt_entries if e[0] is not None}

    # 4. 특수문자(∈, 〓) 누락/추가 검출 + 자동복구
    sp_issues, sp_fixes = check_special_chars(src_map, tgt_map)
    if sp_issues:
        has_issue = True
        buf.append(f"[특수문자(∈,〓) 불일치] {len([i for i in sp_issues if i.startswith('  [')])}건")
        buf.extend(sp_issues)
    else:
        buf.append("[특수문자(∈,〓) 불일치] 없음")

    # 4-2. 이모지/이모티콘 임의 추가 검출 + 자동복구(제거)
    # sp_fixes로 이미 고쳐진 텍스트가 있으면 그 위에 이모지 제거를 이어서 적용한다
    tgt_map_after_sp_fix = dict(tgt_map)
    tgt_map_after_sp_fix.update(sp_fixes)
    emoji_issues, emoji_fixes = check_emoji(tgt_map_after_sp_fix)
    if emoji_issues:
        has_issue = True
        buf.append(f"[이모지/이모티콘 임의 추가] {len([i for i in emoji_issues if i.startswith('  [')])}건")
        buf.extend(emoji_issues)
    else:
        buf.append("[이모지/이모티콘 임의 추가] 없음")

    # 두 자동복구 결과 병합 (같은 줄에 둘 다 해당하면 이모지 제거까지 반영된 버전이 최종본)
    fixes = dict(sp_fixes)
    fixes.update(emoji_fixes)

    # 4-3. "//" 조각 경계 공백 소실 검출 + 자동복구
    # 지금까지의 자동복구 결과(특수문자/이모지)가 반영된 상태를 기준으로 검사한다
    tgt_map_after_fixes = dict(tgt_map)
    tgt_map_after_fixes.update(fixes)
    space_issues, space_fixes = check_spacing(src_map, tgt_map_after_fixes)
    if space_issues:
        has_issue = True
        buf.append(f"[공백 소실] {len([i for i in space_issues if i.startswith('  [')])}건")
        buf.extend(space_issues)
    else:
        buf.append("[공백 소실] 없음")
    fixes.update(space_fixes)

    # 5. 라벨 줄이 엉뚱하게 바뀐 경우 검출
    label_issues = check_label_lines(src_map, tgt_map)
    if label_issues:
        has_issue = True
        buf.append(f"[라벨 줄 오염] {len([i for i in label_issues if i.startswith('  [')])}건")
        buf.extend(label_issues)
    else:
        buf.append("[라벨 줄 오염] 없음")

    # 자동복구: 번역본 파일을 직접 덮어써서 반영 (새 파일 안 만듦)
    # 자동복구는 has_issue와 무관하게 항상 실제로 적용하되(파일 내용
    # 반영은 놓치면 안 되므로), 로그에 남길지는 has_issue 여부를 따른다.
    if do_fix and fixes:
        with open(tgt_path, 'w', encoding='utf-8') as f:
            for line_no, text, _ in tgt_entries:
                if line_no is not None and line_no in fixes:
                    f.write(f"[{line_no:04d}]{fixes[line_no]}\n")
                else:
                    tag = f"[{line_no:04d}]" if line_no is not None else ""
                    f.write(f"{tag}{text}\n")
        buf.append(f"[자동복구] {len(fixes)}건 반영 -> {tgt_path} (원본 덮어씀)")

    if has_issue:
        for line in buf:
            log(line)


def main():
    parser = argparse.ArgumentParser(description="번역 검증 툴")
    parser.add_argument('src', help='원본 파일 또는 폴더 경로')
    parser.add_argument('tgt', help='번역본 파일 또는 폴더 경로')
    parser.add_argument('--dir', action='store_true', help='폴더 단위 일괄 검사 (파일명 매칭)')
    parser.add_argument('--no-fix', action='store_true',
                         help='자동 복구(특수문자 복구, 이모지 제거) 없이 검사만 실행')
    parser.add_argument('--report', default=None,
                         help='검사 결과를 저장할 텍스트 파일 경로 (생략하면 번역본 경로 기준으로 자동 지정)')
    args = parser.parse_args()
    do_fix = not args.no_fix

    if args.dir:
        def collect_txt_files(base_dir):
            """base_dir 이하 모든 하위 폴더까지 재귀적으로 .txt 파일을 찾아
            {상대경로: 전체경로} 형태로 반환"""
            result = {}
            for root, dirs, files in os.walk(base_dir):
                for fname in files:
                    if fname.endswith('.txt'):
                        full_path = os.path.join(root, fname)
                        rel_path = os.path.relpath(full_path, base_dir)
                        result[rel_path] = full_path
            return result

        src_files = collect_txt_files(args.src)
        tgt_files = collect_txt_files(args.tgt)
        common = sorted(set(src_files) & set(tgt_files))
        only_in_src = sorted(set(src_files) - set(tgt_files))
        only_in_tgt = sorted(set(tgt_files) - set(src_files))

        log(f"원본 폴더에서 .txt 파일 {len(src_files)}개, 번역본 폴더에서 {len(tgt_files)}개 발견"
              f" (하위 폴더 포함)")

        if only_in_src:
            log(f"[번역본 폴더에 없는 파일] {only_in_src}")
        if only_in_tgt:
            log(f"[원본 폴더에 없는 파일] {only_in_tgt}")

        flagged_count = 0
        for name in common:
            before = len(_LOG_BUFFER)
            run_check(src_files[name], tgt_files[name], do_fix=do_fix)
            if len(_LOG_BUFFER) > before:
                flagged_count += 1
        log(f"\n총 {len(common)}개 파일 중 문제 있는 파일 {flagged_count}개"
            f" (나머지 {len(common) - flagged_count}개는 이상 없어 검증결과.txt에서 생략됨)")

        report_path = args.report or os.path.join(args.tgt, "검증결과.txt")
    else:
        run_check(args.src, args.tgt, do_fix=do_fix)
        report_path = args.report or (os.path.splitext(args.tgt)[0] + '_검증결과.txt')

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(_LOG_BUFFER) + '\n')
    print(f"\n(검사 결과가 파일로도 저장되었습니다: {report_path})")


if __name__ == '__main__':
    main()
