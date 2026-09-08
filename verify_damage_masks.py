from pathlib import Path
from PIL import Image
import matplotlib.pyplot as plt
import random

ROOT = Path(r"D:\mp-1\xBD_damage_processed_v2\train")

before_dir = ROOT / "before"
after_dir = ROOT / "after"
mask_dir = ROOT / "mask"

files = list(mask_dir.glob("*.png"))

# Prefer samples that actually contain damage
damaged = []

for f in files:
    mask = Image.open(f)
    if mask.getbbox() is not None:
        damaged.append(f)

print(f"Total patches: {len(files)}")
print(f"Damage patches: {len(damaged)}")

# Pick 4 random damaged samples
samples = random.sample(damaged, min(4, len(damaged)))

for f in samples:

    name = f.name

    before = Image.open(before_dir / name)
    after = Image.open(after_dir / name)
    mask = Image.open(mask_dir / name)

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    axes[0].imshow(before)
    axes[0].set_title("Before")

    axes[1].imshow(after)
    axes[1].set_title("After")

    axes[2].imshow(mask, cmap="gray")
    axes[2].set_title("Damage Mask")

    for ax in axes:
        ax.axis("off")

    plt.tight_layout()

    output = Path(r"D:\mp-1") / f"verify_{name}"
    plt.savefig(output, dpi=150)
    plt.close()

    print(f"Saved: {output}")

print("\nVerification images created.")