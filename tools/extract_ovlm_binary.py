"""1ST_READ.BIN 외에 APPEND.BIN, MGJT.BIN 같은 OVLM(오버레이) 실행 파일 안의
텍스트를 스캔하는 범용 도구. 히라가나/구두점 비율로 노이즈를 걸러낸다."""
from extract_1st_read_all import scan_strings

def real_text_filter(text):
    if len(text) < 2:
        return False
    hiragana_or_punct = sum(1 for c in text if (0x3040 <= ord(c) <= 0x309F) or c in '。！？、…∈〓「」')
    return hiragana_or_punct / len(text) >= 0.15 or any(0x3040 <= ord(c) <= 0x30FF for c in text[:3])

def find_real_strings(data, min_chars=4, min_jis_chars=2):
    results = scan_strings(data, min_chars=min_chars, min_jis_chars=min_jis_chars)
    return [(s, b, t) for s, b, t in results if real_text_filter(t)]

if __name__ == '__main__':
    import sys, json, os
    path = sys.argv[1]
    out_txt = sys.argv[2]
    out_manifest = sys.argv[3] if len(sys.argv) > 3 else out_txt.replace('.txt', '.manifest.json')

    with open(path, 'rb') as f:
        data = f.read()
    results = find_real_strings(data)

    lines_out = []
    manifest = []
    for idx, (pos, blen, text) in enumerate(results):
        lines_out.append(f"[{idx:04d}] {text}")
        manifest.append({'idx': idx, 'pos': pos, 'byte_len': blen})

    os.makedirs(os.path.dirname(out_txt) or '.', exist_ok=True)
    with open(out_txt, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines_out) + '\n')
    with open(out_manifest, 'w', encoding='utf-8') as f:
        json.dump(manifest, f)
    print(f"{len(results)}개 문자열 -> {out_txt}")
