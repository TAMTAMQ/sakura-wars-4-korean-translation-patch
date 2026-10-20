"""
CG_ALL*.DAT (여러 ADCG 이미지를 담은 컨테이너) 추출 툴

사용법:
  python3 extract_cg_all.py <CG_ALL1.DAT 경로> [출력폴더] [최대개수]

구조 (CG_ALL1.DAT, 132MB, 1114개 항목으로 확인됨):
  파일 전체가 아래 레코드의 반복이다:
    [AGR1(4) + 0x00000000(4)] + [ADCG 헤더 16B: sig+comp_padded+uncomp_size
    +comp_actual] + [PRS 압축 페이로드 comp_actual바이트] + [EOFC 마커 등
    트레일러] + (다음 레코드가 2048바이트 배수 위치에서 시작하도록 0 패딩)

  각 레코드 안의 ADCG 압축 해제 후 구조는 extract_cbd_images.py 에서 이미
  분석한 EYECATCH(.CBD) 포맷과 완전히 동일하다 (RGB565, 64x64 Morton 트위들
  타일, portrait 저장 후 시계방향 90도 회전). 그래서 렌더링 로직은
  extract_cbd_images.render_adcg_image() 를 그대로 재사용한다.

  레코드 경계는 산술 계산 대신 b'AGR1\\x00\\x00\\x00\\x00ADCG' 패턴을 파일
  전체에서 찾아 안전하게 나눈다 (정렬 패딩 크기가 항상 2048인지 100% 확신할
  수 없어 탐색 방식이 더 안전함).
"""
import struct, sys, os
from extract_cbd_images import decompress_adcg_block, render_adcg_image

PATTERN = b'AGR1\x00\x00\x00\x00ADCG'

def find_entries(raw):
    positions = []
    pos = 0
    while True:
        idx = raw.find(PATTERN, pos)
        if idx == -1:
            break
        positions.append(idx)
        pos = idx + 8  # ADCG 헤더 시작 지점부터 다음 탐색
    return positions

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    src = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else 'cg_all_extracted'
    max_count = int(sys.argv[3]) if len(sys.argv) > 3 else None
    os.makedirs(out_dir, exist_ok=True)

    with open(src, 'rb') as f:
        raw = f.read()

    positions = find_entries(raw)
    print(f"항목 {len(positions)}개 발견 (파일 크기 {len(raw)} 바이트)")
    if max_count:
        positions = positions[:max_count]

    digits = max(4, len(str(len(positions))))
    ok, fail = 0, 0
    for i, pos in enumerate(positions):
        adcg_off = pos + 8  # AGR1(4)+reserved(4) 다음이 ADCG 헤더
        label = f"[{i:0{digits}d}] offset={pos}"
        try:
            dec = decompress_adcg_block(raw, adcg_off)
            if dec is None:
                print(f"  건너뜀 (sig 불일치): {label}")
                fail += 1
                continue
            img, err = render_adcg_image(dec, label=label)
            if img is None:
                print(f"  건너뜀 ({err}): {label}")
                fail += 1
                continue
            out_path = os.path.join(out_dir, f"{i:0{digits}d}.png")
            img.save(out_path)
            ok += 1
            if i % 50 == 0:
                print(f"  진행: {i}/{len(positions)} -> {out_path} ({img.width}x{img.height})")
        except Exception as e:
            print(f"  오류 ({e}): {label}")
            fail += 1

    print(f"\n완료: 성공 {ok}개 / 실패 {fail}개 -> {out_dir}/")

if __name__ == '__main__':
    main()
