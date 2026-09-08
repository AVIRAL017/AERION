import torch
import numpy as np
from pathlib import Path
from PIL import Image
from torch.utils.data import Dataset, DataLoader

from train_damage_detection_v2 import DamageDetectionModel


# ============================================================
# CONFIG
# ============================================================

DATA_ROOT = Path(
    r"D:\mp-1\xBD_damage_processed_v2\val"
)

MODEL_PATH = Path(
    r"D:\mp-1\change_detection_runs_v2\best_model.pth"
)

BATCH_SIZE = 2

DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)


# ============================================================
# DATASET
# ============================================================

class XBDDamageDataset(Dataset):

    def __init__(self, root):

        self.root = Path(root)

        self.before_dir = self.root / "before"
        self.after_dir = self.root / "after"
        self.mask_dir = self.root / "mask"

        self.files = sorted(
            f.name for f in self.mask_dir.glob("*.png")
        )

    def __len__(self):
        return len(self.files)

    def __getitem__(self, idx):

        name = self.files[idx]

        before = np.array(
            Image.open(
                self.before_dir / name
            ).convert("RGB"),
            dtype=np.float32
        ) / 255.0

        after = np.array(
            Image.open(
                self.after_dir / name
            ).convert("RGB"),
            dtype=np.float32
        ) / 255.0

        mask = np.array(
            Image.open(
                self.mask_dir / name
            ).convert("L"),
            dtype=np.float32
        ) / 255.0

        before = torch.from_numpy(
            before
        ).permute(2, 0, 1)

        after = torch.from_numpy(
            after
        ).permute(2, 0, 1)

        mask = torch.from_numpy(
            mask
        ).unsqueeze(0)

        return before, after, mask


# ============================================================
# LOAD
# ============================================================

dataset = XBDDamageDataset(DATA_ROOT)

loader = DataLoader(
    dataset,
    batch_size=BATCH_SIZE,
    shuffle=False,
    num_workers=0,
    pin_memory=True
)

print(f"Validation samples: {len(dataset)}")
print(f"Device: {DEVICE}")

# ============================================================
# MODEL
# ============================================================

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
    f"Checkpoint epoch: "
    f"{checkpoint.get('epoch', 'unknown')}"
)

print(
    f"Saved training IoU: "
    f"{checkpoint.get('iou', 0):.4f}"
)


# ============================================================
# EVALUATION
# ============================================================

threshold = 0.5

image_ious = []
image_dices = []

with torch.no_grad():

    for before, after, target in loader:

        before = before.to(DEVICE)
        after = after.to(DEVICE)

        output = model(
            before,
            after
        )

        probability = torch.sigmoid(output)

        prediction = (
            probability > threshold
        ).float()

        # Calculate separately for EVERY image
        for pred, true in zip(
            prediction,
            target
        ):

            pred = pred.cpu().numpy().astype(bool)
            true = true.numpy().astype(bool)

            intersection = np.logical_and(
                pred,
                true
            ).sum()

            pred_area = pred.sum()
            true_area = true.sum()

            union = np.logical_or(
                pred,
                true
            ).sum()

            # Both empty = perfect match
            if pred_area == 0 and true_area == 0:

                iou = 1.0
                dice = 1.0

            else:

                iou = (
                    intersection / union
                    if union > 0
                    else 0.0
                )

                dice_denominator = (
                    pred_area + true_area
                )

                dice = (
                    2 * intersection
                    / dice_denominator
                    if dice_denominator > 0
                    else 0.0
                )

            image_ious.append(iou)
            image_dices.append(dice)


# ============================================================
# RESULTS
# ============================================================

mean_iou = np.mean(image_ious)
mean_dice = np.mean(image_dices)

print("\n==========================================")
print("PER-IMAGE EVALUATION")
print("==========================================")

print(
    f"Threshold: {threshold:.2f}"
)

print(
    f"Mean IoU:  {mean_iou:.4f}"
)

print(
    f"Mean Dice: {mean_dice:.4f}"
)

print(
    f"Images evaluated: {len(image_ious)}"
)

print("\n==========================================")
print("COMPARISON")
print("==========================================")

print(
    f"Training reported IoU: "
    f"{checkpoint.get('iou', 0):.4f}"
)

print(
    f"Independent mean IoU:  "
    f"{mean_iou:.4f}"
)

print("\nEvaluation complete.")