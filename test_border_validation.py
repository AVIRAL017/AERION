from border_tracking import BorderTracker
from border_zone import BorderZoneAnalyzer
from border_intelligence import BorderIntelligence


# --------------------------------------------------
# Restricted zone
# --------------------------------------------------

restricted_zone = [
    (100, 100),
    (500, 100),
    (500, 400),
    (100, 400)
]


def run_scenario(name, positions, confidence=0.90):
    tracker = BorderTracker(
        persistence_threshold=5
    )

    zone = BorderZoneAnalyzer(
        restricted_zone,
        dwell_threshold=5
    )

    intelligence = BorderIntelligence()

    print("\n" + "=" * 60)
    print(name)
    print("=" * 60)

    results = []

    for frame, position in enumerate(
        positions,
        start=1
    ):

        detection = {
            "track_id": 1,
            "object_class": "person",
            "confidence": confidence,
            "bbox": [
                position[0] - 20,
                position[1] - 40,
                position[0] + 20,
                position[1] + 40
            ]
        }

        tracked = tracker.update(
            [detection]
        )[0]

        zoned = zone.analyze(
            tracked
        )

        result = intelligence.analyze(
            zoned,
            restricted_zone
        )

        results.append(result)

        print(
            f"Frame {frame}: "
            f"pos={result['center']} | "
            f"zone={result['zone_status']} | "
            f"entry={result['zone_entry']} | "
            f"dwell={result['zone_dwell_frames']} | "
            f"approach={result['approach_score']} | "
            f"score={result['border_activity_score']} | "
            f"priority={result['border_priority']}"
        )

    final = results[-1]

    print(
        f"\nFINAL → "
        f"score={final['border_activity_score']} | "
        f"priority={final['border_priority']}"
    )


# --------------------------------------------------
# 1. Stationary outside
# --------------------------------------------------

run_scenario(
    "1. Stationary outside",
    [
        [50, 250],
        [50, 250],
        [50, 250],
        [50, 250],
        [50, 250]
    ]
)


# --------------------------------------------------
# 2. Moving away from zone
# --------------------------------------------------

run_scenario(
    "2. Moving away from zone",
    [
        [90, 250],
        [70, 250],
        [50, 250],
        [30, 250],
        [10, 250]
    ]
)


# --------------------------------------------------
# 3. Approaching zone
# --------------------------------------------------

run_scenario(
    "3. Approaching zone",
    [
        [50, 250],
        [70, 250],
        [90, 250]
    ]
)


# --------------------------------------------------
# 4. Entering zone
# --------------------------------------------------

run_scenario(
    "4. Entering restricted zone",
    [
        [50, 250],
        [70, 250],
        [90, 250],
        [110, 250]
    ]
)


# --------------------------------------------------
# 5. Moving deeper inside
# --------------------------------------------------

run_scenario(
    "5. Moving deeper inside",
    [
        [50, 250],
        [70, 250],
        [90, 250],
        [110, 250],
        [150, 250],
        [200, 250],
        [250, 250]
    ]
)


# --------------------------------------------------
# 6. Stationary inside
# --------------------------------------------------

run_scenario(
    "6. Stationary inside",
    [
        [250, 250],
        [250, 250],
        [250, 250],
        [250, 250],
        [250, 250],
        [250, 250],
        [250, 250]
    ]
)


# --------------------------------------------------
# 7. Enter then leave
# --------------------------------------------------

run_scenario(
    "7. Enter then leave",
    [
        [50, 250],
        [90, 250],
        [110, 250],
        [150, 250],
        [90, 250],
        [50, 250]
    ]
)


# --------------------------------------------------
# 8. Brief low-confidence detection
# --------------------------------------------------

run_scenario(
    "8. Brief low-confidence detection",
    [
        [50, 250],
        [50, 250]
    ],
    confidence=0.40
)