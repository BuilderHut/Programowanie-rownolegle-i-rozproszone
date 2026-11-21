from __future__ import annotations

import unittest

import numpy as np

from image_processing import (
    merge_image,
    process_fragment,
    sobel_filter,
    split_image,
)


class ImageProcessingTests(unittest.TestCase):
    def test_constant_image_has_no_edges(self) -> None:
        image = np.full((20, 30), 127, dtype=np.uint8)
        result = sobel_filter(image)
        self.assertEqual(result.shape, image.shape)
        self.assertTrue(np.all(result == 0))

    def test_vertical_border_is_detected(self) -> None:
        image = np.zeros((20, 30), dtype=np.uint8)
        image[:, 15:] = 255
        result = sobel_filter(image)
        self.assertGreater(int(result[:, 14:16].max()), 0)

    def test_split_process_merge_matches_whole_image(self) -> None:
        rng = np.random.default_rng(1234)
        image = rng.integers(0, 256, size=(57, 41), dtype=np.uint8)
        fragments = split_image(image, parts=7, halo=1)
        merged = merge_image([process_fragment(fragment) for fragment in fragments])
        np.testing.assert_array_equal(merged, sobel_filter(image))

    def test_more_parts_than_rows_is_handled(self) -> None:
        image = np.arange(15, dtype=np.uint8).reshape(3, 5)
        fragments = split_image(image, parts=20)
        self.assertEqual(len(fragments), 3)


if __name__ == "__main__":
    unittest.main()

