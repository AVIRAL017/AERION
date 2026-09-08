import cv2
import numpy as np

from border_pipeline import BorderPipeline


# ============================================================
# CONFIGURATION
# ============================================================

MODEL_PATH = (
    r"D:\mp-1\runs\detect"
    r"\visdrone_8s_1280_30ep"
    r"\weights\best.pt"
)

VIDEO_PATH = (
    r"D:\mp-1\border_test_videos"
    r"\border_test_urban.mp4.mp4"
)

OUTPUT_PATH = (
    r"D:\mp-1\border_test_videos"
    r"\border_pipeline_filtered.mp4"
)


# ============================================================
# RESTRICTED ZONE
# ============================================================

ZONE_POLYGON = [
    (900, 200),
    (1200, 200),
    (1200, 700),
    (900, 700)
]


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    print("=" * 70)
    print("FILTERED BORDER VIDEO PIPELINE TEST")
    print("=" * 70)

    # --------------------------------------------------------
    # Open video
    # --------------------------------------------------------

    cap = cv2.VideoCapture(
        VIDEO_PATH
    )

    if not cap.isOpened():

        raise RuntimeError(
            f"Could not open video:\n{VIDEO_PATH}"
        )

    width = int(
        cap.get(
            cv2.CAP_PROP_FRAME_WIDTH
        )
    )

    height = int(
        cap.get(
            cv2.CAP_PROP_FRAME_HEIGHT
        )
    )

    fps = cap.get(
        cv2.CAP_PROP_FPS
    )

    total_frames = int(
        cap.get(
            cv2.CAP_PROP_FRAME_COUNT
        )
    )

    print(
        f"Video size:    {width} x {height}"
    )

    print(
        f"FPS:           {fps:.2f}"
    )

    print(
        f"Total frames:  {total_frames}"
    )

    # --------------------------------------------------------
    # Output video
    # --------------------------------------------------------

    fourcc = cv2.VideoWriter_fourcc(
        *"mp4v"
    )

    writer = cv2.VideoWriter(
        OUTPUT_PATH,
        fourcc,
        fps,
        (width, height)
    )

    # --------------------------------------------------------
    # Initialize pipeline
    # --------------------------------------------------------

    pipeline = BorderPipeline(
        model_path=MODEL_PATH,
        zone_polygon=ZONE_POLYGON
    )

    # --------------------------------------------------------
    # Statistics
    # --------------------------------------------------------

    frame_number = 0

    total_detections = 0

    filtered_alerts = 0

    critical_alerts = 0

    high_alerts = 0

    medium_alerts = 0

    alerted_tracks = set()

    # --------------------------------------------------------
    # Process video
    # --------------------------------------------------------

    while True:

        success, frame = cap.read()

        if not success:
            break

        frame_number += 1

        # ----------------------------------------------------
        # Run complete pipeline
        # ----------------------------------------------------

        results = pipeline.process_frame(
            frame,
            frame_number
        )

        total_detections += len(
            results
        )

        # ----------------------------------------------------
        # Draw restricted zone
        # ----------------------------------------------------

        polygon = np.array(
            ZONE_POLYGON,
            dtype=np.int32
        )

        cv2.polylines(
            frame,
            [polygon],
            True,
            (255, 255, 0),
            2
        )

        # ----------------------------------------------------
        # Process each object
        # ----------------------------------------------------

        for result in results:

            bbox = result.get(
                "bbox"
            )

            if bbox is None:
                continue

            x1, y1, x2, y2 = map(
                int,
                bbox
            )

            track_id = result.get(
                "track_id",
                "?"
            )

            confidence = float(
                result.get(
                    "confidence",
                    0.0
                )
            )

            priority = result.get(
                "border_priority",
                "LOW"
            )

            direction = result.get(
                "direction_relation",
                "unknown"
            )

            inside = result.get(
                "inside_restricted_zone",
                False
            )

            score = float(
                result.get(
                    "border_activity_score",
                    0.0
                )
            )

            border_alert = bool(
                result.get(
                    "border_alert",
                    False
                )
            )

            class_id = result.get(
                "class_id"
            )

            # ------------------------------------------------
            # Class name
            # ------------------------------------------------

            if class_id is not None:

                class_name = (
                    pipeline.model.names.get(
                        int(class_id),
                        str(class_id)
                    )
                )

            else:

                class_name = "object"

            # ------------------------------------------------
            # Count filtered alerts
            # ------------------------------------------------

            if border_alert:

                filtered_alerts += 1

                alerted_tracks.add(
                    track_id
                )

                if priority == "CRITICAL":

                    critical_alerts += 1

                elif priority == "HIGH":

                    high_alerts += 1

                elif priority == "MEDIUM":

                    medium_alerts += 1

                # --------------------------------------------
                # Console alert
                # --------------------------------------------

                print()
                print(
                    "[BORDER ALERT]"
                )

                print(
                    f"Frame:       {frame_number}"
                )

                print(
                    f"Object:      {class_name}"
                )

                print(
                    f"Track ID:    {track_id}"
                )

                print(
                    f"Confidence:  {confidence:.3f}"
                )

                print(
                    f"Zone:        "
                    f"{'INSIDE' if inside else 'OUTSIDE'}"
                )

                print(
                    f"Direction:   {direction}"
                )

                print(
                    f"Score:       {score:.3f}"
                )

                print(
                    f"Priority:    {priority}"
                )

            # ------------------------------------------------
            # Draw only meaningful information
            # ------------------------------------------------

            cv2.rectangle(
                frame,
                (x1, y1),
                (x2, y2),
                (0, 255, 0),
                2
            )

            label = (
                f"{class_name} "
                f"ID:{track_id}"
            )

            cv2.putText(
                frame,
                label,
                (x1, max(y1 - 10, 20)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 255, 0),
                2
            )

            # ------------------------------------------------
            # Show border state
            # ------------------------------------------------

            state = (
                f"{priority} "
                f"S:{score:.2f}"
            )

            cv2.putText(
                frame,
                state,
                (
                    x1,
                    min(
                        y2 + 20,
                        height - 10
                    )
                ),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1
            )

            # ------------------------------------------------
            # Explicit ALERT label
            # ------------------------------------------------

            if border_alert:

                cv2.putText(
                    frame,
                    "BORDER ALERT",
                    (
                        x1,
                        max(
                            y1 - 30,
                            20
                        )
                    ),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (0, 0, 255),
                    2
                )

        # ----------------------------------------------------
        # Frame counter
        # ----------------------------------------------------

        cv2.putText(
            frame,
            f"Frame: "
            f"{frame_number}/{total_frames}",
            (20, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2
        )

        # ----------------------------------------------------
        # Write output
        # ----------------------------------------------------

        writer.write(
            frame
        )

        # ----------------------------------------------------
        # Progress
        # ----------------------------------------------------

        if frame_number % 50 == 0:

            print(
                f"Processed "
                f"{frame_number}/"
                f"{total_frames} frames"
            )

    # --------------------------------------------------------
    # Cleanup
    # --------------------------------------------------------

    cap.release()

    writer.release()

    # --------------------------------------------------------
    # Final report
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("FILTERED BORDER VIDEO TEST COMPLETE")
    print("=" * 70)

    print(
        f"Frames processed:       "
        f"{frame_number}"
    )

    print(
        f"Total detections:       "
        f"{total_detections}"
    )

    print(
        f"Filtered alerts:        "
        f"{filtered_alerts}"
    )

    print(
        f"Unique alerted tracks:  "
        f"{len(alerted_tracks)}"
    )

    print(
        f"Critical alerts:        "
        f"{critical_alerts}"
    )

    print(
        f"High alerts:            "
        f"{high_alerts}"
    )

    print(
        f"Medium alerts:          "
        f"{medium_alerts}"
    )

    print()
    print(
        "Output video:"
    )

    print(
        OUTPUT_PATH
    )

    print("=" * 70)