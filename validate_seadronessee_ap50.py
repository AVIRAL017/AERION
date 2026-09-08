from pathlib import Path
import json
import cv2
import numpy as np
from ultralytics import YOLO


# ============================================================
# CONFIG
# ============================================================

MODEL_PATH = r"D:\mp-1\runs\detect\visdrone_8s_1280_30ep\weights\best.pt"

DATASET_ROOT = Path(r"D:\mp-1\seadronessee_yolo")
VAL_IMAGES = DATASET_ROOT / "images" / "val"
VAL_LABELS = DATASET_ROOT / "labels" / "val"

OUTPUT_DIR = Path(r"D:\mp-1\seadronessee_validation_ap50")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PERSON_CLASS_ID = 0

IOU_THRESHOLD = 0.50

# Keep predictions down to a very low confidence so AP
# can evaluate the full precision-recall curve.
INFERENCE_CONF = 0.001

IMGSZ = 1280


# ============================================================
# IOU
# ============================================================

def calculate_iou(box1, box2):

    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    iw = max(0.0, x2 - x1)
    ih = max(0.0, y2 - y1)

    intersection = iw * ih

    area1 = max(0.0, box1[2] - box1[0]) * max(0.0, box1[3] - box1[1])
    area2 = max(0.0, box2[2] - box2[0]) * max(0.0, box2[3] - box2[1])

    union = area1 + area2 - intersection

    if union <= 0:
        return 0.0

    return intersection / union


# ============================================================
# LOAD GT PERSON BOXES
# ============================================================

def load_ground_truth(label_path, width, height):

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

            x1 = (cx - w / 2) * width
            y1 = (cy - h / 2) * height
            x2 = (cx + w / 2) * width
            y2 = (cy + h / 2) * height

            boxes.append([x1, y1, x2, y2])

    return boxes


# ============================================================
# VOC-STYLE AP CALCULATION
# ============================================================

