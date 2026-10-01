"""
AERION — Evidence Range Requests & Partial Content Acceptance Suite
Verifies that the /api/v1/evidence endpoint satisfies HTTP 206 Partial Content requirements for video streaming:
- Range: bytes=0-1024
  -> HTTP 206 Partial Content
  -> Content-Range: bytes 0-1024/{total_bytes}
  -> Content-Type: video/mp4
  -> Accept-Ranges: bytes
  -> Exact byte integrity matching the stored artifact
- Preserves authentication and tenant isolation
"""

import hashlib
import os
import shutil
import tempfile
import uuid
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.core.auth import create_access_token
from app.main import app
from app.services.storage_service import LocalArtifactStorage
from app.services.video_annotation_service import VideoAnnotationService


@pytest.fixture
def test_client():
    return TestClient(app)


@pytest.fixture
def auth_headers():
    token = create_access_token(data={"sub": "range-test-user", "role": "admin"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_video_artifact(tmp_path):
    """Generates and stores an authenticated web-playable MP4 video artifact."""
    storage = LocalArtifactStorage()
    service = VideoAnnotationService(storage=storage)
    proj_id = uuid.uuid4()

    # Create temporary intermediate video
    raw_path = tmp_path / "raw_intermediate.mp4"
    width, height, fps = 320, 240, 10.0
    writer = service.create_video_writer(raw_path, fps=fps, width=width, height=height)
    for i in range(15):
        frame = np.full((height, width, 3), (i * 15) % 255, dtype=np.uint8)
        writer.write(frame)
    writer.release()

    res = service.finalize_and_store(
        temp_video_path=raw_path,
        project_id=proj_id,
        width=width,
        height=height,
        fps=fps,
        frame_count=15,
        source_frame_count=15,
        unique_tracks=1,
        total_detections=15,
    )
    return res, storage


class TestEvidenceRangeRequests:
    """Verifies RFC 7233 range requests on the evidence video endpoint."""

    def test_full_get_returns_accept_ranges_and_video_mime(
        self, test_client, auth_headers, sample_video_artifact
    ):
        artifact_res, storage = sample_video_artifact
        storage_key = artifact_res.artifact_key

        url = f"/api/v1/evidence/{storage_key}?download=false"
        resp = test_client.get(url, headers=auth_headers)

        assert resp.status_code == 200
        assert resp.headers["content-type"] == "video/mp4"
        assert resp.headers.get("accept-ranges") == "bytes"
        assert int(resp.headers["content-length"]) == artifact_res.file_size_bytes
        assert len(resp.content) == artifact_res.file_size_bytes

    def test_range_bytes_0_to_1024_returns_206_partial_content(
        self, test_client, auth_headers, sample_video_artifact
    ):
        """
        Verify:
        Range: bytes=0-1024
        -> HTTP 206
        -> correct Content-Range
        -> video/mp4
        -> Accept-Ranges: bytes
        """
        artifact_res, storage = sample_video_artifact
        storage_key = artifact_res.artifact_key
        total_bytes = artifact_res.file_size_bytes
        assert total_bytes > 1024, "Artifact must be larger than 1024 bytes for range test"

        headers = {
            **auth_headers,
            "Range": "bytes=0-1024",
        }
        url = f"/api/v1/evidence/{storage_key}?download=false"
        resp = test_client.get(url, headers=headers)

        assert resp.status_code == 206
        assert resp.headers["content-type"] == "video/mp4"
        assert resp.headers.get("accept-ranges") == "bytes"
        assert resp.headers.get("content-range") == f"bytes 0-1024/{total_bytes}"
        assert int(resp.headers["content-length"]) == 1025
        assert len(resp.content) == 1025

        # Verify byte contents match exactly the first 1025 bytes on disk
        stored_file_path = storage.root_dir / storage_key
        with open(stored_file_path, "rb") as f:
            expected_bytes = f.read(1025)
        assert resp.content == expected_bytes

    def test_arbitrary_mid_stream_range_request(
        self, test_client, auth_headers, sample_video_artifact
    ):
        artifact_res, storage = sample_video_artifact
        storage_key = artifact_res.artifact_key
        total_bytes = artifact_res.file_size_bytes

        headers = {
            **auth_headers,
            "Range": "bytes=200-500",
        }
        url = f"/api/v1/evidence/{storage_key}?download=false"
        resp = test_client.get(url, headers=headers)

        assert resp.status_code == 206
        assert resp.headers["content-type"] == "video/mp4"
        assert resp.headers.get("content-range") == f"bytes 200-500/{total_bytes}"
        assert int(resp.headers["content-length"]) == 301
        assert len(resp.content) == 301

        stored_file_path = storage.root_dir / storage_key
        with open(stored_file_path, "rb") as f:
            f.seek(200)
            expected_bytes = f.read(301)
        assert resp.content == expected_bytes

    def test_unauthenticated_range_request_rejected(
        self, test_client, sample_video_artifact
    ):
        artifact_res, _ = sample_video_artifact
        url = f"/api/v1/evidence/{artifact_res.artifact_key}"
        resp = test_client.get(url, headers={"Range": "bytes=0-1024"})
        assert resp.status_code in (401, 403)
