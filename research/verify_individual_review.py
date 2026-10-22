"""개별 수정의 보존 범위·원본 기호·검수표 비교 칸을 확인한다."""
import hashlib
import json
import sys
import zipfile
from html.parser import HTMLParser
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from remake_individual import PLANS
import export_images as E


class ReviewParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.labels = []
        self.images = 0

    def handle_starttag(self, tag, attrs):
        if tag == 'img':
            self.images += 1
            assert dict(attrs)['src'].startswith('data:image/png;base64,')

    def handle_data(self, data):
        if data in ['원본', 'v0.5', '재제작 (보존본)', '개별 수정']:
            self.labels.append(data)


def main():
    review = ROOT / 'assets/images/review'
    baseline = json.loads((review / 'remake_baseline.json').read_text(encoding='utf-8'))
    current = {}
    for stage in ['slg', 'staffroll', 'ui', 'logo']:
        for row in json.loads((ROOT / 'assets/images/remake' / stage / 'index.json').read_text(encoding='utf-8')):
            current[f"{row['source']}|{row['block']}|{row['texture']}"] = row['remake']
    for key, item in baseline.items():
        for path in [item['path'], current[key]]:
            assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == item['sha256'], path
    corrections = json.loads((ROOT / 'assets/images/remake/individual/index.json').read_text(encoding='utf-8'))
    reviews = json.loads((review / 'image_review.json').read_text(encoding='utf-8'))
    archive = zipfile.ZipFile(ROOT / 'out/sakura_wars_4_kr_dev.dcp')
    results = []
    for row in corrections:
        key = f"{row['source']}|{row['block']}|{row['texture']}"
        old = np.array(Image.open(ROOT / baseline[key]['path']).convert('RGBA'))
        new = np.array(Image.open(ROOT / row['remake']).convert('RGBA'))
        original = np.array(Image.open(ROOT / row['original']).convert('RGBA'))
        plan = PLANS[row['id']]
        rects = list(plan.get('copy', []))
        for x0, y0, x1, y1 in rects:
            assert np.array_equal(new[y0:y1, x0:x1], original[y0:y1, x0:x1]), row['id']
        if plan.get('none_vertical'):
            rects += [[0, 96, 96, 120], [96, 72, 128, 120]]
        if plan.get('hakushiki'):
            rects += [[0, 24, 128, 48], [0, 48, 80, 72], [80, 48, 128, 72], [96, 96, 120, 120]]
        allowed = np.zeros(old.shape[:2], dtype=bool)
        for x0, y0, x1, y1 in rects:
            allowed[y0:y1, x0:x1] = True
        assert np.array_equal(old[~allowed], new[~allowed]), row['id']
        assert np.any(old != new), row['id']
        members = next(r['members'] for r in reviews if r['id'] == row['id'])
        for member in members:
            source, block, texture = member.rsplit(' ', 2)
            spec = E.block_specs(archive.read(source))[int(block[1:])]
            decoded = E.decompress(spec[2], spec[4]) if spec[3] else spec[2]
            got = np.array(E.decode_bpv(decoded)[int(texture[1:])][1].convert('RGBA'))
            assert np.abs(got.astype(int) - new.astype(int)).max() <= 18, member
        results.append({'id': row['id'], 'changed_pixels': int(np.any(old != new, axis=-1).sum()),
                        'outside_changes': 0, 'original_symbols_exact': True, 'dcp_copies_verified': len(members)})
    archive.close()
    parser = ReviewParser()
    parser.feed((review / 'image_review.html').read_text(encoding='utf-8'))
    assert parser.labels.count('개별 수정') == len(corrections)
    for i, label in enumerate(parser.labels):
        if label == '개별 수정':
            assert parser.labels[i - 3:i] == ['원본', 'v0.5', '재제작 (보존본)']
    report = {'baseline_preserved': len(baseline), 'correction_columns': len(corrections),
              'comparison_order_verified': True, 'images': results}
    (ROOT / 'research/individual-review-verification.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
