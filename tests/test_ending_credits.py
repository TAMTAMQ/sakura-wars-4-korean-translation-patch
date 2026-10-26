import hashlib
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from build import encode
from ending_credits import format_names, plan, verify_blank_fonts


class EndingCreditsTests(unittest.TestCase):
    def setUp(self):
        work = Path(__file__).resolve().parents[1] / 'work/tests'
        work.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=work)
        self.root = Path(self.tmp.name)
        (self.root / 'config').mkdir()
        data = bytearray(180)
        data[:4] = b'ASCR'
        struct.pack_into('<II', data, 12, 24, 1)
        struct.pack_into('<I', data, 32, 128 - 32)
        data[128:130] = b'A\0'
        self.data = bytes(data)
        self.codes = {c: ('f1%02x' % (0x40 + i)) for i, c in enumerate('사쿠라군오가미이치로')}
        self.codes['\u2063'] = 'f788'
        self.rows = {'credit': {'id': 'credit', 'file': 'test.SBX', 'kind': 'ascr',
                               'offset': 128, 'capacity': 1, 'raw_hex': '41',
                               'pointer_offset': 32, 'text': '사쿠라 군　　오가미 이치로'}}
        self.cfg = {'file': 'test.SBX', 'baseline_sha256': hashlib.sha256(self.data).hexdigest(),
                    'first_column_cells': 10, 'rows': [{'id': 'credit', 'offset': 64, 'capacity': 50}]}

    def tearDown(self):
        self.tmp.cleanup()

    def execute(self):
        (self.root / 'config/ending-credits-layout.json').write_text(json.dumps(self.cfg), encoding='utf-8')
        return plan(self.root, {'test.SBX': self.data}, self.rows, self.codes, encode)

    def test_repointing_preserves_bytecode_and_source_string(self):
        writes, managed, report = self.execute()
        out = bytearray(self.data)
        for _, off, expected, new, _ in writes:
            self.assertEqual(bytes(out[off:off + len(expected)]), expected)
            out[off:off + len(new)] = new
        self.assertEqual(out[:32], self.data[:32])
        self.assertEqual(out[128:130], b'A\0')
        self.assertEqual(len(out), len(self.data))
        self.assertEqual(struct.unpack_from('<I', out, 32)[0] + 32, 64)
        self.assertEqual(managed, {'credit'})
        self.assertEqual(report['rows'], 1)

    def test_live_string_slot_is_rejected(self):
        self.cfg['rows'][0].update(offset=128, capacity=50)
        with self.assertRaisesRegex(ValueError, '보호 영역'):
            self.execute()

    def test_reserved_translation_padding_is_protected(self):
        self.rows['credit']['capacity'] = 8
        self.cfg['rows'][0].update(offset=131, capacity=40)
        with self.assertRaisesRegex(ValueError, '보호 영역'):
            self.execute()

    def test_capacity_and_hash_fail_closed(self):
        self.cfg['rows'][0]['capacity'] = 1
        with self.assertRaisesRegex(ValueError, '공간 부족'):
            self.execute()
        self.cfg['baseline_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, '해시'):
            self.execute()

    def test_name_lengths_share_same_second_column(self):
        for left in ['사쿠라 군', '오가미 이치로', '사쿠라오가미 이치로']:
            text = format_names(left + '　　사쿠라', {}, 10)
            first = text[:-len('사쿠라')]
            self.assertEqual(len(first.replace(' ', '')), 10)
            self.assertEqual(first.count(' '), 1)
        with self.assertRaisesRegex(ValueError, '침범'):
            format_names('사쿠라오가미이치로 군　　사쿠라', {}, 10)

    def test_final_blank_glyph_cannot_become_visible(self):
        files = {name: bytearray(1786 * size * size // 2) for name, size in
                 [('SKFONT.CG', 26), ('SKFONT2.CG', 24), ('SKFONT3.CG', 22), ('SKFONT4.CG', 22)]}
        verify_blank_fonts(files, self.codes)
        files['SKFONT3.CG'][1785 * 242] = 1
        with self.assertRaisesRegex(ValueError, '빈 타일에 픽셀'):
            verify_blank_fonts(files, self.codes)


if __name__ == '__main__':
    unittest.main()
