from video_input import VideoInput
from border_pipeline import BorderPipeline


VIDEO_PATH = (
    r"D:\mp-1\border_test_videos"
    r"\border_test_urban.mp4.mp4"
)

MODEL_PATH = (
    r"D:\mp-1\runs\detect"
    r"\visdrone_8s_1280_30ep"
    r"\weights\best.pt"
)

ZONE_POLYGON = [
    (900, 200),
    (1200, 200),
    (1200, 700),
    (900, 700)
]


def main():

    video = VideoInput(VIDEO_PATH)
    video.open()

    pipeline = BorderPipeline(
        model_path=MODEL_PATH,
        zone_polygon=ZONE_POLYGON,
        persistence_threshold=10,
        movement_threshold=2.0,
        history_length=30,
        dwell_threshold=5
    )

    print("=" * 70)
    print("BORDER PIPELINE + VIDEO INPUT TEST")
    print("=" * 70)

    print("Video:", VIDEO_PATH)
    print("Resolution:", video.width(), "x", video.height())
    print("Input FPS:", video.fps())

    frame_number = 0
    total_detections = 0
    total_alerts = 0
    critical_alerts = 0
    high_alerts = 0

    while True:

        frame = video.read()

        if frame is None:
            break

        frame_number += 1

        results = pipeline.process_frame(
            frame,
            frame_number=frame_number
        )

        total_detections += len(results)

        for result in results:

            if result.get(
                "border_alert",
                False
            ):

                total_alerts += 1

                priority = result.get(
                    "border_priority",
                    "LOW"
                )

                if priority == "CRITICAL":
                    critical_alerts += 1

                elif priority == "HIGH":
                    high_alerts += 1

                print(
                    f"[ALERT] "
                    f"Frame={frame_number} "
                    f"Track={result.get('track_id')} "
                    f"Class={result.get('class_name', result.get('class_id'))} "
                    f"Priority={priority} "
                    f"Score={result.get('border_activity_score', 0):.3f} "
                    f"Direction={result.get('direction_relation')}"
                    )

        if frame_number % 100 == 0:

            print(
                f"Frames processed: "
                f"{frame_number}"
            )

    video.release()

    print("=" * 70)
    print("BORDER PIPELINE + VIDEO INPUT TEST COMPLETE")
    print("=" * 70)

    print(
        f"Frames processed:   {frame_number}"
    )

    print(
        f"Total detections:   {total_detections}"
    )

    print(
        f"Filtered alerts:    {total_alerts}"
    )

    print(
        f"Critical alerts:    {critical_alerts}"
    )

    print(
        f"High alerts:        {high_alerts}"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()