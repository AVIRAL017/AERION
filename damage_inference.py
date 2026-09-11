import torch
import numpy as np
from pathlib import Path
from PIL import Image
import matplotlib.pyplot as plt

from train_damage_detection_v2 import DamageDetectionModel


# ============================================================
# CONFIG
# ============================================================

_LOCAL_DAMAGE_MODEL = Path(__file__).resolve().parent / "change_detection_runs_v2" / "best_model.pth"
MODEL_PATH = _LOCAL_DAMAGE_MODEL if _LOCAL_DAMAGE_MODEL.exists() else Path(r"D:\mp-1\change_detection_runs_v2\best_model.pth")

THRESHOLD = 0.50

DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)


# ============================================================
# LOAD MODEL
# ============================================================

print("Loading damage detection model...")

model = DamageDetectionModel().to(DEVICE)

checkpoint = torch.load(
    MODEL_PATH,
    map_location=DEVICE,
    weights_only=False
)

model.load_state_dict(
    checkpoint["model_state_dict"]
)

model.eval()

print(
    f"Model loaded from epoch "
    f"{checkpoint.get('epoch', 'unknown')}"
)

print(
    f"Device: {DEVICE}"
)


# ============================================================
# PREPROCESS
# ============================================================

def preprocess(image_path):

    image = Image.open(
        image_path
    ).convert("RGB")

    original = np.array(
        image
    )

    image = image.resize(
        (512, 512)
    )

    image = np.array(
        image,
        dtype=np.float32
    ) / 255.0

    tensor = torch.from_numpy(
        image
    ).permute(2, 0, 1)

    tensor = tensor.unsqueeze(0)

    return tensor.to(DEVICE), original


# ============================================================
# DAMAGE INFERENCE
# ============================================================

def predict_damage(
    before_path,
    after_path
):

    before_tensor, before_original = preprocess(
        before_path
    )

    after_tensor, after_original = preprocess(
        after_path
    )

    with torch.no_grad():

        output = model(
            before_tensor,
            after_tensor
        )

        probability = torch.sigmoid(
            output
        )

    probability = probability[
        0, 0
    ].cpu().numpy()

    damage_mask = (
        probability >= THRESHOLD
    ).astype(np.uint8)

    return (
        before_original,
        after_original,
        probability,
        damage_mask
    )


# ============================================================
# VISUALIZATION
# ============================================================

def save_visualization(
    before,
    after,
    probability,
    damage_mask,
    output_path
):

    damage_pixels = (
        damage_mask > 0
    ).sum()

    total_pixels = (
        damage_mask.size
    )

    damage_percentage = (
        damage_pixels /
        total_pixels
    ) * 100

    fig, axes = plt.subplots(
        1,
        3,
        figsize=(15, 5)
    )

    axes[0].imshow(before)
    axes[0].set_title(
        "Before"
    )

    axes[1].imshow(after)
    axes[1].set_title(
        "After"
    )

    axes[2].imshow(
        after
    )

    axes[2].imshow(
        damage_mask,
        alpha=0.5
    )

    axes[2].set_title(
        f"Predicted Damage\n"
        f"{damage_percentage:.2f}% area"
    )

    for ax in axes:
        ax.axis("off")

    plt.tight_layout()

    plt.savefig(
        output_path,
        dpi=150
    )

    plt.close()

    print(
        f"\nDamage area: "
        f"{damage_percentage:.2f}%"
    )

    print(
        f"Visualization saved: "
        f"{output_path}"
    )


# ============================================================
# MAIN TEST
# ============================================================

if __name__ == "__main__":

    # Use one verified xBD validation pair
    validation_dir = Path(
        r"D:\mp-1\xBD_damage_processed_v2\val"
    )

    before_dir = (
        validation_dir / "before"
    )

    after_dir = (
        validation_dir / "after"
    )

    mask_dir = (
        validation_dir / "mask"
    )

    # Find a sample containing actual damage
    selected = None

    for mask_path in mask_dir.glob("*.png"):

        mask = Image.open(mask_path)

        if mask.getbbox() is not None:

            selected = mask_path.name
            break

    if selected is None:

        raise RuntimeError(
            "No damaged validation sample found."
        )

    before_path = (
        before_dir / selected
    )

    after_path = (
        after_dir / selected
    )

    output_path = Path(
        r"D:\mp-1\damage_inference_result.png"
    )

    print(
        f"\nTesting sample: {selected}"
    )

    before, after, probability, damage_mask = predict_damage(
        before_path,
        after_path
    )

    save_visualization(
        before,
        after,
        probability,
        damage_mask,
        output_path
    )

    print("\nInference complete.")