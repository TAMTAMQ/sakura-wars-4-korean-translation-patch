"""공유 문안의 전체 사용처 반영·드리프트 차단과 빌드 실패 경계를 검증한다."""
import contextlib
import copy
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from build import build, sha
from dialogue import Catalogue, SCHEMA, digest


class SharedDialogueTests(unittest.TestCase):
    def units(self):
        return [
            {'id': 'phrase', 'text': '사쿠라', 'occurrences': []},
            {'id': 'line', 'parts': ['「', {'ref': 'phrase'}, '」'],
             'occurrences': [{'id': 'normal'}, {'id': 'voice'}]},
            {'id': 'quiz', 'parts': ['「', {'ref': 'phrase'}, '」'], 'occurrences': [{'id': 'quiz'}]},
        ]

    def occurrences(self):
        return [{'id': 'normal', 'unit': 'line'}, {'id': 'voice', 'unit': 'line'}, {'id': 'quiz', 'unit': 'quiz'}]

    def test_one_phrase_edit_updates_normal_voice_and_quiz(self):
        units = self.units()
        units[0]['text'] = '사쿠라 군'
        rows = Catalogue(units).resolve(self.occurrences())
        self.assertEqual([r['text'] for r in rows.values()], ['「사쿠라 군」'] * 3)

    def test_stale_context_variant_blocks_instead_of_silently_remaining(self):
        unit = {'id': 'x', 'text': '알았어', 'variants': {'polite': {'text': '알겠습니다',
                'base_text_sha256': digest('알았어')}}, 'occurrences': []}
        Catalogue([unit]).resolve([])
        unit['text'] = '좋아'
        with self.assertRaisesRegex(ValueError, '재검토'):
            Catalogue([unit]).resolve([])

    def test_reference_edit_also_invalidates_parent_variant(self):
        units = self.units()
        units[1]['variants'] = {'v': {'text': '사쿠라 군', 'base_text_sha256': digest('「사쿠라」')}}
        units[0]['text'] = '사쿠라 군'
        with self.assertRaisesRegex(ValueError, '재검토'):
            Catalogue(units).resolve(self.occurrences())

    def test_layout_variant_has_no_duplicate_text(self):
        unit = {'id': 'x', 'text': '사쿠라군', 'variants': {'split': {'breaks': [3],
                'base_text_sha256': digest('사쿠라군')}},
                'occurrences': [{'id': 'normal'}, {'id': 'voice', 'form': 'split'}]}
        rows = Catalogue([unit]).resolve([{'id': 'normal', 'unit': 'x'}, {'id': 'voice', 'unit': 'x', 'form': 'split'}])
        self.assertEqual(rows['voice']['text'], '사쿠라//군')

    def test_missing_use_site_is_rejected(self):
        with self.assertRaisesRegex(ValueError, '모집단'):
            Catalogue(self.units()).resolve(self.occurrences()[:-1])

    def test_duplicate_use_site_is_rejected(self):
        units = self.units()
        units[2]['occurrences'] = [{'id': 'normal'}]
        with self.assertRaisesRegex(ValueError, '중복 대사 사용처'):
            Catalogue(units).resolve(self.occurrences())

    def test_copy_text_cannot_override_authority(self):
        occurrences = self.occurrences()
        occurrences[0]['text'] = '옛 대사'
        with self.assertRaisesRegex(ValueError, '사본'):
            Catalogue(self.units()).resolve(occurrences)

    def test_bad_reference_and_cycles_are_rejected(self):
        with self.assertRaisesRegex(ValueError, '미등록'):
            Catalogue([{'id': 'x', 'parts': [{'ref': 'missing'}]}]).resolve([])
        with self.assertRaisesRegex(ValueError, '순환'):
            Catalogue([{'id': 'x', 'parts': [{'ref': 'y'}]}, {'id': 'y', 'parts': [{'ref': 'x'}]}]).resolve([])

    def test_duplicate_unit_and_wrong_form_are_rejected(self):
        with self.assertRaisesRegex(ValueError, '중복 공유'):
            Catalogue([{'id': 'x'}, {'id': 'x'}])
        with self.assertRaisesRegex(ValueError, '미등록 말투'):
            Catalogue([{'id': 'x', 'text': '가'}]).text('x', 'missing')

    def test_build_writes_every_use_and_one_overflow_prevents_output(self):
        workspace = Path(__file__).resolve().parents[1] / 'work/tests'
        workspace.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=workspace) as temp:
            root = Path(temp)
            for folder in ['config', 'originals/v05', 'assets/translation/segments', 'assets/translation/units']:
                (root / folder).mkdir(parents=True)
            def save(path, obj):
                (root / path).write_text(json.dumps(obj, ensure_ascii=False), encoding='utf-8')
            files, bindings, rows = [], {}, []
            for i, name in enumerate(['normal.SBX', 'voice.SBX', 'quiz.SBX']):
                raw = b'12345678\0TAIL'
                (root / 'originals/v05' / name).write_bytes(raw)
                files.append({'path': name, 'size': len(raw), 'sha256': sha(raw)})
                fixed = {'id': name, 'file': name, 'offset': 0, 'capacity': 8, 'raw_hex': raw[:8].hex(),
                         'baseline_text': '12345678', 'kind': 'fixed'}
                bindings[name] = fixed
                rows.append({**fixed, 'unit': 'x'})
            save('config/baseline.json', {'files': files})
            save('config/text-bindings.json', bindings)
            save('config/encoding.json', {'사': 'f0a6', '쿠': 'f0a7', '라': 'f0a8', '군': 'f0a9'})
            save('assets/translation/index.json', {'schema': SCHEMA,
                 'segments': [{'path': 'assets/translation/segments/a.jsonl'}],
                 'units': [{'path': 'assets/translation/units/a.jsonl'}]})
            (root / 'assets/translation/segments/a.jsonl').write_text('\n'.join(json.dumps(r) for r in rows), encoding='utf-8')
            save('assets/translation/units/a.jsonl', {'id': 'x', 'text': '사쿠라',
                 'occurrences': [{'id': name} for name in bindings]})
            with contextlib.redirect_stdout(io.StringIO()):
                result = build(root)
            with zipfile.ZipFile(result['output']) as z:
                for name in bindings:
                    self.assertEqual(z.read(name), bytes.fromhex('f0a6f0a7f0a8') + b'\0\0\0TAIL')
            bindings['voice.SBX']['capacity'] = 4
            save('config/text-bindings.json', bindings)
            rows[1]['capacity'] = 4
            (root / 'assets/translation/segments/a.jsonl').write_text('\n'.join(json.dumps(r) for r in rows), encoding='utf-8')
            blocked = root / 'out/blocked.dcp'
            with self.assertRaisesRegex(ValueError, '가용'):
                build(root, blocked)
            self.assertFalse(blocked.exists())


if __name__ == '__main__':
    unittest.main()
