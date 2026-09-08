import time

from video_input import VideoInput
from border_pipeline import BorderPipeline


VIDEO_PATH = r"D:\mp-1\border_test_videos\border_test_urban.mp4.mp4"

MODEL_PATH = (
    r"D:\mp-1\runs\detect\visdrone_8s_1280_30ep"
    r"\weights\best.pt"
)

ZONE_POLYGON = [
    (900, 200),
    (1200, 200),
    (1200, 700),
    (900, 700),
]


def run_benchmark(imgsz):

    print()
    print(f"Running BorderPipeline at imgsz={imgsz}...")

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

    frame_count = 0
    detections = 0
    alerts = 0
    critical = 0
    high = 0

    start = time.perf_counter()

    while True:

        frame = video.read()

        if frame is None:
            break

        results = pipeline.process_frame(
            frame,
            frame_number=frame_count,
            imgsz=imgsz
        )

        frame_count += 1
        detections += len(results)

        for result in results:

            if result.get("border_alert", False):

                alerts += 1

                priority = result.get(
                    "border_priority",
                    "UNKNOWN"
                )

                if priority == "CRITICAL":
                    critical += 1

                elif priority == "HIGH":
                    high += 1

    elapsed = time.perf_counter() - start

    video.release()

    return {
        "frames": frame_count,
        "detections": detections,
        "alerts": alerts,
        "critical": critical,
        "high": high,
        "time": elapsed,
        "fps": frame_count / elapsed,
    }


def main():

    print("=" * 70)
    print("BORDER PIPELINE RESOLUTION COMPARISON")
    print("=" * 70)

    result_640 = run_benchmark(640)

    result_1280 = run_benchmark(1280)

    print()
    print("=" * 70)
    print("FINAL RESULTS")
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
        f"{'Alerts':<25}"
        f"{result_640['alerts']:>15}"
        f"{result_1280['alerts']:>15}"
    )

    print(
        f"{'Critical':<25}"
        f"{result_640['critical']:>15}"
        f"{result_1280['critical']:>15}"
    )

    print(
        f"{'High':<25}"
        f"{result_640['high']:>15}"
        f"{result_1280['high']:>15}"
    )

    print(
        f"{'Processing time (s)':<25}"
        f"{result_640['time']:>15.2f}"
        f"{result_1280['time']:>15.2f}"
    )

    print(
        f"{'Effective FPS':<25}"
        f"{result_640['fps']:>15.2f}"
        f"{result_1280['fps']:>15.2f}"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()