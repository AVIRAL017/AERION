from pathlib import Path
import shutil
import yaml


# ============================================================
# CONFIGURATION
# ============================================================

BASE = Path(r"D:\mp-1")

# Exact VisDrone dataset location from VisDrone_Custom.yaml
VISDRONE_ROOT = Path(
    r"C:\Users\avira\yolo_project\datasets\VisDrone"
)

# Converted SeaDronesSee dataset
SEA_ROOT = BASE / "seadronessee_yolo"

# New combined dataset
OUTPUT = BASE / "unified_drone_dataset"


# ============================================================
# UNIFIED 10-CLASS TAXONOMY
# ============================================================

CLASSES = [
    "person",                    # 0
    "light_vehicle",             # 1
    "bus",                       # 2
    "truck",                     # 3
    "motorbike",                 # 4
    "other_transport",           # 5
    "boat",                      # 6
    "jetski",                    # 7
    "life_saving_appliance",     # 8
    "buoy",                      # 9
]


# ============================================================
# SEADRONESSEE CLASS MAPPING
# ============================================================

# SeaDronesSee converted YOLO classes:
#
# 0 = person
# 1 = boat
# 2 = jetski
# 3 = life_saving_appliance
# 4 = buoy
#
# Unified dataset:
#
# 0 = person
# 6 = boat
# 7 = jetski
# 8 = life_saving_appliance
# 9 = buoy

SEA_CLASS_MAP = {
    0: 0,
    1: 6,
    2: 7,
    3: 8,
    4: 9,
}


# ============================================================
# VALIDATE SOURCE DATASETS
# ============================================================

def validate_source_datasets():

    print("=" * 70)
    print("CHECKING SOURCE DATASETS")
    print("=" * 70)

    print()
    print(f"VisDrone root:")
    print(VISDRONE_ROOT)

    print()
    print(f"SeaDronesSee root:")
    print(SEA_ROOT)

    print()

    # --------------------------------------------------------
    # VisDrone
    # --------------------------------------------------------

    if not VISDRONE_ROOT.exists():
        raise FileNotFoundError(
            f"VisDrone dataset not found:\n{VISDRONE_ROOT}"
        )

    # --------------------------------------------------------
    # SeaDronesSee
    # --------------------------------------------------------

    if not SEA_ROOT.exists():
        raise FileNotFoundError(
            f"SeaDronesSee dataset not found:\n{SEA_ROOT}"
        )

    # --------------------------------------------------------
    # Check required split directories
    # --------------------------------------------------------

    for split in ["train", "val"]:

        vis_images = VISDRONE_ROOT / "images" / split
        vis_labels = VISDRONE_ROOT / "labels" / split

        sea_images = SEA_ROOT / "images" / split
        sea_labels = SEA_ROOT / "labels" / split

        if not vis_images.exists():
            raise FileNotFoundError(
                f"VisDrone images not found:\n{vis_images}"
            )

        if not vis_labels.exists():
            raise FileNotFoundError(
                f"VisDrone labels not found:\n{vis_labels}"
            )

        if not sea_images.exists():
            raise FileNotFoundError(
                f"SeaDronesSee images not found:\n{sea_images}"
            )

        if not sea_labels.exists():
            raise FileNotFoundError(
                f"SeaDronesSee labels not found:\n{sea_labels}"
            )

    print("Source dataset validation: PASSED")
    print()


# ============================================================
# CREATE OUTPUT DIRECTORIES
# ============================================================

def create_output_directories():

    for split in ["train", "val"]:

        image_dir = OUTPUT / "images" / split
        label_dir = OUTPUT / "labels" / split

        image_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        label_dir.mkdir(
            parents=True,
            exist_ok=True
        )


# ============================================================
# COPY VISDRONE
# ============================================================

def copy_visdrone_split(split):

    source_images = (
        VISDRONE_ROOT /
        "images" /
        split
    )

    source_labels = (
        VISDRONE_ROOT /
        "labels" /
        split
    )

    destination_images = (
        OUTPUT /
        "images" /
        split
    )

    destination_labels = (
        OUTPUT /
        "labels" /
        split
    )

    image_count = 0
    label_count = 0

    for image_path in source_images.iterdir():

        if not image_path.is_file():
            continue

        # Prefix prevents filename collisions with SeaDronesSee.
        destination_image = (
            destination_images /
            f"visdrone_{image_path.name}"
        )

        shutil.copy2(
            image_path,
            destination_image
        )

        image_count += 1

        # Corresponding YOLO label
        source_label = (
            source_labels /
            f"{image_path.stem}.txt"
        )

        destination_label = (
            destination_labels /
            f"visdrone_{image_path.stem}.txt"
        )

        if source_label.exists():

            shutil.copy2(
                source_label,
                destination_label
            )

            label_count += 1

        else:

            # Keep an empty label file if an image
            # has no annotations.
            destination_label.write_text("")

    return image_count, label_count


# ============================================================
# COPY + REMAP SEADRONESSEE
# ============================================================

