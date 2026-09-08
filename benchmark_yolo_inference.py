import time
import cv2
import torch
from ultralytics import YOLO


VIDEO_PATH = r"D:\mp-1\border_test_videos\border_test_urban.mp4.mp4"

MODEL_PATH = (
    r"D:\mp-1\runs\detect\visdrone_8s_1280_30ep"
    r"\weights\best.pt"
)


def main():

    print("=" * 70)
    print("YOLO INFERENCE BENCHMARK")
    print("=" * 70)

    model = YOLO(MODEL_PATH)

    cap = cv2.VideoCapture(VIDEO_PATH)

    if not cap.isOpened():
        raise RuntimeError("Unable to open video.")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    source_fps = cap.get(cv2.CAP_PROP_FPS)

    print(f"Video FPS: {source_fps}")
    print(f"Total frames: {total_frames}")
    print()

    # Read one frame for warm-up.
    success, frame = cap.read()

    if not success:
        raise RuntimeError("Unable to read video frame.")

    print("Warming up GPU...")

    for _ in range(5):
        model.predict(
            frame,
            imgsz=1280,
            conf=0.25,
            device=0,
            verbose=False
        )

    if torch.cuda.is_available():
        torch.cuda.synchronize()

    # Restart video.
    cap.release()
    cap = cv2.VideoCapture(VIDEO_PATH)

    inference_times = []
    processed = 0
    detections = 0

    print("Starting benchmark...")
    print()

    benchmark_start = time.perf_counter()

    while True:

        success, frame = cap.read()

        if not success:
            break

        start = time.perf_counter()

        results = model.predict(
            frame,
            imgsz=1280,
            conf=0.25,
            device=0,
            verbose=False
        )

        if torch.cuda.is_available():
            torch.cuda.synchronize()

        end = time.perf_counter()

        inference_times.append(end - start)

        processed += 1

        for result in results:
            if result.boxes is not None:
                detections += len(result.boxes)

        if processed % 50 == 0:

            elapsed = time.perf_counter() - benchmark_start

            fps = processed / elapsed

            print(
                f"Frames: {processed:4d} | "
                f"FPS: {fps:6.2f}"
            )

    total_time = time.perf_counter() - benchmark_start

    cap.release()

    average = sum(inference_times) / len(inference_times)

    print()
    print("=" * 70)
    print("YOLO BENCHMARK COMPLETE")
    print("=" * 70)

    print(f"Frames processed:       {processed}")
    print(f"Total detections:       {detections}")

    print()
    print(f"Total benchmark time:   {total_time:.2f} seconds")
    print(f"Effective FPS:          {processed / total_time:.2f}")

    print()
    print(
        f"Average inference:      "
        f"{average * 1000:.2f} ms"
    )

    print(
        f"Minimum inference:      "
        f"{min(inference_times) * 1000:.2f} ms"
    )

    print(
        f"Maximum inference:      "
        f"{max(inference_times) * 1000:.2f} ms"
    )

    if torch.cuda.is_available():

        allocated = torch.cuda.memory_allocated(0) / (1024 ** 3)
        reserved = torch.cuda.memory_reserved(0) / (1024 ** 3)

        print()
        print(
            f"GPU memory allocated:    "
            f"{allocated:.2f} GB"
        )

        print(
            f"GPU memory reserved:     "
            f"{reserved:.2f} GB"
        )

    print("=" * 70)


if __name__ == "__main__":
    main()