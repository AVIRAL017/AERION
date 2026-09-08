import os
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torchvision.models import resnet18, ResNet18_Weights
from PIL import Image
from pathlib import Path
from tqdm import tqdm


# ============================================================
# CONFIGURATION
# ============================================================

DATA_ROOT = Path(r"D:\mp-1\xBD_damage_processed_v2")
OUTPUT_DIR = Path(r"D:\mp-1\change_detection_runs_v2")

BATCH_SIZE = 2
EPOCHS = 40
LEARNING_RATE = 1e-4
WEIGHT_DECAY = 1e-4

NUM_WORKERS = 2
PATIENCE = 8

IMAGE_SIZE = 512

DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# DATASET
# ============================================================

class XBDDamageDataset(Dataset):

    def __init__(self, root):

        self.root = Path(root)

        self.before_dir = self.root / "before"
        self.after_dir = self.root / "after"
        self.mask_dir = self.root / "mask"

        self.files = sorted([
            f.name for f in self.mask_dir.glob("*.png")
        ])

        print(
            f"Loaded {len(self.files)} samples from {root}"
        )

    def __len__(self):
        return len(self.files)

    def __getitem__(self, idx):

        filename = self.files[idx]

        before = Image.open(
            self.before_dir / filename
        ).convert("RGB")

        after = Image.open(
            self.after_dir / filename
        ).convert("RGB")

        mask = Image.open(
            self.mask_dir / filename
        ).convert("L")

        # Convert to tensors
        before = torch.from_numpy(
            __import__("numpy").array(before)
        ).permute(2, 0, 1).float() / 255.0

        after = torch.from_numpy(
            __import__("numpy").array(after)
        ).permute(2, 0, 1).float() / 255.0

        mask = torch.from_numpy(
            __import__("numpy").array(mask)
        ).unsqueeze(0).float() / 255.0

        return before, after, mask


# ============================================================
# SIAMESE RESNET18 ENCODER
# ============================================================

class SiameseResNet18(nn.Module):

    def __init__(self):

        super().__init__()

        backbone = resnet18(
            weights=ResNet18_Weights.DEFAULT
        )

        self.conv1 = backbone.conv1
        self.bn1 = backbone.bn1
        self.relu = backbone.relu
        self.maxpool = backbone.maxpool

        self.layer1 = backbone.layer1
        self.layer2 = backbone.layer2
        self.layer3 = backbone.layer3
        self.layer4 = backbone.layer4

    def forward_once(self, x):

        x0 = self.relu(
            self.bn1(
                self.conv1(x)
            )
        )

        x1 = self.layer1(
            self.maxpool(x0)
        )

        x2 = self.layer2(x1)
        x3 = self.layer3(x2)
        x4 = self.layer4(x3)

        return x0, x1, x2, x3, x4

    def forward(self, before, after):

        before_features = self.forward_once(before)
        after_features = self.forward_once(after)

        differences = []

        for b, a in zip(
            before_features,
            after_features
        ):
            differences.append(
                torch.abs(b - a)
            )

        return differences


# ============================================================
# DECODER
# ============================================================

class DecoderBlock(nn.Module):

    def __init__(
        self,
        in_channels,
        skip_channels,
        out_channels
    ):

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

        x = torch.cat(
            [x, skip],
            dim=1
        )

        return self.conv(x)


# ============================================================
# FULL CHANGE / DAMAGE MODEL
# ============================================================

class DamageDetectionModel(nn.Module):

    def __init__(self):

        super().__init__()

        self.encoder = SiameseResNet18()

        self.decoder4 = DecoderBlock(
            512, 256, 256
        )

        self.decoder3 = DecoderBlock(
            256, 128, 128
        )

        self.decoder2 = DecoderBlock(
            128, 64, 64
        )

        self.decoder1 = DecoderBlock(
            64, 64, 32
        )

        self.final = nn.Conv2d(
            32,
            1,
            kernel_size=1
        )

    def forward(self, before, after):

        features = self.encoder(
            before,
            after
        )

        d0, d1, d2, d3, d4 = features

        x = self.decoder4(
            d4,
            d3
        )

        x = self.decoder3(
            x,
            d2
        )

        x = self.decoder2(
            x,
            d1
        )

        x = self.decoder1(
            x,
            d0
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
        ).sum()

        dice = (
            2 * intersection + 1e-6
        ) / (
            probability.sum()
            + target.sum()
            + 1e-6
        )

        dice_loss = 1 - dice

        return bce + dice_loss


# ============================================================
# METRICS
# ============================================================