def copy_seadronessee_split(split):

    source_images = (
        SEA_ROOT /
        "images" /
        split
    )

    source_labels = (
        SEA_ROOT /
        "labels" /
        split
    )

    destination_images = (
        OUTPUT /
        "images" /
        split
    )

    destination_labels = (
        OUTPUT /
        "labels" /
        split
    )

    image_count = 0
    label_count = 0
    annotation_count = 0

    class_counts = {
        class_name: 0
        for class_name in CLASSES
    }

    for image_path in source_images.iterdir():

        if not image_path.is_file():
            continue

        # Prefix prevents filename collisions.
        destination_image = (
            destination_images /
            f"seadronessee_{image_path.name}"
        )

        shutil.copy2(
            image_path,
            destination_image
        )

        image_count += 1

        source_label = (
            source_labels /
            f"{image_path.stem}.txt"
        )

        destination_label = (
            destination_labels /
            f"seadronessee_{image_path.stem}.txt"
        )

        output_lines = []

        if source_label.exists():

            with open(
                source_label,
                "r"
            ) as f:

                for line in f:

                    values = line.strip().split()

                    if len(values) != 5:
                        continue

                    try:
                        old_class = int(values[0])
                    except ValueError:
                        continue

                    # Ignore unknown classes.
                    if old_class not in SEA_CLASS_MAP:
                        continue

                    new_class = SEA_CLASS_MAP[old_class]

                    # Preserve normalized bbox coordinates.
                    cx = values[1]
                    cy = values[2]
                    width = values[3]
                    height = values[4]

                    output_lines.append(
                        f"{new_class} "
                        f"{cx} "
                        f"{cy} "
                        f"{width} "
                        f"{height}"
                    )

                    annotation_count += 1

                    class_name = CLASSES[new_class]
                    class_counts[class_name] += 1

        with open(
            destination_label,
            "w"
        ) as f:

            if output_lines:
                f.write(
                    "\n".join(output_lines)
                    + "\n"
                )

        label_count += 1

    return (
        image_count,
        label_count,
        annotation_count,
        class_counts
    )


# ============================================================
# COUNT FINAL DATASET
# ============================================================

def count_final_dataset():

    print()
    print("=" * 70)
    print("FINAL DATASET COUNTS")
    print("=" * 70)

    grand_images = 0

    for split in ["train", "val"]:

        image_dir = OUTPUT / "images" / split
        label_dir = OUTPUT / "labels" / split

        image_count = len([
            p for p in image_dir.iterdir()
            if p.is_file()
        ])

        label_count = len([
            p for p in label_dir.iterdir()
            if p.is_file()
        ])

        grand_images += image_count

        print()
        print(f"{split.upper()}")
        print(f"Images: {image_count}")
        print(f"Labels: {label_count}")

    print()
    print(f"Total images: {grand_images}")


# ============================================================
# CREATE YOLO YAML
# ============================================================

def create_yaml():

    dataset_yaml = {
        "path": str(OUTPUT),
        "train": "images/train",
        "val": "images/val",
        "nc": len(CLASSES),
        "names": {
            index: name
            for index, name in enumerate(CLASSES)
        }
    }

    yaml_path = OUTPUT / "unified_drone.yaml"

    with open(
        yaml_path,
        "w"
    ) as f:

        yaml.safe_dump(
            dataset_yaml,
            f,
            sort_keys=False
        )

    return yaml_path


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("UNIFIED DRONE DATASET CREATION")
    print("=" * 70)

    print()
    print("Final taxonomy:")
    print()

    for index, class_name in enumerate(CLASSES):
        print(
            f"  {index}: {class_name}"
        )

    print()

    print(f"Output:")
    print(OUTPUT)

    print()

    # --------------------------------------------------------
    # Validate
    # --------------------------------------------------------

    validate_source_datasets()

    # --------------------------------------------------------
    # Create output
    # --------------------------------------------------------

    create_output_directories()

    total_visdrone_images = 0
    total_sea_images = 0

    # --------------------------------------------------------
    # Process train + validation
    # --------------------------------------------------------

    for split in ["train", "val"]:

        print("=" * 70)
        print(f"SPLIT: {split.upper()}")
        print("=" * 70)

        print()
        print("Copying VisDrone...")

        vis_images, vis_labels = copy_visdrone_split(
            split
        )

        print(
            f"VisDrone images copied : {vis_images}"
        )

        print(
            f"VisDrone labels copied : {vis_labels}"
        )

        print()
        print("Copying + remapping SeaDronesSee...")

        (
            sea_images,
            sea_labels,
            sea_annotations,
            sea_class_counts
        ) = copy_seadronessee_split(split)

        print(
            f"SeaDronesSee images copied : {sea_images}"
        )

        print(
            f"SeaDronesSee labels created : {sea_labels}"
        )

        print(
            f"SeaDronesSee annotations     : {sea_annotations}"
        )

        print()
        print("SeaDronesSee unified classes:")

        for class_name, count in sea_class_counts.items():

            if count > 0:
                print(
                    f"  {class_name:<25}: {count}"
                )

        print()
        print(
            f"Combined {split} images: "
            f"{vis_images + sea_images}"
        )

        total_visdrone_images += vis_images
        total_sea_images += sea_images

    # --------------------------------------------------------
    # YAML
    # --------------------------------------------------------

    yaml_path = create_yaml()

    # --------------------------------------------------------
    # Final counts
    # --------------------------------------------------------

    count_final_dataset()

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("UNIFIED DATASET CREATION COMPLETE")
    print("=" * 70)

    print()
    print(
        f"VisDrone images     : "
        f"{total_visdrone_images}"
    )

    print(
        f"SeaDronesSee images : "
        f"{total_sea_images}"
    )

    print(
        f"Combined images     : "
        f"{total_visdrone_images + total_sea_images}"
    )

    print()
    print("Dataset YAML:")
    print(yaml_path)

    print()
    print("IMPORTANT:")
    print("Original VisDrone dataset was NOT modified.")
    print("Original SeaDronesSee dataset was NOT modified.")

    print()
    print("=" * 70)


if __name__ == "__main__":
    main()