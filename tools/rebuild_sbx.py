"""
사쿠라 대전 4 SBX(ASCR) 재조립 툴
사용법:
  python3 rebuild_sbx.py <원본.SBX> <번역텍스트.txt> <출력.SBX>

번역텍스트.txt 형식은 sbx_text/*.txt 와 동일합니다:
  [0000] 원문 또는 번역문
줄을 비워두거나(빈 문자열) 그대로 두면 원문이 유지됩니다.
_sub_ 로 시작하는 줄은 대사가 아니므로 절대 수정하지 마세요.

레이아웃을 절대 밀지 않는 방식(ESM/LIPSYNC와 동일한 원리). 번역문이
원래 자리에 들어가면 제자리로 덮어쓰고, 안 들어가면 원본 텍스트 영역
뒤(트레일러 바로 앞)에 새로 추가한 뒤 그 줄의 오프셋 표 값 하나만
그쪽을 가리키게 바꾼다.

압축(SBX) 입력이어도 **출력은 항상 비압축(SBN) 내부 구조로 만들고
파일 이름/확장자는 원본 그대로(.SBX) 유지한다.** 압축 여부는 파일
확장자가 아니라 offset 8의 baaf55cc 마커로 판별되므로(우리 코드도
게임도 마찬가지로 보임) 이렇게 해도 정상 인식된다.

이렇게 바꾼 이유(2026-08-14): 압축 SBX를 번역 후 재압축하면 - 압축을
전혀 새로 안 하는 리터럴 인코딩이든, 진짜 LZ 압축(직접 구현)이든,
짧은 매치만 쓰는 안전 모드든 - 압축 페이로드 바이트가 원본과 조금만
달라져도(디코딩 결과가 원문과 100% 동일해도!) 실제 게임에서 해당
스토리가 통째로 스킵되는 현상이 있었다. UDP(xdelta) 문제도, 디스크
이미지 볼륨 크기 문제도, 흔한 체크섬 문제도 아니었고 압축 페이로드
자체에 대한 어떤 검증이 있는 것으로 보였다. 반면 압축을 아예 안 쓰는
형태(SBN과 동일한 내부 구조)로 바꾸면 이 문제가 사라지는 것을 실제
게임에서 확인했다 - 압축 데이터 검증 경로 자체를 타지 않는 것으로
보인다.
"""
import struct, sys, re, os
from prs_decompress import DecompressPrs
from hangul_font_map import load_map, save_map, assign_tiles, encode_mixed
from translation_io import parse_translation_file

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def rebuild(src_sbx_path, translation_path, out_sbx_path, out_font_dir=None):
    with open(src_sbx_path, 'rb') as f:
        raw = f.read()

    sig = raw[:4]
    assert sig == b'ASCR', f"ASCR 헤더가 아닙니다: {sig}"

    # SBN(비압축)은 offset 8에 보조 시그니처 baaf55cc가 바로 옴.
    # SBX(압축)은 offset 8이 uncomp_size 값이라 이 패턴과 다름.
    is_compressed = raw[8:12] != b'\xba\xaf\x55\xcc'
    if is_compressed:
        comp_padded, uncomp_size, comp_actual = struct.unpack_from('<III', raw, 4)
        payload = raw[16:16+comp_actual]
        dec = DecompressPrs(payload).decompress()
        ascr = bytearray(b'ASCR' + struct.pack('<I', len(dec)) + dec)
    else:
        ascr = bytearray(raw)

    text_table_ptr, num_lines, subr_ptr, num_subr = struct.unpack_from('<IIII', ascr, 0xc)
    table_off = text_table_ptr + 8
    entries = list(struct.unpack_from('<%dI' % num_lines, ascr, table_off))

    # 원본 문자열들 파악 (실제 순서: [헤더][바이트코드][오프셋테이블][텍스트])
    positions = []
    orig_raw = []
    for e in entries:
        pos = e + table_off
        end = ascr.index(b'\x00', pos)
        positions.append(pos)
        orig_raw.append(bytes(ascr[pos:end]))

    # 원문 텍스트 뒤에 남는 부분(정렬용 패딩 '@', EOFC 마커 등 - 파일마다
    # 있을 수도 없을 수도 있어 내용을 해석하지 않고) 전부를 트레일러로
    # 통째로 떼어 보존한다 (내용 그대로, 위치만 뒤로 옮김).
    trailer_start = max(p + len(orig_raw[i]) + 1 for i, p in enumerate(positions))
    trailer = bytes(ascr[trailer_start:])

    translations = parse_translation_file(translation_path)

    hangul_map = load_map()
    for text in translations.values():
        if text:
            assign_tiles(text, hangul_map)
    save_map(hangul_map)

    out = bytearray(ascr[:trailer_start])  # 헤더+바이트코드+표+원문 텍스트, 위치 그대로
    appended = bytearray()
    translated_indices = set()

    for i in range(num_lines):
        text = translations.get(i)
        if text is None or text == '':
            continue
        orig_decoded = orig_raw[i].decode('shift_jis', errors='replace')
        if text == orig_decoded:
            continue
        try:
            encoded = encode_mixed(text, hangul_map)
        except UnicodeEncodeError as e:
            raise SystemExit(
                f"[{i:04d}]번 줄 인코딩 실패: {e}\n"
                f"  텍스트: {text!r}\n"
                f"  한글(Shift-JIS 미지원)이 포함된 것으로 보입니다.\n"
                f"  현재는 폰트 매핑 미해결로 한글을 넣을 수 없습니다. 영어/일본어만 가능합니다."
            )
        translated_indices.add(i)
        pos = positions[i]
        blen = len(orig_raw[i])
        if len(encoded) <= blen:
            out[pos:pos+len(encoded)] = encoded
            out[pos+len(encoded):pos+blen] = b'\x00' * (blen - len(encoded))
        else:
            new_pos = trailer_start + len(appended)
            appended += encoded
            appended.append(0)
            struct.pack_into('<I', out, table_off + i*4, new_pos - table_off)

    new_ascr = out + appended + trailer

    # 압축 여부 상관없이 항상 비압축(SBN) 형식으로 출력한다.
    # 실측한 진짜 SBN 파일들 기준 size 필드 = 전체 파일 크기 - 16.
    new_size_field = len(new_ascr) - 16
    struct.pack_into('<I', new_ascr, 4, new_size_field)

    out_bytes = bytes(new_ascr)

    with open(out_sbx_path, 'wb') as f:
        f.write(out_bytes)

    if out_font_dir and hangul_map:
        from hangul_font_map import patch_skfont
        patch_skfont(SCRIPT_DIR, out_font_dir, hangul_map)

    return {
        'num_lines': num_lines,
        'translated_count': len(translated_indices),
        'orig_size': len(raw),
        'new_size': len(out_bytes),
        'hangul_count': len(hangul_map),
    }

if __name__ == '__main__':
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    out_font_dir = sys.argv[4] if len(sys.argv) > 4 else 'patched_fonts'
    stats = rebuild(sys.argv[1], sys.argv[2], sys.argv[3], out_font_dir)
    print(f"완료: {stats['translated_count']}/{stats['num_lines']}줄 번역 적용")
    print(f"원본 크기: {stats['orig_size']} -> 새 크기: {stats['new_size']}")
    print(f"한글 {stats['hangul_count']}자 -> {out_font_dir}/ 폴더에 SKFONT.CG~4.CG 생성됨")
