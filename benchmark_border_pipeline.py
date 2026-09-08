import time
import cv2
import torch

from video_input import VideoInput
from border_pipeline import BorderPipeline


VIDEO_PATH = r"D:\mp-1\border_test_videos\border_test_urban.mp4.mp4"

MODEL_PATH = r"D:\mp-1\runs\detect\visdrone_8s_1280_30ep\weights\best.pt"

ZONE_POLYGON = [
    (900, 200),
    (1200, 200),
    (1200, 700),
    (900, 700),
]


def main():

    print("=" * 70)
    print("BORDER PIPELINE PERFORMANCE BENCHMARK")
    print("=" * 70)

    video = VideoInput(VIDEO_PATH)

    pipeline = BorderPipeline(
        model_path=MODEL_PATH,
        zone_polygon=ZONE_POLYGON,
        persistence_threshold=10,
        movement_threshold=2.0,
        history_length=30,
        dwell_threshold=5,
    )

    video.open()

    total_frames = 0
    total_detections = 0
    total_alerts = 0

    frame_times = []

    print(f"Video: {VIDEO_PATH}")
    print(f"Resolution: {video.width()} x {video.height()}")
    print(f"Input FPS: {video.fps()}")
    print()

    # Warm-up GPU
    print("Warming up GPU...")
    for _ in range(5):
        frame = video.read()

        if frame is None:
            break

        pipeline.process_frame(frame, frame_number=0)

    video.release()

    # Re-open video after warm-up
    video = VideoInput(VIDEO_PATH)
    video.open()

    print("Starting benchmark...")
    print()

    benchmark_start = time.perf_counter()

    while True:

        frame = video.read()

        if frame is None:
            break

        frame_start = time.perf_counter()

        results = pipeline.process_frame(
            frame,
            frame_number=total_frames
        )

        frame_end = time.perf_counter()

        frame_time = frame_end - frame_start
        frame_times.append(frame_time)

        total_frames += 1

        total_detections += len(results)

        for result in results:
            if result.get("border_alert", False):
                total_alerts += 1

        if total_frames % 100 == 0:
            elapsed = time.perf_counter() - benchmark_start
            current_fps = total_frames / elapsed

            print(
                f"Frames: {total_frames:4d} | "
                f"Elapsed: {elapsed:8.2f}s | "
                f"FPS: {current_fps:6.2f}"
            )

    benchmark_end = time.perf_counter()

    video.release()

    total_time = benchmark_end - benchmark_start

    average_frame_time = sum(frame_times) / len(frame_times)

    min_frame_time = min(frame_times)
    max_frame_time = max(frame_times)

    effective_fps = total_frames / total_time

    average_latency_ms = average_frame_time * 1000
    min_latency_ms = min_frame_time * 1000
    max_latency_ms = max_frame_time * 1000

    print()
    print("=" * 70)
    print("BENCHMARK COMPLETE")
    print("=" * 70)

    print(f"Frames processed:       {total_frames}")
    print(f"Total detections:       {total_detections}")
    print(f"Total alerts:           {total_alerts}")
    print()

    print(f"Total processing time:  {total_time:.2f} seconds")
    print(f"Effective FPS:          {effective_fps:.2f}")
    print()

    print(f"Average frame latency:  {average_latency_ms:.2f} ms")
    print(f"Minimum frame latency:  {min_latency_ms:.2f} ms")
    print(f"Maximum frame latency:  {max_latency_ms:.2f} ms")

    if torch.cuda.is_available():

        torch.cuda.synchronize()

        allocated = torch.cuda.memory_allocated(0) / (1024 ** 3)
        reserved = torch.cuda.memory_reserved(0) / (1024 ** 3)

        print()
        print(f"GPU memory allocated:   {allocated:.2f} GB")
        print(f"GPU memory reserved:    {reserved:.2f} GB")

    print()
    print("=" * 70)


if __name__ == "__main__":
    main()