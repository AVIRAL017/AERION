import json
import random
import shutil
from pathlib import Path
from PIL import Image, ImageDraw
from tqdm import tqdm

# =========================
# PATHS
# =========================

XBD_ROOT = Path(r"D:\mp-1\xBD\train")
OUTPUT_ROOT = Path(r"D:\mp-1\xBD_damage_processed_v2")

PATCH_SIZE = 512
STRIDE = 512

DAMAGE_TYPES = {
    "minor-damage",
    "major-damage",
    "destroyed"
}

SEED = 42
VAL_RATIO = 0.20


# =========================
# DAMAGE CHECK
# =========================

def has_damage(json_file):
    with open(json_file, "r") as f:
        data = json.load(f)

    for feature in data["features"]["xy"]:
        subtype = feature.get("properties", {}).get(
            "subtype", ""
        ).lower()

        if subtype in DAMAGE_TYPES:
            return True

    return False


# =========================
# CREATE MASK
# =========================

def polygon_to_mask(json_data, image_size):

    mask = Image.new("L", image_size, 0)
    draw = ImageDraw.Draw(mask)

    for feature in json_data["features"]["xy"]:

        properties = feature.get("properties", {})
        subtype = properties.get("subtype", "").lower()

        if subtype not in DAMAGE_TYPES:
            continue

        wkt = feature.get("wkt", "")

        if not wkt.startswith("POLYGON"):
            continue

        coords_text = (
            wkt.split("((", 1)[-1]
            .split("))", 1)[0]
        )

        points = []

        for point in coords_text.split(","):
            values = point.strip().split()

            if len(values) >= 2:
                x = float(values[0])
                y = float(values[1])
                points.append((x, y))

        if len(points) >= 3:
            draw.polygon(points, fill=255)

    return mask


# =========================
# PATCH CREATION
# =========================

def create_patches(before, after, mask, split, base_name):

    before_dir = OUTPUT_ROOT / split / "before"
    after_dir = OUTPUT_ROOT / split / "after"
    mask_dir = OUTPUT_ROOT / split / "mask"

    before_dir.mkdir(parents=True, exist_ok=True)
    after_dir.mkdir(parents=True, exist_ok=True)
    mask_dir.mkdir(parents=True, exist_ok=True)

    width, height = before.size

    patch_id = 0

    for y in range(0, height - PATCH_SIZE + 1, STRIDE):

        for x in range(0, width - PATCH_SIZE + 1, STRIDE):

            box = (
                x,
                y,
                x + PATCH_SIZE,
                y + PATCH_SIZE
            )

            before.crop(box).save(
                before_dir / f"{base_name}_{patch_id:04d}.png"
            )

            after.crop(box).save(
                after_dir / f"{base_name}_{patch_id:04d}.png"
            )

            mask.crop(box).save(
                mask_dir / f"{base_name}_{patch_id:04d}.png"
            )

            patch_id += 1

    return patch_id


# =========================
# PROCESS
# =========================

def process(files, split):

    total_patches = 0
    damage_pairs = 0

    for json_file in tqdm(
        files,
        desc=f"Processing {split}"
    ):

        base = json_file.name.replace(
            "_post_disaster.json",
            ""
        )

        before_path = (
            XBD_ROOT / "images" /
            f"{base}_pre_disaster.png"
        )

        after_path = (
            XBD_ROOT / "images" /
            f"{base}_post_disaster.png"
        )

        if not before_path.exists() or not after_path.exists():
            continue

        before = Image.open(before_path).convert("RGB")
        after = Image.open(after_path).convert("RGB")

        with open(json_file, "r") as f:
            data = json.load(f)

        mask = polygon_to_mask(
            data,
            before.size
        )

        if mask.getbbox() is not None:
            damage_pairs += 1

        total_patches += create_patches(
            before,
            after,
            mask,
            split,
            base
        )

    return total_patches, damage_pairs


# =========================
# MAIN
# =========================

print("Scanning xBD dataset...")

labels_dir = XBD_ROOT / "labels"

json_files = sorted(
    labels_dir.glob("*_post_disaster.json")
)

print(f"Total pairs: {len(json_files)}")


# --------------------------------
# Separate damage / no-damage
# --------------------------------

print("\nChecking damage distribution...")

random.seed(SEED)

damage_files = []
no_damage_files = []

for file in tqdm(json_files):

    if has_damage(file):
        damage_files.append(file)
    else:
        no_damage_files.append(file)

print(f"\nDamage pairs:     {len(damage_files)}")
print(f"No-damage pairs:  {len(no_damage_files)}")


# --------------------------------
# Shuffle independently
# --------------------------------

random.shuffle(damage_files)
random.shuffle(no_damage_files)


# --------------------------------
# Stratified split
# --------------------------------

def split_group(files):

    val_count = int(len(files) * VAL_RATIO)

    return (
        files[val_count:],
        files[:val_count]
    )


damage_train, damage_val = split_group(
    damage_files
)

nodamage_train, nodamage_val = split_group(
    no_damage_files
)


train_files = damage_train + nodamage_train
val_files = damage_val + nodamage_val

random.shuffle(train_files)
random.shuffle(val_files)


print("\n================================")
print("STRATIFIED SPLIT")
print("================================")

print(
    f"Train: {len(train_files)} pairs"
)

print(
    f"Validation: {len(val_files)} pairs"
)

print(
    f"Train damaged: {len(damage_train)}"
)

print(
    f"Val damaged: {len(damage_val)}"
)

print(
    f"Train no-damage: {len(nodamage_train)}"
)

print(
    f"Val no-damage: {len(nodamage_val)}"
)


# --------------------------------
# Recreate output directory
# --------------------------------

if OUTPUT_ROOT.exists():

    print("\nRemoving previous v2 dataset...")

    shutil.rmtree(OUTPUT_ROOT)


# --------------------------------
# Generate dataset
# --------------------------------

print("\nGenerating training dataset...")

train_patches, train_damage = process(
    train_files,
    "train"
)

print("\nGenerating validation dataset...")

val_patches, val_damage = process(
    val_files,
    "val"
)


# =========================
# FINAL SUMMARY
# =========================

print("\n===================================")
print("xBD DAMAGE DATASET V2 CREATED")
print("===================================")

print(f"Output: {OUTPUT_ROOT}")

print(f"\nTrain pairs: {len(train_files)}")
print(f"Val pairs:   {len(val_files)}")

print(f"\nTrain damage pairs: {train_damage}")
print(f"Val damage pairs:   {val_damage}")

print(f"\nTrain patches: {train_patches}")
print(f"Val patches:   {val_patches}")

print("\nMask:")
print("0   = no damage")
print("255 = damaged building")

print("\nDamage classes:")
print("minor-damage")
print("major-damage")
print("destroyed")

print("\nDataset generation complete.")
