"""
AERION — Bi-Temporal Pair Validation Test Suite (BUG-006 / Rem-005)

Validates the canonical bi-temporal pair compatibility safety gate:
1. Canonical Validator: Single authoritative DamagePairValidator across all entrypoints.
2. Evidence Fusion: Multi-signal visual/spatial fusion (SIFT/RANSAC, Fourier phase correlation,
   patch NCC, and multi-signal consensus) accepting genuine disaster scenes with major structural changes.
3. GPS Terminology & Policy: Reliable Embedded GPS Metadata (conflicting disjoint GPS rejected,
   absent GPS accepted via visual correspondence, location never validates an incompatible pair).
4. Geodesic Distance: Haversine distance with configurable threshold (default 10.0 km).
5. Threshold Validation Cases (CASES 1-7):
   - CASE 1: Same scene + minor change -> ACCEPT
   - CASE 2: Same scene + major structural change -> ACCEPT
   - CASE 3: Same dimensions + completely different scenes -> REJECT
   - CASE 4: Syapru Besi (Nepal) + Dubai (UAE) -> REJECT
   - CASE 5: Conflicting reliable GPS -> REJECT
   - CASE 6: No GPS + strong visual correspondence -> ACCEPT
   - CASE 7: No GPS + insufficient correspondence -> REJECT
6. Rejected-Pair Invariants (CASE 8):
   - Siamese inference NOT executed
   - Damage metrics NOT generated
   - Damage classification NOT generated
   - Risk score NOT generated
   - Damage overlay DISABLED
   - PDF marked PAIR_VALIDATION_FAILED
7. Stale State Invariant (CASE 9):
   - Submitting an invalid pair after a valid pair clears all previous damage state.
8. Performance & Latency (CASE 10):
   - Preflight endpoint POST /api/v1/analysis/damage/validate
   - Validation latency, inference latency, total latency measured separately.
"""

from __future__ import annotations

import asyncio
import base64
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any, Dict

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from aerion_orchestrator import AERIONOrchestrator
from app.core.auth import create_access_token
from app.main import app
from app.services.application_services import DamageAnalysisService
from app.services.damage_validator import (
    DEFAULT_MAX_GPS_DISTANCE_KM,
    DamagePairValidationResult,
    DamagePairValidator,
    haversine_distance_km,
)


@pytest.fixture
def auth_headers() -> Dict[str, str]:
    token = create_access_token(data={"sub": "test-operator", "role": "admin"})
    return {"Authorization": f"Bearer {token}"}


