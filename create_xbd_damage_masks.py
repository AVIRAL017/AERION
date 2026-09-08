import json
from pathlib import Path
from PIL import Image, ImageDraw
from tqdm import tqdm

# =========================
# PATHS
# =========================

XBD_ROOT = Path(r"D:\mp-1\xBD\train")
OUTPUT_ROOT = Path(r"D:\mp-1\xBD_damage_processed")

# =========================
# SETTINGS
# =========================

PATCH_SIZE = 512
STRIDE = 512

# These are considered actual damage
DAMAGE_TYPES = {
    "minor-damage",
    "major-damage",
    "destroyed"
}

# =========================
# HELPERS
# =========================

def polygon_to_mask(json_data, image_size=(1024, 1024)):
    """
    Convert damaged building polygons from xBD JSON
    into a binary damage mask.
    """

    mask = Image.new("L", image_size, 0)
    draw = ImageDraw.Draw(mask)

    features = json_data["features"]["xy"]

    for feature in features:

        properties = feature.get("properties", {})
        subtype = properties.get("subtype", "").lower()

        # Ignore undamaged buildings
        if subtype not in DAMAGE_TYPES:
            continue

        wkt = feature.get("wkt", "")

        if not wkt.startswith("POLYGON"):
            continue

        # Extract coordinate section
        coords_text = wkt.split("((", 1)[-1].split("))", 1)[0]

        points = []

        for point in coords_text.split(","):
            x, y = point.strip().split()[:2]

            # xBD xy coordinates are pixel coordinates
            points.append((float(x), float(y)))

        if len(points) >= 3:
            draw.polygon(points, fill=255)

    return mask


def create_patches(before, after, mask, split, base_name):
    """
    Split before/after/mask into 512x512 patches.
    """

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

            before_patch = before.crop(box)
            after_patch = after.crop(box)
            mask_patch = mask.crop(box)

            filename = f"{base_name}_{patch_id:04d}.png"

            before_patch.save(before_dir / filename)
            after_patch.save(after_dir / filename)
            mask_patch.save(mask_dir / filename)

            patch_id += 1


# =========================
# FIND JSON FILES
# =========================

labels_dir = XBD_ROOT / "labels"
images_dir = XBD_ROOT / "images"

json_files = sorted(labels_dir.glob("*_post_disaster.json"))

print(f"Found {len(json_files)} post-disaster JSON files.")

# =========================
# TRAIN / VALIDATION SPLIT
# =========================

# Pair-level split
split_index = int(len(json_files) * 0.8)

train_files = json_files[:split_index]
val_files = json_files[split_index:]

print(f"Training pairs:   {len(train_files)}")
print(f"Validation pairs: {len(val_files)}")


# =========================
# PROCESS DATA
# =========================

def process_files(files, split):

    total_patches = 0
    damaged_pairs = 0

    for json_file in tqdm(files, desc=f"Processing {split}"):

        base = json_file.name.replace(
            "_post_disaster.json", ""
        )

        before_name = f"{base}_pre_disaster.png"
        after_name = f"{base}_post_disaster.png"

        before_path = images_dir / before_name
        after_path = images_dir / after_name

        if not before_path.exists() or not after_path.exists():
            print(f"\nSkipping missing pair: {base}")
            continue

        # Load images
        before = Image.open(before_path).convert("RGB")
        after = Image.open(after_path).convert("RGB")

        # Read JSON
        with open(json_file, "r") as f:
            data = json.load(f)

        # Generate damage mask
        mask = polygon_to_mask(
            data,
            image_size=before.size
        )

        # Check whether damage exists
        if mask.getbbox() is not None:
            damaged_pairs += 1

        # Create patches
        create_patches(
            before,
            after,
            mask,
            split,
            base
        )

        # 1024 / 512 = 2 x 2
        total_patches += 4

    print(f"\n{split.upper()} COMPLETE")
    print(f"Pairs with damage: {damaged_pairs}")
    print(f"Patches created:   {total_patches}")

    return total_patches


train_count = process_files(train_files, "train")
val_count = process_files(val_files, "val")


# =========================
# SUMMARY
# =========================

print("\n===================================")
print("xBD DAMAGE DATASET CREATED")
print("===================================")

print(f"Output: {OUTPUT_ROOT}")

print(f"\nTrain patches: {train_count}")
print(f"Val patches:   {val_count}")

print("\nMask meaning:")
print("0   = background / no damage")
print("255 = damaged building")
print("\nDamage classes included:")
print("minor-damage")
print("major-damage")
print("destroyed")

print("\nDataset is ready for inspection.")