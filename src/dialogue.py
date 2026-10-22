"""공유 문안 권위본과 출현 위치를 연결한다. 파일별 문안 사본은 만들지 않는다."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'sakura-shared-dialogue/v1'


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]


def inside(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('문안 경로 이탈: ' + relative)
    return path


class Catalogue:
    def __init__(self, units):
        self.units = {}
        self.paths = {}
        for unit in units:
            key = unit['id']
            if key in self.units:
                raise ValueError('중복 공유 대사 ID: ' + key)
            self.units[key] = unit
        self.cache = {}
        self.active = set()

    def text(self, key, form='default'):
        address = (key, form)
        if address in self.cache:
            return self.cache[address]
        if address in self.active:
            raise ValueError('공유 문안 참조 순환: ' + key)
        if key not in self.units:
            raise ValueError('미등록 공유 대사: ' + key)
        self.active.add(address)
        try:
            unit = self.units[key]
            if form == 'default':
                content = unit
            else:
                content = unit.get('variants', {}).get(form)
                if content is None:
                    raise ValueError('미등록 말투·배치 변형: ' + key + '/' + form)
                base = self.text(key)
                if content.get('base_text_sha256') != digest(base):
                    raise ValueError('공유 대사가 바뀌었습니다. 관련 말투·배치 변형 재검토 필요: ' + key + '/' + form)
            if sum(field in content for field in ['text', 'parts', 'breaks']) != 1:
                raise ValueError('공유 문안 본문은 text/parts/breaks 중 하나여야 합니다: ' + key)
            if 'breaks' in content:
                if form == 'default':
                    raise ValueError('대표 문안에 배치 변형을 지정할 수 없음: ' + key)
                body = self.text(key).replace('//', '')
                points = content['breaks']
                if points != sorted(set(points)) or any(not isinstance(p, int) or not 0 < p < len(body) for p in points):
                    raise ValueError('잘못된 줄바꿈 위치: ' + key)
                starts, ends = [0] + points, points + [len(body)]
                value = '//'.join(body[a:b] for a, b in zip(starts, ends))
            elif 'text' in content:
                if 'parts' in content or not isinstance(content['text'], str):
                    raise ValueError('문안 형식 오류: ' + key)
                value = content['text']
            elif 'parts' in content:
                if not isinstance(content['parts'], list):
                    raise ValueError('문안 조합은 목록이어야 합니다: ' + key)
                parts = []
                for part in content['parts']:
                    if isinstance(part, str):
                        parts.append(part)
                    elif isinstance(part, dict) and set(part) == {'ref'}:
                        parts.append(self.text(part['ref']))
                    else:
                        raise ValueError('문안 조합 형식 오류: ' + key)
                value = ''.join(parts)
            else:
                raise ValueError('공유 문안 누락: ' + key)
            self.cache[address] = value
            return value
        finally:
            self.active.remove(address)

    def resolve(self, occurrences):
        declared = {}
        for key, unit in self.units.items():
            self.text(key)
            for form in unit.get('variants', {}):
                self.text(key, form)
            for occurrence in unit.get('occurrences', []):
                oid = occurrence['id']
                if oid in declared:
                    raise ValueError('중복 대사 사용처: ' + oid)
                declared[oid] = (key, occurrence.get('form', 'default'))
        rows = {}
        for occurrence in occurrences:
            oid = occurrence['id']
            if oid in rows:
                raise ValueError('중복 출현 ID: ' + oid)
            if 'text' in occurrence or 'review' in occurrence:
                raise ValueError('파일별 문안 사본은 편집할 수 없습니다. 공유 권위본을 수정하세요: ' + oid)
            address = (occurrence['unit'], occurrence.get('form', 'default'))
            if declared.get(oid) != address:
                raise ValueError('대사 사용처 연결 불일치: ' + oid)
            unit = self.units[address[0]]
            review = unit if address[1] == 'default' else unit['variants'][address[1]]
            rows[oid] = {**occurrence, 'text': self.text(*address), 'review': review.get('review', '교차 검토 필요')}
        if set(rows) != set(declared):
            raise ValueError('공유 대사 사용처 모집단 누락')
        return rows


def load(root=ROOT, index=None, validate=True):
    root = Path(root)
    index = index or json.loads((root / 'assets/translation/index.json').read_text(encoding='utf-8'))
    if index.get('schema') != SCHEMA:
        raise ValueError('공유 대사 색인이 아닙니다.')
    units, hashes, paths = [], {}, {}
    for segment in index['units']:
        path = inside(root, segment['path'])
        data = path.read_bytes()
        hashes[segment['path']] = hashlib.sha256(data).hexdigest()
        for unit in (json.loads(line) for line in data.decode('utf-8').splitlines() if line):
            units.append(unit)
            paths[unit['id']] = segment['path']
    catalogue = Catalogue(units)
    catalogue.paths = paths
    occurrences = []
    for segment in index['segments']:
        path = inside(root, segment['path'])
        data = path.read_bytes()
        hashes[segment['path']] = hashlib.sha256(data).hexdigest()
        occurrences.extend(json.loads(line) for line in data.decode('utf-8').splitlines() if line)
    rows = catalogue.resolve(occurrences) if validate else {o['id']: o for o in occurrences}
    return catalogue, rows, hashes


def main():
    parser = argparse.ArgumentParser(description='공유 대사 검색·연결 검사')
    sub = parser.add_subparsers(dest='command', required=True)
    find = sub.add_parser('find', help='원문·번역·기존 출현 ID 검색')
    find.add_argument('query')
    show = sub.add_parser('show', help='공유 대사 또는 기존 출현 ID 상세 보기')
    show.add_argument('id')
    edit = sub.add_parser('edit', help='대표 문안 또는 지정한 말투·배치 변형 편집')
    edit.add_argument('id')
    edit.add_argument('--variant')
    body = edit.add_mutually_exclusive_group(required=True)
    body.add_argument('--text')
    body.add_argument('--breaks', help='줄바꿈 변형 위치(쉼표로 구분)')
    sub.add_parser('validate', help='모든 사용처·참조·변형 검증')
    args = parser.parse_args()
    catalogue, rows, _ = load(validate=args.command == 'validate')
    if args.command == 'validate':
        print(json.dumps({'shared_units': len(catalogue.units), 'occurrences': len(rows),
                          'variant_review_units': sum(bool(u.get('variants')) for u in catalogue.units.values())}, ensure_ascii=False))
    elif args.command in ('show', 'edit'):
        key = rows[args.id]['unit'] if args.id in rows else args.id
        unit = catalogue.units[key]
        if args.command == 'show':
            print(json.dumps({'path': catalogue.paths[key], **unit, 'resolved_text': catalogue.text(key)}, ensure_ascii=False, indent=2))
        else:
            if args.id in rows and rows[args.id].get('form') and args.variant != rows[args.id]['form']:
                raise SystemExit('이 사용처는 변형을 씁니다. --variant ' + rows[args.id]['form'] + '를 명시하세요.')
            if args.variant:
                content = unit['variants'][args.variant]
                base = catalogue.text(key)
            else:
                content = unit
                if 'parts' in unit:
                    raise SystemExit('공유 구절을 조합한 문안입니다. show로 parts의 ref를 확인하여 해당 구절을 편집하세요.')
            if args.breaks is not None:
                if not args.variant:
                    raise SystemExit('--breaks는 지정한 변형에만 사용할 수 있습니다.')
                positions = [int(p) for p in args.breaks.split(',') if p]
                body_text = base.replace('//', '')
                if positions != sorted(set(positions)) or any(not 0 < p < len(body_text) for p in positions):
                    raise SystemExit('줄바꿈 위치가 문안 범위를 벗어났거나 중복됩니다.')
                replacement = {'breaks': positions}
            else:
                replacement = {'text': args.text}
            for field in ['text', 'parts', 'breaks']:
                content.pop(field, None)
            content.update(replacement)
            content['review'] = '교차 검토 필요'
            if args.variant:
                content['base_text_sha256'] = digest(base)
            path = ROOT / catalogue.paths[key]
            units = read_jsonl(path)
            units = [unit if u['id'] == key else u for u in units]
            temporary = path.with_suffix('.jsonl.partial')
            temporary.write_text(''.join(json.dumps(u, ensure_ascii=False) + '\n' for u in units), encoding='utf-8')
            temporary.replace(path)
            print('공유 문안 저장:', key, '→', catalogue.paths[key])
            print('python src/dialogue.py validate 로 관련 변형을 확인한 뒤 빌드하세요.')
    else:
        found = 0
        for key, unit in catalogue.units.items():
            values = [unit.get('source', ''), catalogue.text(key)]
            values += [v.get('text', '') for v in unit.get('variants', {}).values()]
            values += [o['id'] for o in unit.get('occurrences', [])]
            if any(args.query in v for v in values):
                print(json.dumps({'id': key, 'path': catalogue.paths[key], 'source': unit.get('source'),
                                  'text': catalogue.text(key), 'occurrences': unit.get('occurrences', []),
                                  'variants': list(unit.get('variants', {}))}, ensure_ascii=False))
                found += 1
        print('검색 결과', found, '개')


if __name__ == '__main__':
    main()
