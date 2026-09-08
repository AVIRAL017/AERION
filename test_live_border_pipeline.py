import time

from live_video_input import LiveVideoInput
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


def main():

    print("=" * 70)
    print("REAL-TIME SIMULATION: VIDEO + BORDER PIPELINE")
    print("=" * 70)

    video = LiveVideoInput(
        VIDEO_PATH,
        buffer_size=2
    )

    pipeline = BorderPipeline(
        model_path=MODEL_PATH,
        zone_polygon=ZONE_POLYGON,
        persistence_threshold=10,
        movement_threshold=2.0,
        history_length=30,
        dwell_threshold=5,
    )

    video.open()

    source_fps = video.fps()

    print(f"Source: {VIDEO_PATH}")
    print(f"Resolution: {video.width()} x {video.height()}")
    print(f"Source FPS: {source_fps}")
    print()

    processed_frames = 0
    skipped_frames = 0

    total_detections = 0
    total_alerts = 0
    critical_alerts = 0
    high_alerts = 0

    last_processed_frame = -1
    processing_times = []

    simulation_start = time.perf_counter()

    # Simulate a real 24 FPS camera.
    frame_interval = 1.0 / source_fps
    next_capture_time = time.perf_counter()

    while video.is_open():

        # Wait until the next simulated camera frame time.
        now = time.perf_counter()

        if now < next_capture_time:
            time.sleep(next_capture_time - now)

        next_capture_time += frame_interval

        frame, frame_number = video.read()

        if frame is None:
            time.sleep(0.001)
            continue

        # Count frames skipped by the latest-frame buffer.
        if last_processed_frame >= 0:
            skipped = frame_number - last_processed_frame - 1

            if skipped > 0:
                skipped_frames += skipped

        frame_start = time.perf_counter()

        results = pipeline.process_frame(
            frame,
            frame_number=frame_number
        )

        frame_end = time.perf_counter()

        processing_times.append(
            frame_end - frame_start
        )

        processed_frames += 1
        last_processed_frame = frame_number

        total_detections += len(results)

        for result in results:

            if result.get("border_alert", False):

                total_alerts += 1

                priority = result.get(
                    "border_priority",
                    "UNKNOWN"
                )

                if priority == "CRITICAL":
                    critical_alerts += 1

                elif priority == "HIGH":
                    high_alerts += 1

        if processed_frames % 25 == 0:

            elapsed = time.perf_counter() - simulation_start

            processing_fps = (
                processed_frames / elapsed
                if elapsed > 0
                else 0
            )

            print(
                f"Processed: {processed_frames:4d} | "
                f"Latest source frame: {frame_number:4d} | "
                f"Skipped: {skipped_frames:4d} | "
                f"FPS: {processing_fps:6.2f}"
            )

    total_time = time.perf_counter() - simulation_start

    video.release()

    average_latency = (
        sum(processing_times) /
        len(processing_times)
        if processing_times
        else 0
    )

    effective_fps = (
        processed_frames / total_time
        if total_time > 0
        else 0
    )

    print()
    print("=" * 70)
    print("REAL-TIME SIMULATION COMPLETE")
    print("=" * 70)

    print(f"Source FPS:             {source_fps:.2f}")
    print(f"Processed frames:       {processed_frames}")
    print(f"Skipped frames:         {skipped_frames}")
    print()

    print(f"Total detections:       {total_detections}")
    print(f"Total alerts:           {total_alerts}")
    print(f"Critical alerts:        {critical_alerts}")
    print(f"High alerts:            {high_alerts}")
    print()

    print(f"Total processing time:  {total_time:.2f} seconds")
    print(f"Effective processing FPS:{effective_fps:.2f}")
    print(f"Average inference time: {average_latency * 1000:.2f} ms")

    if processing_times:

        print(
            f"Minimum inference time: "
            f"{min(processing_times) * 1000:.2f} ms"
        )

        print(
            f"Maximum inference time: "
            f"{max(processing_times) * 1000:.2f} ms"
        )

    print("=" * 70)


if __name__ == "__main__":
    main()