"""파일별 문안을 공유 권위본과 적용 위치로 분리한다. 렌더링 문안은 바꾸지 않는다."""
import hashlib
import json
import re
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from dialogue import Catalogue, SCHEMA, digest, read_jsonl


def normal_source(source):
    # 해석이 확인된 글리프 표기와 파일별 개행·공백만 통일한다.
    # 발음·어미·문장부호의 유사도에 따른 의미 추정 병합은 하지 않는다.
    key = re.sub(r'\s+', '', source.replace('//', '').replace('⊇', '曰').replace('∈', '！'))
    if key == '古人曰く、「急いてはことをしそんじる」':
        key = '古人曰く、「急いては事を仕損じる」'
    return key


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def jsonl(rows):
    return ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows)


def breaks(text):
    result, used = [], 0
    for part in text.split('//')[:-1]:
        used += len(part)
        result.append(used)
    return result


def main():
    index_path = ROOT / 'assets/translation/index.json'
    index = json.loads(index_path.read_text(encoding='utf-8'))
    if index.get('schema') == SCHEMA:
        raise SystemExit('이미 공유 문안으로 이관했습니다. 재이관하지 않습니다.')
    all_rows, segment_rows, groups = [], {}, defaultdict(list)
    for seg in index['segments']:
        rows = read_jsonl(ROOT / seg['path'])
        segment_rows[seg['path']] = rows
        for row in rows:
            if row.get('unit'):
                raise ValueError('일부만 이관된 입력')
            row['_segment'] = seg['path']
            all_rows.append(row)
            key = normal_source(row['source']) if row.get('source') else 'unknown:' + row['id']
            groups[key].append(row)
    units, linked, conflicts = [], {}, []
    before_text = {r['id']: r['text'] for r in all_rows}
    for source_key, rows in groups.items():
        key = 'dialogue:' + digest(source_key)[:16]
        first = rows[0]
        unit = {'id': key, 'source': first.get('source') or '', 'text': first['text'],
                'review': first.get('review', '교차 검토 필요'), 'occurrences': []}
        forms = {first['text']: 'default'}
        variants = {}
        for row in rows:
            text = row['text']
            if text not in forms:
                name = f'v{len(variants) + 1:03d}'
                forms[text] = name
                form = {'review': row.get('review', '교차 검토 필요'),
                        'base_text_sha256': digest(first['text'])}
                points = breaks(text)
                if text.replace('//', '') == first['text'].replace('//', '') and points == sorted(set(points)) and all(0 < p < len(text.replace('//', '')) for p in points):
                    form['breaks'] = points
                    form['reason'] = '기존 사용처의 줄바꿈만 보존. 대표 문안 수정 시 배치 재검토 필요.'
                else:
                    form['text'] = text
                    form['reason'] = '기존 번역 차이를 보존하여 이관. 화자·문맥·용량에 따른 차이인지 추가 검토 필요.'
                variants[name] = form
            form_name = forms[text]
            occurrence = {'id': row['id']}
            if form_name != 'default':
                occurrence['form'] = form_name
            unit['occurrences'].append(occurrence)
            metadata = {k: v for k, v in row.items() if k not in ['text', 'review', '_segment']}
            metadata['unit'] = key
            if 'review' in row:
                metadata['prior_review'] = row['review']
            if form_name != 'default':
                metadata['form'] = form_name
            linked[row['id']] = metadata
        if variants:
            unit['variants'] = variants
            conflicts.append({'unit': key, 'source': unit['source'],
                              'semantic_variants': sum('text' in v for v in variants.values()),
                              'layout_variants': sum('breaks' in v for v in variants.values()),
                              'occurrences': unit['occurrences']})
        unit['_path'] = first['_segment'].replace('/segments/', '/units/')
        units.append(unit)
    # 본편의 속담과 그 속담을 묻는 퀴즈는 번역 구절 하나를 참조한다.
    phrase = {'id': 'phrase:kayama-haste', 'source': '急いては事を仕損じる',
              'text': '급할수록 돌아가라', 'review': '교차 검토 필요', 'occurrences': [],
              '_path': 'assets/translation/units/phrases.jsonl'}
    for row_id in ['ADVDATA/LIPSYNC2.LIP#1993', 'ADVDATA/SCRIPT/S0210.SBX#0181', 'ADVDATA/SCRIPT/S0510.SBX#1381']:
        unit = next(u for u in units if u['id'] == linked[row_id]['unit'])
        if 'text' in unit:
            prefix, suffix = unit.pop('text').split(phrase['text'])
            unit['parts'] = [prefix, {'ref': phrase['id']}, suffix]
    units.append(phrase)
    # 저장 전에 모든 출현의 문안이 한 글자도 변하지 않았는지 확인한다.
    catalogue = Catalogue([{k: v for k, v in u.items() if k != '_path'} for u in units])
    resolved = catalogue.resolve(linked.values())
    assert {k: v['text'] for k, v in resolved.items()} == before_text
    bindings = json.loads((ROOT / 'config/text-bindings.json').read_text(encoding='utf-8'))
    for oid, row in linked.items():
        for field, value in bindings[oid].items():
            assert row[field] == value, (oid, field)
    snapshot = ROOT / 'work/issues/shared-dialogue/before-migration.zip'
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(snapshot, 'x', zipfile.ZIP_DEFLATED) as z:
        z.write(index_path, 'assets/translation/index.json')
        for path in segment_rows:
            z.write(ROOT / path, path)
    before_dcp = (ROOT / 'out/sakura_wars_4_kr_dev.dcp').read_bytes()
    unit_segments = defaultdict(list)
    for unit in units:
        path = unit.pop('_path')
        unit_segments[path].append(unit)
    index['schema'] = SCHEMA
    index['units'] = []
    for path, contents in sorted(unit_segments.items()):
        target = ROOT / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(jsonl(contents), encoding='utf-8')
        index['units'].append({'path': path, 'rows': len(contents)})
    # 문안의 소유 위치만 옮긴다. 원본의 보호 메타데이터는 유지한다.
    for seg in index['segments']:
        rows = [linked[r['id']] for r in segment_rows[seg['path']]]
        path = ROOT / seg['path']
        path.write_text(jsonl(rows), encoding='utf-8')
        seg['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    index['release_approved'] = False
    dump(index_path, index)
    report = {'schema': SCHEMA, 'occurrences': len(all_rows), 'units': len(units),
              'shared_units': sum(len(u['occurrences']) > 1 for u in units),
              'shared_occurrences': sum(len(u['occurrences']) for u in units if len(u['occurrences']) > 1),
              'units_with_variants': len(conflicts),
              'semantic_variant_units': sum(c['semantic_variants'] > 0 for c in conflicts),
              'layout_only_variant_units': sum(c['semantic_variants'] == 0 for c in conflicts),
              'changed_rendered_rows': 0, 'before_dcp_sha256': hashlib.sha256(before_dcp).hexdigest(),
              'before_text_sha256': digest(json.dumps(before_text, ensure_ascii=False, sort_keys=True)),
              'phrase': phrase['id'], 'runtime_verified': False}
    dump(ROOT / 'research/shared-dialogue-migration.json', report)
    dump(ROOT / 'research/dialogue-variant-review.json', conflicts)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
