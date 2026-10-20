"""
ADCG(.CBD) 이미지 추출 툴 (EYECATCH 등)

사용법:
  python3 extract_cbd_images.py <입력.CBD 또는 폴더> [출력폴더]

포맷 개요 (EYEC_DTS??.CBD 15개 파일로 리버스엔지니어링/검증됨):
  - 헤더: sig'ADCG'(4) + comp_padded(4) + uncomp_size(4) + comp_actual(4)
    (SBX/ASCR와 동일한 관례. offset16부터 PRS 압축 페이로드)
  - PRS 압축 해제 후 내부 구조:
      offset 0  : 알수없음(플래그성 값으로 추정)
      offset 4  : num_tiles (u32) - 타일 총 개수
      offset 8  : tileW, tileH (u16, u16) - 타일 한 변 크기 (지금까지 전부 64x64)
      offset 12 : table_offset (u32) - 타일 청크 표 시작 위치
      offset 16 : (미해석)
      offset 20 : finalW, finalH (u16,u16) - 최종 화면에 표시되는 이미지 크기
      offset table_offset .. +num_tiles*16 : 청크 표(16바이트×num_tiles, 압축
        스트리밍 청크 경계로 추정 - 실제 타일 픽셀 경계와는 무관해서 무시함)
      표 끝부터 num_tiles*tileW*tileH*2 바이트: 픽셀 데이터 (RGB565, 16bpp)

  - 픽셀 데이터는 세로(portrait) 방향으로 저장되어 있다:
      grid_cols = ceil(finalH / tileH)   (가로로 늘어선 타일 수)
      grid_rows = ceil(finalW / tileW)   (세로로 늘어선 타일 수)
      canvas 크기 = (grid_cols*tileW) x (grid_rows*tileH)  [portrait]
    타일은 이 캔버스에 래스터 순서(왼쪽->오른쪽, 위->아래)로 배치되고,
    타일 하나하나는 64x64 안에서 Morton(Z-order) 순서로 트위들되어 있다.
    캔버스를 다 채운 뒤 시계방향 90도 회전 -> (finalW,finalH)로 크롭하면
    실제 보여지는 이미지가 나온다.
    (EYEC_DTS00.CBD로 검증: 회전 안 하면 뒤죽박죽, 8x10 그리드로 회전하면
     캐릭터들이 이음새 없이 깨끗하게 나옴. 2026-08-14)

  - 이 규칙에 맞지 않는 파일(예: TAIN_DTS.CBD, sig 'BPV1')은 다른 포맷이라
    건너뛴다.
"""
import struct, sys, os, glob
import numpy as np
from PIL import Image
from prs_decompress import DecompressPrs

_MORTON_CACHE = {}

def morton_index_table(n_bits):
    if n_bits in _MORTON_CACHE:
        return _MORTON_CACHE[n_bits]
    size = 1 << n_bits
    idx = np.zeros((size, size), dtype=np.int64)
    for y in range(size):
        for x in range(size):
            m = 0
            for b in range(n_bits):
                m |= ((x >> b) & 1) << (2 * b)
                m |= ((y >> b) & 1) << (2 * b + 1)
            idx[y, x] = m
    _MORTON_CACHE[n_bits] = idx
    return idx

