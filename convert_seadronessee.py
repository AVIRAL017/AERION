import json
from pathlib import Path
from collections import Counter


BASE = Path(r"D:\mp-1\dataset\SeaDronesSee")
ANNOTATIONS = BASE / "annotations" / "annotations"
IMAGES = BASE / "images" / "images"

OUTPUT = Path(r"D:\mp-1\seadronessee_yolo")


# Unified GeoShield AI class schema for maritime extension
CLASS_MAPPING = {
    1: 0,  # swimmer -> person
    2: 1,  # boat -> boat
    3: 2,  # jetski -> jetski
    4: 3,  # life_saving_appliances -> life_saving_appliance
    5: 4,  # buoy -> buoy
}

CLASS_NAMES = [
    "person",
    "boat",
    "jetski",
    "life_saving_appliance",
    "buoy",
]


def convert_split(split):
    json_path = ANNOTATIONS / f"instances_{split}.json"
    image_dir = IMAGES / split

    output_image_dir = OUTPUT / "images" / split
    output_label_dir = OUTPUT / "labels" / split

    output_image_dir.mkdir(parents=True, exist_ok=True)
    output_label_dir.mkdir(parents=True, exist_ok=True)

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    images = {img["id"]: img for img in data["images"]}

    annotations_by_image = {}

    for ann in data["annotations"]:
        image_id = ann["image_id"]

        # Ignore category 0
        if ann["category_id"] not in CLASS_MAPPING:
            continue

        annotations_by_image.setdefault(image_id, []).append(ann)

    class_counter = Counter()
    missing_images = []
    invalid_boxes = 0
    converted_annotations = 0

    for image_id, image_info in images.items():

        filename = image_info["file_name"]
        width = image_info["width"]
        height = image_info["height"]

        source_image = image_dir / filename

        if not source_image.exists():
            missing_images.append(filename)
            continue

        # Copy image into YOLO dataset
        destination_image = output_image_dir / filename

        if not destination_image.exists():
            destination_image.write_bytes(source_image.read_bytes())

        label_path = output_label_dir / f"{Path(filename).stem}.txt"

        lines = []

        for ann in annotations_by_image.get(image_id, []):

            category_id = ann["category_id"]
            class_id = CLASS_MAPPING[category_id]

            x, y, box_w, box_h = ann["bbox"]

            # Validate bounding box
            if box_w <= 0 or box_h <= 0:
                invalid_boxes += 1
                continue

            # Clip bbox to image boundaries
            x1 = max(0.0, x)
            y1 = max(0.0, y)
            x2 = min(float(width), x + box_w)
            y2 = min(float(height), y + box_h)

            clipped_w = x2 - x1
            clipped_h = y2 - y1

            if clipped_w <= 0 or clipped_h <= 0:
                invalid_boxes += 1
                continue

            # COCO -> YOLO normalized center format
            center_x = (x1 + x2) / 2.0 / width
            center_y = (y1 + y2) / 2.0 / height
            norm_w = clipped_w / width
            norm_h = clipped_h / height

            lines.append(
                f"{class_id} "
                f"{center_x:.6f} "
                f"{center_y:.6f} "
                f"{norm_w:.6f} "
                f"{norm_h:.6f}"
            )

            class_counter[CLASS_NAMES[class_id]] += 1
            converted_annotations += 1

        # Empty label file is valid for images without usable objects
        label_path.write_text(
            "\n".join(lines),
            encoding="utf-8"
        )

    print(f"\n{'=' * 60}")
    print(f"Split: {split}")
    print(f"{'=' * 60}")

    print(f"Images in JSON:       {len(images)}")
    print(f"Converted annotations: {converted_annotations}")
    print(f"Missing images:        {len(missing_images)}")
    print(f"Invalid boxes:        {invalid_boxes}")

    print("\nClass counts:")
    for class_name in CLASS_NAMES:
        print(f"  {class_name:25s}: {class_counter[class_name]}")

    if missing_images:
        print("\nFirst missing images:")
        for name in missing_images[:20]:
            print(" ", name)

    return len(images), converted_annotations, missing_images, invalid_boxes


def create_yaml():
    yaml_path = OUTPUT / "seadronessee.yaml"

    yaml_content = f"""path: {OUTPUT.as_posix()}
train: images/train
val: images/val

names:
"""

    for i, name in enumerate(CLASS_NAMES):
        yaml_content += f"  {i}: {name}\n"

    yaml_path.write_text(yaml_content, encoding="utf-8")

    print(f"\nDataset YAML created:")
    print(yaml_path)


def main():
    print("SeaDronesSee COCO -> YOLO conversion")
    print(f"Source: {BASE}")
    print(f"Output: {OUTPUT}")

    train_result = convert_split("train")
    val_result = convert_split("val")

    create_yaml()

    print("\n" + "=" * 60)
    print("CONVERSION COMPLETE")
    print("=" * 60)

    print(f"Train images: {train_result[0]}")
    print(f"Val images:   {val_result[0]}")

    print("\nNo source dataset files were modified.")


if __name__ == "__main__":
    main()