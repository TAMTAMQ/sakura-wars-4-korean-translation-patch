"""LIPSYNC*.LIP (ALPD) 포맷 파서/재조립기.

구조: [헤더 12B: sig'ALPD'+field0+count]
      [표 count×12B: id, off_a, off_b (전부 실제offset+1로 인코딩)]
      [항목들이 표 바로 뒤부터 순서대로: pre(가변) + text + NUL + post(가변)]
      [나머지(꼬리): 원인 불명의 잔여 엔트리 + POF0(빈 재배치 테이블로 보임) + EOFC]

리버스엔지니어링 근거 (원본 파일 4개 전부 바이트 단위로 왕복 검증됨, lip_probe.py 참고):
  - off_b[k]-1 이 항목 k의 텍스트 시작 위치. NUL로 끝난다. (4개 파일 60개+ 샘플 확인)
  - off_a[k]-1 이 항목 k의 시작(pre 구간 시작) 위치. 단, **0번 항목의 off_a는
    표의 마지막 행 off_a 필드 주소를 가리키는 미사용/쓰레기 값**이라 무시하고
    표가 끝나는 자리(table_end)를 0번 항목의 시작으로 쓴다 (4개 파일 전부 동일 패턴).
  - 항목 k의 실제 구간은 [시작(k), 시작(k+1)) 전체이며, 그 안에서 텍스트 앞
    (pre, 의미 불명 - 헤더/포인터류로 추정) 과 텍스트 뒤(post, 캐릭터별 립싱크
    타이밍 데이터로 추정 - 음성 클립 길이에 종속되므로 번역과 무관하게 그대로
    보존해야 함) 를 텍스트 위치로 갈라 각각 통째로 보존한다.
  - 마지막 항목 뒤부터 파일 끝까지(꼬리)는 무엇인지 정확히 알 수 없으나
    (미등록 문자열 1개 + POF0 재배치 테이블처럼 보이는 빈 블록 + EOFC 마커)
    번역과 무관한 내용이라 통째로 그대로 옮기고, field0 값은 이 꼬리 시작
    지점과의 상대 위치를 원본과 동일하게 유지하도록 재계산한다.

이 모델로 원본 4개 파일을 번역 없이 재조립하면 원본과 100% 바이트 일치함이
확인되었다 (round-trip self test). 그래서 텍스트 길이가 원문보다 길어도
건너뛰지 않고 파일 전체를 새로 조립해서 반영할 수 있다.
"""
import struct
from extract_lipsync_text import scan_real_text

def split_pre(pre):
    """pre 안에서 '진짜 텍스트' 부분과 그 앞의 이진 데이터(추정: 립싱크
    프레임/타이밍)를 갈라낸다. 텍스트 런이 pre 끝까지 정확히 이어질 때만
    신뢰한다 (전체 4개 파일 7,943개 표본에서 이어지지 않는 애매한 경우는
    0건이었음 - 정확히 이어지거나 아예 텍스트가 없거나 둘 중 하나).

    반환: (binary_prefix, pre_text). 텍스트가 없으면 (pre, '')."""
    if not pre:
        return pre, ''
    results = scan_real_text(pre)
    if not results:
        return pre, ''
    start, blen, text = results[-1]
    if start + blen != len(pre):
        return pre, ''  # 끝까지 안 이어지면 신뢰하지 않고 전부 보존
    return pre[:start], text

def full_original_text(pre, text):
    """항목의 진짜 전체 원문(일본어)을 복원한다: pre 안의 텍스트 + text."""
    _, pre_text = split_pre(pre)
    return pre_text + text.decode('shift_jis', errors='replace')

def parse(data):
    sig = data[:4]
    if sig != b'ALPD':
        raise ValueError(f"ALPD 헤더가 아닙니다: {sig}")
    field0, count = struct.unpack_from('<2I', data, 4)
    table_start = 12
    table_end = table_start + count*12

    ids, off_a, off_b = [], [], []
    for k in range(count):
        i, a, b = struct.unpack_from('<3I', data, table_start + k*12)
        ids.append(i); off_a.append(a); off_b.append(b)

    starts = [table_end if k == 0 else off_a[k] - 1 for k in range(count)]

    entries = []
    for k in range(count):
        span_start = starts[k]
        span_end = starts[k+1] if k+1 < count else None
        tstart = off_b[k] - 1
        tend = data.find(b'\x00', tstart)
        pre = data[span_start:tstart]
        text = data[tstart:tend]
        post = data[tend+1:span_end] if span_end is not None else b''
        entries.append([pre, text, post])

    last_tend = data.find(b'\x00', off_b[-1]-1)
    leftover_start = last_tend + 1

    return {
        'sig': sig, 'field0': field0, 'count': count,
        'ids': ids, 'entries': entries,
        'off_a': off_a, 'off_b': off_b,
        'table_start': table_start,
        'header_bytes': bytes(data[:table_end]),
        'leftover': data[leftover_start:],
        'leftover_start': leftover_start,
    }

