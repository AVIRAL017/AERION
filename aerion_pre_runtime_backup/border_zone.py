# border_zone.py

import math


class BorderZoneAnalyzer:
    """
    Analyze tracked-object movement relative to a restricted polygon.

    The module is intentionally independent from BorderIntelligence.

    Main output signals:
        - inside_restricted_zone
        - distance_to_zone
        - approach_score
        - direction_relation
        - direction_alignment
        - zone_entry
        - zone_status
        - zone_dwell_frames
        - zone_dwell_score
    """

    def __init__(self, zone_polygon, dwell_threshold=5):

        if not zone_polygon or len(zone_polygon) < 3:
            raise ValueError(
                "zone_polygon must contain at least 3 points."
            )

        self.zone_polygon = zone_polygon
        self.dwell_threshold = dwell_threshold

        # Stateful information for each track
        self.previous_zone_state = {}
        self.dwell_frames = {}
        self.previous_distance = {}
        self.previous_center = {}

    # =========================================================
    # BASIC GEOMETRY
    # =========================================================

    def _point_inside_polygon(self, point):
        """
        Ray-casting point-in-polygon test.

        Returns:
            True  -> point is inside
            False -> point is outside
        """

        x, y = point
        inside = False

        polygon = self.zone_polygon
        n = len(polygon)

        j = n - 1

        for i in range(n):

            xi, yi = polygon[i]
            xj, yj = polygon[j]

            intersects = (
                ((yi > y) != (yj > y))
                and
                (
                    x
                    <
                    (xj - xi) * (y - yi)
                    / ((yj - yi) + 1e-12)
                    + xi
                )
            )

            if intersects:
                inside = not inside

            j = i

        return inside

    # =========================================================
    # POINT → LINE SEGMENT DISTANCE
    # =========================================================

    def _distance_point_to_segment(
        self,
        point,
        segment_start,
        segment_end
    ):
        """
        Calculate shortest Euclidean distance between
        a point and a line segment.
        """

        px, py = point

        x1, y1 = segment_start
        x2, y2 = segment_end

        dx = x2 - x1
        dy = y2 - y1

        # Degenerate segment
        if dx == 0 and dy == 0:
            return math.hypot(
                px - x1,
                py - y1
            )

        # Projection parameter
        t = (
            (px - x1) * dx
            +
            (py - y1) * dy
        ) / (
            dx * dx
            +
            dy * dy
        )

        # Clamp to segment
        t = max(
            0.0,
            min(1.0, t)
        )

        closest_x = x1 + t * dx
        closest_y = y1 + t * dy

        return math.hypot(
            px - closest_x,
            py - closest_y
        )

    # =========================================================
    # DISTANCE TO ZONE BOUNDARY
    # =========================================================

    def _distance_to_boundary(self, point):
        """
        Calculate the shortest distance from a point
        to any edge of the restricted polygon.
        """

        min_distance = float("inf")

        for i in range(len(self.zone_polygon)):

            start = self.zone_polygon[i]

            end = self.zone_polygon[
                (i + 1) % len(self.zone_polygon)
            ]

            distance = self._distance_point_to_segment(
                point,
                start,
                end
            )

            min_distance = min(
                min_distance,
                distance
            )

        return min_distance

    # =========================================================
    # NEAREST BOUNDARY POINT
    # =========================================================

    def _nearest_boundary_point(self, point):
        """
        Return the closest point on the polygon boundary.
        """

        px, py = point

        best_point = None
        best_distance = float("inf")

        for i in range(len(self.zone_polygon)):

            x1, y1 = self.zone_polygon[i]

            x2, y2 = self.zone_polygon[
                (i + 1) % len(self.zone_polygon)
            ]

            dx = x2 - x1
            dy = y2 - y1

            # Degenerate edge
            if dx == 0 and dy == 0:

                candidate = (
                    x1,
                    y1
                )

            else:

                t = (
                    (px - x1) * dx
                    +
                    (py - y1) * dy
                ) / (
                    dx * dx
                    +
                    dy * dy
                )

                t = max(
                    0.0,
                    min(1.0, t)
                )

                candidate = (
                    x1 + t * dx,
                    y1 + t * dy
                )

            distance = math.hypot(
                px - candidate[0],
                py - candidate[1]
            )

            if distance < best_distance:

                best_distance = distance
                best_point = candidate

        return best_point

    # =========================================================
    # MOVEMENT VECTOR
    # =========================================================

    def _movement_vector(
        self,
        current_point,
        previous_point
    ):
        """
        Calculate movement vector:

            previous → current
        """

        if previous_point is None:
            return None

        return (
            current_point[0] - previous_point[0],
            current_point[1] - previous_point[1]
        )

    # =========================================================
    # VECTOR MAGNITUDE
    # =========================================================

    def _vector_magnitude(self, vector):

        if vector is None:
            return 0.0

        return math.hypot(
            vector[0],
            vector[1]
        )

    # =========================================================
    # DIRECTION RELATION
    # =========================================================

    def calculate_direction_relation(
        self,
        current_point,
        previous_point,
        previous_inside,
        current_inside
    ):
        """
        Determine movement relative to the restricted zone.

        Possible values:

            unknown
            stationary
            entering_zone
            leaving_zone
            toward_boundary
            away_from_boundary
            parallel
            deeper_inside

        The transition between inside/outside is evaluated
        separately from the boundary-vector geometry.
        """

        # -----------------------------------------------------
        # No previous point
        # -----------------------------------------------------

        if previous_point is None:

            return {
                "direction_relation": "unknown",
                "direction_alignment": 0.0
            }

        # -----------------------------------------------------
        # Movement vector
        # -----------------------------------------------------

        movement = self._movement_vector(
            current_point,
            previous_point
        )

        movement_magnitude = self._vector_magnitude(
            movement
        )

        # -----------------------------------------------------
        # Stationary
        # -----------------------------------------------------

        if movement_magnitude < 1e-6:

            return {
                "direction_relation": "stationary",
                "direction_alignment": 0.0
            }

        # -----------------------------------------------------
        # ENTERING TRANSITION
        #
        # Outside → Inside
        #
        # This takes precedence over nearest-boundary
        # direction because the object has actually crossed
        # the zone boundary.
        # -----------------------------------------------------

        if not previous_inside and current_inside:

            return {
                "direction_relation": "entering_zone",
                "direction_alignment": 1.0
            }

        # -----------------------------------------------------
        # LEAVING TRANSITION
        #
        # Inside → Outside
        # -----------------------------------------------------

        if previous_inside and not current_inside:

            return {
                "direction_relation": "leaving_zone",
                "direction_alignment": -1.0
            }

        # -----------------------------------------------------
        # BOTH OUTSIDE
        #
        # Compare movement vector against the nearest boundary.
        # -----------------------------------------------------

        if not current_inside:

            nearest_boundary = self._nearest_boundary_point(
                current_point
            )

            if nearest_boundary is None:

                return {
                    "direction_relation": "unknown",
                    "direction_alignment": 0.0
                }

            target_vector = (
                nearest_boundary[0] - current_point[0],
                nearest_boundary[1] - current_point[1]
            )

            target_magnitude = self._vector_magnitude(
                target_vector
            )

            if target_magnitude < 1e-6:

                return {
                    "direction_relation": "boundary",
                    "direction_alignment": 0.0
                }

            alignment = (
                movement[0] * target_vector[0]
                +
                movement[1] * target_vector[1]
            ) / (
                movement_magnitude
                *
                target_magnitude
            )

            alignment = max(
                -1.0,
                min(1.0, alignment)
            )

            if alignment >= 0.5:

                relation = "toward_boundary"

            elif alignment <= -0.5:

                relation = "away_from_boundary"

            else:

                relation = "parallel"

            return {
                "direction_relation": relation,
                "direction_alignment": round(
                    alignment,
                    3
                )
            }

        # -----------------------------------------------------
        # BOTH INSIDE
        #
        # Determine whether movement is:
        #
        #   - deeper_inside
        #   - toward_boundary
        #   - parallel
        # -----------------------------------------------------

        nearest_boundary = self._nearest_boundary_point(
            current_point
        )

        if nearest_boundary is None:

            return {
                "direction_relation": "unknown",
                "direction_alignment": 0.0
            }

        target_vector = (
            nearest_boundary[0] - current_point[0],
            nearest_boundary[1] - current_point[1]
        )

        target_magnitude = self._vector_magnitude(
            target_vector
        )

        if target_magnitude < 1e-6:

            return {
                "direction_relation": "boundary",
                "direction_alignment": 0.0
            }

        alignment = (
            movement[0] * target_vector[0]
            +
            movement[1] * target_vector[1]
        ) / (
            movement_magnitude
            *
            target_magnitude
        )

        alignment = max(
            -1.0,
            min(1.0, alignment)
        )

        # -----------------------------------------------------
        # Distance from boundary
        #
        # If current distance increased, object moved deeper
        # into the zone.
        # -----------------------------------------------------

        current_distance = self._distance_to_boundary(
            current_point
        )

        previous_distance = self._distance_to_boundary(
            previous_point
        )

        distance_change = (
            current_distance
            - previous_distance
        )

        # Strongly moving deeper
        if distance_change > 1e-6:

            relation = "deeper_inside"

        elif alignment >= 0.5:

            relation = "toward_boundary"

        elif alignment <= -0.5:

            relation = "deeper_inside"

        else:

            relation = "parallel"

        return {
            "direction_relation": relation,
            "direction_alignment": round(
                alignment,
                3
            )
        }

    # =========================================================
    # MAIN ANALYSIS
    # =========================================================

    def analyze(self, tracked_detection):
        """
        Analyze one tracked object.

        Required input:

            {
                "track_id": int,
                "center": (x, y)
            }
        """

        track_id = tracked_detection.get(
            "track_id"
        )

        current_point = tracked_detection.get(
            "center"
        )

        if track_id is None:

            raise ValueError(
                "tracked_detection must contain 'track_id'."
            )

        if current_point is None:

            raise ValueError(
                "tracked_detection must contain 'center'."
            )

        current_point = (
            float(current_point[0]),
            float(current_point[1])
        )

        # -----------------------------------------------------
        # Previous state
        # -----------------------------------------------------

        previous_point = self.previous_center.get(
            track_id
        )

        previous_distance = self.previous_distance.get(
            track_id
        )

        previous_inside = self.previous_zone_state.get(
            track_id,
            False
        )

        # -----------------------------------------------------
        # Current state
        # -----------------------------------------------------

        current_inside = self._point_inside_polygon(
            current_point
        )

        current_distance = self._distance_to_boundary(
            current_point
        )

        # -----------------------------------------------------
        # Approach score
        # -----------------------------------------------------

        if previous_distance is None:

            approach_score = 0.0

        elif current_distance < previous_distance:

            approach_score = 1.0

        else:

            approach_score = 0.0

        # -----------------------------------------------------
        # Direction intelligence
        # -----------------------------------------------------

        direction_info = self.calculate_direction_relation(
            current_point=current_point,
            previous_point=previous_point,
            previous_inside=previous_inside,
            current_inside=current_inside
        )

        direction_relation = direction_info[
            "direction_relation"
        ]

        direction_alignment = direction_info[
            "direction_alignment"
        ]

        # -----------------------------------------------------
        # Zone entry
        # -----------------------------------------------------

        zone_entry = (
            current_inside
            and not previous_inside
        )

        # -----------------------------------------------------
        # Zone leaving
        # -----------------------------------------------------

        zone_exit = (
            previous_inside
            and not current_inside
        )

        # -----------------------------------------------------
        # Dwell tracking
        # -----------------------------------------------------

        if current_inside:

            self.dwell_frames[track_id] = (
                self.dwell_frames.get(
                    track_id,
                    0
                )
                + 1
            )

        else:

            self.dwell_frames[track_id] = 0

        dwell_count = self.dwell_frames[
            track_id
        ]

        # -----------------------------------------------------
        # Dwell score
        # -----------------------------------------------------

        if self.dwell_threshold <= 0:

            dwell_score = 0.0

        else:

            dwell_score = min(
                dwell_count
                /
                self.dwell_threshold,
                1.0
            )

        # -----------------------------------------------------
        # Zone status
        # -----------------------------------------------------

        if zone_entry:

            zone_status = "entered"

        elif zone_exit:

            zone_status = "exited"

        elif current_inside:

            zone_status = "inside"

        else:

            zone_status = "outside"

        # -----------------------------------------------------
        # Update state
        # -----------------------------------------------------

        self.previous_center[
            track_id
        ] = current_point

        self.previous_distance[
            track_id
        ] = current_distance

        self.previous_zone_state[
            track_id
        ] = current_inside

        # -----------------------------------------------------
        # Return
        # -----------------------------------------------------

        return {

            "track_id": track_id,

            "inside_restricted_zone": current_inside,

            "distance_to_zone": round(
                current_distance,
                3
            ),

            "previous_distance_to_zone": (
                round(
                    previous_distance,
                    3
                )
                if previous_distance is not None
                else None
            ),

            "approach_score": approach_score,

            "direction_relation": direction_relation,

            "direction_alignment": direction_alignment,

            "zone_entry": zone_entry,

            "zone_exit": zone_exit,

            "zone_status": zone_status,

            "zone_dwell_frames": dwell_count,

            "zone_dwell_score": round(
                dwell_score,
                3
            )
        }