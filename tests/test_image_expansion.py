"""배경판 연장 시 끝 모양과 새 ADCG 타일이 누락되던 문제를 검사한다."""
import struct
import sys
import unittest
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from remake_ui import extend_vertical
from inject_images import rebuild_adcg
from export_images import decode_adcg

class ImageExpansionTests(unittest.TestCase):
    def test_extends_middle_without_scaling_caps_or_touching_neighbors(self):
        src = np.arange(10 * 5 * 4, dtype=np.uint8).reshape(10, 5, 4)
        result = extend_vertical(src, {'rect': [1, 1, 4, 6], 'at': 2, 'extra': 3})
        np.testing.assert_array_equal(result[:3], src[:3])
        np.testing.assert_array_equal(result[3:6, 1:4], np.repeat(src[3:4, 1:4], 3, axis=0))
        np.testing.assert_array_equal(result[6:9, 1:4], src[3:6, 1:4])
        np.testing.assert_array_equal(result[:, 0], src[:, 0])
        np.testing.assert_array_equal(result[:, 4], src[:, 4])
        np.testing.assert_array_equal(result[9:], src[9:])

    def test_refuses_extension_outside_canvas(self):
        with self.assertRaises(ValueError):
            extend_vertical(np.zeros((8, 4, 4), np.uint8), {'rect': [0, 0, 4, 6], 'at': 2, 'extra': 3})

    def test_registered_sparse_tile_expansion_roundtrips_new_pixels(self):
        header = struct.pack('<IIHHIIHH', 0xc0000000, 1, 2, 2, 24, 0x102, 4, 4)
        original = header + struct.pack('<IIII', 0, 16, 0, 0) + struct.pack('<4H', *([0xf00f] * 4))
        img = np.asarray(decode_adcg(original)[0][1]).copy()
        img[2:4, 2:4] = [0, 255, 0, 255]
        policy = {'original_decoded_size': len(original), 'additional_tiles': [[2, 2]]}
        rebuilt = rebuild_adcg(original, img, policy)
        self.assertEqual(struct.unpack_from('<I', rebuilt, 4)[0], 2)
        np.testing.assert_array_equal(np.asarray(decode_adcg(rebuilt)[0][1]), img)
        with self.assertRaisesRegex(ValueError, '기준선'):
            rebuild_adcg(original, img, {**policy, 'original_decoded_size': len(original) + 1})

if __name__ == '__main__': unittest.main()
