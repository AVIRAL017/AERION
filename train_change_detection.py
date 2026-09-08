import os
from pathlib import Path

import numpy as np
from PIL import Image

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torchvision.models import resnet18, ResNet18_Weights


# ============================================================
# CONFIG
# ============================================================

DATASET = Path(r"D:\mp-1\xBD_processed")
OUTPUT = Path(r"D:\mp-1\change_detection_runs")

IMAGE_SIZE = 512

BATCH_SIZE = 2
EPOCHS = 30

LEARNING_RATE = 1e-4
WEIGHT_DECAY = 1e-4

NUM_WORKERS = 2

PATIENCE = 7

DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)

OUTPUT.mkdir(parents=True, exist_ok=True)


# ============================================================
# DATASET
# ============================================================

class XBDDataset(Dataset):

    def __init__(self, root):

        self.root = Path(root)

        self.before_dir = self.root / "before"
        self.after_dir = self.root / "after"
        self.mask_dir = self.root / "mask"

        self.files = sorted(
            self.before_dir.glob("*.png")
        )

        if len(self.files) == 0:
            raise RuntimeError(
                f"No images found in {self.before_dir}"
            )

    def __len__(self):
        return len(self.files)

    def __getitem__(self, index):

        before_path = self.files[index]

        filename = before_path.name

        after_path = self.after_dir / filename
        mask_path = self.mask_dir / filename

        before = np.array(
            Image.open(before_path).convert("RGB"),
            dtype=np.float32
        ) / 255.0

        after = np.array(
            Image.open(after_path).convert("RGB"),
            dtype=np.float32
        ) / 255.0

        mask = np.array(
            Image.open(mask_path).convert("L"),
            dtype=np.float32
        ) / 255.0

        # HWC -> CHW
        before = torch.from_numpy(
            before.transpose(2, 0, 1)
        )

        after = torch.from_numpy(
            after.transpose(2, 0, 1)
        )

        mask = torch.from_numpy(mask)

        mask = mask.unsqueeze(0)

        return before, after, mask


# ============================================================
# SIAMESE ENCODER
# ============================================================

class SiameseEncoder(nn.Module):

    def __init__(self):

        super().__init__()

        backbone = resnet18(
            weights=ResNet18_Weights.DEFAULT
        )

        self.layer0 = nn.Sequential(
            backbone.conv1,
            backbone.bn1,
            backbone.relu
        )

        self.pool = backbone.maxpool

        self.layer1 = backbone.layer1
        self.layer2 = backbone.layer2
        self.layer3 = backbone.layer3
        self.layer4 = backbone.layer4

    def forward(self, x):

        x0 = self.layer0(x)
        x = self.pool(x0)

        x1 = self.layer1(x)
        x2 = self.layer2(x1)
        x3 = self.layer3(x2)
        x4 = self.layer4(x3)

        return x0, x1, x2, x3, x4


# ============================================================
# DECODER BLOCK
# ============================================================

class DecoderBlock(nn.Module):

    def __init__(self, in_channels, skip_channels, out_channels):

        super().__init__()

        self.conv = nn.Sequential(

            nn.Conv2d(
                in_channels + skip_channels,
                out_channels,
                kernel_size=3,
                padding=1
            ),

            nn.BatchNorm2d(out_channels),

            nn.ReLU(inplace=True),

            nn.Conv2d(
                out_channels,
                out_channels,
                kernel_size=3,
                padding=1
            ),

            nn.BatchNorm2d(out_channels),

            nn.ReLU(inplace=True)
        )

    def forward(self, x, skip):

        x = nn.functional.interpolate(
            x,
            size=skip.shape[-2:],
            mode="bilinear",
            align_corners=False
        )

        x = torch.cat([x, skip], dim=1)

        return self.conv(x)


# ============================================================
# SIAMESE U-NET
# ============================================================

class SiameseUNet(nn.Module):

    def __init__(self):

        super().__init__()

        self.encoder = SiameseEncoder()

        # Difference doubles channels.
        self.decoder4 = DecoderBlock(
            512,
            256,
            256
        )

        self.decoder3 = DecoderBlock(
            256,
            128,
            128
        )

        self.decoder2 = DecoderBlock(
            128,
            64,
            64
        )

        self.decoder1 = DecoderBlock(
            64,
            64,
            32
        )

        self.final = nn.Sequential(

            nn.Conv2d(
                32,
                16,
                kernel_size=3,
                padding=1
            ),

            nn.ReLU(inplace=True),

            nn.Conv2d(
                16,
                1,
                kernel_size=1
            )
        )

    def forward(self, before, after):

        b0, b1, b2, b3, b4 = self.encoder(before)
        a0, a1, a2, a3, a4 = self.encoder(after)

        # Absolute feature differences
        x4 = torch.abs(b4 - a4)

        x3 = torch.abs(b3 - a3)
        x2 = torch.abs(b2 - a2)
        x1 = torch.abs(b1 - a1)
        x0 = torch.abs(b0 - a0)

        x = self.decoder4(
            x4,
            x3
        )

        x = self.decoder3(
            x,
            x2
        )

        x = self.decoder2(
            x,
            x1
        )

        x = self.decoder1(
            x,
            x0
        )

        x = nn.functional.interpolate(
            x,
            size=(IMAGE_SIZE, IMAGE_SIZE),
            mode="bilinear",
            align_corners=False
        )

        return self.final(x)


# ============================================================
# LOSS
# ============================================================

