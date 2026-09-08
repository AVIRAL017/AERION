from pathlib import Path
from PIL import Image
import numpy as np
import shutil
import random

# ============================================================
# CONFIGURATION
# ============================================================

SOURCE = Path(r"D:\mp-1\xBD\train")
OUTPUT = Path(r"D:\mp-1\xBD_processed")

PATCH_SIZE = 512
STRIDE = 512

TRAIN_RATIO = 0.8
SEED = 42

# ============================================================
# DIRECTORIES
# ============================================================

TRAIN_BEFORE = OUTPUT / "train" / "before"
TRAIN_AFTER = OUTPUT / "train" / "after"
TRAIN_MASK = OUTPUT / "train" / "mask"

VAL_BEFORE = OUTPUT / "val" / "before"
VAL_AFTER = OUTPUT / "val" / "after"
VAL_MASK = OUTPUT / "val" / "mask"

for folder in [
    TRAIN_BEFORE, TRAIN_AFTER, TRAIN_MASK,
    VAL_BEFORE, VAL_AFTER, VAL_MASK
]:
    folder.mkdir(parents=True, exist_ok=True)

# ============================================================
# FIND PRE/POST IMAGE PAIRS
# ============================================================

images_dir = SOURCE / "images"
targets_dir = SOURCE / "targets"

pre_images = sorted(images_dir.glob("*_pre_disaster.png"))

pairs = []

for pre_path in pre_images:

    base = pre_path.name.replace("_pre_disaster.png", "")

    post_path = images_dir / f"{base}_post_disaster.png"
    post_target = targets_dir / f"{base}_post_disaster_target.png"

    if post_path.exists() and post_target.exists():
        pairs.append(
            (
                base,
                pre_path,
                post_path,
                post_target
            )
        )

print("\n========================================")
print("xBD PREPROCESSING")
print("========================================")

print("Total pre-disaster images:", len(pre_images))
print("Valid pre/post/target pairs:", len(pairs))

if len(pairs) == 0:
    raise RuntimeError("No valid image pairs found.")

# ============================================================
# TRAIN / VALIDATION SPLIT
# ============================================================

random.seed(SEED)

random.shuffle(pairs)

split_index = int(len(pairs) * TRAIN_RATIO)

train_pairs = pairs[:split_index]
val_pairs = pairs[split_index:]

print("\nTraining pairs:", len(train_pairs))
print("Validation pairs:", len(val_pairs))

# ============================================================
# PROCESS FUNCTION
# ============================================================

def process_pair(pair, split, counter):

    base, pre_path, post_path, target_path = pair

    pre = Image.open(pre_path).convert("RGB")
    post = Image.open(post_path).convert("RGB")

    mask = Image.open(target_path).convert("L")

    pre_np = np.array(pre)
    post_np = np.array(post)
    mask_np = np.array(mask)

    height, width = mask_np.shape

    patch_number = 0

    for y in range(0, height, STRIDE):

        for x in range(0, width, STRIDE):

            # Make sure we have a complete patch
            if (
                y + PATCH_SIZE > height
                or x + PATCH_SIZE > width
            ):
                continue

            pre_patch = pre_np[
                y:y + PATCH_SIZE,
                x:x + PATCH_SIZE
            ]

            post_patch = post_np[
                y:y + PATCH_SIZE,
                x:x + PATCH_SIZE
            ]

            mask_patch = mask_np[
                y:y + PATCH_SIZE,
                x:x + PATCH_SIZE
            ]

            patch_name = (
                f"{counter:05d}_{base}_"
                f"p{patch_number:02d}.png"
            )

            if split == "train":
                before_dir = TRAIN_BEFORE
                after_dir = TRAIN_AFTER
                mask_dir = TRAIN_MASK

            else:
                before_dir = VAL_BEFORE
                after_dir = VAL_AFTER
                mask_dir = VAL_MASK

            Image.fromarray(pre_patch).save(
                before_dir / patch_name
            )

            Image.fromarray(post_patch).save(
                after_dir / patch_name
            )

            # Force binary mask: 0 or 1
            binary_mask = (
                mask_patch > 0
            ).astype(np.uint8) * 255

            Image.fromarray(binary_mask).save(
                mask_dir / patch_name
            )

            patch_number += 1

    return patch_number


# ============================================================
# PROCESS TRAINING DATA
# ============================================================

print("\nProcessing training data...")

train_patch_count = 0

for i, pair in enumerate(train_pairs):

    count = process_pair(
        pair,
        "train",
        i
    )

    train_patch_count += count

    if (i + 1) % 100 == 0:
        print(
            f"Processed training pairs: "
            f"{i + 1}/{len(train_pairs)}"
        )

# ============================================================
# PROCESS VALIDATION DATA
# ============================================================

print("\nProcessing validation data...")

val_patch_count = 0

for i, pair in enumerate(val_pairs):

    count = process_pair(
        pair,
        "val",
        i
    )

    val_patch_count += count

    if (i + 1) % 100 == 0:
        print(
            f"Processed validation pairs: "
            f"{i + 1}/{len(val_pairs)}"
        )

# ============================================================
# FINAL REPORT
# ============================================================

print("\n========================================")
print("PREPROCESSING COMPLETE")
print("========================================")

print("Training patches:", train_patch_count)
print("Validation patches:", val_patch_count)

print("\nOutput:")
print(OUTPUT)

print("\nDataset structure:")

print("""
xBD_processed/
│
├── train/
│   ├── before/
│   ├── after/
│   └── mask/
│
└── val/
    ├── before/
    ├── after/
    └── mask/
""")

print("========================================")