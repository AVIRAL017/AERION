from pathlib import Path
from collections import Counter
import json
import shutil
from PIL import Image


# ============================================================
# AERION v1 — UAVDT EXTERNAL VALIDATION PREPARATION
# ============================================================

UAVDT_ROOT = Path(
    r"D:\mp-1\uavdt"
)

IMAGE_ROOT = (
    UAVDT_ROOT
    / "UAV-benchmark-M"
    / "UAV-benchmark-M"
)

GT_ROOT = (
    UAVDT_ROOT
    / "UAV-benchmark-MOTD_v1.0"
    / "UAV-benchmark-MOTD_v1.0"
    / "GT"
)

OUTPUT_ROOT = Path(
    r"D:\mp-1\uavdt_validation"
)

IMAGE_OUT = OUTPUT_ROOT / "images"
LABEL_OUT = OUTPUT_ROOT / "labels"


# ------------------------------------------------------------
# UAVDT DET → AERION taxonomy
# ------------------------------------------------------------

# UAVDT DET README:
# 1 = car
# 2 = truck
# 3 = bus

UAVDT_TO_AERION = {
    1: 1,  # car   -> light_vehicle
    2: 3,  # truck -> truck
    3: 2,  # bus   -> bus
}

AERION_NAMES = [
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


# ------------------------------------------------------------
# Benchmark sampling
# ------------------------------------------------------------

# We are NOT claiming an official UAVDT benchmark score.
#
# This is a reproducible AERION external-validation subset.
#
# Every Nth eligible frame is selected from every sequence.
# This avoids duplicating the complete dataset.

FRAME_STRIDE = 20


def parse_gt_whole(gt_path):
    """
    Parse UAVDT DET ground truth.

    Format:
    frame,target_id,x,y,w,h,out_of_view,occlusion,class
    """

    frame_records = {}

    with gt_path.open(
        "r",
        encoding="utf-8"
    ) as f:

        for line_number, line in enumerate(f, start=1):

            line = line.strip()

            if not line:
                continue

            parts = line.split(",")

            if len(parts) < 9:
                continue

            try:
                frame_id = int(parts[0])
                target_id = int(parts[1])

                x = float(parts[2])
                y = float(parts[3])
                w = float(parts[4])
                h = float(parts[5])

                out_of_view = int(parts[6])
                occlusion = int(parts[7])
                class_id = int(parts[8])

            except ValueError:
                continue

            record = {
                "target_id": target_id,
                "x": x,
                "y": y,
                "w": w,
                "h": h,
                "out_of_view": out_of_view,
                "occlusion": occlusion,
                "class_id": class_id,
            }

            frame_records.setdefault(
                frame_id,
                []
            ).append(record)

    return frame_records


def convert_bbox(
    x,
    y,
    w,
    h,
    image_width,
    image_height
):
    """
    Convert pixel xywh → normalized YOLO xywh.
    """

    if w <= 0 or h <= 0:
        return None

    x1 = max(0.0, x)
    y1 = max(0.0, y)

    x2 = min(
        float(image_width),
        x + w
    )

    y2 = min(
        float(image_height),
        y + h
    )

    if x2 <= x1 or y2 <= y1:
        return None

    xc = (x1 + x2) / 2.0
    yc = (y1 + y2) / 2.0

    bw = x2 - x1
    bh = y2 - y1

    return (
        xc / image_width,
        yc / image_height,
        bw / image_width,
        bh / image_height,
    )


def main():

    print("=" * 72)
    print("AERION v1 — UAVDT EXTERNAL VALIDATION PREPARATION")
    print("=" * 72)

    # --------------------------------------------------------
    # Validate source directories
    # --------------------------------------------------------

    if not IMAGE_ROOT.exists():
        raise FileNotFoundError(
            f"Image directory not found:\n{IMAGE_ROOT}"
        )

    if not GT_ROOT.exists():
        raise FileNotFoundError(
            f"GT directory not found:\n{GT_ROOT}"
        )

    sequences = sorted(
        p for p in IMAGE_ROOT.iterdir()
        if p.is_dir()
    )

    gt_files = sorted(
        GT_ROOT.glob("*_gt_whole.txt")
    )

    print(f"\nImage sequences : {len(sequences)}")
    print(f"DET GT files    : {len(gt_files)}")

    if len(sequences) != len(gt_files):
        print(
            "[WARNING] Image/GT sequence counts differ."
        )

    # --------------------------------------------------------
    # Prepare output
    # --------------------------------------------------------

    OUTPUT_ROOT.mkdir(
        parents=True,
        exist_ok=True
    )

    IMAGE_OUT.mkdir(
        parents=True,
        exist_ok=True
    )

    LABEL_OUT.mkdir(
        parents=True,
        exist_ok=True
    )

    # --------------------------------------------------------
    # Global statistics
    # --------------------------------------------------------

    original_classes = Counter()
    mapped_classes = Counter()

    total_gt = 0
    total_mapped = 0
    total_unmapped = 0

    total_selected_frames = 0
    total_missing_images = 0
    total_invalid_boxes = 0

    sequence_report = []

    # --------------------------------------------------------
    # Process every sequence
    # --------------------------------------------------------

    for sequence_index, sequence_dir in enumerate(
        sequences,
        start=1
    ):

        sequence = sequence_dir.name

        gt_path = (
            GT_ROOT
            / f"{sequence}_gt_whole.txt"
        )

        if not gt_path.exists():

            print(
                f"[{sequence_index}/{len(sequences)}] "
                f"{sequence}: GT missing"
            )

            continue

        print(
            f"\n[{sequence_index}/{len(sequences)}] "
            f"Processing {sequence}..."
        )

        frame_records = parse_gt_whole(
            gt_path
        )

        frames = sorted(
            frame_records.keys()
        )

        selected_frames = [
            frame_id
            for frame_id in frames
            if frame_id % FRAME_STRIDE == 1
        ]

        # If the stride happens to miss everything,
        # retain the first available frame.
        if not selected_frames and frames:
            selected_frames = [frames[0]]

        sequence_selected = 0
        sequence_objects = 0
        sequence_mapped = 0
        sequence_unmapped = 0
        sequence_missing = 0
        sequence_invalid = 0

        for frame_id in selected_frames:

            image_name = (
                f"img{frame_id:06d}.jpg"
            )

            source_image = (
                sequence_dir
                / image_name
            )

            if not source_image.exists():

                total_missing_images += 1
                sequence_missing += 1

                continue

            try:

                with Image.open(
                    source_image
                ) as image:

                    width, height = image.size

            except Exception as exc:

                print(
                    f"  [WARNING] Could not read "
                    f"{source_image}: {exc}"
                )

                total_missing_images += 1
                sequence_missing += 1

                continue

            valid_labels = []

            for record in frame_records[frame_id]:

                class_id = record["class_id"]

                original_classes[class_id] += 1
                total_gt += 1
                sequence_objects += 1

                if class_id not in UAVDT_TO_AERION:

                    total_unmapped += 1
                    sequence_unmapped += 1

                    continue

                aerion_class = (
                    UAVDT_TO_AERION[class_id]
                )

                mapped_classes[aerion_class] += 1
                total_mapped += 1
                sequence_mapped += 1

                bbox = convert_bbox(
                    record["x"],
                    record["y"],
                    record["w"],
                    record["h"],
                    width,
                    height
                )

                if bbox is None:

                    total_invalid_boxes += 1
                    sequence_invalid += 1

                    continue

                xc, yc, bw, bh = bbox

                valid_labels.append(
                    f"{aerion_class} "
                    f"{xc:.6f} "
                    f"{yc:.6f} "
                    f"{bw:.6f} "
                    f"{bh:.6f}"
                )

            # Don't create empty validation examples.
            if not valid_labels:
                continue

            output_name = (
                f"{sequence}_{image_name}"
            )

            output_image = (
                IMAGE_OUT
                / output_name
            )

            output_label = (
                LABEL_OUT
                / output_name.replace(
                    ".jpg",
                    ".txt"
                )
            )

            shutil.copy2(
                source_image,
                output_image
            )

            output_label.write_text(
                "\n".join(valid_labels)
                + "\n",
                encoding="utf-8"
            )

            sequence_selected += 1
            total_selected_frames += 1

        sequence_report.append(
            {
                "sequence": sequence,
                "available_gt_frames": len(frames),
                "selected_frames": len(selected_frames),
                "written_frames": sequence_selected,
                "objects_in_selected_frames": sequence_objects,
                "mapped_objects": sequence_mapped,
                "unmapped_objects": sequence_unmapped,
                "missing_images": sequence_missing,
                "invalid_boxes": sequence_invalid,
            }
        )

        print(
            f"  GT frames     : {len(frames):,}"
        )

        print(
            f"  Selected      : {len(selected_frames):,}"
        )

        print(
            f"  Written       : {sequence_selected:,}"
        )

        print(
            f"  Mapped objs   : {sequence_mapped:,}"
        )

    # --------------------------------------------------------
    # YAML
    # --------------------------------------------------------

    yaml_text = f"""path: {OUTPUT_ROOT.as_posix()}
train: images
val: images

nc: 10

names:
  0: person
  1: light_vehicle
  2: bus
  3: truck
  4: motorbike
  5: other_transport
  6: boat
  7: jetski
  8: life_saving_appliance
  9: buoy
"""

    yaml_path = (
        OUTPUT_ROOT
        / "uavdt_validation.yaml"
    )

    yaml_path.write_text(
        yaml_text,
        encoding="utf-8"
    )

    # --------------------------------------------------------
    # Report
    # --------------------------------------------------------

    report = {
        "dataset": "UAVDT",
        "purpose": (
            "AERION v1 external validation"
        ),
        "official_benchmark_claim": False,
        "sampling": {
            "method": (
                "Every Nth GT frame per sequence"
            ),
            "frame_stride": FRAME_STRIDE,
            "reproducible": True,
        },
        "source_sequences": len(sequences),
        "source_gt_files": len(gt_files),
        "selected_frames": total_selected_frames,
        "original_class_distribution": dict(
            sorted(
                original_classes.items()
            )
        ),
        "mapped_class_distribution": dict(
            sorted(
                mapped_classes.items()
            )
        ),
        "total_gt_objects_in_selected_frames":
            total_gt,
        "mapped_objects": total_mapped,
        "unmapped_objects": total_unmapped,
        "missing_images": total_missing_images,
        "invalid_boxes": total_invalid_boxes,
        "uavdt_to_aerion": {
            "1": "light_vehicle",
            "2": "truck",
            "3": "bus",
        },
        "aerion_names": AERION_NAMES,
        "sequences": sequence_report,
    }

    report_path = (
        OUTPUT_ROOT
        / "preparation_report.json"
    )

    report_path.write_text(
        json.dumps(
            report,
            indent=2
        ),
        encoding="utf-8"
    )

    # --------------------------------------------------------
    # Final summary
    # --------------------------------------------------------

    print("\n")
    print("=" * 72)
    print("UAVDT VALIDATION PREPARATION COMPLETE")
    print("=" * 72)

    print(
        f"Sequences             : {len(sequences):,}"
    )

    print(
        f"Selected frames       : "
        f"{total_selected_frames:,}"
    )

    print(
        f"Mapped objects        : "
        f"{total_mapped:,}"
    )

    print(
        f"Unmapped objects      : "
        f"{total_unmapped:,}"
    )

    print(
        f"Missing images        : "
        f"{total_missing_images:,}"
    )

    print(
        f"Invalid boxes         : "
        f"{total_invalid_boxes:,}"
    )

    print("\nOriginal class distribution:")

    for class_id, count in sorted(
        original_classes.items()
    ):

        print(
            f"  class {class_id}: "
            f"{count:,}"
        )

    print("\nOutput:")
    print(OUTPUT_ROOT)

    print("\nYAML:")
    print(yaml_path)

    print("\nReport:")
    print(report_path)

    print(
        "\nOriginal UAVDT dataset was NOT modified."
    )

    print("=" * 72)


if __name__ == "__main__":
    main()