def calculate_ap(recall, precision):

    # Add sentinel endpoints.
    mrec = np.concatenate(
        ([0.0], recall, [1.0])
    )

    mpre = np.concatenate(
        ([0.0], precision, [0.0])
    )

    # Precision envelope.
    for i in range(len(mpre) - 1, 0, -1):

        mpre[i - 1] = max(
            mpre[i - 1],
            mpre[i]
        )

    # Points where recall changes.
    indices = np.where(
        mrec[1:] != mrec[:-1]
    )[0]

    ap = np.sum(
        (mrec[indices + 1] - mrec[indices])
        * mpre[indices + 1]
    )

    return float(ap)


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("SeaDronesSee ZERO-SHOT AP50 EVALUATION")
    print("=" * 70)

    print(f"Model: {MODEL_PATH}")
    print(f"Dataset: {VAL_IMAGES}")
    print(f"Image size: {IMGSZ}")
    print(f"Inference confidence: {INFERENCE_CONF}")
    print(f"IoU threshold: {IOU_THRESHOLD}")
    print()

    if not Path(MODEL_PATH).exists():
        raise FileNotFoundError(MODEL_PATH)

    if not VAL_IMAGES.exists():
        raise FileNotFoundError(VAL_IMAGES)

    model = YOLO(MODEL_PATH)

    image_paths = sorted(
        list(VAL_IMAGES.glob("*.jpg")) +
        list(VAL_IMAGES.glob("*.jpeg")) +
        list(VAL_IMAGES.glob("*.png"))
    )

    print(f"Validation images found: {len(image_paths)}")
    print()
    print("Running inference...")
    print()

    # Each entry:
    #
    # {
    #   confidence,
    #   image_index,
    #   box
    # }
    #
    all_predictions = []

    ground_truth_per_image = {}

    total_gt = 0

    # ========================================================
    # INFERENCE
    # ========================================================

    for index, image_path in enumerate(image_paths):

        image = cv2.imread(str(image_path))

        if image is None:
            print(f"[WARNING] Could not read {image_path}")
            continue

        height, width = image.shape[:2]

        label_path = VAL_LABELS / f"{image_path.stem}.txt"

        gt_boxes = load_ground_truth(
            label_path,
            width,
            height
        )

        ground_truth_per_image[index] = gt_boxes

        total_gt += len(gt_boxes)

        results = model.predict(
            source=image,
            imgsz=IMGSZ,
            conf=INFERENCE_CONF,
            device=0,
            verbose=False
        )

        result = results[0]

        if result.boxes is not None:

            for box, cls, conf in zip(
                result.boxes.xyxy.cpu().numpy(),
                result.boxes.cls.cpu().numpy(),
                result.boxes.conf.cpu().numpy()
            ):

                class_id = int(cls)

                # Only shared class.
                if class_id != PERSON_CLASS_ID:
                    continue

                all_predictions.append({
                    "image_index": index,
                    "image": image_path.name,
                    "box": box.tolist(),
                    "confidence": float(conf)
                })

        if index == 0 or (index + 1) % 100 == 0:

            print(
                f"Processed "
                f"{index + 1}/{len(image_paths)}"
                f" | GT persons={total_gt}"
                f" | predictions={len(all_predictions)}"
            )

    print()
    print("=" * 70)
    print("INFERENCE COMPLETE")
    print("=" * 70)

    print(f"Total GT persons : {total_gt}")
    print(f"Total predictions: {len(all_predictions)}")
    print()

    # ========================================================
    # SORT PREDICTIONS BY CONFIDENCE
    # ========================================================

    all_predictions.sort(
        key=lambda x: x["confidence"],
        reverse=True
    )

    matched_gt = {
        image_index: set()
        for image_index in ground_truth_per_image
    }

    tp = []
    fp = []

    # ========================================================
    # MATCH PREDICTIONS
    # ========================================================

    for prediction in all_predictions:

        image_index = prediction["image_index"]
        pred_box = prediction["box"]

        gt_boxes = ground_truth_per_image[image_index]

        best_iou = 0.0
        best_gt = None

        for gt_index, gt_box in enumerate(gt_boxes):

            if gt_index in matched_gt[image_index]:
                continue

            iou = calculate_iou(
                pred_box,
                gt_box
            )

            if iou > best_iou:

                best_iou = iou
                best_gt = gt_index

        if (
            best_gt is not None
            and best_iou >= IOU_THRESHOLD
        ):

            tp.append(1)
            fp.append(0)

            matched_gt[image_index].add(best_gt)

        else:

            tp.append(0)
            fp.append(1)

    tp = np.array(tp)
    fp = np.array(fp)

    # ========================================================
    # PRECISION / RECALL CURVE
    # ========================================================

    cumulative_tp = np.cumsum(tp)
    cumulative_fp = np.cumsum(fp)

    recalls = cumulative_tp / max(total_gt, 1)

    precisions = cumulative_tp / np.maximum(
        cumulative_tp + cumulative_fp,
        1
    )

    ap50 = calculate_ap(
        recalls,
        precisions
    )

    # ========================================================
    # BEST F1 OPERATING POINT
    # ========================================================

    f1_scores = (
        2 * precisions * recalls
        / np.maximum(precisions + recalls, 1e-12)
    )

    best_index = int(np.argmax(f1_scores))

    best_confidence = all_predictions[
        best_index
    ]["confidence"]

    best_precision = float(
        precisions[best_index]
    )

    best_recall = float(
        recalls[best_index]
    )

    best_f1 = float(
        f1_scores[best_index]
    )

    # ========================================================
    # RESULTS
    # ========================================================

    print()
    print("=" * 70)
    print("FINAL SEA DRONES SEE RESULTS")
    print("=" * 70)

    print(f"Dataset                    : SeaDronesSee")
    print(f"Evaluation                 : Zero-shot")
    print(f"Evaluated class            : person")
    print(f"Images                     : {len(image_paths)}")
    print(f"Ground-truth persons       : {total_gt}")
    print(f"Predictions evaluated      : {len(all_predictions)}")
    print()

    print(f"AP50                       : {ap50:.4f}")
    print(f"AP50 (%)                   : {ap50 * 100:.2f}%")
    print()

    print("Best F1 operating point")
    print(f"Confidence                 : {best_confidence:.4f}")
    print(f"Precision                  : {best_precision:.4f}")
    print(f"Recall                     : {best_recall:.4f}")
    print(f"F1                         : {best_f1:.4f}")

    print()
    print("=" * 70)

    # ========================================================
    # SAVE
    # ========================================================

    results = {
        "dataset": "SeaDronesSee",
        "evaluation_type": "zero_shot_cross_domain",
        "model": MODEL_PATH,
        "evaluated_class": "person",
        "images": len(image_paths),
        "ground_truth_persons": total_gt,
        "predictions_evaluated": len(all_predictions),
        "iou_threshold": IOU_THRESHOLD,
        "inference_confidence": INFERENCE_CONF,
        "imgsz": IMGSZ,
        "AP50": ap50,
        "AP50_percent": ap50 * 100,
        "best_f1_confidence": best_confidence,
        "best_f1_precision": best_precision,
        "best_f1_recall": best_recall,
        "best_f1": best_f1
    }

    output_file = OUTPUT_DIR / "ap50_results.json"

    with open(output_file, "w") as f:
        json.dump(results, f, indent=4)

    print(f"Results saved to:")
    print(output_file)

    print()
    print("AP50 evaluation complete.")


if __name__ == "__main__":
    main()