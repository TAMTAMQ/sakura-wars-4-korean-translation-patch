"""1ST_READ.BIN 전체에서 플레이어가 보는 텍스트를 스캔 (디버그/노이즈 제외)"""
import re

def is_sjis_lead(b):
    return (0x81 <= b <= 0x9F) or (0xE0 <= b <= 0xFC)

def is_sjis_trail(b):
    return (0x40 <= b <= 0x7E) or (0x80 <= b <= 0xFC)

def scan_strings(data, min_chars=4, min_jis_chars=2, start=0, end=None):
    if end is None:
        end = len(data)
    results = []
    i = start
    while i < end:
        s = i
        chars = 0
        jis_chars = 0
        j = i
        while j < end:
            b = data[j]
            if b == 0:
                break
            if 0x20 <= b <= 0x7E:
                j += 1
                chars += 1
            elif is_sjis_lead(b) and j+1 < end and is_sjis_trail(data[j+1]):
                try:
                    data[j:j+2].decode('shift_jis')
                    j += 2
                    chars += 1
                    jis_chars += 1
                except Exception:
                    break
            else:
                break
        if chars >= min_chars and jis_chars >= min_jis_chars:
            raw = data[s:j]
            try:
                text = raw.decode('shift_jis')
                results.append((s, len(raw), text))
            except Exception:
                pass
            i = j + 1
        else:
            i += 1
    return results

# 노이즈/디버그로 판단되는 오프셋 구간 (제외 대상)
EXCLUDE_RANGES = [
    (2115273, 2115330),   # 노이즈(첫 항목)
    (2119414, 2120050),   # 디버그 콘솔 에러 메시지
    (2125797, 2126170),   # 디버그
    (2129483, 2129520),   # 디버그
    (2130579, 2130910),   # 내부 문자셋 참조 테이블(가나 전체 나열), UI 텍스트 아님
    (2131314, 2131360),   # 디버그
    (2133845, 2133900),   # 디버그
    (2134452, 2134520),   # 디버그
    (2138000, 2138100),   # 디버그
    (2139147, 2139170),   # 디버그
    (2139616, 2139710),   # 디버그
    (2140436, 2140500),   # 디버그
    (2140784, 2140810),   # 디버그
    (2143731, 2143900),   # 디버그
    (2144784, 2144830),   # 디버그
    (2146799, 2147250),   # 디버그(이벤트 시스템 내부 메시지)
    (2148656, 2148900),   # 디버그
    (2149131, 2149160),   # 디버그
    (2150681, 2150720),   # 디버그
    (2151314, 2151360),   # 디버그
    (2151638, 2151700),   # 디버그
    (2151926, 2151980),   # 디버그
    (2152983, 2153020),   # 디버그
    (2153586, 2153700),   # 디버그
    (2154063, 2154090),   # 디버그
    (2156779, 2156860),   # 디버그
    (2157875, 2157900),   # 디버그
    (2158079, 2158120),   # 디버그
    (2158478, 2158520),   # 디버그
    (2159932, 2159970),   # 디버그
    (2162538, 2162590),   # 디버그
    (2163589, 2163700),   # 노이즈(바이너리 오독)
    (2164663, 2164690),   # 디버그
    (2165533, 2165800),   # 디버그(파일 포맷 에러)
    (2166152, 2166503),   # 개발자 테스트용 더미 텍스트
    (2166503, 2166570),   # 디버그 툴 라벨
    (2176921, 2177000),   # 디버그
    (2177052, 2177100),   # 노이즈
    (2185369, 2193150),   # 노이즈(폰트 인덱스 테이블 오독)
    (2193771, 2193900),   # 디버그
    (2203465, 2203560),   # 디버그
    (2208145, 2208260),   # 디버그
    (2208648, 2232420),   # 이후 전부 노이즈(바이너리 오독)
]

def is_excluded(offset):
    return any(s <= offset < e for s, e in EXCLUDE_RANGES)

if __name__ == '__main__':
    import sys
    with open(sys.argv[1], 'rb') as f:
        data = f.read()
    results = scan_strings(data, start=2100000)
    kept = [r for r in results if not is_excluded(r[0])]
    print(f"전체 {len(results)}개 중 노이즈/디버그 제외 후 {len(kept)}개")
    out_path = sys.argv[2] if len(sys.argv) > 2 else 'all_1st_read_strings.txt'
    with open(out_path, 'w', encoding='utf-8') as f:
        for i, (start, blen, text) in enumerate(kept):
            f.write(f"[{i:03d}] {text}\n")
    print(f"저장: {out_path}")
