# border_event_filter.py


class BorderEventFilter:

    def __init__(
        self,
        min_confidence=0.30,
        min_persistence=0.3,
        cooldown_frames=30
    ):
        self.min_confidence = min_confidence
        self.min_persistence = min_persistence
        self.cooldown_frames = cooldown_frames

        self.last_alert_frame = {}

    def evaluate(self, result, frame_number):

        track_id = result.get("track_id")

        confidence = float(
            result.get("confidence", 0.0)
        )

        persistence = float(
            result.get("persistence", 0.0)
        )

        priority = result.get(
            "border_priority",
            "LOW"
        )

        direction = result.get(
            "direction_relation",
            "unknown"
        )

        zone_entry = bool(
            result.get("zone_entry", False)
        )

        inside_zone = bool(
            result.get(
                "inside_restricted_zone",
                False
            )
        )

        moving_away = bool(
            result.get(
                "moving_away",
                False
            )
        )

        # --------------------------------------------------
        # Default state
        # --------------------------------------------------

        border_candidate = False
        border_alert = False
        alert_level = "NONE"

        # --------------------------------------------------
        # Basic quality filters
        # --------------------------------------------------

        if confidence < self.min_confidence:
            return {
                "border_candidate": False,
                "border_alert": False,
                "alert_level": "NONE"
            }

        if moving_away:
            return {
                "border_candidate": False,
                "border_alert": False,
                "alert_level": "NONE"
            }

        # --------------------------------------------------
        # Direction must provide meaningful evidence
        # --------------------------------------------------

        meaningful_direction = direction in {
            "entering_zone",
            "toward_boundary",
            "deeper_inside"
        }

        if not meaningful_direction:
            return {
                "border_candidate": False,
                "border_alert": False,
                "alert_level": "NONE"
            }

        # --------------------------------------------------
        # Candidate event
        # --------------------------------------------------

        if (
            direction == "toward_boundary"
            and not inside_zone
        ):
            border_candidate = True

        elif (
            inside_zone
            and direction == "deeper_inside"
        ):
            border_candidate = True

        # --------------------------------------------------
        # Zone-entry event
        # --------------------------------------------------

        if (
            zone_entry
            and
            direction == "entering_zone"
        ):
            border_candidate = True

        # --------------------------------------------------
        # Alert cooldown
        # --------------------------------------------------

        cooldown_active = False

        if track_id is not None:

            last_frame = self.last_alert_frame.get(
                track_id
            )

            if last_frame is not None:

                if (
                    frame_number - last_frame
                    < self.cooldown_frames
                ):
                    cooldown_active = True

        # --------------------------------------------------
        # HIGH / CRITICAL = actual alert
        # --------------------------------------------------

        if (
            priority in {
                "HIGH",
                "CRITICAL"
            }
            and
            meaningful_direction
            and
            confidence >= self.min_confidence
            and
            not cooldown_active
        ):

            border_alert = True
            alert_level = priority

        elif border_candidate:

            alert_level = "CANDIDATE"

        # --------------------------------------------------
        # Result
        # --------------------------------------------------

        return {
            "border_candidate": border_candidate,
            "border_alert": border_alert,
            "alert_level": alert_level
        }

    def register_alert(
        self,
        result,
        frame_number
    ):

        track_id = result.get(
            "track_id"
        )

        if track_id is not None:

            self.last_alert_frame[
                track_id
            ] = frame_number