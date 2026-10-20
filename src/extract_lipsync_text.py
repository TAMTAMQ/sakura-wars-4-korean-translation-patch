"""LIPSYNC*.LIP 파일에서 실제 대사 텍스트만 스캔
구조: [프레임데이터][Shift-JIS 텍스트]\x00 이 반복됨
프레임 데이터는 좁은 범위(0x00-0x7F 위주)의 반복적인 니블 패턴이라
실제 텍스트(가나/한자 포함)와 구분해서 필터링한다."""
import struct

def is_sjis_lead(b):
    return (0x81 <= b <= 0x9F) or (0xE0 <= b <= 0xFC)

def is_sjis_trail(b):
    return (0x40 <= b <= 0x7E) or (0x80 <= b <= 0xFC)

def scan_real_text(data, min_chars=2, min_jis_chars=1):
    results = []
    i = 0
    n = len(data)
    while i < n:
        s = i
        chars = 0
        jis_chars = 0
        j = i
        while j < n:
            b = data[j]
            if b == 0:
                break
            if 0x20 <= b <= 0x7E:
                j += 1
                chars += 1
            elif is_sjis_lead(b) and j+1 < n and is_sjis_trail(data[j+1]):
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
                # 실제 대사는 최소 하나의 진짜 가나/한자(0x3000 이상)를 포함해야 함
                if any(ord(c) >= 0x3040 for c in text):
                    results.append((s, len(raw), text))
            except Exception:
                pass
            i = j + 1
        else:
            i += 1
    return results

if __name__ == '__main__':
    for name in ['LIPSYNC1.LIP', 'LIPSYNC2.LIP', 'LIPSYNC3.LIP', 'LIPSYNC4.LIP']:
        with open(name, 'rb') as f:
            data = f.read()
        results = scan_real_text(data)
        print(f"{name}: {len(results)}개 실제 대사 후보")
