from typing import Dict, List, Any


# ============================================================
# CONFIGURABLE CLASS WEIGHTS
# ============================================================

DEFAULT_CLASS_WEIGHTS = {
    "person": 0.8,
    "light_vehicle": 0.7,
    "bus": 0.8,
    "truck": 0.8,
    "motorbike": 0.6,
    "other_transport": 0.5,

    "plane": 0.9,
    "ship": 0.9,
    "large_vehicle": 0.8,
    "small_vehicle": 0.6,
    "helicopter": 1.0,

    "building_damage": 1.0,
    "destroyed": 1.0,
}


# ============================================================
# PRIORITY BUCKETS
# ============================================================

def get_priority(score: float) -> str:

    if score >= 0.75:
        return "Critical"

    elif score >= 0.50:
        return "High"

    elif score >= 0.25:
        return "Medium"

    else:
        return "Low"


# ============================================================
# SSIM CHANGE COMPONENT
# ============================================================

def calculate_change_score(
    background_ssim: float,
    local_ssim: float
) -> float:

    if background_ssim <= 0:
        return 0.0

    drop = (
        background_ssim - local_ssim
    ) / background_ssim

    return max(0.0, min(1.0, drop))


# ============================================================
# OBJECT PRIORITY
# ============================================================

def calculate_priority(
    object_class: str,
    confidence: float,
    background_ssim: float,
    local_ssim: float,
    class_weights: Dict[str, float] | None = None
) -> Dict[str, Any]:

    weights = (
        class_weights
        if class_weights is not None
        else DEFAULT_CLASS_WEIGHTS
    )

    confidence = max(
        0.0,
        min(1.0, confidence)
    )

    class_weight = weights.get(
        object_class,
        0.5
    )

    detection_component = (
        class_weight * confidence
    )

    change_component = calculate_change_score(
        background_ssim,
        local_ssim
    )

    # Established 50/50 formula
    score = (
        0.5 * detection_component
        +
        0.5 * change_component
    )

    # Keep score in [0, 1]
    score = max(
        0.0,
        min(1.0, score)
    )

    return {
        "object_class": object_class,
        "confidence": round(confidence, 4),
        "class_weight": round(class_weight, 4),
        "change_score": round(change_component, 4),
        "priority_score": round(score, 4),
        "priority": get_priority(score)
    }


# ============================================================
# INTELLIGENCE ENGINE
# ============================================================

def analyze_detection(
    detection: Dict[str, Any],
    mode: str = "disaster"
) -> Dict[str, Any]:

    object_class = detection.get(
        "class",
        "unknown"
    )

    confidence = float(
        detection.get(
            "confidence",
            0.0
        )
    )

    background_ssim = float(
        detection.get(
            "background_ssim",
            0.0
        )
    )

    local_ssim = float(
        detection.get(
            "local_ssim",
            background_ssim
        )
    )

    result = calculate_priority(
        object_class=object_class,
        confidence=confidence,
        background_ssim=background_ssim,
        local_ssim=local_ssim
    )

    result["mode"] = mode

    # Preserve original detection information
    result["detection"] = detection

    return result


# ============================================================
# MULTIPLE DETECTIONS
# ============================================================

def analyze_scene(
    detections: List[Dict[str, Any]],
    mode: str = "disaster"
) -> Dict[str, Any]:

    results = []

    for detection in detections:

        results.append(
            analyze_detection(
                detection,
                mode
            )
        )

    # Highest priority first
    results.sort(
        key=lambda x: x["priority_score"],
        reverse=True
    )

    critical = sum(
        r["priority"] == "Critical"
        for r in results
    )

    high = sum(
        r["priority"] == "High"
        for r in results
    )

    medium = sum(
        r["priority"] == "Medium"
        for r in results
    )

    low = sum(
        r["priority"] == "Low"
        for r in results
    )

    return {
        "mode": mode,
        "total_detections": len(results),
        "summary": {
            "critical": critical,
            "high": high,
            "medium": medium,
            "low": low
        },
        "detections": results
    }


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    test_detection = {
        "class": "building_damage",
        "confidence": 0.85,
        "background_ssim": 0.4210,
        "local_ssim": 0.2705
    }

    result = analyze_scene(
        [test_detection],
        mode="disaster"
    )

    print("\nGeoShield AI Intelligence Engine")
    print("================================")

    print(result)