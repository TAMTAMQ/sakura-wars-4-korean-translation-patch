"""extract_bpv1.py로 뽑아낸 .bin(압축 해제된 원본 바이트)을 수정한 뒤,
다시 PRS로 압축해서 원본 파일과 같은 BPV1 구조로 되돌리는 도구.

*** 중요: 재압축 위험성 ***
이 프로젝트에서 이전에 SBX(대사 스크립트) 파일을 재압축했을 때, 완전히
무손실로 다시 압축했는데도(디코딩하면 원문과 100% 동일) 실제 게임에서
해당 구간이 통째로 스킵되는 문제가 있었다(rebuild_sbx.py 주석 참고).
리터럴 전용 인코딩으로 바꿔봐도 마찬가지였다. 원인은 정확히 모르지만
압축 페이로드 자체에 대한 별도 검증(체크섬 등)이 있는 것으로 추정된다.
SBX는 "아예 압축을 안 쓰는 내부 구조로 출력"하는 방식으로 우회했는데,
이 우회가 통했던 건 ASCR 포맷 자체에 "이 값이면 비압축"이라는 전용
마커(0xbaaf55cc)가 있었기 때문이다. BPV1에 같은 마커가 있는지는 아직
확인 못 했다 - 즉 이 도구로 재압축한 파일이 SBX와 같은 문제를 겪을
가능성이 있다. 실기/에뮬레이터에서 반드시 테스트해보고, 문제가 생기면
알려주면 비압축 우회를 다시 시도해볼 수 있다.

이 도구는 "리터럴 전용" PRS 인코딩을 쓴다 (모든 바이트를 그대로
저장하고 뒤로 참조하는 압축을 전혀 안 함 - 그래서 무조건 정확하게
디코딩되는 걸 보장하지만, 파일 용량은 원본 압축본보다 커진다).

사용법:
  python repack_bpv1.py <원본.CBD> <수정된.bin> <출력.CBD>
  (원본 파일 크기는 참고용일 뿐, comp_padded/uncomp_size 등은 수정된
   .bin의 실제 크기 기준으로 새로 계산해서 헤더를 다시 만든다)
"""
import sys, struct

def prs_compress_literal(data):
    """모든 바이트를 리터럴로만 인코딩하는 PRS 압축기 (무손실 보장,
    압축률은 없음 - 대신 반드시 정확하게 원본으로 복원됨)."""
    out = bytearray()
    for i in range(0, len(data), 8):
        chunk = data[i:i+8]
        out.append(0xFF)  # 이번 8개 오퍼레이션 전부 "리터럴 바이트" 비트
        out.extend(chunk)
    return bytes(out)

def repack(orig_path, modified_bin_path, out_path):
    with open(orig_path, 'rb') as f:
        orig = f.read()
    with open(modified_bin_path, 'rb') as f:
        dec = f.read()

    payload = prs_compress_literal(dec)
    comp_actual = len(payload)
    comp_padded = (comp_actual + 3) & ~3  # 4바이트 정렬 (ASCR 관례와 동일하게 맞춤)
    uncomp_size = len(dec)

    header = b'BPV1' + struct.pack('<III', comp_padded, uncomp_size, comp_actual)
    out = bytearray(header)
    out += payload
    if len(out) < comp_padded + 16:
        out += b'\x00' * (comp_padded + 16 - len(out))

    with open(out_path, 'wb') as f:
        f.write(bytes(out))

    return {
        'orig_size': len(orig),
        'new_size': len(out),
        'uncomp_size': uncomp_size,
        'comp_actual': comp_actual,
    }

if __name__ == '__main__':
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    stats = repack(sys.argv[1], sys.argv[2], sys.argv[3])
    print(f"완료: 원본 {stats['orig_size']}바이트 -> 새 파일 {stats['new_size']}바이트")
    print(f"  (압축 해제 크기 {stats['uncomp_size']}, 리터럴 압축 페이로드 {stats['comp_actual']})")
    print("주의: 리터럴 전용 재압축은 이 게임에서 검증되지 않았습니다. 실기/에뮬레이터 테스트 필수.")
