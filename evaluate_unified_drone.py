from pathlib import Path
from ultralytics import YOLO
import yaml
import json


MODEL_PATH = r"D:\mp-1\runs\detect\unified_drone_20ep\weights\best.pt"

VISDRONE_BASE = Path(r"C:\Users\avira\yolo_project\datasets\VisDrone")
SEADRONESSEE_BASE = Path(r"D:\mp-1\seadronessee_yolo")

OUTPUT_DIR = Path(r"D:\mp-1\validation_results\unified_drone")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CLASS_NAMES = [
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
]


def create_eval_yaml(name, base_path, split):
    """
    Create a 10-class evaluation YAML while preserving the
    original dataset image/label locations.
    """

    base_path = Path(base_path)

    yaml_path = OUTPUT_DIR / f"{name}_eval.yaml"

    config = {
        "path": str(base_path),
        "train": str(base_path / "images" / "train"),
        "val": str(base_path / "images" / split),
        "nc": len(CLASS_NAMES),
        "names": CLASS_NAMES,
    }

    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, sort_keys=False)

    return yaml_path


def extract_metrics(results):
    box = results.box

    metrics = {
        "precision": float(box.mp),
        "recall": float(box.mr),
        "map50": float(box.map50),
        "map50_95": float(box.map),
    }

    # Per-class metrics
    if hasattr(box, "maps"):
        metrics["per_class_map50_95"] = {
            CLASS_NAMES[i]: float(box.maps[i])
            for i in range(min(len(box.maps), len(CLASS_NAMES)))
        }

    return metrics


def evaluate_dataset(model, dataset_name, dataset_yaml):
    print("\n" + "=" * 70)
    print(f"EVALUATING: {dataset_name}")
    print("=" * 70)

    results = model.val(
        data=str(dataset_yaml),
        imgsz=1280,
        batch=1,
        device=0,
        conf=0.001,
        iou=0.7,
        plots=True,
        verbose=True,
        project=str(OUTPUT_DIR),
        name=dataset_name,
    )

    metrics = extract_metrics(results)

    output_file = OUTPUT_DIR / f"{dataset_name}_metrics.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    print("\nRESULT:")
    print(f"Precision : {metrics['precision']:.4f}")
    print(f"Recall    : {metrics['recall']:.4f}")
    print(f"mAP50     : {metrics['map50']:.4f}")
    print(f"mAP50-95  : {metrics['map50_95']:.4f}")

    return metrics


if __name__ == "__main__":

    print("Loading unified drone model...")
    model = YOLO(MODEL_PATH)

    # ---------------------------------------------------------
    # VISDRONE
    # ---------------------------------------------------------
    vis_yaml = create_eval_yaml(
        "visdrone",
        VISDRONE_BASE,
        "val",
    )

    vis_metrics = evaluate_dataset(
        model,
        "visdrone_eval",
        vis_yaml,
    )

    # ---------------------------------------------------------
    # SEADRONESSEE
    # ---------------------------------------------------------
    sea_yaml = create_eval_yaml(
        "seadronessee",
        SEADRONESSEE_BASE,
        "val",
    )

    sea_metrics = evaluate_dataset(
        model,
        "seadronessee_eval",
        sea_yaml,
    )

    # ---------------------------------------------------------
    # FINAL SUMMARY
    # ---------------------------------------------------------
    summary = {
        "model": MODEL_PATH,
        "model_type": "YOLOv8s Unified Drone Detector",
        "imgsz": 1280,
        "classes": CLASS_NAMES,
        "visdrone": vis_metrics,
        "seadronessee": sea_metrics,
    }

    summary_file = OUTPUT_DIR / "unified_drone_evaluation_summary.json"

    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\n" + "=" * 70)
    print("FINAL EVALUATION SUMMARY")
    print("=" * 70)

    print("\nVisDrone:")
    print(f"  mAP50    : {vis_metrics['map50']:.4f}")
    print(f"  mAP50-95 : {vis_metrics['map50_95']:.4f}")

    print("\nSeaDronesSee:")
    print(f"  mAP50    : {sea_metrics['map50']:.4f}")
    print(f"  mAP50-95 : {sea_metrics['map50_95']:.4f}")

    print(f"\nSummary saved to:")
    print(summary_file)