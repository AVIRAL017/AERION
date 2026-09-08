from border_pipeline import BorderPipeline


MODEL_PATH = (
    r"D:\mp-1\runs\detect"
    r"\visdrone_8s_1280_30ep"
    r"\weights\best.pt"
)

VIDEO_PATH = (
    r"D:\mp-1\border_test_videos"
    r"\border_test_urban.mp4.mp4"
)

ZONE_POLYGON = [
    (900, 200),
    (1200, 200),
    (1200, 700),
    (900, 700)
]


def main():

    import cv2

    pipeline = BorderPipeline(
        model_path=MODEL_PATH,
        zone_polygon=ZONE_POLYGON,
        persistence_threshold=10,
        movement_threshold=2.0,
        history_length=30,
        dwell_threshold=5
    )

    cap = cv2.VideoCapture(VIDEO_PATH)

    if not cap.isOpened():
        raise RuntimeError(
            f"Could not open video: {VIDEO_PATH}"
        )

    frame_number = 0

    while True:

        success, frame = cap.read()

        if not success:
            break

        frame_number += 1

        results = pipeline.process_frame(
            frame,
            frame_number=frame_number
        )

        if results:

            print("\n" + "=" * 70)
            print("ACTUAL BORDER PIPELINE RESULT")
            print("=" * 70)

            result = results[0]

            print("Returned keys:")
            print(sorted(result.keys()))

            print("\nComplete result:")

            for key, value in result.items():
                print(f"{key}: {value}")

            break

    cap.release()


if __name__ == "__main__":
    main()