def calculate_metrics(
    prediction,
    target
):

    prediction = (
        torch.sigmoid(prediction) > 0.5
    ).float()

    intersection = (
        prediction * target
    ).sum()

    union = (
        prediction
        + target
        - prediction * target
    ).sum()

    dice = (
        2 * intersection + 1e-6
    ) / (
        prediction.sum()
        + target.sum()
        + 1e-6
    )

    iou = (
        intersection + 1e-6
    ) / (
        union + 1e-6
    )

    return dice.item(), iou.item()


# ============================================================
# VALIDATION
# ============================================================

def validate(
    model,
    loader,
    criterion
):

    model.eval()

    total_loss = 0
    total_dice = 0
    total_iou = 0

    with torch.no_grad():

        for before, after, mask in loader:

            before = before.to(DEVICE)
            after = after.to(DEVICE)
            mask = mask.to(DEVICE)

            output = model(
                before,
                after
            )

            loss = criterion(
                output,
                mask
            )

            dice, iou = calculate_metrics(
                output,
                mask
            )

            total_loss += loss.item()
            total_dice += dice
            total_iou += iou

    n = len(loader)

    return (
        total_loss / n,
        total_dice / n,
        total_iou / n
    )


# ============================================================
# TRAINING
# ============================================================

def main():

    print("\n================================")
    print("GeoShield AI")
    print("Deep Disaster Damage Detection")
    print("================================")

    print(f"Device: {DEVICE}")

    if torch.cuda.is_available():

        print(
            f"GPU: {torch.cuda.get_device_name(0)}"
        )

    # -----------------------------
    # DATA
    # -----------------------------

    train_dataset = XBDDamageDataset(
        DATA_ROOT / "train"
    )

    val_dataset = XBDDamageDataset(
        DATA_ROOT / "val"
    )

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

    print(
        f"Training samples: {len(train_dataset)}"
    )

    print(
        f"Validation samples: {len(val_dataset)}"
    )

    # -----------------------------
    # MODEL
    # -----------------------------

    model = DamageDetectionModel().to(DEVICE)

    criterion = DiceBCELoss()

    optimizer = optim.AdamW(
        model.parameters(),
        lr=LEARNING_RATE,
        weight_decay=WEIGHT_DECAY
    )

    scaler = torch.amp.GradScaler(
        "cuda",
        enabled=torch.cuda.is_available()
    )

    # -----------------------------
    # TRAINING STATE
    # -----------------------------

    best_iou = 0.0
    patience_counter = 0

    best_path = (
        OUTPUT_DIR / "best_model.pth"
    )

    # -----------------------------
    # EPOCHS
    # -----------------------------

    for epoch in range(EPOCHS):

        model.train()

        running_loss = 0.0

        progress = tqdm(
            train_loader,
            desc=f"Epoch {epoch + 1}/{EPOCHS}"
        )

        for before, after, mask in progress:

            before = before.to(
                DEVICE,
                non_blocking=True
            )

            after = after.to(
                DEVICE,
                non_blocking=True
            )

            mask = mask.to(
                DEVICE,
                non_blocking=True
            )

            optimizer.zero_grad(
                set_to_none=True
            )

            with torch.amp.autocast(
                "cuda",
                enabled=torch.cuda.is_available()
            ):

                output = model(
                    before,
                    after
                )

                loss = criterion(
                    output,
                    mask
                )

            scaler.scale(loss).backward()

            scaler.step(optimizer)

            scaler.update()

            running_loss += loss.item()

            progress.set_postfix(
                loss=f"{loss.item():.4f}"
            )

        train_loss = (
            running_loss
            / len(train_loader)
        )

        # -------------------------
        # VALIDATION
        # -------------------------

        val_loss, dice, iou = validate(
            model,
            val_loader,
            criterion
        )

        print(
            f"\nEpoch {epoch + 1}/{EPOCHS}"
        )

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

        # -------------------------
        # SAVE BEST
        # -------------------------

        if iou > best_iou:

            best_iou = iou

            patience_counter = 0

            torch.save(
                {
                    "epoch": epoch + 1,
                    "model_state_dict":
                        model.state_dict(),
                    "optimizer_state_dict":
                        optimizer.state_dict(),
                    "iou": iou,
                    "dice": dice
                },
                best_path
            )

            print(
                f"✓ New best model saved "
                f"(IoU={iou:.4f})"
            )

        else:

            patience_counter += 1

            print(
                f"No improvement "
                f"({patience_counter}/{PATIENCE})"
            )

            if patience_counter >= PATIENCE:

                print(
                    "\nEarly stopping triggered."
                )

                break

    print("\n================================")
    print("TRAINING COMPLETE")
    print("================================")

    print(
        f"Best IoU: {best_iou:.4f}"
    )

    print(
        f"Best model: {best_path}"
    )


if __name__ == "__main__":
    main()