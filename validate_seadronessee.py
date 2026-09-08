from pathlib import Path
import json
import cv2
import numpy as np
from ultralytics import YOLO


# ============================================================
# CONFIGURATION
# ============================================================

MODEL_PATH = r"D:\mp-1\runs\detect\visdrone_8s_1280_30ep\weights\best.pt"

DATASET_ROOT = Path(r"D:\mp-1\seadronessee_yolo")
VAL_IMAGES = DATASET_ROOT / "images" / "val"
VAL_LABELS = DATASET_ROOT / "labels" / "val"

OUTPUT_DIR = Path(r"D:\mp-1\seadronessee_validation")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Our YOLO model's person class
PERSON_CLASS_ID = 0

# IoU threshold for matching prediction to ground truth
IOU_THRESHOLD = 0.50

# Confidence threshold
CONF_THRESHOLD = 0.25

# Save a few visual examples
MAX_VISUALIZATIONS = 20


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def calculate_iou(box1, box2):
    """
    Calculate IoU between two boxes.

    Boxes:
        [x1, y1, x2, y2]
    """

    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])

    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    intersection_width = max(0, x2 - x1)
    intersection_height = max(0, y2 - y1)

    intersection = intersection_width * intersection_height

    area1 = max(0, box1[2] - box1[0]) * max(0, box1[3] - box1[1])
    area2 = max(0, box2[2] - box2[0]) * max(0, box2[3] - box2[1])

    union = area1 + area2 - intersection

    if union <= 0:
        return 0.0

    return intersection / union


def load_person_ground_truth(label_path, image_width, image_height):
    """
    Load SeaDronesSee YOLO annotations.

    Only category 0 (person) is evaluated.

    YOLO format:
        class_id center_x center_y width height
    """

    boxes = []

    if not label_path.exists():
        return boxes

    with open(label_path, "r") as f:
        for line in f:
            values = line.strip().split()

            if len(values) != 5:
                continue

            class_id = int(values[0])

            if class_id != PERSON_CLASS_ID:
                continue

            cx, cy, w, h = map(float, values[1:])

            x1 = (cx - w / 2) * image_width
            y1 = (cy - h / 2) * image_height
            x2 = (cx + w / 2) * image_width
            y2 = (cy + h / 2) * image_height

            boxes.append([x1, y1, x2, y2])

    return boxes


