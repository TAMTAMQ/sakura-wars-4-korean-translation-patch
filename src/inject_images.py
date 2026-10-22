"""재제작 PNG를 게임 텍스처(BPV1/ADCG)로 되돌려 assets/images/native/에 쓴다.

입력
  - originals/v05/<컨테이너>: 기준선. 매번 여기서 다시 만들므로 여러 번 실행해도 결과가 같다.
  - assets/images/remake/{slg,staffroll,ui,logo}/index.json: 재제작 PNG(뒤 단계가 앞 단계를 덮는다)
  - assets/images/review/image_review.json: 같은 그림을 쓰는 사본(members) 목록

규칙(v0.5가 쓴 방식과 같다)
  - 파일 크기와 모든 블록 위치는 바꾸지 않는다. 블록 안 바이트만 고친다.
  - 압축 블록은 PRS로 다시 압축해 원래 자리(다음 태그 앞까지)에 넣는다. 넘치면 실패한다.
    CG_ALL1.DAT 레코드는 원본처럼 페이로드 뒤에 CPRS/EOFC 꼬리를 붙이고 크기 필드 = 길이 + 8.
  - 비압축 블록은 픽셀 자리만 덮어쓴다.
  - VQ 텍스처는 2×2 블록 k-평균으로 코드북을 새로 만든다(손실 있음).
  - 쓴 뒤 다시 디코딩해서 PNG와 비교한다. VQ 외에는 픽셀이 정확히 같아야 한다.

출력: assets/images/native/<컨테이너>, assets/images/remake/inject_report.json
"""
import argparse
import json
import struct
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import export_images as E  # noqa: E402
from prs_compress import compress_optimal as compress  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'originals/v05'
DISC = ROOT / 'originals/disc'  # v0.5가 손대지 않은 파일(config/disc-baseline.json)은 원본 디스크가 기준선
NATIVE = ROOT / 'assets/images/native'
STAGES = ['slg', 'staffroll', 'ui', 'logo', 'individual']
ALLOW_MOVE = '--allow-move' in sys.argv  # 기본: 레코드를 옮기지 않는다(파일 크기·위치 그대로)


