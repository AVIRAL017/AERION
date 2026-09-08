from pathlib import Path
import shutil


SOURCE = Path(r"D:\mp-1\seadronessee_yolo")
OUTPUT = Path(r"D:\mp-1\seadronessee_unified_eval")

SOURCE_IMAGES = SOURCE / "images" / "val"
SOURCE_LABELS = SOURCE / "labels" / "val"

OUTPUT_IMAGES = OUTPUT / "images" / "val"
OUTPUT_LABELS = OUTPUT / "labels" / "val"

OUTPUT_IMAGES.mkdir(parents=True, exist_ok=True)
OUTPUT_LABELS.mkdir(parents=True, exist_ok=True)


# Current SeaDronesSee YOLO classes:
#
# 0 = person/swimmer
# 1 = boat
# 2 = jetski
# 3 = life_saving_appliance
# 4 = buoy
#
# Unified AERION classes:
#
# 0 = person
# 1 = light_vehicle
# 2 = bus
# 3 = truck
# 4 = motorbike
# 5 = other_transport
# 6 = boat
# 7 = jetski
# 8 = life_saving_appliance
# 9 = buoy

CLASS_MAP = {
    0: 0,  # swimmer -> person
    1: 6,  # boat -> boat
    2: 7,  # jetski -> jetski
    3: 8,  # life_saving_appliance -> life_saving_appliance
    4: 9,  # buoy -> buoy
}


def main():

    image_files = sorted(SOURCE_IMAGES.glob("*"))

    copied_images = 0
    converted_labels = 0
    total_objects = 0

    print(f"Source images: {SOURCE_IMAGES}")
    print(f"Source labels: {SOURCE_LABELS}")
    print(f"Output: {OUTPUT}")
    print()

    for image_path in image_files:

        if image_path.suffix.lower() not in {
            ".jpg", ".jpeg", ".png", ".bmp", ".webp"
        }:
            continue

        # Copy image
        destination_image = OUTPUT_IMAGES / image_path.name
        shutil.copy2(image_path, destination_image)
        copied_images += 1

        # Matching label
        label_path = SOURCE_LABELS / f"{image_path.stem}.txt"
        output_label = OUTPUT_LABELS / f"{image_path.stem}.txt"

        new_lines = []

        if label_path.exists():

            with open(label_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            for line in lines:

                parts = line.strip().split()

                if len(parts) != 5:
                    continue

                old_class = int(parts[0])

                if old_class not in CLASS_MAP:
                    continue

                new_class = CLASS_MAP[old_class]

                new_line = (
                    f"{new_class} "
                    f"{parts[1]} "
                    f"{parts[2]} "
                    f"{parts[3]} "
                    f"{parts[4]}\n"
                )

                new_lines.append(new_line)
                total_objects += 1

        with open(output_label, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

        converted_labels += 1

    print("=" * 70)
    print("SeaDronesSee evaluation dataset created")
    print("=" * 70)
    print(f"Images copied       : {copied_images}")
    print(f"Labels created      : {converted_labels}")
    print(f"Objects converted   : {total_objects}")
    print(f"Output directory    : {OUTPUT}")
    print()
    print("Class mapping:")
    print("  swimmer                  -> person")
    print("  boat                     -> boat")
    print("  jetski                   -> jetski")
    print("  life_saving_appliance    -> life_saving_appliance")
    print("  buoy                     -> buoy")


if __name__ == "__main__":
    main()