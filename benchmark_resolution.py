import time
import cv2
import torch
from ultralytics import YOLO


VIDEO_PATH = r"D:\mp-1\border_test_videos\border_test_urban.mp4.mp4"

MODEL_PATH = (
    r"D:\mp-1\runs\detect\visdrone_8s_1280_30ep"
    r"\weights\best.pt"
)


def benchmark(model, imgsz):

    cap = cv2.VideoCapture(VIDEO_PATH)

    if not cap.isOpened():
        raise RuntimeError("Unable to open video.")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # Warm-up
    success, frame = cap.read()

    if not success:
        raise RuntimeError("Unable to read video.")

    for _ in range(5):
        model.predict(
            frame,
            imgsz=imgsz,
            conf=0.25,
            device=0,
            verbose=False
        )

    if torch.cuda.is_available():
        torch.cuda.synchronize()

    cap.release()
    cap = cv2.VideoCapture(VIDEO_PATH)

    times = []
    detections = 0
    processed = 0

    start_total = time.perf_counter()

    while True:

        success, frame = cap.read()

        if not success:
            break

        start = time.perf_counter()

        results = model.predict(
            frame,
            imgsz=imgsz,
            conf=0.25,
            device=0,
            verbose=False
        )

        if torch.cuda.is_available():
            torch.cuda.synchronize()

        end = time.perf_counter()

        times.append(end - start)
        processed += 1

        for result in results:
            if result.boxes is not None:
                detections += len(result.boxes)

    total_time = time.perf_counter() - start_total

    cap.release()

    return {
        "frames": processed,
        "detections": detections,
        "fps": processed / total_time,
        "avg_ms": sum(times) / len(times) * 1000,
        "min_ms": min(times) * 1000,
        "max_ms": max(times) * 1000,
    }


def main():

    print("=" * 70)
    print("YOLO RESOLUTION COMPARISON")
    print("=" * 70)

    model = YOLO(MODEL_PATH)

    print("\nTesting 640...")
    result_640 = benchmark(model, 640)

    print("Testing 1280...")
    result_1280 = benchmark(model, 1280)

    print()
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)

    print(
        f"{'Metric':<25}"
        f"{'640':>15}"
        f"{'1280':>15}"
    )

    print("-" * 55)

    print(
        f"{'Frames':<25}"
        f"{result_640['frames']:>15}"
        f"{result_1280['frames']:>15}"
    )

    print(
        f"{'Detections':<25}"
        f"{result_640['detections']:>15}"
        f"{result_1280['detections']:>15}"
    )

    print(
        f"{'FPS':<25}"
        f"{result_640['fps']:>15.2f}"
        f"{result_1280['fps']:>15.2f}"
    )

    print(
        f"{'Average latency (ms)':<25}"
        f"{result_640['avg_ms']:>15.2f}"
        f"{result_1280['avg_ms']:>15.2f}"
    )

    print(
        f"{'Minimum latency (ms)':<25}"
        f"{result_640['min_ms']:>15.2f}"
        f"{result_1280['min_ms']:>15.2f}"
    )

    print(
        f"{'Maximum latency (ms)':<25}"
        f"{result_640['max_ms']:>15.2f}"
        f"{result_1280['max_ms']:>15.2f}"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()