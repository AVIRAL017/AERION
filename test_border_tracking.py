from border_tracking import BorderTracker


tracker = BorderTracker(persistence_threshold=5)

detections = [
    {
        "track_id": 1,
        "object_class": "person",
        "confidence": 0.87,
        "bbox": [100, 100, 140, 180]
    }
]

for frame in range(8):

    # Simulate the person moving
    detections[0]["bbox"] = [
        100 + frame * 5,
        100 + frame * 3,
        140 + frame * 5,
        180 + frame * 3
    ]

    result = tracker.update(detections)

    print(
        f"Frame {frame + 1}:",
        result[0]
    )