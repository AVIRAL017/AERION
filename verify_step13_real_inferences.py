import asyncio
import base64
import json
import time
from pathlib import Path
from fastapi.testclient import TestClient

from app.core.auth import create_access_token
from app.core.config import AERIONSettings
from app.main import create_app

def run_real_e2e_validations():
    settings = AERIONSettings(ENVIRONMENT="test")
    app = create_app(settings=settings)
    client = TestClient(app)

    token = create_access_token({
        "sub": "e2e-operator-uuid",
        "org": "e2e-org-uuid",
        "role": "operator",
        "email": "operator@aerion.mil",
    })
    headers = {"Authorization": f"Bearer {token}"}

    results = {}

    # -------------------------------------------------------------
    # 1. REAL DRONE IMAGE (VisDrone validation image)
    # -------------------------------------------------------------
    drone_img_path = Path(r"C:\Users\avira\yolo_project\datasets\VisDrone\images\val\0000001_02999_d_0000005.jpg")
    print(f"\n[1/4] Testing REAL Drone Image: {drone_img_path.name}")
    if not drone_img_path.exists():
        raise FileNotFoundError(f"Drone image not found: {drone_img_path}")

    with open(drone_img_path, "rb") as f:
        drone_b64 = base64.b64encode(f.read()).decode("utf-8")

    t0 = time.perf_counter()
    res = client.post(
        "/api/v1/analysis/image",
        json={
            "image_base64": drone_b64,
            "source_type": "drone",
            "mode": "border",
            "drone_model": "visdrone_only",
            "confidence_threshold": 0.25,
            "run_intelligence": True,
        },
        headers=headers,
    )
    t_drone = (time.perf_counter() - t0) * 1000.0
    print(f"Drone HTTP Status: {res.status_code}, Elapsed: {t_drone:.1f}ms")
    drone_json = res.json()
    assert res.status_code == 200 and drone_json["success"] is True
    detections = drone_json["data"]["detections"]
    print(f"Detected {len(detections)} targets in real VisDrone frame.")
    for d in detections[:3]:
        print(f"  - Class: {d['class_name']}, Conf: {d['confidence']:.2f}, Box: {d.get('bbox')}")
    results["drone"] = {
        "status": res.status_code,
        "elapsed_ms": round(t_drone, 1),
        "detections_count": len(detections),
        "sample": detections[:2] if detections else [],
    }

    # -------------------------------------------------------------
    # 2. REAL SATELLITE IMAGE (DOTA OBB validation tile)
    # -------------------------------------------------------------
    sat_img_path = Path(r"C:\Users\avira\yolo_project\datasets\DOTAv1.5-split\images\val\P0003__1024__0___0.jpg")
    print(f"\n[2/4] Testing REAL Satellite Image: {sat_img_path.name}")
    if not sat_img_path.exists():
        raise FileNotFoundError(f"Satellite image not found: {sat_img_path}")

    with open(sat_img_path, "rb") as f:
        sat_b64 = base64.b64encode(f.read()).decode("utf-8")

    t0 = time.perf_counter()
    res = client.post(
        "/api/v1/analysis/image",
        json={
            "image_base64": sat_b64,
            "source_type": "satellite",
            "mode": "border",
            "run_intelligence": True,
        },
        headers=headers,
    )
    t_sat = (time.perf_counter() - t0) * 1000.0
    print(f"Satellite HTTP Status: {res.status_code}, Elapsed: {t_sat:.1f}ms")
    sat_json = res.json()
    assert res.status_code == 200 and sat_json["success"] is True
    sat_dets = sat_json["data"]["detections"]
    print(f"Detected {len(sat_dets)} OBB targets in DOTA tile.")
    for d in sat_dets[:3]:
        print(f"  - Class: {d['class_name']}, Conf: {d['confidence']:.2f}, OBB: {d.get('obb_points')}")
    results["satellite"] = {
        "status": res.status_code,
        "elapsed_ms": round(t_sat, 1),
        "detections_count": len(sat_dets),
        "sample": sat_dets[:2] if sat_dets else [],
    }

    # -------------------------------------------------------------
    # 3. REAL BI-TEMPORAL DAMAGE PAIR (xBD Guatemala Volcano)
    # -------------------------------------------------------------
    dmg_before_path = Path(r"D:\mp-1\xBD_damage_processed_v2\val\before\guatemala-volcano_00000000_0000.png")
    dmg_after_path = Path(r"D:\mp-1\xBD_damage_processed_v2\val\after\guatemala-volcano_00000000_0000.png")
    print(f"\n[3/4] Testing REAL Damage Pair: {dmg_before_path.name}")
    if not (dmg_before_path.exists() and dmg_after_path.exists()):
        raise FileNotFoundError(f"Damage pair images missing")

    with open(dmg_before_path, "rb") as f:
        before_b64 = base64.b64encode(f.read()).decode("utf-8")
    with open(dmg_after_path, "rb") as f:
        after_b64 = base64.b64encode(f.read()).decode("utf-8")

    t0 = time.perf_counter()
    res = client.post(
        "/api/v1/analysis/damage",
        json={
            "before_base64": before_b64,
            "after_base64": after_b64,
            "threshold": 0.50,
            "run_intelligence": True,
        },
        headers=headers,
    )
    t_dmg = (time.perf_counter() - t0) * 1000.0
    print(f"Damage HTTP Status: {res.status_code}, Elapsed: {t_dmg:.1f}ms")
    dmg_json = res.json()
    assert res.status_code == 200 and dmg_json["success"] is True
    dmg_analysis = dmg_json["data"]["damage_analysis"]
    print(f"Damage result: percentage={dmg_analysis['damage_percentage']:.2f}%, damaged_pixels={dmg_analysis['damage_pixels']}, mean_prob={dmg_analysis['probability_mean']:.4f}")
    results["damage"] = {
        "status": res.status_code,
        "elapsed_ms": round(t_dmg, 1),
        "damage_percentage": dmg_analysis["damage_percentage"],
        "damaged_pixels": dmg_analysis["damage_pixels"],
        "mean_probability": dmg_analysis["probability_mean"],
    }

    # -------------------------------------------------------------
    # 4. REAL BORDER VIDEO (Small sample: 10 frames, stride=5)
    # -------------------------------------------------------------
    video_path = Path(r"D:\mp-1\border_test_videos\border_test_urban.mp4.mp4")
    print(f"\n[4/4] Testing REAL Border Video: {video_path.name}")
    if not video_path.exists():
        raise FileNotFoundError(f"Video file missing: {video_path}")

    t0 = time.perf_counter()
    res = client.post(
        "/api/v1/analysis/border/video",
        json={
            "video_path": str(video_path),
            "max_frames": 10,
            "frame_stride": 5,
            "terrain_context": "arid",
        },
        headers=headers,
    )
    t_vid = (time.perf_counter() - t0) * 1000.0
    print(f"Border Video HTTP Status: {res.status_code}, Elapsed: {t_vid:.1f}ms")
    vid_json = res.json()
    assert res.status_code == 200 and vid_json["success"] is True
    report = vid_json["data"]["report"]
    print(f"Video report: processed_frames={vid_json['data']['processed_frames']}, active_tracks={report.get('active_tracks_count', 0)}")
    results["video"] = {
        "status": res.status_code,
        "elapsed_ms": round(t_vid, 1),
        "processed_frames": vid_json["data"]["processed_frames"],
        "total_video_frames": vid_json["data"]["total_video_frames"],
        "report_summary": report.get("executive_summary", "")[:100],
    }

    print("\n--- SUMMARY OF REAL INFERENCE VALIDATIONS ---")
    print(json.dumps(results, indent=2))
    return results

if __name__ == "__main__":
    run_real_e2e_validations()