def rebuild(parsed, new_texts=None, new_pre=None):
    """new_texts: {idx: 인코딩된 bytes} - text(off_b) 자리에 넣을 내용.
    new_pre: {idx: 대체할 pre bytes} - pre 안에 진짜 텍스트가 있던 항목은
    번역할 때 그 부분을 지우고 이진 데이터만 남긴 값을 넘겨야 한다
    (split_pre 참고). 둘 다 없는 idx는 원문 그대로 유지."""
    count = parsed['count']
    table_start = parsed['table_start']
    header = bytearray(parsed['header_bytes'])
    data_start = len(header)

    blob = bytearray()
    for k in range(count):
        orig_pre, orig_text, post = parsed['entries'][k]
        text = new_texts.get(k) if new_texts else None
        if text is None:
            text = orig_text
        pre = new_pre.get(k) if new_pre else None
        if pre is None:
            pre = orig_pre
        a = data_start + len(blob)
        blob += pre
        b = data_start + len(blob)
        blob += text
        blob.append(0)
        blob += post
        if k != 0:  # 0번 행의 off_a 필드는 미사용 값이라 원본 그대로 둔다
            struct.pack_into('<I', header, table_start + k*12 + 4, a + 1)
        struct.pack_into('<I', header, table_start + k*12 + 8, b + 1)

    leftover_start_new = data_start + len(blob)
    delta_within_leftover = parsed['field0'] - parsed['leftover_start']
    struct.pack_into('<I', header, 4, leftover_start_new + delta_within_leftover)

    return bytes(header) + bytes(blob) + parsed['leftover']

def rebuild_repoint(data, parsed, translations, hangul_map):
    """레이아웃을 절대 안 건드리는 버전. 표(off_a/off_b)는 절대 값을
    바꾸지 않는다.

    **왜 표 값을 절대 안 바꾸는가 (2026-08-14 실기 테스트로 확인)**:
    처음에는 원문보다 길어지면 파일 끝(꼬리 앞)에 새로 추가하고 표의
    off_b 값만 그쪽을 가리키게 바꾸는 "repoint" 방식을 썼다(ESM에서
    쓴 것과 같은 원리). 그런데 LIPSYNC는 자막이 음성에 맞춰 타이핑
    효과로 나오는데, off_b 값을 원래 자리에서 멀리 떨어진 곳(파일
    끝 쪽)으로 바꾸면 자막이 앞부분 몇 글자만 나오고 멈춰버리는
    현상이 실제 게임에서 확인됐다 - 게임이 off_b를 단순 "텍스트
    시작 포인터"가 아니라 타이핑 효과의 길이/속도 계산 등 다른
    용도로도 같이 쓰는 것으로 보인다. 반면 표 값은 그대로 두고
    pre_text+text를 합친 자리 안에서만 내용을 바꾸면(아래 방식)
    문장 전체가 정상적으로 나오는 게 확인됐다.

    **실제 적용 방식**:
      - 항목 k는 원래 [pre_text(있으면) 그대로 이어서][text(off_b)]가
        메모리상 한 덩어리로 붙어 있다. 이 둘을 합친 공간
        (pre_text 길이 + text 길이)에 번역문 전체를 밀어넣는다 -
        표는 1바이트도 안 건드린다.
      - 합친 공간에 다 안 들어가면(번역문이 너무 길면) - repoint는
        안전하지 않다고 확인됐으므로 원문을 그대로 유지한다(건너뜀).
      - pre 안의 바이너리 프리픽스(추정: 립싱크 ID 등)와 post(립싱크
        타이밍 데이터로 추정)는 절대 건드리지 않는다.

    translations: {row_k: 번역문 전체 문자열}."""
    from hangul_font_map import encode_mixed, encode_mixed_fit

    out = bytearray(data)
    table_start = parsed['table_start']
    off_a, off_b = parsed['off_a'], parsed['off_b']
    count = parsed['count']
    applied = 0
    too_long = []
    encode_failed = []

    table_end = table_start + count * 12
    starts = [table_end if k == 0 else off_a[k] - 1 for k in range(count)]

    for k in range(count):
        text = translations.get(k)
        if not text:
            continue
        pre, orig_text_bytes, post = parsed['entries'][k]
        orig_full = full_original_text(pre, orig_text_bytes)
        if text == orig_full:
            continue
        text_start = off_b[k] - 1
        blen = len(orig_text_bytes)

        binary_prefix, pre_text = split_pre(pre)
        pre_text_start = (starts[k] + len(binary_prefix)) if pre_text else text_start
        combined_space = (text_start - pre_text_start) + blen

        try:
            encoded = encode_mixed_fit(text, hangul_map, combined_space)
        except UnicodeEncodeError:
            encode_failed.append((k, orig_full, text))
            continue

        if len(encoded) > combined_space:
            too_long.append((k, orig_full, text, len(encoded), combined_space))
            continue

        end = pre_text_start + combined_space
        out[pre_text_start:pre_text_start+len(encoded)] = encoded
        out[pre_text_start+len(encoded):end] = b'\x00' * (combined_space - len(encoded))
        applied += 1

    return bytes(out), applied, too_long, encode_failed
