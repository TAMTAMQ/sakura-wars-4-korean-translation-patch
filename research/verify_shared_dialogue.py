"""이관 전 문안 전체·DCP 동일성과 참조에 따른 전 사용처 반영을 검증한다."""
import copy
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from dialogue import Catalogue, digest, load


def main():
    migration = json.loads((ROOT / 'research/shared-dialogue-migration.json').read_text(encoding='utf-8'))
    catalogue, rows, hashes = load(ROOT)
    with zipfile.ZipFile(ROOT / 'work/issues/shared-dialogue/before-migration.zip') as z:
        old_index = json.loads(z.read('assets/translation/index.json'))
        old_rows = {}
        for seg in old_index['segments']:
            for line in z.read(seg['path']).decode('utf-8').splitlines():
                old = json.loads(line)
                row = rows[old['id']]
                assert row['text'] == old['text'], old['id']
                for key, value in old.items():
                    assert row.get('prior_review' if key == 'review' else key) == value, (old['id'], key)
                old_rows[old['id']] = old['text']
    assert set(rows) == set(old_rows)
    assert digest(json.dumps(old_rows, ensure_ascii=False, sort_keys=True)) == migration['before_text_sha256']
    dcp = ROOT / 'out/sakura_wars_4_kr_dev.dcp'
    current_sha = hashlib.sha256(dcp.read_bytes()).hexdigest()
    assert current_sha == migration['before_dcp_sha256'], '이관 과정에서 DCP 결과가 바뀜'
    report = json.loads((ROOT / 'out/build-report.json').read_text(encoding='utf-8'))
    assert report['sha256'] == current_sha
    for path, sha in hashes.items():
        assert report['segment_hashes'][path] == sha, path
    # 실제 전체 권위본에서 구절 하나만 메모리상 수정한다. 디스크 입력은 바꾸지 않는다.
    units = copy.deepcopy(list(catalogue.units.values()))
    phrase = next(u for u in units if u['id'] == 'phrase:kayama-haste')
    phrase['text'] = '서두르지 말고 돌아가라'
    occurrences = [{k: v for k, v in r.items() if k not in ['text', 'review']} for r in rows.values()]
    changed = Catalogue(units).resolve(occurrences)
    ids = ['ADVDATA/LIPSYNC2.LIP#1993', 'ADVDATA/SCRIPT/S0210.SBX#0181', 'ADVDATA/SCRIPT/S0510.SBX#1381']
    different = [oid for oid in rows if rows[oid]['text'] != changed[oid]['text']]
    assert set(different) == set(ids), different
    assert all(phrase['text'] in changed[oid]['text'] for oid in ids)
    result = {**migration, 'after_dcp_sha256': current_sha, 'identical_dcp': True,
              'all_occurrence_texts_identical': len(rows), 'protected_metadata_identical': True,
              'phrase_edit_propagates_to': ids, 'inputs_tracked': len(hashes)}
    (ROOT / 'research/shared-dialogue-verification.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
