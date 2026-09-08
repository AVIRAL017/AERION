# border_pipeline.py

from ultralytics import YOLO

from border_tracking import BorderTracker
from border_zone import BorderZoneAnalyzer
from border_intelligence import BorderIntelligence
from border_event_filter import BorderEventFilter


class BorderPipeline:

    def __init__(
        self,
        model_path,
        zone_polygon,
        persistence_threshold=10,
        movement_threshold=2.0,
        history_length=30,
        dwell_threshold=5
    ):

        # --------------------------------------------------
        # YOLO detector
        # --------------------------------------------------

        self.model = YOLO(
            model_path
        )

        # --------------------------------------------------
        # Tracking
        # --------------------------------------------------

        self.tracker = BorderTracker(
            persistence_threshold=persistence_threshold,
            movement_threshold=movement_threshold,
            history_length=history_length
        )

        # --------------------------------------------------
        # Zone analyzer
        # --------------------------------------------------

        self.zone_analyzer = BorderZoneAnalyzer(
            zone_polygon=zone_polygon,
            dwell_threshold=dwell_threshold
        )

        # --------------------------------------------------
        # Border intelligence
        # --------------------------------------------------

        self.intelligence = BorderIntelligence()

        # --------------------------------------------------
        # Event filter
        # --------------------------------------------------

        self.event_filter = BorderEventFilter()

        self.zone_polygon = zone_polygon

    # ======================================================
    # PROCESS FRAME
    # ======================================================

    def process_frame(
        self,
        frame,
        frame_number=0,
        imgsz=1280
    ):

        # --------------------------------------------------
        # YOLO + ByteTrack
        # --------------------------------------------------

        results = self.model.track(
            frame,
            persist=True,
            tracker="bytetrack.yaml",
            imgsz=imgsz,
            verbose=False
        )

        detections = []

        # --------------------------------------------------
        # Convert YOLO detections
        # --------------------------------------------------

        for result in results:

            if result.boxes is None:
                continue

            boxes = result.boxes

            for i in range(len(boxes)):

                xyxy = (
                    boxes.xyxy[i]
                    .cpu()
                    .numpy()
                )

                confidence = float(
                    boxes.conf[i]
                    .cpu()
                    .item()
                )

                class_id = int(
                    boxes.cls[i]
                    .cpu()
                    .item()
                )

                track_id = None

                if boxes.id is not None:

                    track_id = int(
                        boxes.id[i]
                        .cpu()
                        .item()
                    )

                x1, y1, x2, y2 = xyxy

                center = (
                    float((x1 + x2) / 2),
                    float((y1 + y2) / 2)
                )

                detections.append({
                    "track_id": track_id,
                    "class_id": class_id,
                    "confidence": confidence,
                    "bbox": [
                        float(x1),
                        float(y1),
                        float(x2),
                        float(y2)
                    ],
                    "center": center
                })

        # --------------------------------------------------
        # Tracking
        # --------------------------------------------------

        tracked = self.tracker.update(
            detections
        )

        enriched = []

        # --------------------------------------------------
        # Zone + Intelligence + Event Filter
        # --------------------------------------------------

        for detection in tracked:

            # --------------------------------------------------
            # Safety check
            # --------------------------------------------------

            if detection.get("track_id") is None:
                continue

            # --------------------------------------------------
            # Zone analysis
            # --------------------------------------------------

            zone_result = (
                self.zone_analyzer.analyze(
                    detection
                )
            )

            combined = {
                **detection,
                **zone_result
            }

            # --------------------------------------------------
            # Border intelligence
            # --------------------------------------------------

            intelligence = (
                self.intelligence.analyze(
                    combined,
                    self.zone_polygon
                )
            )

            # --------------------------------------------------
            # Event filter
            # --------------------------------------------------

            event_result = (
                self.event_filter.evaluate(
                    intelligence,
                    frame_number
                )
            )

            # --------------------------------------------------
            # Add event information
            # --------------------------------------------------

            intelligence.update(
                event_result
            )

            # --------------------------------------------------
            # Register only real alerts
            # --------------------------------------------------

            if intelligence.get(
                "border_alert",
                False
            ):

                self.event_filter.register_alert(
                    intelligence,
                    frame_number
                )

            enriched.append(
                intelligence
            )

        return enriched