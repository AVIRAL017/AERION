from pathlib import Path
import json

ROOT = Path(r"D:\mp-1\xBD\train")

folders = ["images", "labels", "targets"]

print("\n=== xBD DATASET INSPECTION ===\n")

for folder in folders:
    path = ROOT / folder

    print(f"\n[{folder.upper()}]")
    print("Path:", path)

    if not path.exists():
        print("❌ Folder not found")
        continue

    files = list(path.iterdir())

    print("Files:", len(files))

    for file in files[:5]:
        print("  ", file.name)

        if file.suffix.lower() == ".json":
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                print("     JSON keys:", list(data.keys()))
                print("     JSON values:", list(data.values()))

            except Exception as e:
                print("     JSON error:", e)

print("\n=== DONE ===")