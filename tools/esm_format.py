"""SMAPnn.ESM 안에 박혀있는 CTPA/ASCR 텍스트 청크 파서/재조립기.

SBX(rebuild_sbx.py)와 원리는 같지만(청크 자체가 오프셋 표 방식의
ASCR/CTPA 텍스트 블록), 청크가 훨씬 큰 ESM 파일(최대 2.5MB) 안에 여러
개(최대 220개) 촘촘히 이어붙어 있다는 점이 다르다. 청크 하나가 커지면
그 뒤의 모든 바이트(다른 청크 포함)가 밀린다.

이 파일 안에서 청크 위치를 가리키는 절대 포인터가 있는지 찾아봤지만
찾을 수 없었다(OVLM과 달리 신호가 전혀 없음, patch_ovlm_binary.py의
발견과 대조됨). 그래서 이 게임의 SRPG 전투 스크립트 엔진은 청크를
CTPA/ASCR 시그니처를 스캔해서 찾는 것으로 추정된다(우리 스캐너와 동일한
방식). 100% 확신할 수는 없지만, 청크 사이/앞뒤의 알 수 없는 바이트는
절대 해석하지 않고 그대로 보존만 하므로 이 가정이 틀렸더라도 최소한
파일이 깨지지는 않는다(원문 그대로 재조립하면 원본과 100% 동일한지
round-trip 검증됨).
"""
import struct

def rebuild_repoint(data, chunks, translations_by_chunk, hangul_map):
    """청크/파일 레이아웃을 절대 건드리지 않는 버전 (모든 청크가 원래
    파일 위치·크기 그대로 유지됨 - 어떤 바이트도 밀리지 않는다).

    rebuild()(청크 전체를 오프셋 표까지 다시 계산해서 통째로 재조립,
    청크가 커지면 뒤 데이터가 전부 밀리는 방식)를 실제 게임에 넣었더니
    첫 전투 진입과 동시에 멈추는 문제가 발생했다(2026-08-14). 파일 안에
    청크 위치를 가리키는 절대 포인터를 못 찾았으므로 정확한 원인은
    모르지만(밀리는 것 자체가 문제라는 뜻), ASCR/CTPA 포맷 자체가 이미
    "오프셋 표를 통한 간접 참조" 구조라는 점을 이용하면 아무것도 밀지
    않고도 번역문을 늘릴 수 있다:

      - 번역문이 원래 텍스트 자리([pos, pos+blen)) 안에 들어가면 그
        자리에 제자리로 덮어쓴다 (기존 patch_esm.py와 동일, 안전).
      - 안 들어가면 파일 맨 끝(모든 청크보다 뒤)에 새로 추가하고, 그
        항목의 오프셋 표 값 하나만 그쪽을 가리키도록 바꾼다. 표 자체가
        원래 이런 간접 참조를 위한 구조라서 이 값만 바꾸면 되고, 다른
        무엇도 옮길 필요가 없다. 1ST_READ.BIN 리포인팅과 같은 원리이되
        절대 포인터를 찾을 필요 없이 포맷 자체의 표를 그대로 쓴다."""
    from hangul_font_map import encode_mixed

    out = bytearray(data)
    appended = bytearray()
    applied_inplace = 0
    applied_repoint = 0
    encode_failed = []

    for c in chunks:
        table_off = c['table_off']
        num_lines = c['num_lines']
        trans = translations_by_chunk.get(c['offset'], {})
        for i in range(num_lines):
            text = trans.get(i)
            if not text:
                continue
            pos, blen = c['positions'][i]
            orig_text = bytes(data[pos:pos+blen]).decode('shift_jis', errors='replace')
            if text == orig_text:
                continue
            try:
                encoded = encode_mixed(text, hangul_map)
            except UnicodeEncodeError:
                encode_failed.append((c['offset'], i, orig_text, text))
                continue

            if len(encoded) <= blen:
                out[pos:pos+len(encoded)] = encoded
                out[pos+len(encoded):pos+blen] = b'\x00' * (blen - len(encoded))
                applied_inplace += 1
            else:
                new_pos = len(data) + len(appended)
                appended += encoded
                appended.append(0)
                new_offset_val = new_pos - table_off
                struct.pack_into('<I', out, table_off + i*4, new_offset_val)
                applied_repoint += 1

    out += appended
    return bytes(out), applied_inplace, applied_repoint, encode_failed

