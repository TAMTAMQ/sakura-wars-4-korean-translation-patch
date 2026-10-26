"""엔딩 이름 2열을 고정 칸으로 배치한다. ASCR 데이터·포인터만 변경한다.

한글 뒤 반각 띄어쓰기는 별도 글자가 아니라 글리프 플래그다. 첫 이름은
모두 성/이름 사이의 반각 공백 하나를 가지므로, 그 플래그를 유지하고 빈
한글 타일로 10칸까지 채우면 글꼴 크기에 관계없이 둘째 이름의 시작이 같다.
문안은 공유 units에서 읽으며, 번역문을 레이아웃 설정에 복제하지 않는다.
"""
import hashlib
import json
import struct


def live_strings(data):
    if data[:4] != b'ASCR':
        raise ValueError('엔딩 레이아웃: ASCR 아님')
    off, count = struct.unpack_from('<II', data, 12)
    table = off + 8
    pool = table + count * 4
    if pool > len(data):
        raise ValueError('엔딩 레이아웃: 문자열 표 범위')
    spans = []
    for i in range(count):
        start = table + struct.unpack_from('<I', data, table + i * 4)[0]
        if not pool <= start < len(data):
            raise ValueError('엔딩 레이아웃: 문자열 포인터 범위')
        end = data.find(b'\0', start)
        if end < 0:
            raise ValueError('엔딩 레이아웃: 문자열 종결 누락')
        spans.append((start, end + 1))
    return table, pool, spans


def format_names(text, item, cells):
    if 'split_at' in item:
        at = item['split_at']
        if text[at:at + 1] != ' ':
            raise ValueError('엔딩 레이아웃: 이름 경계 변경')
        left, right = text[:at], text[at + 1:]
    else:
        parts = text.split('　　')
        if len(parts) != 2:
            raise ValueError('엔딩 레이아웃: 2열 구분 누락')
        left, right = parts
    if left.count(' ') != 1 or not right or left != left.strip() or right != right.strip():
        raise ValueError('엔딩 레이아웃: 이름별 반각 공백 조건 변경')
    used = len(left.replace(' ', ''))
    if used >= cells:
        raise ValueError('엔딩 레이아웃: 첫 열 이름이 간격을 침범')
    # U+2063은 config/encoding.json에 등록된 투명 한글 타일이다.
    return left + '\u2063' * (cells - used) + right


def plan(root, baseline, rows, codes, encode):
    path = root / 'config/ending-credits-layout.json'
    if not path.exists():
        return [], set(), {'rows': 0}
    cfg = json.loads(path.read_text(encoding='utf-8'))
    rel = cfg['file']
    data = baseline[rel]
    if hashlib.sha256(data).hexdigest() != cfg['baseline_sha256']:
        raise ValueError('엔딩 레이아웃: 기준선 해시 불일치')
    table, pool, live = live_strings(data)
    # 다른 번역이 쓰는 종결 뒤의 가용 공간도 재사용하지 않는다.
    protected = live + [(r['offset'], r['offset'] + r['capacity'] + 1)
                        for r in rows.values() if r['file'] == rel]
    writes, managed, slots, report = [], set(), [], []
    for item in cfg['rows']:
        key = item['id']
        if key in managed:
            raise ValueError('엔딩 레이아웃: 중복 ID')
        row = rows[key]
        if row['file'] != rel or row['kind'] != 'ascr':
            raise ValueError('엔딩 레이아웃: 대상 형식 변경')
        ptr = row['pointer_offset']
        if not table <= ptr < pool or (ptr - table) % 4:
            raise ValueError('엔딩 레이아웃: 포인터 위치')
        if table + struct.unpack_from('<I', data, ptr)[0] != row['offset']:
            raise ValueError('엔딩 레이아웃: 원본 참조 불일치')
        raw = bytes.fromhex(row['raw_hex'])
        if data[row['offset']:row['offset'] + len(raw) + 1] != raw + b'\0':
            raise ValueError('엔딩 레이아웃: 원본 문자열 불일치')
        text = format_names(row['text'], item, cfg['first_column_cells'])
        if any(ch not in codes and ch != ' ' for ch in text.split('\u2063', 1)[0]):
            raise ValueError('엔딩 레이아웃: 첫 열에 고정 한글 칸이 아닌 문자')
        encoded = encode(text, codes) + b'\0'
        start, capacity = item['offset'], item['capacity']
        end = start + capacity
        if capacity < len(encoded) or start < pool or end > len(data):
            raise ValueError('엔딩 레이아웃: 재사용 공간 부족·범위 오류')
        if any(start < e and s < end for s, e in protected + slots):
            raise ValueError('엔딩 레이아웃: 살아 있는 문자열·보호 영역·슬롯과 겹침')
        slots.append((start, end))
        writes.append((rel, start, data[start:start + len(encoded)], encoded, 'ending-name:' + key))
        new_ptr = struct.pack('<I', start - table)
        writes.append((rel, ptr, data[ptr:ptr + 4], new_ptr, 'ending-pointer:' + key))
        managed.add(key)
        report.append({'id': key, 'offset': start, 'size': len(encoded),
                       'first_column_cells': cfg['first_column_cells'], 'half_spaces': 1})
    return writes, managed, {'rows': len(report), 'allocations': report,
                            'layout_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                            'file_size_unchanged': True, 'bytecode_unchanged': True}


def verify_blank_fonts(files, codes):
    """레이아웃의 빈 타일이 최종 글꼴에서도 투명한지 확인한다."""
    code = int(codes['\u2063'], 16)
    lead, lo = code >> 8, code & 255
    if not 0xF0 <= lead <= 0xF7:
        raise ValueError('엔딩 레이아웃: 빈 타일 코드 형식 변경')
    tile = 398 + (lead - 0x68 - 0x88) * 188 + lo - 0x40 - (1 if lo > 0x7F else 0)
    for name, size in [('SKFONT.CG', 26), ('SKFONT2.CG', 24), ('SKFONT3.CG', 22), ('SKFONT4.CG', 22)]:
        stride = size * size // 2
        data = files[name]
        raw = data[tile * stride:(tile + 1) * stride]
        if len(raw) != stride or any(raw):
            raise ValueError('엔딩 레이아웃: 빈 타일에 픽셀이 있음: ' + name)