def precision_recall_f1(tp, fp, fn):
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0

    if precision + recall > 0:
        f1 = 2 * precision * recall / (precision + recall)
    else:
        f1 = 0.0

    return precision, recall, f1


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("SeaDronesSee ZERO-SHOT CROSS-DOMAIN VALIDATION")
    print("=" * 70)

    print(f"Model: {MODEL_PATH}")
    print(f"Validation images: {VAL_IMAGES}")
    print()

    if not Path(MODEL_PATH).exists():
        raise FileNotFoundError(
            f"Model not found:\n{MODEL_PATH}"
        )

    if not VAL_IMAGES.exists():
        raise FileNotFoundError(
            f"Validation image directory not found:\n{VAL_IMAGES}"
        )

    model = YOLO(MODEL_PATH)

    image_paths = sorted(
        list(VAL_IMAGES.glob("*.jpg")) +
        list(VAL_IMAGES.glob("*.jpeg")) +
        list(VAL_IMAGES.glob("*.png"))
    )

    print(f"Validation images found: {len(image_paths)}")
    print()

    if len(image_paths) == 0:
        raise RuntimeError("No validation images found.")

    total_tp = 0
    total_fp = 0
    total_fn = 0

    images_with_gt = 0
    images_with_prediction = 0

    visualizations_saved = 0

    prediction_records = []

    print("Starting inference...")
    print()

    for index, image_path in enumerate(image_paths, start=1):

        image = cv2.imread(str(image_path))

        if image is None:
            print(f"[WARNING] Could not read: {image_path}")
            continue

        image_height, image_width = image.shape[:2]

        label_path = VAL_LABELS / f"{image_path.stem}.txt"

        gt_boxes = load_person_ground_truth(
            label_path,
            image_width,
            image_height
        )

        if len(gt_boxes) > 0:
            images_with_gt += 1

        # ----------------------------------------------------
        # YOLO inference
        # ----------------------------------------------------

        results = model.predict(
            source=image,
            imgsz=1280,
            conf=CONF_THRESHOLD,
            device=0,
            verbose=False
        )

        result = results[0]

        predictions = []

        if result.boxes is not None:

            for box, cls, conf in zip(
                result.boxes.xyxy.cpu().numpy(),
                result.boxes.cls.cpu().numpy(),
                result.boxes.conf.cpu().numpy()
            ):

                class_id = int(cls)

                # Only evaluate person
                if class_id != PERSON_CLASS_ID:
                    continue

                predictions.append({
                    "box": box.tolist(),
                    "confidence": float(conf)
                })

        if len(predictions) > 0:
            images_with_prediction += 1

        # ----------------------------------------------------
        # Match predictions to ground truth
        # ----------------------------------------------------

        matched_gt = set()

        image_tp = 0
        image_fp = 0

        # Highest confidence predictions first
        predictions.sort(
            key=lambda x: x["confidence"],
            reverse=True
        )

        for prediction in predictions:

            best_iou = 0.0
            best_gt_index = None

            for gt_index, gt_box in enumerate(gt_boxes):

                if gt_index in matched_gt:
                    continue

                iou = calculate_iou(
                    prediction["box"],
                    gt_box
                )

                if iou > best_iou:
                    best_iou = iou
                    best_gt_index = gt_index

            if (
                best_gt_index is not None
                and best_iou >= IOU_THRESHOLD
            ):
                image_tp += 1
                matched_gt.add(best_gt_index)

            else:
                image_fp += 1

        image_fn = len(gt_boxes) - len(matched_gt)

        total_tp += image_tp
        total_fp += image_fp
        total_fn += image_fn

        prediction_records.append({
            "image": image_path.name,
            "ground_truth_persons": len(gt_boxes),
            "predicted_persons": len(predictions),
            "true_positive": image_tp,
            "false_positive": image_fp,
            "false_negative": image_fn
        })

        # ----------------------------------------------------
        # Save visualizations
        # ----------------------------------------------------

        if (
            visualizations_saved < MAX_VISUALIZATIONS
            and len(gt_boxes) > 0
        ):

            vis = image.copy()

            # Ground truth = green
            for box in gt_boxes:

                x1, y1, x2, y2 = map(int, box)

                cv2.rectangle(
                    vis,
                    (x1, y1),
                    (x2, y2),
                    (0, 255, 0),
                    2
                )

                cv2.putText(
                    vis,
                    "GT person",
                    (x1, max(20, y1 - 5)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2
                )

            # Predictions = red
            for prediction in predictions:

                x1, y1, x2, y2 = map(
                    int,
                    prediction["box"]
                )

                confidence = prediction["confidence"]

                cv2.rectangle(
                    vis,
                    (x1, y1),
                    (x2, y2),
                    (0, 0, 255),
                    2
                )

                cv2.putText(
                    vis,
                    f"Pred person {confidence:.2f}",
                    (x1, min(image_height - 5, y2 + 20)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 0, 255),
                    2
                )

            output_path = (
                OUTPUT_DIR /
                f"{visualizations_saved:03d}_{image_path.name}"
            )

            cv2.imwrite(
                str(output_path),
                vis
            )

            visualizations_saved += 1

        # ----------------------------------------------------
        # Progress
        # ----------------------------------------------------

        if index % 100 == 0 or index == len(image_paths):

            print(
                f"Processed {index}/{len(image_paths)} "
                f"| TP={total_tp} "
                f"| FP={total_fp} "
                f"| FN={total_fn}"
            )

    # ========================================================
    # FINAL METRICS
    # ========================================================

    precision, recall, f1 = precision_recall_f1(
        total_tp,
        total_fp,
        total_fn
    )

    print()
    print("=" * 70)
    print("FINAL RESULTS")
    print("=" * 70)

    print(f"Images evaluated       : {len(image_paths)}")
    print(f"Images with GT person  : {images_with_gt}")
    print(f"Images with prediction : {images_with_prediction}")
    print()

    print(f"True Positives         : {total_tp}")
    print(f"False Positives        : {total_fp}")
    print(f"False Negatives        : {total_fn}")
    print()

    print(f"Precision              : {precision:.4f}")
    print(f"Recall                 : {recall:.4f}")
    print(f"F1 Score               : {f1:.4f}")
    print(f"IoU matching threshold : {IOU_THRESHOLD}")
    print(f"Confidence threshold   : {CONF_THRESHOLD}")

    # ========================================================
    # SAVE RESULTS
    # ========================================================

    results = {
        "dataset": "SeaDronesSee",
        "evaluation_type": "zero_shot_cross_domain",
        "model": MODEL_PATH,
        "evaluated_class": "person",
        "images": len(image_paths),
        "images_with_ground_truth_person": images_with_gt,
        "images_with_prediction": images_with_prediction,
        "true_positive": total_tp,
        "false_positive": total_fp,
        "false_negative": total_fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "iou_threshold": IOU_THRESHOLD,
        "confidence_threshold": CONF_THRESHOLD
    }

    results_path = OUTPUT_DIR / "results.json"

    with open(results_path, "w") as f:
        json.dump(results, f, indent=4)

    records_path = OUTPUT_DIR / "per_image_results.json"

    with open(records_path, "w") as f:
        json.dump(prediction_records, f, indent=4)

    print()
    print(f"Results saved to:")
    print(f"  {results_path}")
    print(f"  {records_path}")
    print(f"  Visualizations: {OUTPUT_DIR}")

    print()
    print("=" * 70)
    print("VALIDATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()