def try_parse_chunk(data, off, sig):
    if data[off:off+4] != sig:
        return None
    try:
        if sig == b'CTPA':
            size_after8, num_lines, table_ptr, unk1 = struct.unpack_from('<4I', data, off+4)
            if not (0 < num_lines <= 2000):
                return None
            if unk1 != num_lines:
                return None
            table_off = off + table_ptr + 8
        else:  # ASCR
            size_after8 = struct.unpack_from('<I', data, off+4)[0]
            sig2 = data[off+8:off+12]
            if sig2 != b'\xba\xaf\x55\xcc':
                return None
            table_ptr, num_lines = struct.unpack_from('<II', data, off+12)
            if not (0 < num_lines <= 2000):
                return None
            table_off = off + table_ptr + 8

        if table_off < 0 or table_off + num_lines*4 > len(data):
            return None
        entries = struct.unpack_from('<%dI' % num_lines, data, table_off)
        texts = []
        positions = []
        for e in entries:
            pos = e + table_off
            if pos < 0 or pos >= len(data):
                return None
            end = data.find(b'\x00', pos)
            if end == -1 or end - pos > 500:
                return None
            raw = data[pos:end]
            try:
                text = raw.decode('shift_jis')
            except Exception:
                return None
            texts.append(text)
            positions.append((pos, end - pos))
        has_real_text = any(any(ord(c) > 0x3000 for c in t) for t in texts if t)
        if not has_real_text and num_lines > 1:
            return None
        chunk_end = off + 8 + size_after8
        if chunk_end > len(data):
            return None
        return {'offset': off, 'sig': sig.decode(), 'num_lines': num_lines,
                'size_after8': size_after8, 'texts': texts, 'positions': positions,
                'table_off': table_off, 'chunk_end': chunk_end}
    except (struct.error, IndexError):
        return None

def scan_esm(data_or_path):
    if isinstance(data_or_path, (bytes, bytearray)):
        data = data_or_path
    else:
        with open(data_or_path, 'rb') as f:
            data = f.read()

    chunks = []
    for sig in (b'CTPA', b'ASCR'):
        idx = 0
        while True:
            idx = data.find(sig, idx)
            if idx == -1:
                break
            result = try_parse_chunk(data, idx, sig)
            if result:
                chunks.append(result)
            idx += 1
    chunks.sort(key=lambda c: c['offset'])
    return chunks

def _entry_pre_gaps(data, table_off, num_lines, positions):
    """각 항목 텍스트 '앞'에는 다음 항목까지 이어지는 몇십 바이트짜리
    미상의 데이터가 있다(LIPSYNC의 pre 구간과 같은 패턴 - 아이콘/좌표
    같은 표시용 메타데이터로 추정). 텍스트만 뽑아서 이어붙이면 이 구간이
    통째로 사라지므로, 파일 위치 순서로 정렬해서 '이전 항목 끝 ~ 이번
    항목 시작' 구간을 각 항목의 pre-gap으로 캡처해 보존한다.

    offset 값 0(=표 자기 자신을 가리킴, blen=0인 "빈 문자열" 슬롯)은
    실제 텍스트 영역 밖의 특수/센티널 값이라 위치 순서 계산에서 아예
    제외한다(포함시키면 표 영역을 텍스트 영역으로 착각해서 크기 계산이
    어긋난다) - 항상 offset 0 그대로 유지한다."""
    table_end = table_off + num_lines * 4
    real = [i for i in range(num_lines) if positions[i][0] >= table_end]
    sentinel = [i for i in range(num_lines) if positions[i][0] < table_end]
    order = sorted(real, key=lambda i: positions[i][0])
    pre_gap = [b''] * num_lines
    # 이 항목이 이미 처리한 다른 항목의 텍스트(+NUL) 구간 안에 완전히
    # 겹쳐 들어가 있으면(같은 문장의 뒷부분을 공유하는 경우 포함)
    # alias_of[i] = (그 항목 인덱스, 그 항목 시작 기준 상대 오프셋)
    alias_of = [None] * num_lines
    max_reach = table_end       # 지금까지 나온 항목들이 도달한 가장 먼 끝 지점
    reach_owner = None          # 그 max_reach 를 만든 항목 인덱스
    reach_owner_start = None
    for i in order:
        pos, blen = positions[i]
        end = pos + blen + 1  # 텍스트 + NUL
        if pos < max_reach and reach_owner is not None and end <= max_reach:
            alias_of[i] = (reach_owner, pos - reach_owner_start)
            continue
        pre_gap[i] = bytes(data[max(max_reach, 0):pos]) if pos >= max_reach else b''
        if end > max_reach:
            max_reach = end
            reach_owner = i
            reach_owner_start = pos
    return pre_gap, alias_of, sentinel, max_reach  # max_reach = 마지막 항목 텍스트 바로 뒤(=old_text_end)

