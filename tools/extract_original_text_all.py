# -*- coding: utf-8 -*-
"""번역 이전 원문(일본어) 텍스트를 원본 바이너리에서 직접 다시 뽑아서
번역용 폴더 구조 그대로 별도 폴더에 저장한다 (번역 템플릿은 이미 번역이
반영되어 있어 원문이 아니므로, 항상 원본 바이너리에서 재추출한다).

지원 포맷:
  - SBX/SBN (ASCR) : ADVDATA/SCRIPT, SLG, MINIGAME - 표의 모든 줄(라벨
    포함) 그대로, rebuild_sbx.py와 동일한 파싱 로직 재사용
  - ESM : SLG_ESM - build_esm_template.py 재사용 (실제 대사만 필터링,
    원래 템플릿 생성 방식과 동일)
  - LIPSYNC : lipsync_format.py 재사용 (pre_text+text 합친 전체 원문)
"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prs_decompress import DecompressPrs
from build_esm_template import build_template as build_esm_template
import lipsync_format as lf
from extract_ovlm_binary import find_real_strings as find_ovlm_strings
from extract_1st_read_all import scan_strings as scan_1st_read_strings, is_excluded as is_1st_read_excluded

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIGINAL_DIR = os.path.join(BASE_DIR, 'original_files')
TEMPLATES_DIR = os.path.join(BASE_DIR, 'translation_templates')
OUT_DIR = os.path.join(BASE_DIR, 'original_txt')


def find_original(base_no_ext):
    for ext in ('.SBX', '.SBN'):
        p = base_no_ext + ext
        if os.path.exists(p):
            return p
    return None


def extract_sbx_original_lines(path):
    with open(path, 'rb') as f:
        raw = f.read()
    sig = raw[:4]
    assert sig == b'ASCR', f"ASCR 헤더가 아닙니다: {path} {sig}"
    is_compressed = raw[8:12] != b'\xba\xaf\x55\xcc'
    if is_compressed:
        comp_padded, uncomp_size, comp_actual = struct.unpack_from('<III', raw, 4)
        payload = raw[16:16 + comp_actual]
        dec = DecompressPrs(payload).decompress()
        ascr = bytearray(b'ASCR' + struct.pack('<I', len(dec)) + dec)
    else:
        ascr = bytearray(raw)

    text_table_ptr, num_lines, subr_ptr, num_subr = struct.unpack_from('<IIII', ascr, 0xc)
    table_off = text_table_ptr + 8
    entries = list(struct.unpack_from('<%dI' % num_lines, ascr, table_off))

    lines = []
    for e in entries:
        pos = e + table_off
        end = ascr.index(b'\x00', pos)
        text = bytes(ascr[pos:end]).decode('shift_jis', errors='replace')
        lines.append(text)
    return lines


def process_sbx_dir(rel_dirs):
    """SLG, MINIGAME, ADVDATA/SCRIPT 등 SBX/SBN 템플릿 폴더들을 처리."""
    count_files = 0
    count_lines = 0
    for rel_dir in rel_dirs:
        template_root = os.path.join(TEMPLATES_DIR, rel_dir)
        if not os.path.isdir(template_root):
            continue
        for root, dirs, files in os.walk(template_root):
            for fname in sorted(files):
                if not fname.endswith('.txt'):
                    continue
                template_path = os.path.join(root, fname)
                rel_path = os.path.relpath(template_path, TEMPLATES_DIR)
                base_no_ext = os.path.join(ORIGINAL_DIR, rel_path[:-4])
                src = find_original(base_no_ext)
                if not src:
                    print(f"  [건너뜀] 원본을 못 찾음: {rel_path}")
                    continue
                try:
                    lines = extract_sbx_original_lines(src)
                except Exception as e:
                    print(f"  [오류] {rel_path}: {e}")
                    continue
                out_path = os.path.join(OUT_DIR, rel_path)
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                with open(out_path, 'w', encoding='utf-8') as f:
                    for i, t in enumerate(lines):
                        f.write(f"[{i:04d}] {t}\n")
                count_files += 1
                count_lines += len(lines)
    return count_files, count_lines


def process_esm():
    count_files = 0
    count_lines = 0
    src_dir = os.path.join(ORIGINAL_DIR, 'SLG_ESM')
    if not os.path.isdir(src_dir):
        return 0, 0
    for fname in sorted(os.listdir(src_dir)):
        if not fname.endswith('.ESM'):
            continue
        esm_path = os.path.join(src_dir, fname)
        out_path = os.path.join(OUT_DIR, 'SLG_ESM', fname[:-4] + '.txt')
        manifest_path = out_path[:-4] + '.manifest.json'
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        n = build_esm_template(esm_path, out_path, manifest_path)
        os.remove(manifest_path)  # 매니페스트는 필요 없음, 텍스트만
        count_files += 1
        count_lines += n
    return count_files, count_lines


def process_lipsync():
    count_files = 0
    count_lines = 0
    src_dir = os.path.join(ORIGINAL_DIR, 'ADVDATA')
    for n in range(1, 5):
        fname = f'LIPSYNC{n}.LIP'
        lip_path = os.path.join(src_dir, fname)
        if not os.path.exists(lip_path):
            continue
        with open(lip_path, 'rb') as f:
            data = f.read()
        parsed = lf.parse(data)
        out_path = os.path.join(OUT_DIR, 'LIPSYNC', f'LIPSYNC{n}.txt')
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            for k in range(parsed['count']):
                pre, text, post = parsed['entries'][k]
                full = lf.full_original_text(pre, text)
                f.write(f"[{k:04d}] {full}\n")
        count_files += 1
        count_lines += parsed['count']
    return count_files, count_lines


def process_ovlm():
    targets = [
        ('APPEND', os.path.join(ORIGINAL_DIR, 'ADVDATA', 'APPEND', 'APPEND.BIN')),
        ('MGJT', os.path.join(ORIGINAL_DIR, 'MINIGAME', 'MGJT.BIN')),
    ]
    count_files = 0
    count_lines = 0
    for name, src_path in targets:
        if not os.path.exists(src_path):
            print(f"  [건너뜀] 원본을 못 찾음: {src_path}")
            continue
        with open(src_path, 'rb') as f:
            data = f.read()
        results = find_ovlm_strings(data)
        out_path = os.path.join(OUT_DIR, 'OVLM', name + '.txt')
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            for i, (start, blen, text) in enumerate(results):
                f.write(f"[{i:04d}] {text}\n")
        count_files += 1
        count_lines += len(results)
    return count_files, count_lines


def process_1st_read():
    src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '1ST_READ.BIN')
    if not os.path.exists(src_path):
        print(f"  [건너뜀] 원본을 못 찾음: {src_path}")
        return 0, 0
    with open(src_path, 'rb') as f:
        data = f.read()
    results = scan_1st_read_strings(data, start=2100000)
    kept = [r for r in results if not is_1st_read_excluded(r[0])]
    out_path = os.path.join(OUT_DIR, '1ST_READ', 'all_1st_read_strings.txt')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        for i, (start, blen, text) in enumerate(kept):
            f.write(f"[{i:04d}] {text}\n")
    return 1, len(kept)


if __name__ == '__main__':
    print("=== SBX/SBN (ADVDATA/SCRIPT, ADVDATA/APPEND, SLG, MINIGAME) 원문 재추출 ===")
    f1, l1 = process_sbx_dir(['ADVDATA/SCRIPT', 'ADVDATA/APPEND', 'SLG', 'MINIGAME'])
    print(f"  {f1}개 파일, {l1}줄")

    print("=== SLG_ESM 원문 재추출 ===")
    f2, l2 = process_esm()
    print(f"  {f2}개 파일, {l2}줄")

    print("=== LIPSYNC 원문 재추출 ===")
    f3, l3 = process_lipsync()
    print(f"  {f3}개 파일, {l3}줄")

    print("=== OVLM 원문 재추출 ===")
    f4, l4 = process_ovlm()
    print(f"  {f4}개 파일, {l4}줄")

    print("=== 1ST_READ 원문 재추출 ===")
    f5, l5 = process_1st_read()
    print(f"  {f5}개 파일, {l5}줄")

    print(f"\n총 {f1+f2+f3+f4+f5}개 파일 -> {OUT_DIR}")
