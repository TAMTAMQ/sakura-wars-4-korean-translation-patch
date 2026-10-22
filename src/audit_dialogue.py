"""전 출현의 정적 검사와 대사 검수 대장을 만든다. 미검수를 합격 처리하지 않는다."""
import collections
import hashlib
import json
import math
import re
import sys
from pathlib import Path

from build import encode
from dialogue import ROOT, digest, load


def is_dialogue(row):
    path = row['file']
    return (path.endswith('.LIP') or path.startswith('ADVDATA/SCRIPT/') or
            (path.startswith('SLG/') and '/E/' in path and path.endswith('.SBN')))


def measure(text):
    # 16전각 창의 보수적 후보 검사. 실제 표시 확인과 동등하지 않다.
    # 가변 글꼴·좌표·미해석 raw 제어가 있는 문안은 별도 확인 대상으로 둔다.
    controls = re.findall(r'@[A-Za-z]+[0-9,]*|⟦[^⟧]*⟧', text)
    cleaned = re.sub(r'@[A-Za-z]+[0-9,]*|⟦[^⟧]*⟧', '', text).replace('\u2063', '')
    line_columns = [sum(1 if c == ' ' or ord(c) < 128 else 2 for c in line) for line in cleaned.split('//')]
    lines = sum(max(1, math.ceil(n / 32)) for n in line_columns)
    return {'columns': line_columns, 'estimated_lines': lines, 'controls': controls}


def main():
    catalogue, rows, hashes = load()
    codes = json.loads((ROOT / 'config/encoding.json').read_text(encoding='utf-8'))
    output = ROOT / 'work/qa/dialogue'
    output.mkdir(parents=True, exist_ok=True)
    decisions_path = ROOT / 'assets/translation/review/decisions.jsonl'
    decisions = {}
    if decisions_path.exists():
        decisions = {d['unit']: d for d in map(json.loads, decisions_path.read_text(encoding='utf-8').splitlines())}
    issues, inventory, by_form = [], [], collections.defaultdict(list)
    counters = collections.Counter()
    for oid, row in rows.items():
        text = row['text']; flags = []
        try:
            size = len(encode(text, codes))
            if size > row['capacity']:
                flags.append('capacity_overflow' if text != row['baseline_text'] else 'baseline_encoding_difference')
        except (UnicodeError, ValueError) as error:
            size = None
            flags.append('unencodable' if text != row['baseline_text'] else 'baseline_unencodable')
        display = measure(text)
        linguistic = bool(re.search('[가-힣ぁ-ヿ一-龥]', text))
        dialogue = linguistic and is_dialogue(row)
        if dialogue and display['estimated_lines'] > 3:
            flags.append('possible_dialogue_overflow')
        if dialogue and display['controls']:
            flags.append('control_layout_review')
        if dialogue and re.search('[ぁ-ゖァ-ヺ]', text):
            flags.append('remaining_kana')
        if dialogue and re.search('([가-힣]{2,})(?: \1){1,}', text):
            flags.append('repeated_word_candidate')
        if dialogue and text.count('「') != text.count('」'):
            flags.append('quote_balance_candidate')
        counters.update(flags)
        form = row.get('form', 'default')
        entry = {'id': oid, 'unit': row['unit'], 'form': form, 'file': row['file'],
                 'text_sha256': digest(text), 'capacity': row['capacity'], 'encoded_bytes': size,
                 'dialogue_candidate': dialogue, 'flags': flags, 'layout_estimate': display}
        inventory.append(entry)
        by_form[(row['unit'], form)].append(entry)
        if flags:
            issues.append({**entry, 'text': text, 'source': row.get('source')})
    review_units = []
    for key, unit in catalogue.units.items():
        if not unit.get('occurrences'):
            continue
        samples = [rows[o['id']] for o in unit['occurrences']]
        if not any(re.search('[가-힣ぁ-ヿ一-龥]', r['text']) for r in samples):
            continue
        rendered = {form: catalogue.text(key, form) for form in ['default'] + list(unit.get('variants', {}))}
        content_sha = digest(json.dumps({'source': unit['source'], 'texts': rendered}, ensure_ascii=False, sort_keys=True))
        decision = decisions.get(key, {})
        language = decision.get('status', 'pending') if decision.get('content_sha256') == content_sha else 'pending'
        review_units.append({'unit': key, 'path': catalogue.paths[key], 'source': unit['source'],
                             'texts': rendered, 'content_sha256': content_sha,
                             'occurrences': unit['occurrences'], 'language_review': language})
    (output / 'occurrences.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in inventory), encoding='utf-8')
    (output / 'issues.json').write_text(json.dumps(issues, ensure_ascii=False, indent=2), encoding='utf-8')
    batches = output / 'batches'; batches.mkdir(exist_ok=True)
    for start in range(0, len(review_units), 100):
        (batches / f'{start // 100 + 1:04d}.jsonl').write_text(
            ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in review_units[start:start + 100]), encoding='utf-8')
    summary = {'occurrences_checked': len(rows), 'shared_units': len(catalogue.units),
               'language_units': len(review_units), 'language_reviewed': sum(r['language_review'] != 'pending' for r in review_units),
               'language_approved': sum(r['language_review'] == 'approved' for r in review_units),
               'scope': '대사 검수만 수행; 게임 내 표시 확인은 사용자 요청으로 제외', 'flags': dict(counters),
               'issue_occurrences': len(issues), 'review_batches': math.ceil(len(review_units) / 100),
               'input_hashes_sha256': digest(json.dumps(hashes, sort_keys=True)),
               'static_layout_is_runtime_verification': False}
    (output / 'review-units.json').write_text(json.dumps(review_units, ensure_ascii=False), encoding='utf-8')
    target = ROOT / 'research/dialogue-qa-summary.json'
    target.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
