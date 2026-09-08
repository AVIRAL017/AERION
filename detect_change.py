from ultralytics import YOLO
from collections import Counter

def detect_and_count(model, image_path, conf=0.15, imgsz=1920):
    results = model(image_path, conf=conf, imgsz=imgsz)
    class_names = results[0].names
    detected_classes = [class_names[int(cls)] for cls in results[0].obb.cls]
    return Counter(detected_classes)

if __name__ == "__main__":
    model = YOLO(r"D:\mp-1\runs\obb\train-6\weights\best.pt")

    before_counts = detect_and_count(model, r"D:\mp-1\before.png")
    after_counts = detect_and_count(model, r"D:\mp-1\after.png")

    print("Before:", dict(before_counts))
    print("After:", dict(after_counts))

    print("\n--- Change Summary ---")
    all_classes = set(before_counts.keys()) | set(after_counts.keys())
    for cls in sorted(all_classes):
        b = before_counts.get(cls, 0)
        a = after_counts.get(cls, 0)
        if b != a:
            direction = "increased" if a > b else "decreased"
            print(f"{cls}: {b} -> {a} ({direction} by {abs(a-b)})")