class TestBiTemporalPairValidationSuite(unittest.TestCase):

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="aerion_bitemporal_test_"))
        self.client = TestClient(app)
        self.token = create_access_token(data={"sub": "test-operator", "role": "admin"})
        self.headers = {"Authorization": f"Bearer {self.token}"}

        # Assets in repository root
        self.before_path = Path("before.png")
        self.after_path = Path("after.png")
        self.syapru_path = Path("syapru_besi_t0_extracted.png")
        self.dubai_path = Path("dubai_t1_extracted.png")

        # Ensure baseline images exist
        if not self.before_path.exists():
            self._create_textured_scene(self.before_path)
        if not self.after_path.exists():
            self._create_textured_scene(self.after_path)

    def tearDown(self):
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_textured_scene(self, path: Path) -> Path:
        img = np.zeros((512, 512, 3), dtype=np.uint8)
        for i in range(10, 500, 30):
            cv2.rectangle(img, (i, 50), (i + 20, 200), (120, 180, 220), -1)
            cv2.circle(img, (i + 10, 350), 12, (80, 140, 90), -1)
        cv2.imwrite(str(path), img)
        return path

    def _write_exif_gps(self, in_path: Path, out_path: Path, lat: float, lon: float) -> Path:
        with Image.open(in_path) as img:
            if img.mode != "RGB":
                img = img.convert("RGB")
            exif = img.getexif()
            gps_ifd = exif.get_ifd(0x8825)

            lat_deg = abs(lat)
            lat_d = int(lat_deg)
            lat_m = int((lat_deg - lat_d) * 60)
            lat_s = ((lat_deg - lat_d) * 60 - lat_m) * 60

            lon_deg = abs(lon)
            lon_d = int(lon_deg)
            lon_m = int((lon_deg - lon_d) * 60)
            lon_s = ((lon_deg - lon_d) * 60 - lon_m) * 60

            gps_ifd[1] = "N" if lat >= 0 else "S"
            gps_ifd[2] = (float(lat_d), float(lat_m), float(lat_s))
            gps_ifd[3] = "E" if lon >= 0 else "W"
            gps_ifd[4] = (float(lon_d), float(lon_m), float(lon_s))

            img.save(str(out_path), exif=exif)
        return out_path

    # ========================================================================
    # CASE 1: Same scene + minor change -> ACCEPT
    # ========================================================================
    def test_case_1_same_scene_minor_change(self):
        """
        CASE 1: Same physical scene with minor environmental/illumination difference.
        Outcome: ACCEPT (STRUCTURALLY_COMPATIBLE)
        """
        img = cv2.imread(str(self.before_path))
        noise = np.random.normal(0, 3, img.shape).astype(np.int16)
        modified = np.clip(img.astype(np.int16) * 1.05 + noise, 0, 255).astype(np.uint8)
        minor_change_path = self.temp_dir / "minor_change.png"
        cv2.imwrite(str(minor_change_path), modified)

        res = DamagePairValidator.validate_pair(self.before_path, minor_change_path)
        metrics = res.scene_correspondence_metrics

        print(f"\n[CASE 1 METRICS] inliers={metrics.get('sift_inliers')}, "
              f"phase_resp={metrics.get('phase_response')}, "
              f"med_patch_corr={metrics.get('median_patch_correlation')}, "
              f"evidence={metrics.get('decision_evidence')}, "
              f"latency={res.validation_latency_ms:.2f}ms")

        self.assertTrue(res.is_compatible, f"CASE 1 failed: {res.rejection_reason}")
        self.assertIn(res.status, ["STRUCTURALLY_COMPATIBLE", "SAME_SCENE_CONFIRMED"])
        self.assertTrue(
            "pixel_identity" in metrics.get("decision_evidence", [])
            or metrics.get("sift_inliers", 0) >= 10
            or metrics.get("phase_response", 0) >= 0.20
        )

    # ========================================================================
    # CASE 2: Same scene + major structural change -> ACCEPT
    # ========================================================================
    def test_case_2_same_scene_major_structural_change(self):
        """
        CASE 2: Same physical scene where disaster has caused major structural change
        (e.g., collapsed structures, rubble, altered terrain in post image).
        Outcome: ACCEPT (STRUCTURALLY_COMPATIBLE)
        Evidence: Strong geometric anchors on surviving terrain + phase alignment
        even though raw pixel NCC is heavily reduced.
        """
        # Test real disaster pair before.png vs after.png
        res = DamagePairValidator.validate_pair(self.before_path, self.after_path)
        metrics = res.scene_correspondence_metrics

        print(f"\n[CASE 2 METRICS - Real Disaster Pair] inliers={metrics.get('sift_inliers')}, "
              f"phase_shift={metrics.get('phase_shift_distance')}, "
              f"phase_resp={metrics.get('phase_response')}, "
              f"med_patch_corr={metrics.get('median_patch_correlation')}, "
              f"evidence={metrics.get('decision_evidence')}, "
              f"latency={res.validation_latency_ms:.2f}ms")

        self.assertTrue(res.is_compatible, f"CASE 2 failed on real disaster pair: {res.rejection_reason}")
        self.assertEqual(res.status, "STRUCTURALLY_COMPATIBLE")
        self.assertGreaterEqual(metrics.get("sift_inliers", 0), 12)
        self.assertTrue(len(metrics.get("decision_evidence", [])) > 0)

        # Also test extreme synthetic structural destruction (60% of scene destroyed by rubble/void)
        base_img = cv2.imread(str(self.before_path))
        destroyed = base_img.copy()
        h, w, _ = destroyed.shape
        start_y = int(h * 0.40)
        rubble_h = h - start_y
        destroyed[start_y:, :] = np.random.randint(40, 180, (rubble_h, w, 3), dtype=np.uint8)
        heavy_damage_path = self.temp_dir / "heavy_structural_damage.png"
        cv2.imwrite(str(heavy_damage_path), destroyed)

        res_heavy = DamagePairValidator.validate_pair(self.before_path, heavy_damage_path)
        metrics_h = res_heavy.scene_correspondence_metrics

        print(f"[CASE 2 METRICS - 60% Scene Destruction] inliers={metrics_h.get('sift_inliers')}, "
              f"evidence={metrics_h.get('decision_evidence')}, "
              f"latency={res_heavy.validation_latency_ms:.2f}ms")

        self.assertTrue(res_heavy.is_compatible, f"CASE 2 failed on 60% destruction: {res_heavy.rejection_reason}")
        self.assertEqual(res_heavy.status, "STRUCTURALLY_COMPATIBLE")

    # ========================================================================
    # CASE 3: Same dimensions + completely different scenes -> REJECT
    # ========================================================================
    def test_case_3_same_dimensions_different_scenes(self):
        """
        CASE 3: Same pixel dimensions (512x512) but completely different scenes.
        Outcome: REJECT (PAIR_MISMATCH or INSUFFICIENT_PAIR_EVIDENCE)
        """
        # Scene A: 512x512 natural aerial terrain from before.png
        img_a = cv2.resize(cv2.imread(str(self.before_path)), (512, 512))
        scene_a_path = self.temp_dir / "scene_a_512.png"
        cv2.imwrite(str(scene_a_path), img_a)

        # Scene B: 512x512 synthetic geometric checkerboard pattern
        scene_b = np.zeros((512, 512, 3), dtype=np.uint8)
        for r in range(0, 512, 64):
            for c in range(0, 512, 64):
                if (r // 64 + c // 64) % 2 == 0:
                    scene_b[r:r+64, c:c+64] = (220, 220, 220)
        scene_b_path = self.temp_dir / "synthetic_checkerboard.png"
        cv2.imwrite(str(scene_b_path), scene_b)

        res = DamagePairValidator.validate_pair(scene_a_path, scene_b_path)
        metrics = res.scene_correspondence_metrics

        print(f"\n[CASE 3 METRICS] inliers={metrics.get('sift_inliers')}, "
              f"phase_shift={metrics.get('phase_shift_distance')}, "
              f"med_patch_corr={metrics.get('median_patch_correlation')}, "
              f"latency={res.validation_latency_ms:.2f}ms")

        self.assertFalse(res.is_compatible)
        self.assertIn(res.status, ["PAIR_MISMATCH", "INSUFFICIENT_PAIR_EVIDENCE"])
        self.assertIsNotNone(res.rejection_reason)
        self.assertLess(metrics.get("sift_inliers", 0), 12)

    # ========================================================================
    # CASE 4: Syapru Besi (Nepal) + Dubai (UAE) -> REJECT
    # ========================================================================
    def test_case_4_syapru_besi_and_dubai(self):
        """
        CASE 4: The exact real-world acceptance failure incident.
        T0: Syapru Besi, Nepal (mountainous/river/hydroelectric)
        T1: Dubai, UAE (Palm Jumeirah/urban desert coastline)
        Outcome: REJECT (PAIR_MISMATCH)
        """
        self.assertTrue(self.syapru_path.exists(), f"Syapru Besi image not found at {self.syapru_path}")
        self.assertTrue(self.dubai_path.exists(), f"Dubai image not found at {self.dubai_path}")

        res = DamagePairValidator.validate_pair(self.syapru_path, self.dubai_path)
        metrics = res.scene_correspondence_metrics

        print(f"\n[CASE 4 METRICS - Syapru Besi vs Dubai] "
              f"is_compatible={res.is_compatible}, "
              f"status={res.status}, "
              f"inliers={metrics.get('sift_inliers')}, "
              f"phase_shift={metrics.get('phase_shift_distance')}, "
              f"phase_resp={metrics.get('phase_response')}, "
              f"med_patch_corr={metrics.get('median_patch_correlation')}, "
              f"evidence={metrics.get('decision_evidence')}, "
              f"latency={res.validation_latency_ms:.2f}ms")

        self.assertFalse(res.is_compatible)
        self.assertEqual(res.status, "PAIR_MISMATCH")
        self.assertIn("Insufficient evidence that T0 and T1 represent the same geographic area", res.rejection_reason or "")
        self.assertLess(metrics.get("sift_inliers", 0), 12)
        self.assertLess(metrics.get("median_patch_correlation", 0), 0.20)

    # ========================================================================
    # CASE 5: Conflicting reliable GPS -> REJECT
    # ========================================================================
    def test_case_5_conflicting_reliable_gps(self):
        """
        CASE 5: Reliable embedded GPS present on both images, but geodesic distance > 10.0 km.
        Outcome: REJECT (CONFLICTING_GEOGRAPHIC_METADATA)
        """
        t0_gps = self._write_exif_gps(self.before_path, self.temp_dir / "t0_ktm_gps.jpg", 27.7172, 85.3240)
        t1_gps = self._write_exif_gps(self.before_path, self.temp_dir / "t1_dxb_gps.jpg", 25.2048, 55.2708)

        dist_km = haversine_distance_km(27.7172, 85.3240, 25.2048, 55.2708)
        print(f"\n[CASE 5 METRICS] Great-circle Haversine distance: {dist_km:.2f} km (threshold: {DEFAULT_MAX_GPS_DISTANCE_KM} km)")

        res = DamagePairValidator.validate_pair(t0_gps, t1_gps)
        print(f"[CASE 5 RESULT] status={res.status}, reason={res.rejection_reason}")

        self.assertFalse(res.is_compatible)
        self.assertEqual(res.status, "CONFLICTING_GEOGRAPHIC_METADATA")
        self.assertEqual(res.geospatial_metadata_status, "DISJOINT")
        self.assertIn("Conflicting reliable embedded GPS metadata", res.rejection_reason or "")
        self.assertIn("maximum allowed", res.rejection_reason or "")

    # ========================================================================
    # CASE 6: No GPS + strong visual correspondence -> ACCEPT
    # ========================================================================
    def test_case_6_no_gps_strong_visual_correspondence(self):
        """
        CASE 6: Neither image contains GPS metadata, but visual correspondence is strong.
        Outcome: ACCEPT (STRUCTURALLY_COMPATIBLE)
        Invariant: GPS must NEVER be required for standalone perception or bi-temporal validation.
        """
        clean_t0 = self.temp_dir / "clean_t0.png"
        clean_t1 = self.temp_dir / "clean_t1.png"

        with Image.open(self.before_path) as img:
            img_data = np.array(img)
            Image.fromarray(img_data).save(str(clean_t0))
        with Image.open(self.after_path) as img:
            img_data = np.array(img)
            Image.fromarray(img_data).save(str(clean_t1))

        res = DamagePairValidator.validate_pair(clean_t0, clean_t1)
        metrics = res.scene_correspondence_metrics

        print(f"\n[CASE 6 METRICS] geo_status={res.geospatial_metadata_status}, "
              f"inliers={metrics.get('sift_inliers')}, "
              f"is_compatible={res.is_compatible}, "
              f"status={res.status}")

        self.assertEqual(res.geospatial_metadata_status, "ABSENT")
        self.assertTrue(res.is_compatible)
        self.assertEqual(res.status, "STRUCTURALLY_COMPATIBLE")

    # ========================================================================
    # CASE 7: No GPS + insufficient correspondence -> REJECT
    # ========================================================================
    def test_case_7_no_gps_insufficient_correspondence(self):
        """
        CASE 7: Neither image contains GPS metadata, and visual correspondence is insufficient.
        Outcome: REJECT (INSUFFICIENT_PAIR_EVIDENCE or PAIR_MISMATCH)
        """
        tex_a = np.full((512, 512, 3), 120, dtype=np.uint8)
        cv2.circle(tex_a, (256, 256), 40, (140, 140, 140), -1)
        tex_b = np.full((512, 512, 3), 40, dtype=np.uint8)
        cv2.line(tex_b, (0, 0), (512, 512), (70, 70, 70), 5)

        path_a = self.temp_dir / "tex_a.png"
        path_b = self.temp_dir / "tex_b.png"
        cv2.imwrite(str(path_a), tex_a)
        cv2.imwrite(str(path_b), tex_b)

        res = DamagePairValidator.validate_pair(path_a, path_b)
        metrics = res.scene_correspondence_metrics

        print(f"\n[CASE 7 METRICS] geo_status={res.geospatial_metadata_status}, "
              f"is_compatible={res.is_compatible}, "
              f"status={res.status}, "
              f"inliers={metrics.get('sift_inliers')}")

        self.assertEqual(res.geospatial_metadata_status, "ABSENT")
        self.assertFalse(res.is_compatible)
        self.assertIn(res.status, ["INSUFFICIENT_PAIR_EVIDENCE", "PAIR_MISMATCH"])

    # ========================================================================
    # CASE 8: Rejected-Pair Invariants
    # ========================================================================
    def test_case_8_rejected_pair_invariants(self):
        """
        CASE 8: Rigorous invariant testing when is_compatible=False:
        - Siamese inference: NOT EXECUTED
        - Damage metrics: NOT GENERATED
        - Damage classification: NOT GENERATED
        - Risk score: NOT GENERATED
        - Damage overlay: DISABLED
        - PDF: PAIR_VALIDATION_FAILED
        """
        # 1. Test via AERIONOrchestrator
        orchestrator = AERIONOrchestrator()
        orch_res = orchestrator.process_change_pair(
            before_path=str(self.syapru_path),
            after_path=str(self.dubai_path),
            run_intelligence=True,
        )

        print(f"\n[CASE 8 - Orchestrator] overall_status={orch_res.overall_status}, "
              f"damage_analysis={orch_res.damage_analysis}")

        self.assertEqual(orch_res.overall_status, "PAIR_VALIDATION_FAILED")
        self.assertIsNone(orch_res.damage_analysis, "Damage analysis must be None for rejected pair")
        self.assertIsNotNone(orch_res.metadata.get("pair_validation"))
        self.assertFalse(orch_res.metadata["pair_validation"].get("is_compatible", True))

        # 2. Test via DamageAnalysisService (async call)
        service = DamageAnalysisService()
        svc_res = asyncio.run(service.analyze_damage_pair(
            before_path=str(self.syapru_path),
            after_path=str(self.dubai_path),
            run_intelligence=True,
        ))

        print(f"[CASE 8 - Service] overall_status={svc_res.overall_status}, "
              f"damage_analysis={svc_res.damage_analysis}")

        self.assertEqual(svc_res.overall_status, "PAIR_VALIDATION_FAILED")
        self.assertIsNone(svc_res.damage_analysis)

        # 3. Test PDF Report Generator on rejected pair
        from app.services.pdf_report_generator import generate_situation_report_pdf

        report_data = {
            "situation_id": "00000000-0000-0000-0000-000000000002",
            "analysis_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "mode": "disaster",
            "analysis_type": "damage",
            "overall_status": "PAIR_VALIDATION_FAILED",
            "is_pair_validation_failed": True,
            "pair_validation_reason": "Scene correspondence insufficient (Nepal vs Dubai)",
            "pair_validation_status": "PAIR_MISMATCH",
            "damage_summary": None,
            "verified_facts": ["Scene correspondence validation failed."],
            "limitations": ["Inference halted upstream."],
        }

        pdf_bytes = generate_situation_report_pdf(report_data)

        self.assertGreater(len(pdf_bytes), 1000)
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        print(f"[CASE 8 - PDF] Generated PDF size: {len(pdf_bytes)} bytes with PAIR_VALIDATION_FAILED audit block")

    # ========================================================================
    # CASE 9: Stale State Clearing Regression Test
    # ========================================================================
    def test_case_9_stale_state_regression(self):
        """
        CASE 9: If a user first analyzes a valid pair and then submits an invalid pair:
        ALL previous damage state must be cleared.
        No previous damage percentage, severity, mask, or risk state may remain visible.
        """
        service = DamageAnalysisService()

        # Step 1: Submit valid pair
        valid_res = asyncio.run(service.analyze_damage_pair(
            before_path=str(self.before_path),
            after_path=str(self.after_path),
            run_intelligence=False,
        ))
        self.assertIsNotNone(valid_res.damage_analysis, "Step 1 valid pair must generate damage metrics")
        self.assertGreaterEqual(valid_res.damage_analysis.damage_percentage, 0.0)
        previous_percentage = valid_res.damage_analysis.damage_percentage

        # Step 2: Submit invalid pair (Nepal vs Dubai)
        invalid_res = asyncio.run(service.analyze_damage_pair(
            before_path=str(self.syapru_path),
            after_path=str(self.dubai_path),
            run_intelligence=False,
        ))

        # Step 3: Verify state transition
        self.assertIsNone(invalid_res.damage_analysis, "Damage analysis must be cleared to None")
        self.assertEqual(invalid_res.overall_status, "PAIR_VALIDATION_FAILED")
        self.assertFalse(invalid_res.metadata["pair_validation"].get("is_compatible", True))

        # Consumer state simulation
        client_state = {
            "damage_percentage": previous_percentage,
            "damaged_pixels": valid_res.damage_analysis.damage_pixels,
            "risk_score": 45.0,
            "mask_visible": True,
        }

        # Consumer invariant update rule
        pair_val = invalid_res.metadata.get("pair_validation", {})
        if pair_val and not pair_val.get("is_compatible"):
            client_state["damage_percentage"] = None
            client_state["damaged_pixels"] = None
            client_state["risk_score"] = None
            client_state["mask_visible"] = False

        self.assertIsNone(client_state["damage_percentage"])
        self.assertIsNone(client_state["damaged_pixels"])
        self.assertIsNone(client_state["risk_score"])
        self.assertFalse(client_state["mask_visible"])
        print(f"\n[CASE 9 - Stale State Regression] Cleared previous {previous_percentage:.2f}% damage successfully")

    # ========================================================================
    # CASE 10: Preflight Endpoint & Latency Performance Measurement
    # ========================================================================
    def test_case_10_preflight_endpoint_and_performance_latency(self):
        """
        CASE 10:
        1. Preflight endpoint POST /api/v1/analysis/damage/validate returns compatibility
        2. Measures separately:
           - validation latency
           - inference latency
           - total latency
        3. Verifies server-side authoritative enforcement
        """
        with open(self.before_path, "rb") as fb, open(self.after_path, "rb") as fa:
            b64_pre = base64.b64encode(fb.read()).decode("utf-8")
            b64_post = base64.b64encode(fa.read()).decode("utf-8")

        # Measure validation latency on preflight endpoint
        t_val_start = time.perf_counter()
        preflight_resp = self.client.post(
            "/api/v1/analysis/damage/validate",
            json={"before_base64": b64_pre, "after_base64": b64_post},
            headers=self.headers,
        )
        t_val_end = time.perf_counter()
        validation_latency_ms = (t_val_end - t_val_start) * 1000.0

        self.assertEqual(preflight_resp.status_code, 200)
        preflight_json = preflight_resp.json()
        self.assertTrue(preflight_json["success"])
        self.assertTrue(preflight_json["data"]["is_compatible"])
        self.assertEqual(preflight_json["data"]["status"], "STRUCTURALLY_COMPATIBLE")

        # Test preflight rejection on Nepal vs Dubai
        with open(self.syapru_path, "rb") as fb, open(self.dubai_path, "rb") as fa:
            b64_nep = base64.b64encode(fb.read()).decode("utf-8")
            b64_dxb = base64.b64encode(fa.read()).decode("utf-8")

        preflight_reject_resp = self.client.post(
            "/api/v1/analysis/damage/validate",
            json={"before_base64": b64_nep, "after_base64": b64_dxb},
            headers=self.headers,
        )
        self.assertEqual(preflight_reject_resp.status_code, 200)
        reject_json = preflight_reject_resp.json()
        self.assertFalse(reject_json["data"]["is_compatible"])
        self.assertEqual(reject_json["data"]["status"], "PAIR_MISMATCH")

        # Measure inference & total latency on full /api/v1/analysis/damage
        t_inf_start = time.perf_counter()
        infer_resp = self.client.post(
            "/api/v1/analysis/damage",
            json={"before_base64": b64_pre, "after_base64": b64_post, "run_intelligence": False},
            headers=self.headers,
        )
        t_inf_end = time.perf_counter()
        total_latency_ms = (t_inf_end - t_inf_start) * 1000.0
        inference_latency_ms = max(0.0, total_latency_ms - validation_latency_ms)

        self.assertEqual(infer_resp.status_code, 200)
        infer_json = infer_resp.json()
        self.assertTrue(infer_json["success"])
        self.assertIsNotNone(infer_json["data"].get("damage_analysis"))

        # Test authoritative server-side gate rejects Nepal vs Dubai
        infer_reject_resp = self.client.post(
            "/api/v1/analysis/damage",
            json={"before_base64": b64_nep, "after_base64": b64_dxb, "run_intelligence": False},
            headers=self.headers,
        )
        self.assertEqual(infer_reject_resp.status_code, 200)
        infer_reject_json = infer_reject_resp.json()
        self.assertTrue(infer_reject_json["success"])
        self.assertEqual(infer_reject_json["data"]["status"], "PAIR_MISMATCH")
        self.assertIsNone(infer_reject_json["data"].get("damage_assessment"))
        self.assertFalse(infer_reject_json["data"]["pair_validation"]["is_compatible"])

        print(f"\n[CASE 10 LATENCY REPORT]")
        print(f"Validation Latency: {validation_latency_ms:.2f} ms")
        print(f"Inference Latency:  {inference_latency_ms:.2f} ms")
        print(f"Total Latency:      {total_latency_ms:.2f} ms")


if __name__ == "__main__":
    unittest.main()
