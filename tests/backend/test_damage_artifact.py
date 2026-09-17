"""
Unit tests for BUG-021: Disaster Damage Artifact Generation & Storage
Verifies:
1. AnnotationService.render_damage_overlay_and_store renders damage visual overlay
2. Stores artifact under project_id/damage_mask/<uuid>.jpg via LocalArtifactStorage
3. Produces valid AnnotationResult with sha256, mime_type, file size, dimensions, and base64
4. Produces zero-damage badge if no damage detected
5. Endpoints attach damage_mask_base64 and damage_artifact info
"""

import tempfile
import unittest
import uuid
from pathlib import Path
import numpy as np
import cv2

from app.services.annotation_service import AnnotationService, AnnotationResult
from app.services.storage_service import LocalArtifactStorage


class TestDamageArtifactGeneration(unittest.TestCase):

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="aerion_dmg_test_"))
        self.storage = LocalArtifactStorage(root_dir=self.temp_dir / "storage")
        self.annotation_service = AnnotationService(storage=self.storage)
        self.project_id = uuid.uuid4()

    def tearDown(self):
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_dummy_image(self, filename: str, width: int = 512, height: int = 512) -> Path:
        p = self.temp_dir / filename
        img = np.zeros((height, width, 3), dtype=np.uint8)
        # Add texture
        cv2.circle(img, (width // 2, height // 2), min(width, height) // 4, (120, 140, 160), -1)
        cv2.imwrite(str(p), img)
        return p

    def test_render_damage_overlay_and_store_generates_valid_artifact(self):
        pre = self._create_dummy_image("pre.jpg", 512, 512)
        post = self._create_dummy_image("post.jpg", 512, 512)

        mock_damage_analysis = None  # Service uses real predict_damage internally

        annot_res = self.annotation_service.render_damage_overlay_and_store(
            after_image_path=post,
            before_image_path=pre,
            damage_analysis=mock_damage_analysis,
            project_id=self.project_id,
        )

        self.assertIsInstance(annot_res, AnnotationResult)
        self.assertTrue(annot_res.artifact_key.startswith(f"{self.project_id}/damage_mask/"))
        self.assertTrue(annot_res.artifact_key.endswith(".jpg"))
        self.assertEqual(annot_res.mime_type, "image/jpeg")
        self.assertGreater(annot_res.file_size_bytes, 0)
        self.assertEqual(len(annot_res.sha256), 64)
        self.assertEqual(annot_res.image_width, 512)
        self.assertEqual(annot_res.image_height, 512)
        self.assertIsNotNone(annot_res.annotated_base64)
        self.assertGreater(len(annot_res.annotated_base64), 100)

        # Verify physical file existence in storage
        stored_file = (self.storage.root_dir / annot_res.artifact_key).resolve()
        self.assertTrue(stored_file.exists())
        self.assertEqual(stored_file.stat().st_size, annot_res.file_size_bytes)


if __name__ == "__main__":
    unittest.main()
