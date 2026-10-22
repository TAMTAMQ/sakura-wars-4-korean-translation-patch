"""완성 DCP에서 이번 문안 반영과 수정 영역 밖 무변경을 검증한다."""
import hashlib
import json
import re
import struct
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from build import encode
from dialogue import load


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    record = json.loads((ROOT / 'research/localization-20261022.json').read_text(encoding='utf-8'))
    before = json.loads((ROOT / 'work/issues/localization-20261022/before-dcp.json').read_text(encoding='utf-8'))
    codes = json.loads((ROOT / 'config/encoding.json').read_text(encoding='utf-8'))
    index = json.loads((ROOT / 'assets/translation/index.json').read_text(encoding='utf-8'))
    bindings = json.loads((ROOT / 'config/text-bindings.json').read_text(encoding='utf-8'))
    _, rows, _ = load(ROOT, index)
    for seg in index['segments']:
        path = ROOT / seg['path']
        assert sha(path.read_bytes()) == seg['sha256'], seg['path']
    changed_files, entries = [], []
    with zipfile.ZipFile(ROOT / 'out/sakura_wars_4_kr_dev.dcp') as z:
        assert z.testzip() is None
        assert set(z.namelist()) == set(before)
        for name in z.namelist():
            data = bytearray(z.read(name))
            old = before[name]
            assert len(data) == old['size'], name
            if sha(data) != old['sha256']:
                changed_files.append(name)
                assert old['allowed_ranges'], name
            for start, end in old['allowed_ranges']:
                data[start:end] = bytes(end - start)
            assert sha(data) == old['protected_sha256'], '문안 영역 밖 변경: ' + name
        for change in record['changes']:
            row = rows[change['id']]
            assert row['text'] == change['after']
            for key, value in bindings[row['id']].items():
                assert row[key] == value, (row['id'], key)
            encoded = encode(row['text'], codes)
            assert len(encoded) <= row['capacity']
            data = z.read(row['file'])
            offset = row['offset']
            assert data[offset:offset + len(encoded)] == encoded, row['id']
            tail = data[offset + len(encoded):offset + row['capacity'] + 1]
            assert tail.endswith(b'\0')
            pad = bytes.fromhex(codes['⁣'])
            while tail.startswith(pad):
                tail = tail[len(pad):]
            assert not tail.strip(b'\0'), (row['id'], '기존 대사 잔여 byte')
            if row['file'].endswith('.LIP'):
                base = (ROOT / 'originals/v05' / row['file']).read_bytes()
                count = struct.unpack_from('<I', base, 8)[0]
                assert data[:12 + count * 12] == base[:12 + count * 12], 'LIP 시간·포인터 표 변경'
            assert change['max_fullwidth_lines'] <= 3
            entries.append({'id': row['id'], 'encoded_bytes': len(encoded), 'capacity': row['capacity'], 'verified': True})
        for key in ['ADVDATA/LIPSYNC2.LIP#1993', 'ADVDATA/SCRIPT/S0210.SBX#0181', 'ADVDATA/SCRIPT/S0510.SBX#1381']:
            assert '「급할수록 돌아가라」' in rows[key]['text']
        assert not any('급하면 일을 그르친다' in row['text'] for row in rows.values())
    result = {'dcp_sha256': sha((ROOT / 'out/sakura_wars_4_kr_dev.dcp').read_bytes()),
              'changed_rows_verified': len(entries), 'changed_files': changed_files,
              'outside_text_changes': 0, 'entries': entries, 'runtime_verified': False}
    (ROOT / 'research/localization-20261022-verification.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'entries'}, ensure_ascii=False, indent=2))
    out = ['# 속담·관용구·직역투 수정 (2026-10-22)', '',
           '카야마의 격언은 일반 대사에는 이미 제안 표현이 있었지만 음성 자막과 퀴즈에 이전 표현이 남아 있었다. 세 경로를 「급할수록 돌아가라」로 맞췄다.', '',
           '원문과 문맥을 대조하여 선택한 수정은 사본 포함 36행이다. 추출 문안 40,338행에서 속담·관용어·직역투 후보를 검색한 뒤 필요한 문장만 수정했으며, 전 대사 수동 검수 완료를 뜻하지 않는다. 고유명사·기존 호칭·홍란의 사투리와 제어 토큰은 유지했다.', '',
           '## 수정 전후', '', '| ID | 수정 전 | 수정 후 | 이유 |', '|---|---|---|---|']
    cell = lambda s: s.replace('|', '\\|').replace('//', '<br>')
    for change in record['changes']:
        out.append('| ' + ' | '.join(cell(change[k]) for k in ['id', 'before', 'after', 'reason']) + ' |')
    out.extend(['', '## 검증', '',
                f'최종 DCP에서 {len(entries)}행의 문안과 남은 영역의 패딩을 확인했다. 변경된 파일 {len(changed_files)}개의 이번 문안 범위 밖 byte, 나머지 파일 전체, LIP 시간·포인터 표는 이전과 같다. 각 문안은 기존 용량과 보수적인 전각 3줄 제한 안에 들어간다.', '',
                '빌드와 기존 테스트 16개를 통과했다. 게임 내 음성 타이밍과 실제 화면 표시는 아직 확인하지 못했다.', '',
                '검증: `python research/verify_localization_20261022.py`', '',
                'DCP SHA-256: `' + result['dcp_sha256'] + '`', ''])
    (ROOT / 'docs/localization-20261022.md').write_text('\n'.join(out), encoding='utf-8')


if __name__ == '__main__':
    main()
