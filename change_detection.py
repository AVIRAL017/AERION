import cv2
import json
import random
from skimage.metrics import structural_similarity as ssim

def crop_region(img, x_center, y_center, size=60):
    h, w = img.shape[:2]
    x1, x2 = max(0, x_center - size), min(w, x_center + size)
    y1, y2 = max(0, y_center - size), min(h, y_center + size)
    return img[y1:y2, x1:x2]

def local_ssim(before, after, x_center, y_center, size=60):
    b_crop = cv2.cvtColor(crop_region(before, x_center, y_center, size), cv2.COLOR_BGR2GRAY)
    a_crop = cv2.cvtColor(crop_region(after, x_center, y_center, size), cv2.COLOR_BGR2GRAY)
    score, _ = ssim(b_crop, a_crop, full=True)
    return score

def load_building_boxes(json_path, margin=80):
    with open(json_path) as f:
        data = json.load(f)
    boxes = []
    for feat in data["features"]["xy"]:
        wkt = feat["wkt"]
        coords_str = wkt.split("((")[1].split("))")[0]
        points = [tuple(map(float, p.strip().split())) for p in coords_str.split(",")]
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        # bounding box around each building, expanded by 'margin' so background
        # points can't land just outside a building but still touching it
        boxes.append((min(xs)-margin, max(xs)+margin, min(ys)-margin, max(ys)+margin))
    return boxes

def is_far_from_buildings(x, y, boxes):
    return not any(x1 <= x <= x2 and y1 <= y <= y2 for x1, x2, y1, y2 in boxes)

if __name__ == "__main__":
    before = cv2.imread(r"D:\mp-1\test\images\guatemala-volcano_00000003_pre_disaster.png")
    after = cv2.imread(r"D:\mp-1\test\images\guatemala-volcano_00000003_post_disaster.png")

    boxes = load_building_boxes(r"D:\mp-1\test\labels\guatemala-volcano_00000003_post_disaster.json")

    buildings = {
        "minor-damage_1": (463, 111),
        "destroyed":      (240, 315),
        "minor-damage_2": (592, 266),
    }

    print("--- Building-region scores ---")
    for name, (x, y) in buildings.items():
        score = local_ssim(before, after, x, y)
        print(f"{name}: {score:.4f}")

    # Sample multiple verified background points, well clear of any building
    random.seed(0)
    h, w = before.shape[:2]
    bg_scores = []
    attempts = 0
    while len(bg_scores) < 8 and attempts < 300:
        x, y = random.randint(80, w-80), random.randint(80, h-80)
        attempts += 1
        if is_far_from_buildings(x, y, boxes):
            bg_scores.append(local_ssim(before, after, x, y))

    print(f"\n--- Background scores ({len(bg_scores)} verified points) ---")
    for s in bg_scores:
        print(f"{s:.4f}")
    print(f"\nAverage background score: {sum(bg_scores)/len(bg_scores):.4f}")