def rebuild(data, chunks, translations_by_chunk, hangul_map):
    """translations_by_chunk: {chunk_offset: {line_idx: new_text}}.
    청크 하나하나를 [헤더 프리픽스(표 시작 전까지, size_after8 필드만
    나중에 패치)] + [새 오프셋 표] + [새 텍스트 블롭(각 항목 = pre-gap
    보존 + 텍스트)] + [트레일러(청크 선언 끝까지 남은 바이트, 원본 그대로
    보존해서 재배치)] 로 다시 조립한다. 청크 사이/앞뒤의 바이트는 전혀
    건드리지 않는다."""
    from hangul_font_map import encode_mixed

    out = bytearray()
    cursor = 0
    for c in chunks:
        off = c['offset']
        out += data[cursor:off]

        table_off = c['table_off']
        num_lines = c['num_lines']
        chunk_end = c['chunk_end']
        prefix = bytearray(data[off:table_off])
        positions = c['positions']

        pre_gaps, alias_of, sentinel, old_text_end = _entry_pre_gaps(data, table_off, num_lines, positions)

        trans = translations_by_chunk.get(off, {})
        new_blob = bytearray()
        new_offsets = [None] * num_lines
        sentinel_set = set(sentinel)
        for i in sentinel:
            new_offsets[i] = positions[i][0] - table_off  # 표 자기 자신을 가리키는 특수값, 그대로 유지 (표 크기 더하지 않음)
        for i in range(num_lines):
            if i in sentinel_set or alias_of[i] is not None:
                continue  # sentinel은 위에서 처리 끝, alias는 아래에서 대상과 같이 처리
            pos, blen = positions[i]
            orig_raw = bytes(data[pos:pos+blen])
            text = trans.get(i)
            new_blob += pre_gaps[i]
            new_offsets[i] = len(new_blob)  # 오프셋 표는 pre-gap 다음, 텍스트 시작을 가리켜야 함
            if text is None or text == orig_raw.decode('shift_jis', errors='replace'):
                encoded = orig_raw
            else:
                encoded = encode_mixed(text, hangul_map)
            new_blob += encoded
            new_blob.append(0)

        for i in range(num_lines):
            if alias_of[i] is not None:
                # 원본에서 다른 항목의 텍스트(+NUL) 구간 안에 겹쳐 들어가
                # 있던 항목(같은 문장의 뒷부분을 공유하는 경우 포함). 둘 다
                # 번역 안 됐으면(원문 그대로) 겹치던 그 관계를 그대로 재현해
                # 새 위치에서도 같이 공유하고, 어느 한쪽이라도 번역됐으면
                # 더는 안전하게 공유할 수 없으니 이 항목만 따로 새로 쓴다.
                j, offset_within = alias_of[i]
                pos, blen = positions[i]
                orig_raw = bytes(data[pos:pos+blen])
                pos_j, blen_j = positions[j]
                orig_raw_j = bytes(data[pos_j:pos_j+blen_j])
                text_i = trans.get(i)
                text_j = trans.get(j)
                i_untranslated = text_i is None or text_i == orig_raw.decode('shift_jis', errors='replace')
                j_untranslated = text_j is None or text_j == orig_raw_j.decode('shift_jis', errors='replace')
                if i_untranslated and j_untranslated:
                    new_offsets[i] = new_offsets[j] + offset_within
                else:
                    new_offsets[i] = len(new_blob)
                    if i_untranslated:
                        encoded = orig_raw
                    else:
                        encoded = encode_mixed(text_i, hangul_map)
                    new_blob += encoded
                    new_blob.append(0)

        trailer = bytes(data[old_text_end:chunk_end])

        # 오프셋 표 값은 table_off 기준(표 자신의 크기까지 포함)이라
        # new_blob 시작 기준으로 잰 값에 표 크기(num_lines*4)를 더해야 한다.
        # sentinel(표 자기 자신을 가리키는 특수값)은 이미 table_off 기준
        # 절대값이므로 더하지 않는다.
        table_size = num_lines * 4
        new_offsets = [o if i in sentinel_set else table_size + o
                       for i, o in enumerate(new_offsets)]
        new_table = struct.pack('<%dI' % num_lines, *new_offsets)
        new_chunk = bytearray(bytes(prefix) + new_table + bytes(new_blob) + trailer)
        new_size_after8 = len(new_chunk) - 8
        struct.pack_into('<I', new_chunk, 4, new_size_after8)

        out += new_chunk
        cursor = chunk_end

    out += data[cursor:]
    return bytes(out)
