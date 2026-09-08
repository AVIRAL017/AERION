from pathlib import Path
import hashlib
import json
from datetime import datetime, timezone


# ============================================================
# AERION v1 — SATELLITE MODEL FREEZE
# ============================================================

MODEL_PATH = Path(
    r"D:\mp-1\runs\obb\train-6\weights\best.pt"
)

OUTPUT_DIR = Path(
    r"D:\mp-1\test_results\model_freeze"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


SATELLITE_CLASSES = [
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
]


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

    print("=" * 72)
    print("AERION v1 — SATELLITE MODEL FREEZE")
    print("=" * 72)

    print(f"\nChecking model:")
    print(MODEL_PATH)

    if not MODEL_PATH.exists():

        raise FileNotFoundError(
            f"Satellite model not found:\n{MODEL_PATH}"
        )

    size_mb = (
        MODEL_PATH.stat().st_size
        / (1024 * 1024)
    )

    print(
        f"Size: {size_mb:.2f} MB"
    )

    print(
        "Calculating SHA-256..."
    )

    sha256 = sha256_file(
        MODEL_PATH
    )

    print(
        f"SHA-256: {sha256}"
    )

    record = {

        "project": "AERION",

        "version": "v1",

        "subsystem": "satellite_detection",

        "freeze_status": "FROZEN",

        "freeze_timestamp_utc": (
            datetime.now(timezone.utc)
            .isoformat()
        ),

        "model": {

            "model_path": str(
                MODEL_PATH
            ),

            "file_size_mb": round(
                size_mb,
                2
            ),

            "sha256": sha256,

            "architecture":
                "YOLOv8n-OBB",

            "dataset":
                "DOTA-v1.5",

            "dataset_format":
                "Oriented Bounding Boxes",

            "training_configuration": {

                "tile_size":
                    "1024x1024",

                "tile_gap":
                    200,

                "scale":
                    [1.0],

                "selected_checkpoint":
                    "train-6/best.pt",

            },

            "classes":
                SATELLITE_CLASSES,

            "validation_metrics": {

                "precision":
                    0.808,

                "recall":
                    0.649,

                "mAP50":
                    0.695,

                "mAP50_95":
                    0.523,

            },

            "status":
                "FROZEN",
        },

        "notes": [

            "This is the selected AERION v1 satellite model.",

            "The 1280px fine-tuning experiment was not selected "
            "as the final model.",

            "The selected model is YOLOv8n-OBB trained on "
            "tiled DOTA-v1.5 imagery.",

            "No further satellite training is required for "
            "AERION v1 integration.",

            "The model file was not modified during freezing.",

        ],
    }

    output_path = (
        OUTPUT_DIR
        / "aerion_v1_satellite_freeze.json"
    )

    output_path.write_text(
        json.dumps(
            record,
            indent=2
        ),
        encoding="utf-8"
    )

    print("\n" + "=" * 72)
    print("SATELLITE MODEL FREEZE COMPLETE")
    print("=" * 72)

    print(
        f"\nFreeze record:"
    )

    print(
        output_path
    )

    print(
        "\nSHA-256:"
    )

    print(
        sha256
    )

    print(
        f"\nSize:"
        f" {size_mb:.2f} MB"
    )

    print(
        "\nStatus: FROZEN"
    )

    print(
        "\nNo model files were modified."
    )


if __name__ == "__main__":
    main()