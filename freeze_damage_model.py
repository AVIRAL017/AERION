import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


MODEL_PATH = Path(r"D:\mp-1\change_detection_runs_v2\best_model.pth")
FREEZE_DIR = Path(r"D:\mp-1\test_results\model_freeze")
FREEZE_RECORD = FREEZE_DIR / "aerion_v1_damage_freeze.json"


def sha256_file(path: Path) -> str:
    sha256 = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            sha256.update(chunk)

    return sha256.hexdigest()


def main():
    print("=" * 72)
    print("AERION v1 — DAMAGE MODEL FREEZE")
    print("=" * 72)

    print("\nChecking model:")
    print(MODEL_PATH)

    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Damage model not found: {MODEL_PATH}"
        )

    size_mb = MODEL_PATH.stat().st_size / (1024 * 1024)

    print(f"Size: {size_mb:.2f} MB")
    print("Calculating SHA-256...")

    sha256 = sha256_file(MODEL_PATH)

    print(f"SHA-256: {sha256}")

    metadata = {
        "project": "AERION",
        "version": "v1",
        "component": "damage_detection",
        "status": "FROZEN",

        "model": {
            "path": str(MODEL_PATH),
            "architecture": "Siamese ResNet18",
            "framework": "PyTorch",
            "weights": "ImageNet pretrained backbone",
        },

        "dataset": {
            "name": "xBD / xView2 Challenge Training Set",
            "processing": "AERION damage processing v2",
            "train_images": 2240,
            "validation_images": 559,
            "validation_patches": 2236,
        },

        "training": {
            "epochs_configured": 40,
            "early_stopping": True,
            "best_epoch": 7,
            "optimizer": "AdamW",
            "learning_rate": 0.0001,
            "weight_decay": 0.0001,
            "batch_size": 2,
            "input_size": 512,
        },

        "validation": {
            "mean_iou": 0.6515,
            "mean_dice": 0.6867,
            "threshold": 0.50,
        },

        "integrity": {
            "sha256": sha256,
            "size_bytes": MODEL_PATH.stat().st_size,
            "size_mb": round(size_mb, 2),
        },

        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "model_files_modified": False,
    }

    FREEZE_DIR.mkdir(parents=True, exist_ok=True)

    with FREEZE_RECORD.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print("\n" + "=" * 72)
    print("DAMAGE MODEL FREEZE COMPLETE")
    print("=" * 72)

    print("\nFreeze record:")
    print(FREEZE_RECORD)

    print("\nSHA-256:")
    print(sha256)

    print(f"\nSize: {size_mb:.2f} MB")

    print("\nStatus: FROZEN")
    print("No model files were modified.")


if __name__ == "__main__":
    main()