"""조각 경계가 단어 중간에 인위적인 자간을 만들던 회귀를 검사한다."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import remake_slg_plates as plates

class SplitPlateLayoutTests(unittest.TestCase):
    def test_shift_whole_word_preserves_spacing(self):
        ink = [(0, 16), (0, 16), (0, 16)]
        starts = [0, 18, 36]
        positions = plates.place(ink, starts, 88, [40], 'center', 0)
        self.assertIsNotNone(positions)
        self.assertEqual([positions[i] - positions[i - 1] for i in (1, 2)], [18, 18])
        self.assertTrue(all(not x < 40 < x + 16 for x in positions))

    def test_no_global_solution_requests_uniform_scaling(self):
        self.assertIsNone(plates.place([(0, 20)] * 3, [0, 20, 40], 80, [20, 40, 60], 'center', 0))

    def test_actual_shikami_keeps_equal_advances(self):
        import json
        config = json.loads(plates.CONFIG.read_text(encoding='utf-8'))
        plates.LAYOUT_AUDIT.clear()
        mask = plates.render_chain('시카미', 72, 24, 'center', 0, 0, config['font'], [48], shadow_guard=0)
        row = plates.LAYOUT_AUDIT[-1]
        self.assertEqual(mask.shape, (24, 72))
        self.assertLess(row['artificial_gap'], 1e-8)
        p = row['positions']
        self.assertAlmostEqual(p[1] - p[0], p[2] - p[1], places=3)

if __name__ == '__main__': unittest.main()