# ---------------------------------------------------------------- 픽셀 인코딩
def _lut(bits):
    levels = np.array([k * 255 // ((1 << bits) - 1) for k in range(1 << bits)])
    return np.abs(np.arange(256)[:, None] - levels[None, :]).argmin(1).astype(np.uint32)


L4, L5, L6 = (np.arange(256) * 15 + 127) // 255, _lut(5), _lut(6)


def encode_rgba(a, pf):
    a = a.astype(np.int64)
    r, g, b, al = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    if pf == 2:
        q = lambda c: np.round(c / 17).astype(np.uint32)
        return ((q(al) << 12) | (q(r) << 8) | (q(g) << 4) | q(b)).astype(np.uint16)
    if pf == 1:
        return ((L5[r] << 11) | (L6[g] << 5) | L5[b]).astype(np.uint16)
    if pf == 0:
        return (((al >= 128).astype(np.uint32) << 15) | (L5[r] << 10) | (L5[g] << 5) | L5[b]).astype(np.uint16)
    raise ValueError('미지원 픽셀 포맷 %d' % pf)


def decode_rgba(v, pf):
    return np.asarray(E.rgba(v.astype(np.uint32), pf), float)


def nearest(x, centers, chunk=8192):
    lab = np.empty(len(x), np.int64)
    cn = (centers ** 2).sum(1)
    for i in range(0, len(x), chunk):
        xs = x[i:i + chunk]
        lab[i:i + chunk] = (cn[None] - 2 * xs @ centers.T).argmin(1)
    return lab


def kmeans(x, init, iters=12):
    """기존 코드북(init)에서 시작하는 k-평균. 바뀐 글자 부분만 새 색으로 옮겨 가게 된다."""
    centers = init.astype(float).copy()
    for _ in range(iters):
        lab = nearest(x, centers)
        cnt = np.bincount(lab, minlength=len(centers))
        sums = np.zeros_like(centers)
        np.add.at(sums, lab, x)
        used = cnt > 0
        centers[used] = sums[used] / cnt[used, None]
        # 빈 항목은 가장 오차 큰 블록들로 다시 채운다
        empty = np.where(~used)[0]
        if len(empty):
            err = ((x - centers[lab]) ** 2).sum(1)
            centers[empty] = x[np.argsort(err)[::-1][:len(empty)]]
    return centers, nearest(x, centers)


def encode_texture(img, payload, w, h, pf, layout):
    """img(RGBA h×w)를 payload(기존 바이트)와 같은 길이로 인코딩한 bytes를 돌려준다."""
    out = bytearray(payload)
    if layout in (3, 4, 16, 17):
        entries = 256 if layout in (3, 4) else (16 if w <= 16 else 32 if w <= 32 else 128 if w <= 64 else 256)
        vec = np.zeros((h // 2, w // 2, 4, 4))
        for y in range(2):
            for x in range(2):
                vec[:, :, x * 2 + y] = img[y::2, x::2]
        flat = vec.reshape(-1, 16)
        old_cb = np.frombuffer(bytes(payload[:entries * 8]), dtype='<u2').reshape(entries, 4)
        init = decode_rgba(old_cb, pf).reshape(entries, 16)
        centers, lab = kmeans(flat, init)
        cb = encode_rgba(np.clip(np.round(centers.reshape(entries, 4, 4)), 0, 255), pf)
        out[:entries * 8] = cb.astype('<u2').tobytes()
        codes = np.zeros((h // 2) * (w // 2), np.uint8)
        idx = E.morton(w // 2, h // 2)
        codes[idx.reshape(-1)] = lab.astype(np.uint8)
        start = len(out) - w * h // 4 if layout in (4, 17) else entries * 8
        out[start:start + len(codes)] = codes.tobytes()
        return bytes(out)
    vals = encode_rgba(img, pf)
    if layout in (1, 2, 13, 18):
        pix = np.zeros(w * h, np.uint16)
        pix[E.morton(w, h).reshape(-1)] = vals.reshape(-1)
    else:
        pix = vals.reshape(-1)
    data = pix.astype('<u2').tobytes()
    start = (len(out) // 2 * 2 - w * h * 2) if layout in (2, 18) else 0
    out[start:start + len(data)] = data
    return bytes(out)


# ---------------------------------------------------------------- 블록 재구성
def rebuild_bpv(dec, images):
    """images: {텍스처 번호: RGBA}. BPV1 압축 해제 바이트를 고쳐 돌려준다."""
    dec = bytearray(dec)
    count = E.u32(dec, 4)
    descs = [E.u32(dec, 8 + i * 12) for i in range(count)]
    starts = sorted(set(struct.unpack_from('<I', dec, d)[0] for d in descs)) + [len(dec)]
    for ti, img in images.items():
        d = descs[ti]
        data_off, mode = struct.unpack_from('<II', dec, d)
        w, h = struct.unpack_from('<II', dec, d + 16)
        pf, layout = (mode >> 16) & 255, mode >> 24
        end = next(s for s in starts if s > data_off)
        if img.shape[:2] != (h, w):
            raise ValueError('크기 불일치 %s' % ((h, w),))
        dec[data_off:end] = encode_texture(img, dec[data_off:end], w, h, pf, layout)
    return bytes(dec)


def rebuild_adcg(dec, img, expansion=None):
    dec = bytearray(dec)
    count = E.u32(dec, 4)
    tw, th = struct.unpack_from('<HH', dec, 8)
    table = E.u32(dec, 12)
    pf = dec[16]
    fw, fh = struct.unpack_from('<HH', dec, 20)
    if img.shape[:2] != (fh, fw):
        raise ValueError('ADCG 크기 불일치')
    size = tw * th * 2
    entries = []
    for i in range(count):
        e = table + i * 16
        tileid, ptr, xy, flags = struct.unpack_from('<IIII', dec, e)
        entries.append((e, e + ptr, xy & 65535, xy >> 16))
    data_start = min(s for _, s, _, _ in entries)
    old_unique = len({s for _, s, _, _ in entries})
    if expansion is not None:
        if len(dec) != expansion['original_decoded_size']:
            raise ValueError('ADCG 확장 기준선 크기 불일치')
        if data_start != table + count * 16 or len(dec) != data_start + old_unique * size:
            raise ValueError('ADCG 확장 대상의 표·픽셀 풀 경계 불일치')
        existing = {(x, y) for _, _, x, y in entries}
        extra = [tuple(xy) for xy in expansion['additional_tiles']]
        if existing.intersection(extra) or len(set(extra)) != len(extra):
            raise ValueError('ADCG 확장 타일 중복')
        rows = []
        next_id = max(E.u32(dec, e) for e, _, _, _ in entries) + 1
        for e, start, x, y in entries:
            old = np.asarray(E.texture(bytes(dec[start:start + size]), tw, th, pf, 1).convert('RGBA')).copy()
            rows.append((E.u32(dec, e), x, y, E.u32(dec, e + 12), old))
        # 추가 타일도 기존 타일과 같은 플래그(0x80000000)를 써야 한다. 0이면 실기에서 투명 부분이 검은 상자로 그려졌다.
        flags = {row[3] for row in rows}
        if len(flags) != 1:
            raise ValueError('ADCG 확장 대상의 타일 플래그가 섞여 있음')
        for i, (x, y) in enumerate(extra):
            if x % tw or y % th or not (0 <= x < fw and 0 <= y < fh):
                raise ValueError('ADCG 확장 타일 좌표 오류')
            rows.append((next_id + i, x, y, rows[0][3], np.zeros((th, tw, 4), np.uint8)))
        tiles = []
        for _, x, y, _, tile in rows:
            vw, vh = min(tw, fw - x), min(th, fh - y)
            tile[:vh, :vw] = img[y:y + vh, x:x + vw]
            tiles.append(encode_texture(tile, bytes(size), tw, th, pf, 1))
        unique = {tile: i for i, tile in enumerate(dict.fromkeys(tiles))}
        start = table + len(rows) * 16
        output = bytearray(dec[:table])
        struct.pack_into('<I', output, 4, len(rows))
        for i, ((tile_id, x, y, flags, _), tile) in enumerate(zip(rows, tiles)):
            entry = table + i * 16
            output += struct.pack('<IIII', tile_id, start + unique[tile] * size - entry, x | (y << 16), flags)
        output += b''.join(unique)
        return bytes(output)
    tiles = []
    for e, s, x, y in entries:
        old = np.asarray(E.texture(bytes(dec[s:s + size]), tw, th, pf, 1).convert('RGBA')).copy()
        vw, vh = min(tw, fw - x), min(th, fh - y)
        old[:vh, :vw] = img[y:y + vh, x:x + vw]  # 캔버스 밖 부분은 원래 타일 값을 둔다
        tiles.append(encode_texture(old, bytes(size), tw, th, pf, 1))
    uniq = {}
    for t in tiles:
        uniq.setdefault(t, len(uniq))
    if len(uniq) > old_unique:
        raise ValueError(f'ADCG 고유 타일 {len(uniq)}개 > 원래 {old_unique}개(압축 해제 크기를 늘려야 함)')
    for t, k in uniq.items():
        p = data_start + k * size
        dec[p:p + size] = t
    for (e, _, _, _), t in zip(entries, tiles):
        struct.pack_into('<I', dec, e + 4, data_start + uniq[t] * size - e)
    return bytes(dec)


# ---------------------------------------------------------------- 대상 수집
def targets():
    """{(source, block): {texture: png 경로}}"""
    rows = json.loads((ROOT / 'assets/images/review/image_review.json').read_text(encoding='utf-8'))
    members = {(r['source'], r['block'], r['texture']): r['members'] for r in rows}
    final = {}
    for stage in STAGES:
        idx = ROOT / 'assets/images/remake' / stage / 'index.json'
        if idx.exists():
            for r in json.loads(idx.read_text(encoding='utf-8')):
                final[(r['source'], r['block'], r['texture'])] = r['remake']
    out = defaultdict(dict)
    for key, png in final.items():
        for m in members.get(key, [f'{key[0]} b{key[1]} t{key[2]}']):
            src, b, t = m.rsplit(' ', 2)
            out[(src, int(b[1:]))][int(t[1:])] = png
    return out


def write_block(raw, spec, specs_index, new_dec, rel):
    sig, off, packed, compressed, expected = spec
    raw = bytearray(raw)
    size, a, b = struct.unpack_from('<III', raw, off + 4)
    if not compressed:
        if len(new_dec) != size:
            raise ValueError('비압축 블록 크기 변경')
        raw[off + 8:off + 8 + size] = new_dec
        return raw, {'compressed': False}
    payload = compress(new_dec)
    if E.decompress(payload, len(new_dec)) != new_dec:
        raise ValueError('PRS 왕복 검증 실패')
    nxt = specs_index[1] if specs_index else len(raw)
    tail = bytes(raw[off + 16 + b:nxt])
    if rel.endswith('CG_ALL1.DAT'):
        # 원본 레코드: 페이로드(4정렬) + 'CPRS'00000000 + 'EOFC'00000000, 그 뒤 0 채움, 다음 AGR1
        agr = tail.find(b'AGR1')
        limit = off + 16 + b + (agr if agr >= 0 else len(tail))
        body = payload + b'\0' * (-len(payload) % 4)
        trailer = b'CPRS\0\0\0\0EOFC\0\0\0\0'
        if off + 16 + len(body) + len(trailer) > limit:
            # 원래 자리(다음 2048 경계 레코드 전)에 안 들어가면 파일 끝으로 옮긴다. GR.IDX는 main에서 고친다.
            record = bytes(raw[off - 8:off]) + b'ADCG' + struct.pack('<III', len(body) + 8, len(new_dec), len(payload)) + body + trailer
            return raw, {'compressed': True, 'payload': len(payload), 'slot': limit - off - 32, 'old': b,
                         'relocate': record}
        raw[off + 16:limit] = body + trailer + b'\0' * (limit - off - 16 - len(body) - len(trailer))
        struct.pack_into('<II', raw, off + 4, len(body) + 8, len(new_dec))
        struct.pack_into('<I', raw, off + 12, len(payload))
        return raw, {'compressed': True, 'payload': len(payload), 'slot': limit - off - 16 - 16, 'old': b}
    first = next((i for i, v in enumerate(tail) if v), len(tail))
    limit = off + 16 + b + first
    if off + 16 + len(payload) > limit:
        raise ValueError(f'자리 부족: {len(payload)} > {limit - off - 16}')
    raw[off + 16:limit] = payload + b'\0' * (limit - off - 16 - len(payload))
    struct.pack_into('<I', raw, off + 12, len(payload))
    return raw, {'compressed': True, 'payload': len(payload), 'slot': limit - off - 16, 'old': b}


def relocate(new, specs, rows, rel):
    """CG_ALL1.DAT에서 자리가 모자란 레코드를 파일 끝(2048 정렬)에 붙이고 GR.IDX의 섹터·길이를 고친다.
    GR.IDX: 0x128부터 16바이트 항목(섹터, 길이, 번호, 0). 길이 = ADCG 크기 필드 + 32."""
    if not rel.endswith('CG_ALL1.DAT'):
        raise ValueError('파일 끝 이동은 CG_ALL1.DAT만 지원')
    gpath = 'ADVDATA/GR.IDX'
    gr = bytearray((BASE / gpath).read_bytes())
    entries = {}
    for p in range(296, len(gr) - 15, 16):
        entries.setdefault(struct.unpack_from('<I', gr, p)[0], []).append(p)
    new = bytearray(new)
    for r in rows:
        if 'relocate' not in r:
            # 제자리에 넣은 레코드도 읽는 길이(항목 길이)가 새 크기 + 32 이상이어야 한다
            off = specs[r['block']][1]
            need = struct.unpack_from('<I', new, off + 4)[0] + 32
            for p in entries.get((off - 8) // 2048, []):
                if struct.unpack_from('<I', gr, p + 4)[0] < need:
                    struct.pack_into('<I', gr, p + 4, need)
                    r.setdefault('gr_idx_entries', []).append(p)
            continue
        rec = r.pop('relocate')
        if not ALLOW_MOVE:
            raise ValueError(f'블록 {r["block"]}: 압축해도 원래 자리보다 큼({r["payload"]} > {r["slot"]}). '
                             '이미지를 단순화하거나 --allow-move로 파일 끝 이동을 허용하세요')
        off = specs[r['block']][1]
        start = off - 8
        if start % 2048:
            raise ValueError(f'블록 {r["block"]} 레코드가 2048 정렬이 아님')
        old_size = struct.unpack_from('<I', BASE.joinpath(rel).read_bytes(), off + 4)[0]
        ps = entries.get(start // 2048, [])
        if not ps:
            raise ValueError(f'블록 {r["block"]}의 GR.IDX 항목 없음')
        for p in ps:
            if struct.unpack_from('<I', gr, p + 4)[0] < old_size + 32:
                raise ValueError(f'블록 {r["block"]} GR.IDX 길이가 예상과 다름')
        new += b'\0' * (-len(new) % 2048)
        sector = len(new) // 2048
        new += rec
        for p in ps:
            struct.pack_into('<II', gr, p, sector, len(rec))
        r['moved_to'] = sector * 2048 + 8
        r['gr_idx_entries'] = ps
    new += b'\0' * (-len(new) % 2048)
    out = NATIVE / gpath
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(bytes(gr))
    return new


def decode_block(spec):
    sig, off, packed, compressed, expected = spec
    dec = E.decompress(packed, expected) if compressed else packed
    return dec, (E.decode_bpv(dec) if sig == 'BPV1' else E.decode_adcg(dec))


def main(source_prefix=None):
    work = targets()
    if source_prefix is not None:
        work = {key: value for key, value in work.items() if key[0].startswith(source_prefix)}
        if not work:
            raise ValueError('선택한 경로에 재삽입 대상 없음: ' + source_prefix)
    by_file = defaultdict(dict)
    expansion_path = ROOT / 'config/image-expansions.json'
    expansions = {(r['source'], r['block']): r for r in json.loads(expansion_path.read_text(encoding='utf-8'))['blocks']} if expansion_path.exists() else {}
    for (src, block), texs in work.items():
        by_file[src][block] = texs
    report = {'files': [], 'errors': []}
    report_path = ROOT / 'assets/images/remake/inject_report.json'
    if source_prefix is not None and report_path.exists():
        previous = json.loads(report_path.read_text(encoding='utf-8'))
        report = {key: [r for r in previous.get(key, []) if r['source'] not in by_file]
                  for key in ('files', 'errors')}
    for rel, blocks in sorted(by_file.items()):
        raw = (BASE / rel if (BASE / rel).exists() else DISC / rel).read_bytes()
        specs = E.block_specs(raw)
        if rel.endswith('CG_ALL1.DAT') and (NATIVE / 'ADVDATA/GR.IDX').exists():
            (NATIVE / 'ADVDATA/GR.IDX').write_bytes((BASE / 'ADVDATA/GR.IDX').read_bytes())
        new = bytearray(raw)
        rows = []
        try:
            for bi, texs in sorted(blocks.items()):
                spec = specs[bi]
                dec, decoded = decode_block(spec)
                imgs = {t: np.asarray(Image.open(ROOT / p).convert('RGBA')) for t, p in texs.items()}
                if spec[0] == 'BPV1':
                    new_dec = rebuild_bpv(dec, imgs)
                else:
                    new_dec = rebuild_adcg(dec, imgs[0], expansions.get((rel, bi)))
                if len(new_dec) != len(dec) and (rel, bi) not in expansions:
                    raise ValueError('미등록 압축 해제 크기 변경')
                nxt = specs[bi + 1] if bi + 1 < len(specs) else None
                new, info = write_block(new, spec, nxt, new_dec, rel)
                rows.append({'block': bi, 'textures': sorted(texs), **info})
            moved = {}
            if rel.endswith('CG_ALL1.DAT'):
                new = relocate(new, specs, rows, rel)
                moved = {r['block']: r['moved_to'] for r in rows if 'moved_to' in r}
            # 검증: 기존 블록 위치 동일(옮긴 레코드는 파일 끝에 추가), 대상 텍스처는 PNG와 일치, 나머지는 그대로
            if len(new) != len(raw) and not moved:
                raise ValueError('파일 크기 변경')
            nspecs = E.block_specs(bytes(new))
            if [s[1] for s in nspecs[:len(specs)]] != [s[1] for s in specs]:
                raise ValueError('블록 위치 변경')
            if len(nspecs) != len(specs) + len(moved):
                raise ValueError('옮긴 블록 수 불일치')
            by_off = {s[1]: s for s in nspecs}
            for bi, spec in enumerate(nspecs[:len(specs)]):
                if bi not in blocks:
                    if spec[2] != specs[bi][2]:
                        raise ValueError(f'대상 아닌 블록 {bi} 변경')
                    continue
                if bi in moved:
                    spec = by_off[moved[bi]]
                _, decoded = decode_block(spec)
                for t, p in blocks[bi].items():
                    got = np.asarray(decoded[t][1].convert('RGBA')).astype(int)
                    want = np.asarray(Image.open(ROOT / p).convert('RGBA')).astype(int)
                    dec_old, _ = decode_block(specs[bi])
                    diff = np.abs(got - want)
                    if spec[0] == 'BPV1':
                        mode = struct.unpack_from('<I', dec_old, E.u32(dec_old, 8 + t * 12) + 4)[0]
                        vq = (mode >> 24) in (3, 4, 16, 17)
                    else:
                        vq = False
                    # 4444/565/1555 단계로 양자화된 PNG는 반올림 1단계 차이까지만 허용.
                    # VQ는 손실 압축이라 평균 차이로 판정한다.
                    if vq:
                        if diff.mean() > 6:
                            raise ValueError(f'블록 {bi} 텍스처 {t} VQ 평균 차이 {diff.mean():.1f}')
                    elif diff.max() > 18:
                        raise ValueError(f'블록 {bi} 텍스처 {t} 재디코딩 차이 {diff.max()}')
                    for r in rows:
                        if r['block'] == bi:
                            r.setdefault('max_diff', {})[t] = int(diff.max())
                            r.setdefault('mean_diff', {})[t] = round(float(diff.mean()), 2)
            out = NATIVE / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(bytes(new))
            report['files'].append({'source': rel, 'blocks': rows})
            print('OK', rel, len(rows), '블록')
        except Exception as exc:
            report['errors'].append({'source': rel, 'error': str(exc)})
            print('실패', rel, exc)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
    print('완료', len(report['files']), '파일, 실패', len(report['errors']))
    return 1 if report['errors'] else 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-prefix', help='선택한 게임 경로만 기준선에서 재삽입한다. 나머지 파일과 검증 기록은 보존한다.')
    sys.exit(main(parser.parse_args().source_prefix))
