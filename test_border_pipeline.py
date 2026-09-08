from border_tracking import BorderTracker
from border_zone import BorderZoneAnalyzer
from border_intelligence import BorderIntelligence


# --------------------------------------------------
# 1. Define a simulated restricted zone
# --------------------------------------------------

restricted_zone = [
    (100, 100),
    (500, 100),
    (500, 400),
    (100, 400)
]


# --------------------------------------------------
# 2. Initialize all three modules
# --------------------------------------------------

tracker = BorderTracker(
    persistence_threshold=5
)

zone_analyzer = BorderZoneAnalyzer(
    restricted_zone
)

intelligence = BorderIntelligence()


# --------------------------------------------------
# 3. Simulated person trajectory
#
# Starts outside
# Approaches the zone
# Enters the zone
# Continues moving inside
# --------------------------------------------------

positions = [
    [50, 250],
    [70, 250],
    [90, 250],
    [110, 250],
    [150, 250],
    [200, 250],
    [250, 250],
]


# --------------------------------------------------
# 4. Process every frame
# --------------------------------------------------

for frame_number, position in enumerate(
    positions,
    start=1
):

    detection = {
        "track_id": 1,
        "object_class": "person",
        "confidence": 0.87,
        "bbox": [
            position[0] - 20,
            position[1] - 40,
            position[0] + 20,
            position[1] + 40
        ]
    }

    # Tracking
    tracked = tracker.update(
        [detection]
    )[0]

    # Zone analysis
    zoned = zone_analyzer.analyze(
        tracked
    )

    # Border intelligence
    result = intelligence.analyze(
        zoned,
        restricted_zone
    )

    print(
        f"\nFrame {frame_number}"
    )

    print(
        f"Position: {result['center']}"
    )

    print(
        f"Direction: {result['direction']}"
    )

    print(
        f"Persistence: {result['persistence']}"
    )

    print(
        f"Zone status: {result['zone_status']}"
    )

    print(
        f"Zone entry: {result['zone_entry']}"
    )

    print(
        f"Distance to zone: "
        f"{result['distance_to_zone']}"
    )

    print(
        f"Approach score: "
        f"{result['approach_score']}"
    )

    print(
        f"Border score: "
        f"{result['border_activity_score']}"
    )

    print(
        f"Priority: "
        f"{result['border_priority']}"
    )