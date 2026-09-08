from border_intelligence import BorderIntelligence

ZONE_POLYGON = [
    (200, 150),
    (1000, 150),
    (1000, 600),
    (200, 600)
]


def test_case(name, detection):

    engine = BorderIntelligence()

    result = engine.analyze(
        detection,
        ZONE_POLYGON
    )

    print("\n" + "=" * 70)
    print(f"TEST: {name}")
    print("=" * 70)

    print(f"Border score:        {result['border_activity_score']}")
    print(f"Priority:            {result['border_priority']}")
    print(f"Movement score:      {result['movement_score']}")
    print(f"Approach score:      {result['approach_score']}")
    print(f"Movement inside:     {result['movement_inside_score']}")
    print(f"Direction relation:  {result['direction_relation']}")
    print(f"Direction alignment: {result['direction_alignment']}")
    print(f"Direction score:     {result['direction_score']}")
    print(f"Direction consistent:{result['direction_consistent']}")
    print(f"Moving away:         {result['moving_away']}")


if __name__ == "__main__":

    test_case(
        "Stationary outside",
        {
            "track_id": 1,
            "center": (100, 100),
            "confidence": 0.90,
            "movement_distance": 0.0,
            "displacement": 0.0,
            "direction": "stationary",
            "frames_seen": 20,
            "persistence": True,
            "distance_to_zone": 111.8,
            "previous_distance_to_zone": 111.8,
            "zone_entry": False,
            "zone_exit": False,
            "inside_restricted_zone": False,
            "zone_dwell_score": 0.0,
            "direction_relation": "stationary",
            "direction_alignment": 0.0
        }
    )

    test_case(
        "Moving away from zone",
        {
            "track_id": 2,
            "center": (100, 100),
            "confidence": 0.90,
            "movement_distance": 10.0,
            "displacement": 10.0,
            "direction": "west",
            "frames_seen": 15,
            "persistence": True,
            "distance_to_zone": 120.0,
            "previous_distance_to_zone": 110.0,
            "zone_entry": False,
            "zone_exit": False,
            "inside_restricted_zone": False,
            "zone_dwell_score": 0.0,
            "direction_relation": "away_from_boundary",
            "direction_alignment": -1.0
        }
    )

    test_case(
        "Approaching zone",
        {
            "track_id": 3,
            "center": (190, 300),
            "confidence": 0.85,
            "movement_distance": 10.0,
            "displacement": 10.0,
            "direction": "east",
            "frames_seen": 12,
            "persistence": True,
            "distance_to_zone": 10.0,
            "previous_distance_to_zone": 20.0,
            "zone_entry": False,
            "zone_exit": False,
            "inside_restricted_zone": False,
            "zone_dwell_score": 0.0,
            "direction_relation": "toward_boundary",
            "direction_alignment": 1.0
        }
    )

    test_case(
        "Entering restricted zone",
        {
            "track_id": 4,
            "center": (250, 300),
            "confidence": 0.95,
            "movement_distance": 15.0,
            "displacement": 15.0,
            "direction": "east",
            "frames_seen": 15,
            "persistence": True,
            "distance_to_zone": 50.0,
            "previous_distance_to_zone": 10.0,
            "zone_entry": True,
            "zone_exit": False,
            "inside_restricted_zone": True,
            "zone_dwell_score": 0.2,
            "direction_relation": "entering_zone",
            "direction_alignment": 1.0
        }
    )

    test_case(
        "Moving deeper inside",
        {
            "track_id": 5,
            "center": (400, 350),
            "confidence": 0.90,
            "movement_distance": 12.0,
            "displacement": 12.0,
            "direction": "east",
            "frames_seen": 20,
            "persistence": True,
            "distance_to_zone": 150.0,
            "previous_distance_to_zone": 100.0,
            "zone_entry": False,
            "zone_exit": False,
            "inside_restricted_zone": True,
            "zone_dwell_score": 0.8,
            "direction_relation": "deeper_inside",
            "direction_alignment": 0.0
        }
    )

    test_case(
        "Stationary inside",
        {
            "track_id": 6,
            "center": (500, 350),
            "confidence": 0.90,
            "movement_distance": 0.0,
            "displacement": 0.0,
            "direction": "stationary",
            "frames_seen": 20,
            "persistence": True,
            "distance_to_zone": 150.0,
            "previous_distance_to_zone": 150.0,
            "zone_entry": False,
            "zone_exit": False,
            "inside_restricted_zone": True,
            "zone_dwell_score": 1.0,
            "direction_relation": "stationary",
            "direction_alignment": 0.0
        }
    )

    test_case(
        "Leaving zone",
        {
            "track_id": 7,
            "center": (150, 300),
            "confidence": 0.90,
            "movement_distance": 10.0,
            "displacement": 10.0,
            "direction": "west",
            "frames_seen": 10,
            "persistence": True,
            "distance_to_zone": 50.0,
            "previous_distance_to_zone": 20.0,
            "zone_entry": False,
            "zone_exit": True,
            "inside_restricted_zone": False,
            "zone_dwell_score": 0.0,
            "direction_relation": "leaving_zone",
            "direction_alignment": -1.0
        }
    )

    print("\n")
    print("=" * 70)
    print("INTEGRATED BORDER INTELLIGENCE VALIDATION COMPLETE")
    print("=" * 70)
