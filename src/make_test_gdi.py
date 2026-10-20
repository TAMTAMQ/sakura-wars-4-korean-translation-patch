"""DCP 내용을 원본 GDI에 직접 써서 에뮬레이터 확인용 GDI를 만든다(배포용 아님).

UDP(Universal Dreamcast Patcher)는 GUI 전용이라 자동 실행 확인에 쓰기 어렵다.
track03.bin(2352바이트 raw 섹터, LBA 45000부터)의 ISO9660 디렉터리를 읽어
DCP의 각 파일을 원래 자리에 덮어쓴다. 원래 할당 섹터보다 크면(v0.5가 SBX를
비압축으로 넣어 2~3배 커졌다) 디렉터리 뒤~첫 파일 앞의 빈 섹터(약 6000개)에 넣고
디렉터리 레코드의 위치·크기를 고친다. 트랙 크기는 바꾸지 않는다. EDC/ECC는 다시 계산하지 않는다(Flycast는 검사 안 함).

usage: python src/make_test_gdi.py <원본 gdi 폴더> <DCP> <출력 폴더>
"""
import shutil
import struct
import sys
import zipfile
from pathlib import Path

SECTOR = 2352
DATA = 16
TRACK_LBA = 45000


def main(src, dcp, out):
    src, out = Path(src), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for f in src.iterdir():
        if f.suffix.lower() in ('.gdi', '.raw', '.bin') and f.name != 'track03.bin':
            shutil.copy2(f, out / f.name)
    gdi = next(out.glob('*.gdi'))
    t3 = out / 'track03.bin'
    shutil.copyfile(src / 'track03.bin', t3)
    fh = open(t3, 'r+b')
    nsec = t3.stat().st_size // SECTOR

    def read(lba, n=1):
        res = bytearray()
        for i in range(n):
            fh.seek((lba - TRACK_LBA + i) * SECTOR + DATA)
            res += fh.read(2048)
        return bytes(res)

    def write(lba, data):
        for i in range(0, len(data), 2048):
            idx = lba - TRACK_LBA + i // 2048
            assert idx < nsec, '트랙 밖 쓰기'
            fh.seek(idx * SECTOR + DATA)
            fh.write(data[i:i + 2048].ljust(2048, b'\0'))

    pvd = read(TRACK_LBA + 16)
    assert pvd[1:6] == b'CD001'
    root = pvd[156:156 + 34]
    entries = {}

    def walk(lba, size, path):
        data = read(lba, (size + 2047) // 2048)
        pos = 0
        while pos < len(data):
            ln = data[pos]
            if ln == 0:
                pos = (pos // 2048 + 1) * 2048
                continue
            rec = data[pos:pos + ln]
            elba, esize, flags = struct.unpack_from('<I', rec, 2)[0], struct.unpack_from('<I', rec, 10)[0], rec[25]
            name = rec[33:33 + rec[32]].decode('ascii', 'replace').split(';')[0]
            if name not in ('\x00', '\x01'):
                p = f'{path}/{name}' if path else name
                if flags & 2:
                    walk(elba, esize, p)
                else:
                    entries[p.upper()] = (lba, pos, elba, esize)
            pos += ln

    walk(struct.unpack_from('<I', root, 2)[0], struct.unpack_from('<I', root, 10)[0], '')
    # 빈 공간: 디렉터리 등 마지막 비영 섹터 다음부터 첫 파일 앞까지
    first = min(e[2] for e in entries.values())
    free = TRACK_LBA + 16
    for lba in range(TRACK_LBA + 16, first):
        if any(read(lba)):
            free = lba + 1
    with zipfile.ZipFile(dcp) as z:
        names = [n for n in z.namelist() if not n.endswith('/')]
        for n in names:
            key = n.upper()
            if key not in entries:
                print('ISO에 없는 파일(건너뜀):', n)
                continue
            data = z.read(n)
            dlba, dpos, elba, esize = entries[key]
            alloc = (esize + 2047) // 2048 * 2048
            if len(data) <= alloc:
                write(elba, data)
                newlba = elba
            else:
                newlba = free
                free += (len(data) + 2047) // 2048
                if free > first:
                    raise SystemExit('빈 공간 부족: ' + n)
                write(newlba, data)
            # 디렉터리 레코드 수정(위치·크기, 양쪽 엔디언)
            sec = (dlba - TRACK_LBA) + dpos // 2048
            off = dpos % 2048
            fh.seek(sec * SECTOR + DATA + off + 2)
            fh.write(struct.pack('<I', newlba) + struct.pack('>I', newlba) + struct.pack('<I', len(data)) + struct.pack('>I', len(data)))
    fh.close()
    print('완료', gdi, '빈 공간 남음', first - free, '섹터')


if __name__ == '__main__':
    main(*sys.argv[1:4])
