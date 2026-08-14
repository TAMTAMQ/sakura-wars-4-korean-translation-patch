"""번역 템플릿(.txt) 파일을 읽는 공통 모듈.
모든 patch_*.py / rebuild_sbx.py 가 이 함수를 같이 쓴다.

정리 기능:
- [번호] 형식이 아닌 줄(빈 줄 등)은 자동으로 무시됨
- 번역문 안의 "//" 앞뒤에 붙은 반각(일반) 공백만 자동으로 제거됨
  (예: "가나다 // 라마바" -> "가나다//라마바")
  주의: 전각 공백(　, U+3000)은 지우지 않음 — 원문에서 독백체 대사 등의
  들여쓰기로 의도적으로 쓰인 서식이라, 이걸 지우면 원문 자체가
  훼손된다.
- 연속된 말줄임표(…)는 1개로 줄임 (예: "……" -> "…", "………" -> "…")
  단, 한글이 포함된 줄에서만 적용됨. 일본어는 "……"(말줄임표 2개)를
  표준적인 문장부호 관습으로 쓰기 때문에, 번역 안 하고 원문 그대로
  남아있는 일본어 줄까지 건드리면 원문이 훼손된다.
"""
import re

LINE_PATTERN = re.compile(r'^\[(\d+)\]\s?(.*)$')
SLASH_SPACE_PATTERN = re.compile(r'[ \t]*//[ \t]*')
ELLIPSIS_PATTERN = re.compile(r'…{2,}')
HANGUL_PATTERN = re.compile(r'[\uAC00-\uD7A3]')

def clean_text(text):
    """// 앞뒤 공백 제거 + (한글 포함 줄에 한해) 연속 말줄임표(…) 1개로 축약"""
    text = SLASH_SPACE_PATTERN.sub('//', text)
    if HANGUL_PATTERN.search(text):
        text = ELLIPSIS_PATTERN.sub('…', text)
    return text

def parse_translation_file(path):
    result = {}
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')
            if not line.strip():
                continue  # 빈 줄은 무시
            m = LINE_PATTERN.match(line)
            if m:
                idx = int(m.group(1))
                text = clean_text(m.group(2))
                result[idx] = text
    return result
