import json
from pathlib import Path

labels_dir = Path(r"D:\mp-1\xBD\train\labels")

json_file = next(labels_dir.glob("*.json"))

with open(json_file, "r") as f:
    data = json.load(f)

print("File:", json_file.name)
print("Top-level keys:", data.keys())

features = data["features"]

print("\nFeature keys:", features.keys())

for key, items in features.items():
    print(f"{key}: {len(items)} items")

    if items:
        print("First item:")
        print(items[0])
        break