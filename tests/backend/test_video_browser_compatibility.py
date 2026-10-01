"""
AERION — Video Browser Compatibility Test Suite
Verifies that generated border surveillance video artifacts meet strict HTML5 browser playback requirements:
1. MP4 container format
2. H.264 / avc1 video codec (strictly NOT mp4v / MPEG-4 Part 2)
3. yuv420p pixel format
4. Progressive faststart streaming (moov atom placed BEFORE mdat atom)
5. Zero dependency on broken Linux OpenCV avc1 writers
"""

import hashlib
import os
import shutil
import struct
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path

import cv2
import numpy as np

from aerion_runtime_contracts import AERIONAnalysisResult, BoundingBox, Detection
from app.services.storage_service import LocalArtifactStorage
from app.services.video_annotation_service import (
    VideoAnnotationResult,
    VideoAnnotationService,
    get_ffmpeg_executable,
    transcode_to_browser_h264,
)


def parse_mp4_atoms(file_path: Path):
    """Parses top-level MP4 container boxes (atoms) and returns [(name, offset, size)]."""
    atoms = []
    with open(file_path, "rb") as f:
        file_size = file_path.stat().st_size
        offset = 0
        while offset < file_size:
            f.seek(offset)
            header = f.read(8)
            if len(header) < 8:
                break
            size = struct.unpack(">I", header[:4])[0]
            name = header[4:8].decode("latin1", errors="ignore")
            if size == 1:
                ext_header = f.read(8)
                size = struct.unpack(">Q", ext_header)[0]
            elif size == 0:
                size = file_size - offset
            atoms.append((name, offset, size))
            if size <= 0:
                break
            offset += size
    return atoms


class TestVideoBrowserCompatibility(unittest.TestCase):
    """Test suite ensuring all generated annotated videos are browser-playable."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="aerion_compat_test_")
        self.storage = LocalArtifactStorage(root_dir=Path(self.temp_dir) / "storage")
        self.service = VideoAnnotationService(storage=self.storage)
        self.project_id = uuid.uuid4()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_ffmpeg_executable_available(self):
        """Verify reliable FFmpeg binary is discovered in runtime environment."""
        exe = get_ffmpeg_executable()
        self.assertIsNotNone(exe, "FFmpeg binary must be available via system PATH or imageio-ffmpeg")
        self.assertTrue(Path(exe).exists(), f"Discovered FFmpeg binary must exist on disk: {exe}")

    def test_generated_video_artifact_is_browser_compatible(self):
        """
        Generates an annotated video artifact through the production pipeline and verifies:
        - Codec is avc1
        - MIME type is video/mp4
        - Container is MP4 with faststart (moov before mdat)
        - Pixel format is yuv420p
        - Does NOT contain mp4v / MPEG-4 Part 2
        """
        # 1. Create a synthetic intermediate video with OpenCV
        raw_video_path = Path(self.temp_dir) / "intermediate_raw.mp4"
        fps = 10.0
        width, height = 320, 240
        writer = self.service.create_video_writer(raw_video_path, fps=fps, width=width, height=height)
        self.assertTrue(writer.isOpened(), "OpenCV VideoWriter must open intermediate file")

        # Write 10 frames
        for frame_idx in range(10):
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            # Add simple pattern
            cv2.rectangle(frame, (20, 20), (100, 100), (0, 255, 0), -1)
            writer.write(frame)
        writer.release()
        self.assertTrue(raw_video_path.exists())

        # 2. Finalize and store through production service
        result = self.service.finalize_and_store(
            temp_video_path=raw_video_path,
            project_id=self.project_id,
            width=width,
            height=height,
            fps=fps,
            frame_count=10,
            source_frame_count=10,
            unique_tracks=1,
            total_detections=10,
        )

        self.assertIsInstance(result, VideoAnnotationResult)
        self.assertEqual(result.codec, "avc1", "Stored artifact codec metadata must be avc1")
        self.assertEqual(result.mime_type, "video/mp4")
        self.assertGreater(result.file_size_bytes, 0)

        stored_file = Path(self.temp_dir) / "storage" / result.artifact_key
        self.assertTrue(stored_file.exists(), f"Stored video artifact must exist: {stored_file}")

        # 3. Inspect top-level MP4 container atoms
        atoms = parse_mp4_atoms(stored_file)
        atom_names = [a[0] for a in atoms]
        self.assertIn("ftyp", atom_names, "MP4 must contain 'ftyp' atom")
        self.assertIn("moov", atom_names, "MP4 must contain 'moov' atom")
        self.assertIn("mdat", atom_names, "MP4 must contain 'mdat' atom")

        moov_idx = atom_names.index("moov")
        mdat_idx = atom_names.index("mdat")
        self.assertLess(
            moov_idx,
            mdat_idx,
            f"moov atom (index {moov_idx}) must precede mdat atom (index {mdat_idx}) for browser faststart",
        )

        # 4. Probe video stream properties via FFmpeg inspection
        ffmpeg_exe = get_ffmpeg_executable()
        probe_cmd = [ffmpeg_exe, "-i", str(stored_file)]
        res = subprocess.run(probe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        probe_info = res.stderr.lower()

        # Must be H.264 / avc1
        self.assertTrue(
            "h264" in probe_info or "avc1" in probe_info,
            "Video stream must be encoded in H.264 / avc1",
        )

        # Must NOT be mp4v / mpeg4
        self.assertNotIn(
            "mp4v",
            probe_info,
            "Video stream must NOT contain mp4v codec",
        )
        self.assertNotIn(
            "mpeg4 (simple profile)",
            probe_info,
            "Video stream must NOT be MPEG-4 Part 2",
        )

        # Must be yuv420p for universal HTML5 browser decode
        self.assertIn(
            "yuv420p",
            probe_info,
            "Video stream pixel format must be yuv420p for broad browser playback",
        )


if __name__ == "__main__":
    unittest.main()
