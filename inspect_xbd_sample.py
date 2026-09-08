from pathlib import Path
from PIL import Image
import json
import numpy as np

ROOT = Path(r"D:\mp-1\xBD\train")
IMAGE_ID = "guatemala-volcano_00000000"

print("\n=== xBD SAMPLE INSPECTION ===\n")

for stage in ["pre_disaster", "post_disaster"]:

    print(f"\n===== {stage.upper()} =====")

    image_path = ROOT / "images" / f"{IMAGE_ID}_{stage}.png"
    label_path = ROOT / "labels" / f"{IMAGE_ID}_{stage}.json"
    target_path = ROOT / "targets" / f"{IMAGE_ID}_{stage}_target.png"

    # ---------------- IMAGE ----------------
    image = Image.open(image_path)

    print("Image size:", image.size)
    print("Image mode:", image.mode)

    # ---------------- TARGET ----------------
    target = np.array(Image.open(target_path))

    print("Target shape:", target.shape)
    print("Target unique values:", np.unique(target))

    # ---------------- JSON ----------------
    with open(label_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    features = data["features"]

    print("Feature container type:", type(features))
    print("Feature keys:", list(features.keys()))

    for feature_type in ["lng_lat", "xy"]:

        items = features.get(feature_type, [])

        print(f"{feature_type} count:", len(items))

        if items:

            first = items[0]

            print("First item type:", type(first))

            if isinstance(first, dict):
                print("Properties:", first.get("properties"))
                print("WKT:", first.get("wkt"))

print("\n=== INSPECTION COMPLETE ===")