"""
AERION v1 — Satellite Detector Real Inference Test

Tests satellite_detector.py against a real DOTA-v1.5
validation tile.

This test performs real inference using the frozen
YOLOv8n-OBB model.

No training.
No synthetic data.
No model modification.
"""

from pathlib import Path

from satellite_detector import SatelliteDetector


# ================================================================
# REAL DOTA VALIDATION DATASET
# ================================================================

DOTA_VAL = Path(
    r"C:\Users\avira\yolo_project\datasets\DOTAv1.5-split\images\val"
)


# ================================================================
# FIND REAL VALIDATION TILE
# ================================================================

def find_test_image() -> Path:

    if not DOTA_VAL.exists():
        raise FileNotFoundError(
            f"DOTA validation directory not found:\n{DOTA_VAL}"
        )

    extensions = {
        ".jpg",
        ".jpeg",
        ".png",
        ".bmp",
    }

    images = sorted(
        path
        for path in DOTA_VAL.iterdir()
        if path.is_file()
        and path.suffix.lower() in extensions
    )

    if not images:
        raise RuntimeError(
            f"No DOTA validation images found in:\n{DOTA_VAL}"
        )

    return images[0]


# ================================================================
# MAIN TEST
# ================================================================

def main():

    print("=" * 72)
    print("AERION v1 — SATELLITE DETECTOR REAL INFERENCE TEST")
    print("=" * 72)

    image_path = find_test_image()

    print("\nReal DOTA validation tile:")
    print(image_path)

    print("\nLoading frozen satellite detector...")

    detector = SatelliteDetector(
        device=0,
        confidence=0.25,
        iou=0.50,
        imgsz=1024,
    )

    print("[OK] Detector loaded")

    # ============================================================
    # REAL INFERENCE
    # ============================================================

    print("\nRunning real OBB inference...")

    result = detector.detect(image_path)

    # ============================================================
    # RESULT CONTRACT VALIDATION
    # ============================================================

    if not isinstance(result.detection_count, int):
        raise RuntimeError(
            "detection_count is not an integer."
        )

    if result.detection_count != len(result.detections):
        raise RuntimeError(
            "detection_count does not match detections list."
        )

    if result.image_width <= 0:
        raise RuntimeError(
            "Invalid image width returned by adapter."
        )

    if result.image_height <= 0:
        raise RuntimeError(
            "Invalid image height returned by adapter."
        )

    # ============================================================
    # VALIDATE OBB DETECTIONS
    # ============================================================

    allowed_classes = {
        "plane",
        "ship",
        "storage_tank",
        "baseball_diamond",
        "tennis_court",
        "basketball_court",
        "ground_track_field",
        "harbor",
        "bridge",
        "large_vehicle",
        "small_vehicle",
        "helicopter",
        "roundabout",
        "soccer_ball_field",
        "swimming_pool",
        "container_crane",
    }

    for index, detection in enumerate(result.detections):

        if detection.class_name not in allowed_classes:
            raise RuntimeError(
                f"Detection {index} returned unexpected class: "
                f"{detection.class_name}"
            )

        if not 0.0 <= detection.confidence <= 1.0:
            raise RuntimeError(
                f"Detection {index} has invalid confidence: "
                f"{detection.confidence}"
            )

        # OBB must contain exactly four corner points.
        if len(detection.obb_points) != 4:
            raise RuntimeError(
                f"Detection {index} does not contain exactly "
                f"4 OBB corner points: "
                f"{detection.obb_points}"
            )

        for point_index, point in enumerate(
            detection.obb_points
        ):

            if len(point) != 2:
                raise RuntimeError(
                    f"Detection {index}, point {point_index} "
                    f"is not an (x,y) pair: {point}"
                )

            x, y = point

            if not isinstance(x, (int, float)):
                raise RuntimeError(
                    f"Invalid X coordinate: {x}"
                )

            if not isinstance(y, (int, float)):
                raise RuntimeError(
                    f"Invalid Y coordinate: {y}"
                )

    # ============================================================
    # REPORT
    # ============================================================

    print("\n" + "=" * 72)
    print("REAL SATELLITE INFERENCE RESULT")
    print("=" * 72)

    print("\nImage:")
    print(f"  Width  : {result.image_width}")
    print(f"  Height : {result.image_height}")

    print("\nModel:")
    print(f"  {result.model}")

    print("\nDetection count:")
    print(f"  {result.detection_count}")

    if result.detections:

        print("\nOBB detections:")

        for index, detection in enumerate(
            result.detections,
            start=1,
        ):

            points = " ".join(
                f"({point[0]:.1f},{point[1]:.1f})"
                for point in detection.obb_points
            )

            print(
                f"  {index:02d}. "
                f"{detection.class_name:<22} "
                f"conf={detection.confidence:.3f} "
                f"OBB={points}"
            )

    else:
        print("\nNo detections returned.")

    # ============================================================
    # SERIALIZATION TEST
    # ============================================================

    serialized = result.to_dict()

    if not isinstance(serialized, dict):
        raise RuntimeError(
            "Result serialization failed."
        )

    required_keys = {
        "model",
        "image_width",
        "image_height",
        "detections",
        "detection_count",
    }

    missing = required_keys - serialized.keys()

    if missing:
        raise RuntimeError(
            f"Serialized result missing keys: {missing}"
        )

    # Verify serialized OBB structure as well.
    for detection in serialized["detections"]:

        if len(detection["obb_points"]) != 4:
            raise RuntimeError(
                "Serialized OBB does not contain 4 points."
            )

        for point in detection["obb_points"]:
            if len(point) != 2:
                raise RuntimeError(
                    "Serialized OBB point is not [x, y]."
                )

    # ============================================================
    # SUCCESS
    # ============================================================

    print("\n" + "=" * 72)
    print("SATELLITE DETECTOR REAL INFERENCE TEST PASSED")
    print("=" * 72)

    print("\nVerified:")
    print("  [OK] Real DOTA-v1.5 validation tile")
    print("  [OK] Frozen YOLOv8n-OBB inference")
    print("  [OK] Image dimensions")
    print("  [OK] Satellite class mapping")
    print("  [OK] Confidence values")
    print("  [OK] Four-point OBB geometry")
    print("  [OK] Detection count")
    print("  [OK] Result serialization")

    print("\nNo model files were modified.")
    print("No training was performed.")


if __name__ == "__main__":
    main()