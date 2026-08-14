"""SMAPnn.ESM 파일 안의 CTPA/ASCR 텍스트 청크를 시그니처 스캔으로 찾아 추출"""
import struct

def try_parse_chunk(data, off, sig):
    """off 위치에 sig(CTPA 또는 ASCR)로 시작하는 유효한 텍스트 청크가 있는지 검증 후 파싱"""
    if data[off:off+4] != sig:
        return None
    try:
        if sig == b'CTPA':
            # CTPA: sig(4) size(4) num_lines(4) table_ptr(4) unk(4)==num_lines table2_ptr(4) ...
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
        # 유효성 추가 검증: 적어도 하나는 실제 문자(가나/한자 등)를 포함해야 함
        has_real_text = any(any(ord(c) > 0x3000 for c in t) for t in texts if t)
        if not has_real_text and num_lines > 1:
            return None
        return {'offset': off, 'sig': sig.decode(), 'num_lines': num_lines,
                'size_after8': size_after8, 'texts': texts, 'positions': positions}
    except (struct.error, IndexError):
        return None

def scan_esm(path):
    with open(path, 'rb') as f:
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
    # 겹치는(같은 근처) 중복 방지: offset 기준 정렬 후 너무 가까운 것 제거
    chunks.sort(key=lambda c: c['offset'])
    return chunks

if __name__ == '__main__':
    import sys
    chunks = scan_esm(sys.argv[1])
    print(f"유효 청크 {len(chunks)}개 발견")
    total_lines = sum(c['num_lines'] for c in chunks)
    print(f"총 텍스트 줄 수: {total_lines}")
    for c in chunks[:5]:
        print(f"  offset={c['offset']} sig={c['sig']} num_lines={c['num_lines']}")
        for t in c['texts'][:3]:
            print(f"    {t!r}")
