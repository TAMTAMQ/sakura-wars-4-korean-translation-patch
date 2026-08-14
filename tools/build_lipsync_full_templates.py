"""LIPSYNC*.LIP 의 진짜 전체 원문(표의 pre 안에 있던 텍스트 + text)을
복원해서 translation_templates/LIPSYNC/*.txt 를 표 행 번호(row k) 기준으로
새로 만든다.

기존 템플릿(옛 휴리스틱 스캔 번호 기준, 문장이 pre/text로 쪼개져 있던
번역들)은 통째로 버리고 원문으로 되돌린다 - 번역은 이 새 템플릿에
처음부터 다시 채워야 한다.

사용법: python build_lipsync_full_templates.py [--apply]
  --apply 없이 실행하면 통계만 보여주고 파일은 만들지 않는다.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lipsync_format as lf

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(HERE, '..')
ORIG_DIR = os.path.join(BASE, 'original_files', 'ADVDATA')
TPL_DIR = os.path.join(BASE, 'translation_templates', 'LIPSYNC')

def build_one(n, apply_changes):
    name = f'LIPSYNC{n}'
    lip_path = os.path.join(ORIG_DIR, name + '.LIP')
    tpl_path = os.path.join(TPL_DIR, name + '.txt')

    data = open(lip_path, 'rb').read()
    parsed = lf.parse(data)
    count = parsed['count']

    lines = []
    with_pre_text = 0
    for k in range(count):
        pre, text, post = parsed['entries'][k]
        full = lf.full_original_text(pre, text)
        if lf.split_pre(pre)[1]:
            with_pre_text += 1
        lines.append(f"[{k:04d}] {full}")

    print(f"{name}: {count}줄 (pre 안에 텍스트 있던 항목 {with_pre_text}개)")

    if apply_changes:
        os.makedirs(TPL_DIR, exist_ok=True)
        with open(tpl_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines) + '\n')
        old_manifest = os.path.join(TPL_DIR, name + '.manifest.json')
        if os.path.exists(old_manifest):
            os.remove(old_manifest)  # 더 이상 필요 없음(원본에서 직접 파싱)
        print(f"  -> {tpl_path} 새로 생성")

if __name__ == '__main__':
    apply_changes = '--apply' in sys.argv
    if not apply_changes:
        print("(--apply 없이 실행: 통계만 표시, 파일 변경 없음)\n")
    for n in [1, 2, 3, 4]:
        build_one(n, apply_changes)
