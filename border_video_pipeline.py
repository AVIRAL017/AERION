from ultralytics import YOLO

from border_tracking import BorderTracker
from border_zone import BorderZoneAnalyzer
from border_intelligence import BorderIntelligence
from terrain_context import TerrainContext


MODEL_PATH = r"D:\mp-1\runs\detect\visdrone_8s_1280_30ep\weights\best.pt"

VIDEO_PATH = r"D:\mp-1\border_test_videos\border_test_urban.mp4.mp4"

OUTPUT_PATH = r"D:\mp-1\border_test_output_terrain.mp4"

# Current test environment.
# This is metadata, not automatic terrain classification.
TERRAIN_TYPE = "arid"


ZONE_POLYGON = [
    (200, 150),
    (1000, 150),
    (1000, 600),
    (200, 600)
]


CLASS_NAMES = {
    0: "person",
    1: "light_vehicle",
    2: "bus",
    3: "truck",
    4: "motorbike",
    5: "other_transport"
}


def main():

    print("=" * 60)
    print("GEOSHIELD AI - BORDER MODE")
    print("=" * 60)

    # --------------------------------------------------
    # Load terrain context
    # --------------------------------------------------

    terrain = TerrainContext(TERRAIN_TYPE)

    terrain_data = terrain.get_context()

    print("\nTerrain context:")
    print("Environment:", terrain_data["environment"])
    print(
        "Relevant objects:",
        ", ".join(terrain_data["relevant_objects"])
    )

    # --------------------------------------------------
    # Load YOLO
    # --------------------------------------------------

    print("\nLoading YOLO model...")

    model = YOLO(MODEL_PATH)

    print("Model loaded.")

    # --------------------------------------------------
    # Initialize Border modules
    # --------------------------------------------------

    tracker = BorderTracker(
        persistence_threshold=10,
        movement_threshold=2.0,
        history_length=30
    )

    zone_analyzer = BorderZoneAnalyzer(
        zone_polygon=ZONE_POLYGON,
        dwell_threshold=5
    )

    intelligence = BorderIntelligence()

    print("\nStarting video processing...")
    print("Video:", VIDEO_PATH)

    results = model.track(
        source=VIDEO_PATH,
        tracker="bytetrack.yaml",
        persist=True,
        stream=True,
        imgsz=1280,
        conf=0.35,
        verbose=False
    )

    frame_number = 0
    highest_score = 0.0
    highest_priority = "LOW"

    output_writer = None

    import cv2

    for result in results:

        frame_number += 1

        frame = result.orig_img

        # --------------------------------------------------
        # Initialize video writer
        # --------------------------------------------------

        if output_writer is None:

            height, width = frame.shape[:2]

            fourcc = cv2.VideoWriter_fourcc(
                *"mp4v"
            )

            output_writer = cv2.VideoWriter(
                OUTPUT_PATH,
                fourcc,
                30,
                (width, height)
            )

        # --------------------------------------------------
        # Extract YOLO + ByteTrack detections
        # --------------------------------------------------

        detections = []

        if result.boxes is not None:

            boxes = result.boxes

            for i in range(len(boxes)):

                if boxes.id is None:
                    continue

                track_id = int(
                    boxes.id[i].item()
                )

                class_id = int(
                    boxes.cls[i].item()
                )

                confidence = float(
                    boxes.conf[i].item()
                )

                bbox = boxes.xyxy[i].tolist()

                object_class = CLASS_NAMES.get(
                    class_id,
                    f"class_{class_id}"
                )

                detections.append({
                    "track_id": track_id,
                    "object_class": object_class,
                    "confidence": confidence,
                    "bbox": bbox
                })

        # --------------------------------------------------
        # Border Tracking
        # --------------------------------------------------

        tracked = tracker.update(
            detections
        )

        analyzed = []

        for detection in tracked:

            # --------------------------------------------------
            # Restricted-zone analysis
            # --------------------------------------------------

            zone_result = zone_analyzer.analyze(
                detection
            )

            # --------------------------------------------------
            # Border intelligence
            # --------------------------------------------------

            intelligence_result = intelligence.analyze(
                zone_result,
                ZONE_POLYGON
            )

            # Add terrain context WITHOUT changing score
            intelligence_result["terrain"] = (
                terrain_data["terrain_type"]
            )

            intelligence_result["environment"] = (
                terrain_data["environment"]
            )

            intelligence_result["terrain_relevant"] = (
                terrain.is_object_relevant(
                    detection["object_class"]
                )
            )

            analyzed.append(
                intelligence_result
            )

            score = intelligence_result[
                "border_activity_score"
            ]

            priority = intelligence_result[
                "border_priority"
            ]

            if score > highest_score:

                highest_score = score
                highest_priority = priority

            # --------------------------------------------------
            # Log significant events
            # --------------------------------------------------

            if (
                zone_result["zone_entry"]
                or priority in [
                    "HIGH",
                    "CRITICAL"
                ]
            ):

                print(
                    f"Frame {frame_number} | "
                    f"Track {detection['track_id']} | "
                    f"{detection['object_class']} | "
                    f"Terrain={terrain_data['terrain_type']} | "
                    f"Zone={zone_result['zone_status']} | "
                    f"Score={score:.3f} | "
                    f"Priority={priority}"
                )

        # --------------------------------------------------
        # Draw restricted zone
        # --------------------------------------------------

        for j in range(
            len(ZONE_POLYGON)
        ):

            p1 = ZONE_POLYGON[j]

            p2 = ZONE_POLYGON[
                (j + 1) % len(ZONE_POLYGON)
            ]

            cv2.line(
                frame,
                p1,
                p2,
                (0, 0, 255),
                3
            )

        # --------------------------------------------------
        # Draw detections
        # --------------------------------------------------

        for item in analyzed:

            x1, y1, x2, y2 = map(
                int,
                item["bbox"]
            )

            track_id = item["track_id"]

            object_class = item[
                "object_class"
            ]

            priority = item[
                "border_priority"
            ]

            score = item[
                "border_activity_score"
            ]

            label = (
                f"ID {track_id} | "
                f"{object_class} | "
                f"{priority} "
                f"{score:.2f}"
            )

            cv2.rectangle(
                frame,
                (x1, y1),
                (x2, y2),
                (255, 255, 0),
                2
            )

            cv2.putText(
                frame,
                label,
                (x1, max(20, y1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 255, 0),
                2
            )

        # --------------------------------------------------
        # Header
        # --------------------------------------------------

        cv2.putText(
            frame,
            (
                "GeoShield AI | BORDER MODE | "
                f"Terrain: {terrain_data['terrain_type']}"
            ),
            (20, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (255, 255, 255),
            2
        )

        output_writer.write(frame)

    # --------------------------------------------------
    # Cleanup
    # --------------------------------------------------

    if output_writer is not None:
        output_writer.release()

    print("\n" + "=" * 60)
    print("PROCESSING COMPLETE")
    print("=" * 60)

    print("Terrain:", terrain_data["terrain_type"])
    print("Frames processed:", frame_number)
    print(
        "Highest score:",
        round(highest_score, 4)
    )
    print(
        "Highest priority:",
        highest_priority
    )

    print("\nOutput saved to:")
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()