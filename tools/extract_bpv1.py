"""BPV1 포맷(SAVEMENU.CBD, SAVESLG.CBD, TITLEMENU.CBD, WARNING.CBD 등 UI
스프라이트 아틀라스로 추정) 파일을 일괄 압축 해제하는 도구.

이 포맷은 ASCR(대사 텍스트)와 완전히 같은 PRS 압축 헤더 구조를 쓴다는
것까지는 확인했다(2026-08-15):
  [0:4]   시그니처 "BPV1"
  [4:8]   comp_padded (uint32 LE)
  [8:12]  uncomp_size (uint32 LE) - 압축 해제 후 크기
  [12:16] comp_actual (uint32 LE) - 실제 압축 페이로드 크기
  [16:]   PRS 압축 페이로드 (prs_decompress.py로 해제 가능, 크기 정확히 일치 확인)

다만 압축 해제된 바이트가 정확히 어떤 이미지 포맷(픽셀 포맷/타일링/
스프라이트별 크기표)인지는 아직 못 풀었다. 그래서 이 도구는 "보기 좋은
이미지"가 아니라 압축 해제된 원본 바이트를 그대로 .bin으로 저장한다 -
헥스 에디터나 직접 분석용. 같은 폴더에 재압축(repack_bpv1.py)에 필요한
메타데이터(.json)도 같이 저장한다.

사용법:
  python extract_bpv1.py <디스크 루트 폴더> <출력 폴더>
  (디스크 루트 폴더 이하를 재귀적으로 뒤져서 시그니처가 BPV1인 파일을
   전부 찾아 처리한다 - 확장자는 안 가림, .CBD/.DAT/.CSD/.CCL/.BP1/.CNK
   등 다양하게 쓰이는 것으로 확인됨)
"""
import sys, os, json, struct
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from prs_decompress import DecompressPrs

def find_bpv1_files(root):
    for dirpath, dirs, files in os.walk(root):
        for fn in files:
            path = os.path.join(dirpath, fn)
            try:
                with open(path, 'rb') as f:
                    sig = f.read(4)
            except Exception:
                continue
            if sig == b'BPV1':
                yield path

def extract_one(path, root, out_dir):
    with open(path, 'rb') as f:
        data = f.read()
    comp_padded, uncomp_size, comp_actual = struct.unpack_from('<III', data, 4)
    payload = data[16:16+comp_actual]
    try:
        dec = DecompressPrs(payload).decompress()
    except Exception as e:
        print(f"  압축 해제 실패: {path}: {e}")
        return False
    if len(dec) != uncomp_size:
        print(f"  경고: 압축 해제 크기 불일치 {path}: {len(dec)} != {uncomp_size}")

    rel = os.path.relpath(path, root)
    out_bin = os.path.join(out_dir, rel + '.bin')
    out_json = os.path.join(out_dir, rel + '.json')
    os.makedirs(os.path.dirname(out_bin), exist_ok=True)
    with open(out_bin, 'wb') as f:
        f.write(dec)
    meta = {
        'source_rel_path': rel.replace('\\', '/'),
        'orig_file_size': len(data),
        'comp_padded': comp_padded,
        'uncomp_size': uncomp_size,
        'comp_actual': comp_actual,
        'header_size': 16,
        'decompressed_size': len(dec),
    }
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2)
    return True

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    root, out_dir = sys.argv[1], sys.argv[2]
    found = list(find_bpv1_files(root))
    print(f"BPV1 시그니처 파일 {len(found)}개 발견")
    ok = 0
    for path in found:
        if extract_one(path, root, out_dir):
            ok += 1
            print(f"  OK: {os.path.relpath(path, root)}")
    print(f"\n완료: {ok}/{len(found)}개 압축 해제 -> {out_dir}")
