DISASTER_WEIGHTS = {
    "person": 0.9, "bus": 0.8, "truck": 0.8, "motorbike": 0.3,
    "light_vehicle": 0.5, "ship": 0.6, "building_damage": 1.0,
}
BORDER_WEIGHTS = {
    "person": 0.7, "bus": 0.6, "truck": 0.6, "motorbike": 0.9,
    "light_vehicle": 0.6, "ship": 0.9, "building_damage": 0.2,
}

def priority_score(object_class, confidence, local_ssim, background_avg_ssim, mode="disaster"):
    weights = DISASTER_WEIGHTS if mode == "disaster" else BORDER_WEIGHTS
    class_weight = weights.get(object_class, 0.4)

    class_component = class_weight * confidence
    change_signal = max(0, (background_avg_ssim - local_ssim) / background_avg_ssim)

    score = 0.5 * class_component + 0.5 * change_signal
    return min(score, 1.0)

def bucket(score):
    if score >= 0.7: return "Critical"
    if score >= 0.4: return "High"
    if score >= 0.2: return "Medium"
    return "Low"

if __name__ == "__main__":
    background_avg = 0.4210

    test_cases = [
        ("building_damage", 0.85, 0.3005, "minor-damage_1"),
        ("building_damage", 0.85, 0.2705, "minor-damage_2"),
        ("building_damage", 0.85, 0.4495, "destroyed"),
    ]

    for cls, conf, local_ssim, label in test_cases:
        score = priority_score(cls, conf, local_ssim, background_avg, mode="disaster")
        print(f"{label}: priority={score:.3f} -> {bucket(score)}")