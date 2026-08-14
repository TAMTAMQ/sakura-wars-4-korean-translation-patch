"""
이미 번역해둔 SBX/SBN 대사를 원문 매칭으로 찾아서
LIPSYNC 템플릿에 자동으로 채워넣는 도구.

사용법 (korean_font_package 폴더에서):
  python3 tools/auto_fill_lipsync.py

동작:
1) original_files/ 와 translation_templates/ 를 비교해서
   "원문 -> 번역문" 사전을 만듭니다 (실제로 번역해서 원문과
   달라진 줄만 대상).
2) translation_templates/LIPSYNC/*.txt 를 훑으면서, 원문이
   1번 사전과 정확히 일치하는 줄이 있으면 그 번역문으로
   자동으로 바꿔줍니다.
3) 매칭 안 된(아직 아무도 번역 안 한) 줄은 원문 그대로 남겨두니,
   나머지만 직접 번역하시면 됩니다.
"""
import os, re, glob

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(BASE_DIR)  # tools/ -> korean_font_package/
ORIGINAL_DIR = os.path.join(BASE_DIR, 'original_files')
TEMPLATES_DIR = os.path.join(BASE_DIR, 'translation_templates')

LINE_PATTERN = re.compile(r'^\[(\d+)\]\s?(.*)$')

def parse_template(path):
    result = {}
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')
            m = LINE_PATTERN.match(line)
            if m:
                result[int(m.group(1))] = m.group(2)
    return result

def get_original_text_for_sbx(sbx_path):
    """SBX/SBN 원본에서 ASCR 텍스트 목록을 뽑는다 (rebuild_sbx.py와 동일 로직)."""
    import struct
    from prs_decompress import DecompressPrs
    with open(sbx_path, 'rb') as f:
        raw = f.read()
    if raw[8:12] == b'\xba\xaf\x55\xcc':
        ascr = raw
    else:
        comp_actual = struct.unpack_from('<I', raw, 12)[0]
        payload = raw[16:16+comp_actual]
        dec = DecompressPrs(payload).decompress()
        ascr = b'ASCR' + struct.pack('<I', len(dec)) + dec
    text_table_ptr, num_lines, subr_ptr, num_subr = struct.unpack_from('<IIII', ascr, 0xc)
    table_off = text_table_ptr + 8
    entries = struct.unpack_from('<%dI' % num_lines, ascr, table_off)
    texts = {}
    for i, e in enumerate(entries):
        pos = e + table_off
        end = ascr.index(b'\x00', pos)
        texts[i] = ascr[pos:end].decode('shift_jis', errors='replace')
    return texts

def build_translation_dict():
    known = {}
    for root, dirs, files in os.walk(TEMPLATES_DIR):
        rel_root = os.path.relpath(root, TEMPLATES_DIR)
        top = rel_root.split(os.sep)[0]
        if top in ('LIPSYNC', '1ST_READ', 'SLG_ESM'):
            continue
        for fname in files:
            if not fname.endswith('.txt'):
                continue
            rel_path = os.path.join(rel_root, fname) if rel_root != '.' else fname
            base_no_ext = os.path.join(ORIGINAL_DIR, rel_path[:-4])
            src = None
            for ext in ('.SBX', '.SBN'):
                if os.path.exists(base_no_ext + ext):
                    src = base_no_ext + ext
                    break
            if not src:
                continue
            try:
                orig_texts = get_original_text_for_sbx(src)
            except Exception:
                continue
            translated = parse_template(os.path.join(root, fname))
            for idx, trans_text in translated.items():
                orig_text = orig_texts.get(idx)
                if orig_text is not None and trans_text and trans_text != orig_text:
                    known[orig_text] = trans_text
    return known

def main():
    print("1) 기존 번역 수집 중...")
    known = build_translation_dict()
    print(f"   원문 매칭 사전 {len(known)}개 확보")

    lip_dir = os.path.join(TEMPLATES_DIR, 'LIPSYNC')
    if not os.path.isdir(lip_dir):
        print("   translation_templates/LIPSYNC 폴더가 없습니다. 먼저 립싱크 템플릿을 넣어주세요.")
        return

    print("2) LIPSYNC 템플릿에 자동 채우는 중...")
    total_filled = 0
    for fname in sorted(os.listdir(lip_dir)):
        if not fname.endswith('.txt'):
            continue
        path = os.path.join(lip_dir, fname)
        with open(path, encoding='utf-8') as f:
            lines = f.readlines()
        filled = 0
        new_lines = []
        for line in lines:
            stripped = line.rstrip('\n')
            m = LINE_PATTERN.match(stripped)
            if m:
                idx, text = m.group(1), m.group(2)
                if text in known:
                    new_lines.append(f"[{idx}] {known[text]}\n")
                    filled += 1
                    continue
            new_lines.append(line if line.endswith('\n') else line + '\n')
        with open(path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        if filled:
            print(f"   {fname}: {filled}줄 자동 채움")
        total_filled += filled

    print(f"\n완료: 총 {total_filled}줄을 기존 번역으로 자동 채웠습니다.")
    print("나머지(자동으로 안 채워진) 줄만 직접 번역하시면 됩니다.")

if __name__ == '__main__':
    main()
