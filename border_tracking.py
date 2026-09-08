from collections import defaultdict
from math import hypot


class BorderTracker:
    def __init__(
        self,
        persistence_threshold=10,
        movement_threshold=2.0,
        history_length=30
    ):
        self.history = defaultdict(list)

        self.persistence_threshold = persistence_threshold
        self.movement_threshold = movement_threshold
        self.history_length = history_length

    def _get_direction(self, history):
        """
        Determine movement direction using the recent trajectory.

        Image coordinates:
            x increases -> right/east
            y increases -> down/south
        """

        if len(history) < 2:
            return "unknown"

        start = history[0]
        end = history[-1]

        dx = end["x"] - start["x"]
        dy = end["y"] - start["y"]

        displacement = hypot(dx, dy)

        if displacement < self.movement_threshold:
            return "stationary"

        # Mostly horizontal movement
        if abs(dx) > abs(dy) * 2:
            return "east" if dx > 0 else "west"

        # Mostly vertical movement
        if abs(dy) > abs(dx) * 2:
            return "south" if dy > 0 else "north"

        # Diagonal movement
        if dx > 0 and dy > 0:
            return "south-east"

        if dx > 0 and dy < 0:
            return "north-east"

        if dx < 0 and dy > 0:
            return "south-west"

        return "north-west"

    def update(self, detections):
        """
        Update tracking information for the current frame.

        Expected detection format:

        [
            {
                "track_id": 1,
                "object_class": "person",
                "confidence": 0.87,
                "bbox": [x1, y1, x2, y2]
            }
        ]

        Returns the same detections enriched with:

            center
            previous_center
            frames_seen
            movement_distance
            displacement
            direction
            persistence
        """

        results = []

        for detection in detections:

            track_id = detection["track_id"]
            bbox = detection["bbox"]

            x1, y1, x2, y2 = bbox

            # Current object center
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2

            history = self.history[track_id]

            # Save the previous center BEFORE adding
            # the current position to history.
            previous_center = None

            if history:
                previous_center = [
                    history[-1]["x"],
                    history[-1]["y"]
                ]

            # Add current position
            history.append({
                "x": center_x,
                "y": center_y
            })

            # Keep only recent trajectory
            if len(history) > self.history_length:
                history.pop(0)

            frames_seen = len(history)

            # Frame-to-frame movement
            movement_distance = 0.0

            if previous_center is not None:
                movement_distance = hypot(
                    center_x - previous_center[0],
                    center_y - previous_center[1]
                )

            # Total displacement over stored trajectory
            displacement = 0.0

            if len(history) >= 2:
                displacement = hypot(
                    history[-1]["x"] - history[0]["x"],
                    history[-1]["y"] - history[0]["y"]
                )

            # Persistence score
            persistence = min(
                frames_seen / self.persistence_threshold,
                1.0
            )

            # Direction
            direction = self._get_direction(history)

            results.append({
                **detection,

                "center": [
                    center_x,
                    center_y
                ],

                "previous_center": previous_center,

                "frames_seen": frames_seen,

                "movement_distance": round(
                    movement_distance,
                    4
                ),

                "displacement": round(
                    displacement,
                    4
                ),

                "direction": direction,

                "persistence": round(
                    persistence,
                    4
                )
            })

        return results