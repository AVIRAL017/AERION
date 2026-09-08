import cv2

from border_pipeline import BorderPipeline


# --------------------------------------------------
# 1. YOLO model
# --------------------------------------------------

MODEL_PATH = (
    r"D:\mp-1\runs\detect"
    r"\visdrone_8s_1280_30ep"
    r"\weights\best.pt"
)


# --------------------------------------------------
# 2. Restricted zone
# --------------------------------------------------

ZONE_POLYGON = [
    (900, 200),
    (1200, 200),
    (1200, 700),
    (900, 700)
]


# --------------------------------------------------
# 3. Test image
# --------------------------------------------------

IMAGE_PATH = r"D:\mp-1\before.png"


# --------------------------------------------------
# 4. Main test
# --------------------------------------------------

if __name__ == "__main__":

    print("=" * 70)
    print("BORDER YOLO PIPELINE TEST")
    print("=" * 70)

    # Load image
    frame = cv2.imread(IMAGE_PATH)

    if frame is None:
        raise FileNotFoundError(
            f"Could not load image: {IMAGE_PATH}"
        )

    print(
        f"Image size: "
        f"{frame.shape[1]} x {frame.shape[0]}"
    )

    # Initialize pipeline
    pipeline = BorderPipeline(
        model_path=MODEL_PATH,
        zone_polygon=ZONE_POLYGON
    )

    # Process image
    results = pipeline.process_frame(frame)

    print(
        f"\nDetections processed: "
        f"{len(results)}"
    )

    print("-" * 70)

    # Display results
    for i, result in enumerate(results, 1):

        print(f"\nObject {i}")

        print(
            "Track ID:          ",
            result.get("track_id")
        )

        print(
            "Class ID:          ",
            result.get("class_id")
        )

        print(
            "Confidence:        ",
            round(
                result.get("confidence", 0),
                3
            )
        )

        print(
            "Inside zone:       ",
            result.get(
                "inside_restricted_zone"
            )
        )

        print(
            "Zone entry:        ",
            result.get("zone_entry")
        )

        print(
            "Zone exit:         ",
            result.get("zone_exit")
        )

        print(
            "Movement:          ",
            round(
                result.get(
                    "movement_distance",
                    0
                ),
                2
            )
        )

        print(
            "Direction:         ",
            result.get(
                "direction_relation"
            )
        )

        print(
            "Direction score:   ",
            result.get(
                "direction_score"
            )
        )

        print(
            "Border score:      ",
            result.get(
                "border_activity_score"
            )
        )

        print(
            "Priority:          ",
            result.get(
                "border_priority"
            )
        )

        print(
            "Moving away:       ",
            result.get(
                "moving_away"
            )
        )

    print("\n" + "=" * 70)
    print("BORDER YOLO PIPELINE TEST COMPLETE")
    print("=" * 70)