def rgb565_to_rgb888(v):
    r = ((v >> 11) & 0x1f).astype(np.uint16)
    g = ((v >> 5) & 0x3f).astype(np.uint16)
    b = (v & 0x1f).astype(np.uint16)
    r = (r * 255 // 31).astype(np.uint8)
    g = (g * 255 // 63).astype(np.uint8)
    b = (b * 255 // 31).astype(np.uint8)
    return np.stack([r, g, b], axis=-1)

def decompress_adcg_block(raw, offset=0):
    """raw[offset:] 가 sig'ADCG'(4)+comp_padded(4)+uncomp_size(4)+comp_actual(4)+
    payload 로 시작한다고 가정하고 압축 해제된 내부 구조(dec)를 돌려준다.
    sig가 'ADCG'가 아니면 None."""
    if raw[offset:offset+4] != b'ADCG':
        return None
    comp_padded, uncomp_size, comp_actual = struct.unpack_from('<III', raw, offset + 4)
    payload = raw[offset+16:offset+16+comp_actual]
    dec = bytes(DecompressPrs(payload).decompress())
    return dec

def render_adcg_image(dec, label=''):
    """decompress_adcg_block()의 결과(dec)를 PIL Image로 렌더링. 형식이
    안 맞으면 (None, 사유) 를 돌려준다."""
    if len(dec) < 24:
        return None, 'dec too short'

    num_tiles = struct.unpack_from('<I', dec, 4)[0]
    tileW, tileH = struct.unpack_from('<HH', dec, 8)
    table_offset = struct.unpack_from('<I', dec, 12)[0]
    finalW, finalH = struct.unpack_from('<HH', dec, 20)

    if tileW != tileH:
        return None, '정사각 타일 아님, 미지원'
    n_bits = tileW.bit_length() - 1
    if (1 << n_bits) != tileW:
        return None, '타일 크기가 2의 거듭제곱 아님'

    table_end = table_offset + num_tiles * 16
    pixel_bytes_needed = num_tiles * tileW * tileH * 2
    pixel_data = dec[table_end:table_end + pixel_bytes_needed]
    if len(pixel_data) < pixel_bytes_needed:
        return None, '픽셀 데이터 부족'

    arr = np.frombuffer(pixel_data, dtype='<u2')
    tiles = arr.reshape(num_tiles, tileH * tileW)
    morton = morton_index_table(n_bits)

    grid_cols = -(-finalH // tileH)  # ceil
    grid_rows = -(-finalW // tileW)
    if grid_cols * grid_rows != num_tiles:
        print(f"  경고: 그리드({grid_cols}x{grid_rows}={grid_cols*grid_rows}) != "
              f"num_tiles({num_tiles}), 그래도 진행: {label}")

    canvas = np.zeros((grid_rows * tileH, grid_cols * tileW), dtype='<u2')
    for t in range(num_tiles):
        tr, tc = divmod(t, grid_cols)
        if tr >= grid_rows:
            break
        tile_img = tiles[t][morton]
        canvas[tr*tileH:(tr+1)*tileH, tc*tileW:(tc+1)*tileW] = tile_img

    rgb = rgb565_to_rgb888(canvas.reshape(-1)).reshape(canvas.shape[0], canvas.shape[1], 3)
    img = Image.fromarray(rgb).rotate(-90, expand=True)
    img = img.crop((0, 0, finalW, finalH))
    # 시계방향 90도 회전만으로는 좌우가 뒤집혀 나온다 (WARNING2.CBD로 확인,
    # 2026-08-14) - 좌우반전을 추가로 적용해야 정방향이 된다.
    img = img.transpose(Image.FLIP_LEFT_RIGHT)
    return img, None

def extract_one(cbd_path, out_path):
    with open(cbd_path, 'rb') as f:
        raw = f.read()

    dec = decompress_adcg_block(raw, 0)
    if dec is None:
        print(f"  건너뜀 (미지원 포맷 sig={raw[:4]!r}): {cbd_path}")
        return False

    img, err = render_adcg_image(dec, label=cbd_path)
    if img is None:
        print(f"  건너뜀 ({err}): {cbd_path}")
        return False

    img.save(out_path)
    print(f"  저장: {out_path} ({img.width}x{img.height})")
    return True

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    src = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else 'cbd_extracted'
    os.makedirs(out_dir, exist_ok=True)

    if os.path.isdir(src):
        seen = {}
        for fp in glob.glob(os.path.join(src, '*.CBD')) + glob.glob(os.path.join(src, '*.cbd')):
            seen[os.path.normcase(os.path.abspath(fp))] = fp
        files = sorted(seen.values())
    else:
        files = [src]

    ok, fail = 0, 0
    for fp in files:
        base = os.path.splitext(os.path.basename(fp))[0]
        out_path = os.path.join(out_dir, base + '.png')
        print(f"처리 중: {fp}")
        try:
            if extract_one(fp, out_path):
                ok += 1
            else:
                fail += 1
        except Exception as e:
            print(f"  오류: {e}")
            fail += 1

    print(f"\n완료: 성공 {ok}개 / 실패(건너뜀) {fail}개 -> {out_dir}/")

if __name__ == '__main__':
    main()
