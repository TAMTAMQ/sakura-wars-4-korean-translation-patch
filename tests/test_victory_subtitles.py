"""프레임 꼬리 f로 오인했던 승리 자막의 실제 편집 경계를 검사한다."""
import json
import struct
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from build import encode
from dialogue import load

class VictorySubtitleTests(unittest.TestCase):
    def test_short_caption_population_is_registered_at_actual_text(self):
        expected = {'LIPSYNC1.LIP': [823, 1475], 'LIPSYNC2.LIP': [2418],
                    'LIPSYNC3.LIP': [1044, 2133], 'LIPSYNC4.LIP': [1710]}
        codes = json.loads((ROOT / 'config/encoding.json').read_text(encoding='utf-8'))
        _, rows, _ = load(ROOT)
        for filename, table_rows in expected.items():
            original = (ROOT / 'originals/v05/ADVDATA' / filename).read_bytes()
            for table_row in table_rows:
                with self.subTest(file=filename, row=table_row):
                    row = rows[f'ADVDATA/{filename}#{table_row:04d}']
                    offset = row['offset']; pointer = struct.unpack_from('<I', original, 12 + table_row * 12 + 8)[0] - 1
                    self.assertEqual(offset, pointer + 2)
                    self.assertEqual(original[pointer:offset], b'f\0')
                    self.assertEqual(original[offset:offset + row['capacity']], bytes.fromhex(row['raw_hex']))
                    self.assertEqual(row['source'], '決め∈')
                    self.assertEqual(row['text'], '결정∈')
                    self.assertEqual(len(encode(row['text'], codes)), row['capacity'])

if __name__ == '__main__': unittest.main()
