# border_intelligence.py


class BorderIntelligence:

    def __init__(self):

        self.weights = {
            "zone_entry": 0.40,
            "approach": 0.15,
            "movement": 0.15,
            "persistence": 0.10,
            "confidence": 0.05,
            "zone_dwell": 0.05,
            "movement_inside": 0.10
        }

    def _movement_score(self, movement_distance):

        if movement_distance <= 2:
            return 0.0

        if movement_distance >= 20:
            return 1.0

        return (movement_distance - 2) / 18

    def _approach_score(
        self,
        distance_to_zone,
        previous_distance_to_zone
    ):

        if (
            distance_to_zone is None
            or previous_distance_to_zone is None
        ):
            return 0.0

        return (
            1.0
            if distance_to_zone < previous_distance_to_zone
            else 0.0
        )

    def _direction_evidence(
        self,
        direction_relation,
        direction_alignment
    ):

        try:
            alignment = float(direction_alignment)
        except (TypeError, ValueError):
            alignment = 0.0

        alignment = max(
            -1.0,
            min(1.0, alignment)
        )

        if direction_relation == "entering_zone":
            return 1.0

        if direction_relation == "toward_boundary":
            return max(0.0, alignment)

        if direction_relation == "deeper_inside":
            return 1.0

        return 0.0

    def analyze(
        self,
        detection,
        zone_polygon
    ):

        confidence = float(
            detection.get("confidence", 0.0)
        )

        persistence = float(
            detection.get("persistence", 0.0)
        )

        movement_distance = float(
            detection.get("movement_distance", 0.0)
        )

        distance_to_zone = detection.get(
            "distance_to_zone"
        )

        previous_distance = detection.get(
            "previous_distance_to_zone"
        )

        zone_entry = bool(
            detection.get("zone_entry", False)
        )

        zone_exit = bool(
            detection.get("zone_exit", False)
        )

        inside_zone = bool(
            detection.get(
                "inside_restricted_zone",
                False
            )
        )

        dwell_score = float(
            detection.get(
                "zone_dwell_score",
                0.0
            )
        )

        direction_relation = detection.get(
            "direction_relation",
            "unknown"
        )

        direction_alignment = float(
            detection.get(
                "direction_alignment",
                0.0
            )
        )

        direction_score = self._direction_evidence(
            direction_relation,
            direction_alignment
        )

        direction_consistent = (
            direction_relation in {
                "toward_boundary",
                "entering_zone",
                "deeper_inside"
            }
        )

        movement_score = self._movement_score(
            movement_distance
        )

        approach_score = self._approach_score(
            distance_to_zone,
            previous_distance
        )

        # =====================================================
        # MOVING AWAY / LEAVING
        # =====================================================

        moving_away = (
            not inside_zone
            and (
                direction_relation in {
                    "away_from_boundary",
                    "leaving_zone"
                }
                or (
                    previous_distance is not None
                    and distance_to_zone is not None
                    and distance_to_zone > previous_distance
                )
            )
        )

        if moving_away:

            score = round(
                0.05 * confidence
                +
                0.05 * persistence,
                4
            )

            return {
                **detection,

                "border_activity_score": score,
                "border_priority": "LOW",

                "approach_score": 0.0,

                "movement_score": round(
                    movement_score,
                    4
                ),

                "moving_away": True,

                "movement_inside_score": 0.0,

                "direction_relation": direction_relation,

                "direction_alignment": round(
                    direction_alignment,
                    4
                ),

                "direction_score": round(
                    direction_score,
                    4
                ),

                "direction_consistent": direction_consistent,

                "zone_exit": zone_exit
            }

        # =====================================================
        # NORMAL SCORING
        # =====================================================

        movement_inside_score = (
            movement_score
            if inside_zone
            else 0.0
        )

        score = (

            self.weights["zone_entry"]
            * (1.0 if zone_entry else 0.0)

            +

            self.weights["approach"]
            * approach_score

            +

            self.weights["movement"]
            * movement_score

            +

            self.weights["persistence"]
            * persistence

            +

            self.weights["confidence"]
            * confidence

            +

            self.weights["zone_dwell"]
            * dwell_score

            +

            self.weights["movement_inside"]
            * movement_inside_score
        )

        # =====================================================
        # DIRECTION SUPPORT
        # =====================================================

        if (
            approach_score > 0
            and
            direction_relation == "toward_boundary"
        ):

            score += (
                0.05
                * direction_score
            )

        if (
            zone_entry
            and
            direction_relation == "entering_zone"
        ):

            score += 0.05

        if (
            inside_zone
            and
            direction_relation == "deeper_inside"
            and
            movement_inside_score > 0
        ):

            score += (
                0.05
                * direction_score
            )

        score = round(
            min(
                max(score, 0.0),
                1.0
            ),
            4
        )

        # =====================================================
        # PRIORITY
        # =====================================================

        if (
            zone_entry
            and
            movement_inside_score >= 0.5
            and
            direction_relation == "entering_zone"
        ):

            priority = "CRITICAL"

        elif zone_entry:

            priority = "HIGH"

        elif (
            inside_zone
            and
            movement_inside_score >= 0.5
        ):

            priority = "HIGH"

        elif inside_zone:

            priority = "LOW"

        elif approach_score > 0:

            priority = "MEDIUM"

        elif score >= 0.25:

            priority = "MEDIUM"

        else:

            priority = "LOW"

        # =====================================================
        # FINAL RESULT
        # =====================================================

        return {
            **detection,

            "border_activity_score": score,

            "border_priority": priority,

            "approach_score": round(
                approach_score,
                4
            ),

            "movement_score": round(
                movement_score,
                4
            ),

            "moving_away": False,

            "movement_inside_score": round(
                movement_inside_score,
                4
            ),

            "direction_relation": direction_relation,

            "direction_alignment": round(
                direction_alignment,
                4
            ),

            "direction_score": round(
                direction_score,
                4
            ),

            "direction_consistent": direction_consistent,

            "zone_exit": zone_exit
        }