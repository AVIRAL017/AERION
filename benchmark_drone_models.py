from pathlib import Path
import csv
import time
import cv2
import torch
from ultralytics import YOLO


# ============================================================
# CONFIGURATION
# ============================================================

VIDEO_PATH = Path(
    r"D:\mp-1\border_test_videos\border_test_urban.mp4.mp4"
)

MODELS = {
    "visdrone_only": Path(
        r"D:\mp-1\runs\detect\visdrone_8s_1280_30ep\weights\best.pt"
    ),
    "unified": Path(
        r"D:\mp-1\runs\detect\unified_drone_20ep\weights\best.pt"
    ),
}

OUTPUT_DIR = Path(r"D:\mp-1\benchmark_results\drone_models")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Fair comparison settings
IMG_SIZE = 1280
CONF = 0.25
IOU = 0.50
MAX_DET = 300

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


# ============================================================
# MODEL BENCHMARK
# ============================================================

def benchmark_model(model_name, model_path):

    print("\n" + "=" * 75)
    print(f"MODEL: {model_name}")
    print(f"PATH : {model_path}")
    print("=" * 75)

    if not model_path.exists():
        raise FileNotFoundError(
            f"Model not found: {model_path}"
        )

    model = YOLO(str(model_path))

    cap = cv2.VideoCapture(str(VIDEO_PATH))

    if not cap.isOpened():
        raise RuntimeError(
            f"Could not open video: {VIDEO_PATH}"
        )

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps_video = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    print(f"Video resolution : {width}x{height}")
    print(f"Video FPS        : {fps_video}")
    print(f"Total frames     : {total_frames}")
    print(f"Test resolution  : {IMG_SIZE}")
    print(f"Confidence       : {CONF}")
    print()

    # Class statistics
    class_counts = {
        name: 0 for name in CLASS_NAMES
    }

    confidence_values = []

    total_detections = 0
    processed_frames = 0

    inference_times = []

    # --------------------------------------------------------
    # Warm-up
    # --------------------------------------------------------

    print("Warming up GPU...")

    ret, frame = cap.read()

    if not ret:
        cap.release()
        raise RuntimeError("Could not read first frame.")

    model.predict(
        frame,
        imgsz=IMG_SIZE,
        conf=CONF,
        iou=IOU,
        max_det=MAX_DET,
        device=0,
        verbose=False,
    )

    if torch.cuda.is_available():
        torch.cuda.synchronize()

    # Restart video
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    print("Running benchmark...\n")

    benchmark_start = time.perf_counter()

    while True:

        ret, frame = cap.read()

        if not ret:
            break

        if torch.cuda.is_available():
            torch.cuda.synchronize()

        start = time.perf_counter()

        results = model.predict(
            frame,
            imgsz=IMG_SIZE,
            conf=CONF,
            iou=IOU,
            max_det=MAX_DET,
            device=0,
            verbose=False,
        )

        if torch.cuda.is_available():
            torch.cuda.synchronize()

        elapsed = time.perf_counter() - start

        inference_times.append(elapsed)

        result = results[0]

        if result.boxes is not None and len(result.boxes) > 0:

            classes = result.boxes.cls.cpu().numpy()
            confidences = result.boxes.conf.cpu().numpy()

            total_detections += len(classes)

            for cls_id, confidence in zip(
                classes,
                confidences
            ):

                cls_id = int(cls_id)

                if 0 <= cls_id < len(CLASS_NAMES):
                    class_counts[CLASS_NAMES[cls_id]] += 1

                confidence_values.append(
                    float(confidence)
                )

        processed_frames += 1

        if processed_frames % 100 == 0:

            elapsed_total = time.perf_counter() - benchmark_start

            current_fps = (
                processed_frames / elapsed_total
                if elapsed_total > 0
                else 0
            )

            print(
                f"Processed {processed_frames}/{total_frames} "
                f"| FPS: {current_fps:.2f} "
                f"| Detections: {total_detections}"
            )

    benchmark_elapsed = time.perf_counter() - benchmark_start

    cap.release()

    # --------------------------------------------------------
    # Statistics
    # --------------------------------------------------------

    avg_inference_ms = (
        sum(inference_times)
        / len(inference_times)
        * 1000
        if inference_times
        else 0
    )

    min_inference_ms = (
        min(inference_times) * 1000
        if inference_times
        else 0
    )

    max_inference_ms = (
        max(inference_times) * 1000
        if inference_times
        else 0
    )

    benchmark_fps = (
        processed_frames / benchmark_elapsed
        if benchmark_elapsed > 0
        else 0
    )

    detections_per_frame = (
        total_detections / processed_frames
        if processed_frames > 0
        else 0
    )

    avg_confidence = (
        sum(confidence_values)
        / len(confidence_values)
        if confidence_values
        else 0
    )

    # --------------------------------------------------------
    # Results
    # --------------------------------------------------------

    metrics = {
        "model": model_name,
        "model_path": str(model_path),
        "video": str(VIDEO_PATH),
        "video_width": width,
        "video_height": height,
        "video_fps": fps_video,
        "test_imgsz": IMG_SIZE,
        "confidence_threshold": CONF,
        "iou_threshold": IOU,
        "frames": processed_frames,
        "total_detections": total_detections,
        "detections_per_frame": detections_per_frame,
        "benchmark_time_seconds": benchmark_elapsed,
        "benchmark_fps": benchmark_fps,
        "average_inference_ms": avg_inference_ms,
        "minimum_inference_ms": min_inference_ms,
        "maximum_inference_ms": max_inference_ms,
        "average_confidence": avg_confidence,
        "class_counts": class_counts,
    }

    output_json = (
        OUTPUT_DIR / f"{model_name}_1280_metrics.json"
    )

    import json

    with open(
        output_json,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            metrics,
            f,
            indent=2
        )

    print("\n" + "-" * 75)
    print(f"{model_name.upper()} RESULTS")
    print("-" * 75)

    print(f"Frames              : {processed_frames}")
    print(f"Total detections    : {total_detections}")
    print(f"Detections/frame    : {detections_per_frame:.2f}")
    print(f"Benchmark FPS       : {benchmark_fps:.2f}")
    print(f"Average inference   : {avg_inference_ms:.2f} ms")
    print(f"Minimum inference   : {min_inference_ms:.2f} ms")
    print(f"Maximum inference   : {max_inference_ms:.2f} ms")
    print(f"Average confidence  : {avg_confidence:.4f}")

    print("\nClass detections:")

    for class_name, count in class_counts.items():
        print(
            f"  {class_name:<24} {count}"
        )

    print(f"\nSaved: {output_json}")

    return metrics


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    print("=" * 75)
    print("AERION DRONE MODEL BENCHMARK")
    print("=" * 75)

    print(f"\nVideo: {VIDEO_PATH}")
    print(f"Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'}")

    all_results = []

    for model_name, model_path in MODELS.items():

        result = benchmark_model(
            model_name,
            model_path
        )

        all_results.append(result)

    # --------------------------------------------------------
    # Comparison
    # --------------------------------------------------------

    print("\n\n" + "=" * 75)
    print("FINAL MODEL COMPARISON")
    print("=" * 75)

    print(
        f"{'Metric':<28}"
        f"{'VisDrone-only':>20}"
        f"{'Unified':>20}"
    )

    print("-" * 68)

    for metric, label in [
        ("total_detections", "Total detections"),
        ("detections_per_frame", "Detections/frame"),
        ("benchmark_fps", "Benchmark FPS"),
        ("average_inference_ms", "Avg inference ms"),
        ("average_confidence", "Avg confidence"),
    ]:

        a = all_results[0][metric]
        b = all_results[1][metric]

        print(
            f"{label:<28}"
            f"{a:>20.3f}"
            f"{b:>20.3f}"
        )

    # Save comparison
    comparison_file = (
        OUTPUT_DIR / "drone_model_comparison.json"
    )

    import json

    with open(
        comparison_file,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            all_results,
            f,
            indent=2
        )

    print("\nComparison saved to:")
    print(comparison_file)

    print("\nBenchmark complete.")