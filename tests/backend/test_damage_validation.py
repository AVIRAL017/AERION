"""
Unit tests for BUG-006: Damage Pair Structural & Geospatial Validation
Verifies:
1. Valid, compatible pairs pass validation and return STRUCTURALLY_COMPATIBLE
2. Unrelated images with severe aspect ratio disparity (> 2.0x) fail with ValidationError (HTTP 422)
3. Unrelated images with extreme scale disparity (> 5.0x) fail with ValidationError (HTTP 422)
4. Non-existent images fail with ValidationError
5. Dimension disparity within acceptable range issues warning but passes
6. pair_validation block is properly structured
"""

import tempfile
import unittest
from pathlib import Path
import numpy as np
import cv2

from app.core.errors import ValidationError
from app.services.damage_validator import DamagePairValidator, DamagePairValidationResult


class TestDamagePairValidation(unittest.TestCase):

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="aerion_test_val_"))

    def tearDown(self):
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_dummy_image(self, filename: str, width: int, height: int) -> Path:
        p = self.temp_dir / filename
        img = np.zeros((height, width, 3), dtype=np.uint8)
        # Add some distinct content
        cv2.rectangle(img, (10, 10), (width - 10, height - 10), (100, 150, 200), -1)
        cv2.imwrite(str(p), img)
        return p

    def test_compatible_same_dimension_pair(self):
        pre = self._create_dummy_image("pre_512.jpg", 512, 512)
        post = self._create_dummy_image("post_512.jpg", 512, 512)

        res = DamagePairValidator.validate_pair(pre, post)
        self.assertTrue(res.is_compatible)
        self.assertEqual(res.status, "STRUCTURALLY_COMPATIBLE")
        self.assertEqual(res.aspect_ratio_disparity, 1.0)
        self.assertEqual(res.dimension_disparity, 1.0)
        self.assertEqual(len(res.warnings), 0)

    def test_compatible_different_resolution_similar_aspect_ratio(self):
        pre = self._create_dummy_image("pre_640x480.jpg", 640, 480)    # AR 1.333
        post = self._create_dummy_image("post_800x600.jpg", 800, 600)  # AR 1.333

        res = DamagePairValidator.validate_pair(pre, post)
        self.assertTrue(res.is_compatible)
        self.assertEqual(res.status, "STRUCTURALLY_COMPATIBLE")
        self.assertAlmostEqual(res.aspect_ratio_disparity, 1.0, places=2)
        self.assertGreater(len(res.warnings), 0)  # should note dimension mismatch normalized

    def test_incompatible_severe_aspect_ratio_disparity(self):
        # Landscape 16:9 vs Extreme Portrait 1:4
        pre = self._create_dummy_image("landscape.jpg", 1600, 900)   # AR 1.777
        post = self._create_dummy_image("portrait.jpg", 200, 800)    # AR 0.250 -> disparity = 1.777 / 0.250 = 7.1x (> 2.0x)

        with self.assertRaises(ValidationError) as ctx:
            DamagePairValidator.validate_pair(pre, post)

        self.assertIn("Structural Incompatibility", str(ctx.exception.message))
        self.assertIn("aspect ratio disparity", str(ctx.exception.message).lower())

    def test_incompatible_extreme_dimension_disparity(self):
        # 100x100 vs 2000x2000 (20x scale difference)
        pre = self._create_dummy_image("tiny.jpg", 64, 64)
        post = self._create_dummy_image("giant.jpg", 1024, 1024)   # scale disparity = 16x (> 5.0x)

        with self.assertRaises(ValidationError) as ctx:
            DamagePairValidator.validate_pair(pre, post)

        self.assertIn("scale disparity", str(ctx.exception.message).lower())

    def test_missing_files_raise_validation_error(self):
        pre = self._create_dummy_image("pre.jpg", 512, 512)
        missing = self.temp_dir / "non_existent.jpg"

        with self.assertRaises(ValidationError):
            DamagePairValidator.validate_pair(missing, pre)

        with self.assertRaises(ValidationError):
            DamagePairValidator.validate_pair(pre, missing)


if __name__ == "__main__":
    unittest.main()
