from pathlib import Path
import hashlib
import json
from datetime import datetime

# ============================================================
# AERION v1 — DRONE MODEL FREEZE RECORD
# ============================================================

MODELS = {
    "drone_visdrone_only": {
        "path": Path(
            r"D:\mp-1\runs\detect\visdrone_8s_1280_30ep\weights\best.pt"
        ),
        "architecture": "YOLOv8s",
        "input_size": 1280,
        "training_dataset": "VisDrone custom 6-class",
        "classes": [
            "person",
            "light_vehicle",
            "bus",
            "truck",
            "motorbike",
            "other_transport",
        ],
        "primary_metrics": {
            "precision": 0.591,
            "recall": 0.516,
            "mAP50": 0.477,
            "mAP50_95": 0.295,
        },
        "external_validation": {
            "UAVDT": {
                "frames": 2043,
                "instances": 40423,
                "precision": 0.568,
                "recall": 0.569,
                "mAP50": 0.515,
                "mAP50_95": 0.307,
            },
            "SeaDronesSee": {
                "precision": 0.860,
                "recall": 0.765,
                "mAP50": 0.792,
                "mAP50_95": 0.475,
            },
        },
        "runtime_benchmark": {
            "video": "border_test_urban.mp4.mp4",
            "input_size": 1280,
            "frames": 725,
            "detections": 29427,
            "fps": 14.79,
            "avg_inference_ms": 41.23,
        },
    },

    "drone_unified": {
        "path": Path(
            r"D:\mp-1\runs\detect\unified_drone_20ep\weights\best.pt"
        ),
        "architecture": "YOLOv8s",
        "input_size": 1280,
        "training_dataset": "Unified VisDrone + SeaDronesSee",
        "classes": [
            "person",
            "light_vehicle",
            "bus",
            "truck",
            "motorbike",
            "other_transport",
            "boat",
            "jetski",
            "life_saving_appliance",
            "buoy",
        ],
        "primary_metrics": {
            "mAP50": 0.575,
            "mAP50_95": 0.354,
        },
        "external_validation": {
            "UAVDT": {
                "frames": 2043,
                "instances": 40423,
                "precision": 0.515,
                "recall": 0.572,
                "mAP50": 0.504,
                "mAP50_95": 0.295,
            },
            "SeaDronesSee": {
                "precision": 0.860,
                "recall": 0.765,
                "mAP50": 0.792,
                "mAP50_95": 0.475,
            },
        },
        "runtime_benchmark": {
            "video": "border_test_urban.mp4.mp4",
            "input_size": 1280,
            "frames": 725,
            "detections": 20327,
            "fps": 9.82,
            "avg_inference_ms": 60.74,
        },
    },
}


def sha256_file(path: Path) -> str:

    sha256 = hashlib.sha256()

    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)

            if not chunk:
                break

            sha256.update(chunk)

    return sha256.hexdigest()


def main():

    output_dir = Path(
        r"D:\mp-1\test_results\model_freeze"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    print("=" * 72)
    print("AERION v1 — DRONE MODEL FREEZE")
    print("=" * 72)

    frozen = {}

    for model_name, metadata in MODELS.items():

        path = metadata["path"]

        print(f"\nChecking: {model_name}")
        print(f"Path: {path}")

        if not path.exists():

            raise FileNotFoundError(
                f"Model not found:\n{path}"
            )

        size_mb = path.stat().st_size / (1024 * 1024)

        print(
            f"Size: {size_mb:.2f} MB"
        )

        print("Calculating SHA-256...")

        sha256 = sha256_file(path)

        print(
            f"SHA-256: {sha256}"
        )

        frozen[model_name] = {
            "model_path": str(path),
            "file_size_mb": round(size_mb, 2),
            "sha256": sha256,
            "architecture": metadata["architecture"],
            "input_size": metadata["input_size"],
            "training_dataset": metadata["training_dataset"],
            "classes": metadata["classes"],
            "primary_metrics": metadata["primary_metrics"],
            "external_validation": metadata["external_validation"],
            "runtime_benchmark": metadata["runtime_benchmark"],
            "status": "FROZEN",
        }

    record = {
        "project": "AERION",
        "version": "v1",
        "subsystem": "drone_detection",
        "freeze_status": "FROZEN",
        "freeze_timestamp_utc": datetime.utcnow().isoformat() + "Z",
        "models": frozen,
        "notes": [
            "Models are frozen for AERION v1 integration.",
            "No further drone training is required for v1.",
            "VisDrone-only model is preferred for land/border vehicle surveillance.",
            "Unified model is retained for maritime/multi-domain capability.",
            "UAVDT results are from a reproducible external-validation subset.",
            "SeaDronesSee results use the corrected unified 10-class evaluation.",
        ],
    }

    output_path = (
        output_dir
        / "aerion_v1_drone_freeze.json"
    )

    output_path.write_text(
        json.dumps(
            record,
            indent=2
        ),
        encoding="utf-8"
    )

    print("\n" + "=" * 72)
    print("DRONE MODEL FREEZE COMPLETE")
    print("=" * 72)

    print(f"\nFreeze record:")
    print(output_path)

    print("\nFrozen models:")

    for name, data in frozen.items():

        print(f"\n{name}")
        print(f"  SHA-256 : {data['sha256']}")
        print(f"  Size    : {data['file_size_mb']} MB")
        print(f"  Status  : {data['status']}")

    print("\nNo model files were modified.")


if __name__ == "__main__":
    main()