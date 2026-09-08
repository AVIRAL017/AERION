import torch
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from pathlib import Path
from PIL import Image
import numpy as np

# Import the model architecture from your training script
from train_damage_detection_v2 import DamageDetectionModel


# ============================================================
# CONFIG
# ============================================================

DATA_ROOT = Path(r"D:\mp-1\xBD_damage_processed_v2\val")

MODEL_PATH = Path(
    r"D:\mp-1\change_detection_runs_v2\best_model.pth"
)

BATCH_SIZE = 2
NUM_WORKERS = 0

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
# LOAD DATA
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

if torch.cuda.is_available():
    print(
        f"GPU: {torch.cuda.get_device_name(0)}"
    )


# ============================================================
# LOAD MODEL
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
    f"Loaded checkpoint from epoch "
    f"{checkpoint.get('epoch', 'unknown')}"
)

print(
    f"Checkpoint IoU: "
    f"{checkpoint.get('iou', 0):.4f}"
)


# ============================================================
# COLLECT PREDICTIONS
# ============================================================

all_predictions = []
all_targets = []

print("\nRunning validation inference...")

with torch.no_grad():

    for before, after, mask in loader:

        before = before.to(
            DEVICE,
            non_blocking=True
        )

        after = after.to(
            DEVICE,
            non_blocking=True
        )

        output = model(
            before,
            after
        )

        probability = torch.sigmoid(
            output
        )

        all_predictions.append(
            probability.cpu()
        )

        all_targets.append(
            mask.cpu()
        )


predictions = torch.cat(
    all_predictions,
    dim=0
)

targets = torch.cat(
    all_targets,
    dim=0
)

print("Inference complete.")


# ============================================================
# THRESHOLD TEST
# ============================================================

thresholds = [
    0.20,
    0.25,
    0.30,
    0.35,
    0.40,
    0.45,
    0.50,
    0.55,
    0.60,
    0.65,
    0.70
]

results = []

print("\n==========================================")
print("THRESHOLD EVALUATION")
print("==========================================")

for threshold in thresholds:

    prediction = (
        predictions > threshold
    ).float()

    intersection = (
        prediction * targets
    ).sum()

    union = (
        prediction
        + targets
        - prediction * targets
    ).sum()

    dice = (
        2 * intersection + 1e-6
    ) / (
        prediction.sum()
        + targets.sum()
        + 1e-6
    )

    iou = (
        intersection + 1e-6
    ) / (
        union + 1e-6
    )

    dice = dice.item()
    iou = iou.item()

    results.append(
        (threshold, dice, iou)
    )

    print(
        f"Threshold {threshold:.2f} "
        f"| Dice: {dice:.4f} "
        f"| IoU: {iou:.4f}"
    )


# ============================================================
# BEST RESULTS
# ============================================================

best_iou = max(
    results,
    key=lambda x: x[2]
)

best_dice = max(
    results,
    key=lambda x: x[1]
)

print("\n==========================================")
print("BEST RESULTS")
print("==========================================")

print(
    f"Best IoU threshold: {best_iou[0]:.2f}"
)

print(
    f"Best IoU:            {best_iou[2]:.4f}"
)

print(
    f"Dice at best IoU:    {best_iou[1]:.4f}"
)

print()

print(
    f"Best Dice threshold: {best_dice[0]:.2f}"
)

print(
    f"Best Dice:            {best_dice[1]:.4f}"
)

print(
    f"IoU at best Dice:     {best_dice[2]:.4f}"
)

print("\nThreshold testing complete.")