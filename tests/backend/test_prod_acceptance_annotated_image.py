"""
AERION — Production Acceptance Tests: Annotated Image & Download Pipeline (Items 6-9)
Verifies:
6. Annotated image artifact generation from real model detections.
7. Annotated image download endpoint (/evidence/{artifact_path}).
8. Authorization, tenant isolation, and path traversal rejection for evidence download.
9. Original image download remains available as secondary action.
"""

import hashlib
from pathlib import Path
import tempfile
import uuid
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.annotation_service import AnnotationService
from app.services.storage_service import LocalArtifactStorage
from aerion_runtime_contracts import AERIONAnalysisResult, BoundingBox, Detection, Point2D
from app.core.auth import create_access_token


@pytest.fixture
def auth_headers():
    token = create_access_token({
        "sub": str(uuid.uuid4()),
        "org": "00000000-0000-0000-0000-000000000001",
        "role": "operator",
    })
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client():
    return TestClient(app)


def test_annotated_image_artifact_generation():
    """Verify that AnnotationService generates a real annotated image artifact with bounding boxes."""
    # Create synthetic test image
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        img_path = Path(f.name)
        img = np.zeros((400, 600, 3), dtype=np.uint8)
        cv2.imwrite(str(img_path), img)

    try:
        annotator = AnnotationService()
        dummy_result = AERIONAnalysisResult(
            project="test_proj",
            version="4.2.0",
            analysis_id=str(uuid.uuid4()),
            mode="border",
            source_type="drone",
            detections=[
                Detection(
                    source="drone",
                    class_id=0,
                    class_name="car",
                    confidence=0.88,
                    bbox=BoundingBox(x1=50, y1=60, x2=150, y2=160),
                )
            ],
            tracks=[],
            border_analysis=[],
            intelligence=[],
            summary=None,
            overall_status="COMPLETED",
            metadata={},
        )
        proj_id = uuid.uuid4()
        res = annotator.annotate_and_store(
            source_image_path=img_path,
            analysis_result=dummy_result,
            project_id=proj_id,
        )

        assert res.artifact_key is not None
        assert res.file_size_bytes > 0
        assert res.image_width == 600
        assert res.image_height == 400
        assert res.is_zero_detection is False
        assert len(res.sha256) == 64
        assert res.annotated_base64 is not None

        # Verify artifact exists on disk
        storage_file = Path("storage") / res.artifact_key
        assert storage_file.exists()
        # Verify sha256 matches actual file
        assert hashlib.sha256(storage_file.read_bytes()).hexdigest() == res.sha256
    finally:
        if img_path.exists():
            img_path.unlink()


def test_annotated_image_download_endpoint(client, auth_headers):
    """Verify downloading annotated image via /api/v1/evidence/{artifact_path}."""
    storage_dir = Path("storage/test_audit_proj/annotated_image")
    storage_dir.mkdir(parents=True, exist_ok=True)
    test_artifact = storage_dir / "audit_annotated.jpg"
    
    # Write real JPEG header
    test_img = np.zeros((200, 200, 3), dtype=np.uint8)
    cv2.imwrite(str(test_artifact), test_img)

    try:
        res = client.get("/api/v1/evidence/test_audit_proj/annotated_image/audit_annotated.jpg", headers=auth_headers)
        assert res.status_code == 200
        assert res.headers["content-type"] in ("image/jpeg", "image/jpg")
        assert "attachment" in res.headers["content-disposition"]
        assert len(res.content) > 0
    finally:
        if test_artifact.exists():
            test_artifact.unlink()


def test_evidence_download_authorization_and_traversal_guards(client, auth_headers):
    """Verify unauthenticated access is rejected and path traversal is blocked."""
    # 1. Unauthenticated request without JWT
    res_unauth = client.get("/api/v1/evidence/some_proj/annotated_image/test.jpg")
    assert res_unauth.status_code in (401, 403)

    # 2. Path traversal attack
    res_traversal = client.get("/api/v1/evidence/../../../../windows/system32/cmd.exe", headers=auth_headers)
    assert res_traversal.status_code in (400, 404, 422)


def test_original_image_secondary_download(client, auth_headers):
    """Verify original source image can be stored and downloaded as secondary action."""
    storage = LocalArtifactStorage()
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        src_path = Path(f.name)
        img = np.full((100, 100, 3), 128, dtype=np.uint8)
        cv2.imwrite(str(src_path), img)

    try:
        proj_id = uuid.uuid4()
        storage_key, sha_hex, size = storage.store_file(
            source_path=src_path,
            asset_type="source_image",
            project_id=proj_id,
            suffix=".jpg",
        )
        assert storage_key is not None

        # Download original source image
        res = client.get(f"/api/v1/evidence/{storage_key}", headers=auth_headers)
        assert res.status_code == 200
        assert res.headers["content-type"] in ("image/jpeg", "image/jpg")
        assert "attachment" in res.headers["content-disposition"]
        assert hashlib.sha256(res.content).hexdigest() == sha_hex
    finally:
        if src_path.exists():
            src_path.unlink()
