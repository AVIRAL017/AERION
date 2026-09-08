from border_zone import BorderZoneAnalyzer


restricted_zone = [
    (100, 100),
    (500, 100),
    (500, 400),
    (100, 400)
]

zone = BorderZoneAnalyzer(restricted_zone)


positions = [
    [50, 250],    # outside
    [80, 250],    # outside
    [99, 250],    # outside
    [150, 250],   # ENTERS
    [200, 250],   # inside
    [300, 250],   # inside
]


for frame, position in enumerate(positions, start=1):

    detection = {
        "track_id": 1,
        "object_class": "person",
        "confidence": 0.87,
        "center": position
    }

    result = zone.analyze(detection)

    print(
        f"Frame {frame}: "
        f"position={position}, "
        f"status={result['zone_status']}, "
        f"entry={result['zone_entry']}"
    )