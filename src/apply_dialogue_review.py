"""명시적인 검수 교정안을 저장 전 검증하고, 공유 문안 및 검수 근거를 함께 보관한다."""
import copy
import hashlib
import json
import re
import zipfile

from build import encode
from dialogue import Catalogue, ROOT, digest, load, read_jsonl


def fingerprint(catalogue, key):
    unit = catalogue.units[key]
    texts = {f: catalogue.text(key, f) for f in ['default'] + list(unit.get('variants', {}))}
    return digest(json.dumps({'source': unit['source'], 'texts': texts}, ensure_ascii=False, sort_keys=True))


def apply(label, plan, reviews, date='2026-10-22'):
    current, old_rows, hashes = load()
    evidence = ROOT / 'assets/translation/review' / label
    if evidence.exists():
        raise ValueError('이미 적용한 검수입니다: ' + label)
    units = copy.deepcopy(list(current.units.values()))
    proposed = Catalogue(units)
    changed_ids = set()
    for key, correction in plan.items():
        unit = proposed.units[key]
        if 'parts' in unit:
            raise ValueError('조합 문안은 참조 구절을 수정하세요: ' + key)
        for field in ['parts', 'breaks', 'variants']:
            unit.pop(field, None)
        unit.update(text=correction['text'], review='원문 대조 교정 · ' + date)
        for use in unit['occurrences']:
            changed_ids.add(use['id'])
            use.pop('form', None)
    index_path = ROOT / 'assets/translation/index.json'
    index = json.loads(index_path.read_text(encoding='utf-8'))
    segments = {}
    for item in index['segments']:
        records = read_jsonl(ROOT / item['path'])
        for row in records:
            if row['id'] in changed_ids:
                row.pop('form', None)
        segments[item['path']] = records
    new_rows = proposed.resolve([row for records in segments.values() for row in records])
    codes = json.loads((ROOT / 'config/encoding.json').read_text(encoding='utf-8'))
    errors = []
    for oid in sorted(changed_ids):
        row = new_rows[oid]
        try:
            size = len(encode(row['text'], codes))
            if size > row['capacity']:
                errors.append([oid, size, row['capacity'], row['text']])
        except UnicodeError as error:
            errors.append([oid, str(error), row['text']])
        control = r'@[A-Za-z]+[0-9,]*|⟦[^⟧]*⟧'
        if re.findall(control, row['text']) != re.findall(control, old_rows[oid]['text']):
            errors.append([oid, '제어 코드 변경'])
        protected = {k:v for k,v in row.items() if k not in {'form','review','text'}}
        previous = {k:v for k,v in old_rows[oid].items() if k not in {'form','review','text'}}
        if protected != previous:
            errors.append([oid, '보호 메타데이터 변경'])
    if errors:
        raise ValueError(json.dumps(errors, ensure_ascii=False, indent=2))
    records = []
    for key, review in reviews.items():
        records.append({'unit':key, **review, 'date':date, 'content_sha256':fingerprint(proposed,key)})
    for key, correction in plan.items():
        records = [r for r in records if r['unit'] != key]
        records.append({'unit':key, 'status':'approved', 'date':date, 'note':correction['reason'], 'content_sha256':fingerprint(proposed,key)})
    evidence.mkdir(parents=True)
    with zipfile.ZipFile(evidence/'before.zip','w',zipfile.ZIP_DEFLATED) as archive:
        archive.write(index_path,index_path.relative_to(ROOT))
        for path in hashes:
            archive.write(ROOT/path,path)
    affected = {current.paths[key] for key in plan}
    for path in affected:
        old = read_jsonl(ROOT/path)
        (ROOT/path).write_text(''.join(json.dumps(proposed.units[u['id']],ensure_ascii=False)+'\n' for u in old),encoding='utf-8')
    for item in index['segments']:
        path = item['path']
        if any(row['id'] in changed_ids for row in segments[path]):
            (ROOT/path).write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in segments[path]),encoding='utf-8')
        item['sha256'] = hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
    index_path.write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    ledger = ROOT/'assets/translation/review/decisions.jsonl'
    prior = read_jsonl(ledger) if ledger.exists() else []
    keys = {r['unit'] for r in records}
    ledger.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in prior if r['unit'] not in keys)+''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in records),encoding='utf-8')
    changes = [{'unit':key,'source':current.units[key]['source'],'before':current.units[key],'after':proposed.units[key],'reason':correction['reason']} for key,correction in plan.items()]
    (evidence/'changes.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    load()
    print(json.dumps({'batch':label,'corrected_units':len(plan),'occurrences':len(changed_ids),'examined_units':len(reviews)},ensure_ascii=False))