class DiceBCELoss(nn.Module):

    def __init__(self):

        super().__init__()

        self.bce = nn.BCEWithLogitsLoss()

    def forward(self, prediction, target):

        bce = self.bce(
            prediction,
            target
        )

        probability = torch.sigmoid(
            prediction
        )

        intersection = (
            probability * target
        ).sum(dim=(1, 2, 3))

        denominator = (
            probability.sum(dim=(1, 2, 3))
            +
            target.sum(dim=(1, 2, 3))
        )

        dice = (
            (2 * intersection + 1e-6)
            /
            (denominator + 1e-6)
        ).mean()

        dice_loss = 1 - dice

        return bce + dice_loss


# ============================================================
# METRICS
# ============================================================

def calculate_metrics(prediction, target):

    probability = torch.sigmoid(prediction)

    prediction = (
        probability > 0.5
    ).float()

    intersection = (
        prediction * target
    ).sum()

    union = (
        prediction + target
        -
        prediction * target
    ).sum()

    pred_sum = prediction.sum()
    target_sum = target.sum()

    dice = (
        (2 * intersection + 1e-6)
        /
        (pred_sum + target_sum + 1e-6)
    )

    iou = (
        (intersection + 1e-6)
        /
        (union + 1e-6)
    )

    return dice.item(), iou.item()


# ============================================================
# TRAINING
# ============================================================

def train_one_epoch(
    model,
    loader,
    optimizer,
    criterion,
    scaler
):

    model.train()

    total_loss = 0

    for before, after, mask in loader:

        before = before.to(DEVICE)
        after = after.to(DEVICE)
        mask = mask.to(DEVICE)

        optimizer.zero_grad(
            set_to_none=True
        )

        with torch.cuda.amp.autocast(
            enabled=(DEVICE.type == "cuda")
        ):

            prediction = model(
                before,
                after
            )

            loss = criterion(
                prediction,
                mask
            )

        scaler.scale(loss).backward()

        scaler.step(optimizer)

        scaler.update()

        total_loss += loss.item()

    return total_loss / len(loader)


# ============================================================
# VALIDATION
# ============================================================

@torch.no_grad()
def validate(
    model,
    loader,
    criterion
):

    model.eval()

    total_loss = 0

    dice_scores = []
    iou_scores = []

    for before, after, mask in loader:

        before = before.to(DEVICE)
        after = after.to(DEVICE)
        mask = mask.to(DEVICE)

        prediction = model(
            before,
            after
        )

        loss = criterion(
            prediction,
            mask
        )

        total_loss += loss.item()

        dice, iou = calculate_metrics(
            prediction,
            mask
        )

        dice_scores.append(dice)
        iou_scores.append(iou)

    return (
        total_loss / len(loader),
        np.mean(dice_scores),
        np.mean(iou_scores)
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("\n======================================")
    print("GEOSHIELD AI")
    print("SIAMESE U-NET CHANGE DETECTION")
    print("======================================")

    print("Device:", DEVICE)

    if DEVICE.type == "cuda":

        print(
            "GPU:",
            torch.cuda.get_device_name(0)
        )

    # ---------------- DATASETS ----------------

    train_dataset = XBDDataset(
        DATASET / "train"
    )

    val_dataset = XBDDataset(
        DATASET / "val"
    )

    print(
        "Training samples:",
        len(train_dataset)
    )

    print(
        "Validation samples:",
        len(val_dataset)
    )

    # ---------------- DATALOADERS ----------------

    train_loader = DataLoader(
        train_dataset,
        batch_size=BATCH_SIZE,
        shuffle=True,
        num_workers=NUM_WORKERS,
        pin_memory=True,
        persistent_workers=True
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=BATCH_SIZE,
        shuffle=False,
        num_workers=NUM_WORKERS,
        pin_memory=True,
        persistent_workers=True
    )

    # ---------------- MODEL ----------------

    model = SiameseUNet().to(DEVICE)

    # ---------------- LOSS ----------------

    criterion = DiceBCELoss()

    # ---------------- OPTIMIZER ----------------

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=LEARNING_RATE,
        weight_decay=WEIGHT_DECAY
    )

    # ---------------- SCHEDULER ----------------

    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer,
        mode="max",
        factor=0.5,
        patience=3
    )

    # ---------------- AMP ----------------

    scaler = torch.cuda.amp.GradScaler(
        enabled=(DEVICE.type == "cuda")
    )

    best_iou = 0.0

    epochs_without_improvement = 0

    # ========================================================
    # TRAIN
    # ========================================================

    for epoch in range(1, EPOCHS + 1):

        print(
            f"\nEpoch {epoch}/{EPOCHS}"
        )

        train_loss = train_one_epoch(
            model,
            train_loader,
            optimizer,
            criterion,
            scaler
        )

        val_loss, dice, iou = validate(
            model,
            val_loader,
            criterion
        )

        scheduler.step(iou)

        print(
            f"Train Loss: {train_loss:.4f}"
        )

        print(
            f"Val Loss:   {val_loss:.4f}"
        )

        print(
            f"Dice:       {dice:.4f}"
        )

        print(
            f"IoU:        {iou:.4f}"
        )

        # ---------------- BEST MODEL ----------------

        if iou > best_iou:

            best_iou = iou

            epochs_without_improvement = 0

            torch.save(
                {
                    "epoch": epoch,
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict(),
                    "best_iou": best_iou
                },
                OUTPUT / "best_model.pth"
            )

            print(
                f"✓ New best model saved "
                f"(IoU={best_iou:.4f})"
            )

        else:

            epochs_without_improvement += 1

        # ---------------- EARLY STOPPING ----------------

        if epochs_without_improvement >= PATIENCE:

            print(
                "\nEarly stopping triggered."
            )

            break

    print("\n======================================")
    print("TRAINING COMPLETE")
    print("======================================")

    print(
        f"Best validation IoU: {best_iou:.4f}"
    )

    print(
        "Best model:",
        OUTPUT / "best_model.pth"
    )


if __name__ == "__main__":
    main()