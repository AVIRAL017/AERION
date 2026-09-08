"""
AERION v1 — Drone Detector Real Inference Test

Tests the frozen drone_detector.py adapter against one real
VisDrone validation image.

This test:
    - uses a real dataset image
    - loads the frozen model through the adapter
    - performs real inference
    - verifies the AERION result contract
    - prints actual detections

This test does NOT:
    - train
    - modify model weights
    - generate fake detections
    - generate fake confidence values
"""

from pathlib import Path

from drone_detector import DroneDetector


# ================================================================
# CONFIGURATION
# ================================================================

VISDRONE_VAL = Path(
    r"C:\Users\avira\yolo_project\datasets\VisDrone\images\val"
)


# ================================================================
# FIND REAL IMAGE
# ================================================================

def find_test_image() -> Path:

    if not VISDRONE_VAL.exists():
        raise FileNotFoundError(
            f"VisDrone validation directory not found:\n"
            f"{VISDRONE_VAL}"
        )

    supported_extensions = {
        ".jpg",
        ".jpeg",
        ".png",
        ".bmp",
    }

    images = sorted(
        path
        for path in VISDRONE_VAL.iterdir()
        if path.is_file()
        and path.suffix.lower() in supported_extensions
    )

    if not images:
        raise RuntimeError(
            f"No validation images found in:\n"
            f"{VISDRONE_VAL}"
        )

    return images[0]


# ================================================================
# TEST
# ================================================================

def main():

    print("=" * 72)
    print("AERION v1 — DRONE DETECTOR REAL INFERENCE TEST")
    print("=" * 72)

    image_path = find_test_image()

    print("\nReal test image:")
    print(image_path)

    print("\nLoading frozen VisDrone-only detector...")

    detector = DroneDetector(
        model_name="visdrone_only",
        device=0,
        confidence=0.25,
        iou=0.50,
        imgsz=1280,
        agnostic_nms=True,
    )

    print("[OK] Detector loaded")

    # ============================================================
    # REAL INFERENCE
    # ============================================================

    print("\nRunning real inference...")

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
    # DETECTION VALIDATION
    # ============================================================

    allowed_classes = {
        "person",
        "light_vehicle",
        "bus",
        "truck",
        "motorbike",
        "other_transport",
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

        if len(detection.bbox) != 4:
            raise RuntimeError(
                f"Detection {index} has invalid bbox."
            )

        x1, y1, x2, y2 = detection.bbox

        if x2 < x1 or y2 < y1:
            raise RuntimeError(
                f"Detection {index} has invalid bbox coordinates: "
                f"{detection.bbox}"
            )

    # ============================================================
    # REPORT
    # ============================================================

    print("\n" + "=" * 72)
    print("REAL INFERENCE RESULT")
    print("=" * 72)

    print(f"\nImage size:")
    print(f"  Width  : {result.image_width}")
    print(f"  Height : {result.image_height}")

    print(f"\nModel:")
    print(f"  {result.model}")

    print(f"\nDetection count:")
    print(f"  {result.detection_count}")

    if result.detections:

        print("\nDetections:")

        for index, detection in enumerate(
            result.detections,
            start=1
        ):

            print(
                f"  {index:02d}. "
                f"{detection.class_name:<20} "
                f"conf={detection.confidence:.3f} "
                f"bbox=["
                f"{detection.bbox[0]:.1f}, "
                f"{detection.bbox[1]:.1f}, "
                f"{detection.bbox[2]:.1f}, "
                f"{detection.bbox[3]:.1f}"
                f"]"
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

    print("\n" + "=" * 72)
    print("DRONE DETECTOR REAL INFERENCE TEST PASSED")
    print("=" * 72)

    print("\nVerified:")
    print("  [OK] Real dataset image")
    print("  [OK] Frozen model inference")
    print("  [OK] Image dimensions")
    print("  [OK] Detection objects")
    print("  [OK] Class mapping")
    print("  [OK] Confidence values")
    print("  [OK] Bounding boxes")
    print("  [OK] Detection count")
    print("  [OK] Result serialization")

    print("\nNo model files were modified.")
    print("No training was performed.")


if __name__ == "__main__":
    main()