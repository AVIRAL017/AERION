from pathlib import Path
from collections import Counter


# ============================================================
# CONFIG
# ============================================================

DATASET = Path(r"D:\mp-1\unified_drone_dataset")

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".webp",
}

CLASS_NAMES = [
    "person",
    "light_vehicle",
    "bus",
    "truck",
    "motorbike",
    "other_transport",
    "boat",
    "jetski",
    "life_saving_appliance",
    "buoy",
]

NUM_CLASSES = len(CLASS_NAMES)


# ============================================================
# GET IMAGES
# ============================================================

def get_images(directory):

    return [
        p for p in directory.iterdir()
        if p.is_file()
        and p.suffix.lower() in IMAGE_EXTENSIONS
    ]


# ============================================================
# VALIDATE LABEL
# ============================================================

def validate_label(label_path):

    valid = 0
    invalid = 0
    classes = Counter()

    if not label_path.exists():
        return valid, invalid, classes

    with open(label_path, "r") as f:

        for line in f:

            values = line.strip().split()

            if not values:
                continue

            if len(values) != 5:
                invalid += 1
                continue

            try:
                class_id = int(values[0])

                cx = float(values[1])
                cy = float(values[2])
                width = float(values[3])
                height = float(values[4])

            except ValueError:

                invalid += 1
                continue

            # ------------------------------------------------
            # Class validation
            # ------------------------------------------------

            if not (0 <= class_id < NUM_CLASSES):

                invalid += 1
                continue

            # ------------------------------------------------
            # YOLO normalized coordinate validation
            # ------------------------------------------------

            if not (
                0.0 <= cx <= 1.0
                and 0.0 <= cy <= 1.0
                and 0.0 < width <= 1.0
                and 0.0 < height <= 1.0
            ):

                invalid += 1
                continue

            # ------------------------------------------------
            # Bounding box boundary validation
            # ------------------------------------------------

            x1 = cx - width / 2
            y1 = cy - height / 2

            x2 = cx + width / 2
            y2 = cy + height / 2

            if (
                x1 < -1e-6
                or y1 < -1e-6
                or x2 > 1.000001
                or y2 > 1.000001
            ):

                invalid += 1
                continue

            valid += 1
            classes[class_id] += 1

    return valid, invalid, classes


# ============================================================
# VERIFY SPLIT
# ============================================================

def verify_split(split):

    print()
    print("=" * 70)
    print(f"VERIFYING {split.upper()}")
    print("=" * 70)

    image_dir = DATASET / "images" / split
    label_dir = DATASET / "labels" / split

    if not image_dir.exists():
        raise FileNotFoundError(image_dir)

    if not label_dir.exists():
        raise FileNotFoundError(label_dir)

    images = get_images(image_dir)

    image_stems = {
        p.stem
        for p in images
    }

    label_files = list(label_dir.glob("*.txt"))

    label_stems = {
        p.stem
        for p in label_files
    }

    print()
    print(f"Images found : {len(images)}")
    print(f"Labels found : {len(label_files)}")

    # --------------------------------------------------------
    # Filename consistency
    # --------------------------------------------------------

    missing_labels = image_stems - label_stems
    orphan_labels = label_stems - image_stems

    print()
    print(f"Missing labels : {len(missing_labels)}")
    print(f"Orphan labels  : {len(orphan_labels)}")

    if missing_labels:

        print()
        print("First missing labels:")

        for stem in sorted(missing_labels)[:20]:
            print(f"  {stem}.txt")

    if orphan_labels:

        print()
        print("First orphan labels:")

        for stem in sorted(orphan_labels)[:20]:
            print(f"  {stem}.jpg")

    # --------------------------------------------------------
    # Validate labels
    # --------------------------------------------------------

    print()
    print("Validating label files...")

    total_valid = 0
    total_invalid = 0
    empty_labels = 0

    class_counts = Counter()

    for index, label_path in enumerate(label_files, start=1):

        if label_path.stat().st_size == 0:

            empty_labels += 1
            continue

        valid, invalid, classes = validate_label(
            label_path
        )

        total_valid += valid
        total_invalid += invalid

        class_counts.update(classes)

        if index % 2000 == 0:

            print(
                f"  Checked {index}/{len(label_files)} labels..."
            )

    print()
    print(f"Valid annotations   : {total_valid}")
    print(f"Invalid annotations : {total_invalid}")
    print(f"Empty label files   : {empty_labels}")

    # --------------------------------------------------------
    # Class distribution
    # --------------------------------------------------------

    print()
    print("CLASS DISTRIBUTION")
    print("-" * 55)

    for class_id, class_name in enumerate(CLASS_NAMES):

        print(
            f"{class_id:2d}  "
            f"{class_name:<25} "
            f"{class_counts[class_id]:>8}"
        )

    return {
        "images": len(images),
        "labels": len(label_files),
        "missing": len(missing_labels),
        "orphan": len(orphan_labels),
        "valid": total_valid,
        "invalid": total_invalid,
        "empty": empty_labels,
        "classes": class_counts,
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("FAST UNIFIED DATASET SANITY CHECK")
    print("=" * 70)

    print()
    print(f"Dataset: {DATASET}")

    if not DATASET.exists():
        raise FileNotFoundError(DATASET)

    results = {}

    for split in ["train", "val"]:

        results[split] = verify_split(split)

    # ========================================================
    # FINAL RESULT
    # ========================================================

    print()
    print("=" * 70)
    print("FINAL RESULT")
    print("=" * 70)

    errors = 0

    for split in ["train", "val"]:

        r = results[split]

        errors += (
            r["missing"]
            + r["orphan"]
            + r["invalid"]
        )

        print()
        print(split.upper())
        print(f"  Images             : {r['images']}")
        print(f"  Labels             : {r['labels']}")
        print(f"  Missing labels     : {r['missing']}")
        print(f"  Orphan labels      : {r['orphan']}")
        print(f"  Valid annotations  : {r['valid']}")
        print(f"  Invalid annotations: {r['invalid']}")
        print(f"  Empty labels       : {r['empty']}")

    print()
    print("=" * 70)

    if errors == 0:

        print("RESULT: PASSED")
        print("Dataset structure and YOLO annotations are valid.")

    else:

        print(
            f"RESULT: {errors} structural/annotation "
            f"issues detected."
        )

    print("=" * 70)


if __name__ == "__main__":
    main()