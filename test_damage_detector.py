"""
AERION v1 — Damage Detector Real Inference Test

Tests the frozen Siamese ResNet18 damage model against
a genuine xBD validation before/after image pair.

No training.
No synthetic data.
No model modification.
"""

from pathlib import Path

import cv2
import numpy as np

from damage_inference import predict_damage


# ================================================================
# REAL xBD VALIDATION PAIR
# ================================================================

BEFORE_IMAGE = Path(
    r"D:\mp-1\xBD_damage_processed_v2\val\before"
    r"\guatemala-volcano_00000000_0000.png"
)

AFTER_IMAGE = Path(
    r"D:\mp-1\xBD_damage_processed_v2\val\after"
    r"\guatemala-volcano_00000000_0000.png"
)


# ================================================================
# IMAGE VALIDATION
# ================================================================

def validate_image(path: Path, name: str):

    if not path.exists():
        raise FileNotFoundError(
            f"{name} image not found:\n{path}"
        )

    image = cv2.imread(
        str(path),
        cv2.IMREAD_COLOR,
    )

    if image is None:
        raise RuntimeError(
            f"Could not read {name} image:\n{path}"
        )

    height, width = image.shape[:2]

    if width <= 0 or height <= 0:
        raise RuntimeError(
            f"Invalid {name} image dimensions."
        )

    return image, width, height


# ================================================================
# MAIN
# ================================================================

def main():

    print("=" * 72)
    print("AERION v1 — DAMAGE DETECTOR REAL INFERENCE TEST")
    print("=" * 72)

    # ------------------------------------------------------------
    # Validate real xBD pair
    # ------------------------------------------------------------

    print("\nValidating real xBD validation pair...")

    before, before_width, before_height = validate_image(
        BEFORE_IMAGE,
        "BEFORE",
    )

    after, after_width, after_height = validate_image(
        AFTER_IMAGE,
        "AFTER",
    )

    print("[OK] BEFORE image loaded")
    print("[OK] AFTER image loaded")

    print("\nBEFORE:")
    print(f"  {BEFORE_IMAGE}")
    print(
        f"  Size: {before_width} x {before_height}"
    )

    print("\nAFTER:")
    print(f"  {AFTER_IMAGE}")
    print(
        f"  Size: {after_width} x {after_height}"
    )

    if before.shape[:2] != after.shape[:2]:
        raise RuntimeError(
            "BEFORE and AFTER image dimensions do not match."
        )

    print("[OK] Before/after dimensions match")

    # ------------------------------------------------------------
    # Real frozen inference
    # ------------------------------------------------------------

    print("\nRunning frozen damage model inference...")

    result = predict_damage(
        str(BEFORE_IMAGE),
        str(AFTER_IMAGE),
    )

    print("[OK] Damage inference completed")

    # ------------------------------------------------------------
    # Validate authoritative return contract
    #
    # predict_damage() returns:
    #
    #   (
    #       before_image,
    #       after_image,
    #       damage_probability,
    #       damage_mask
    #   )
    # ------------------------------------------------------------

    if not isinstance(result, tuple):
        raise RuntimeError(
            "Unexpected predict_damage() return type: "
            f"{type(result)}"
        )

    if len(result) != 4:
        raise RuntimeError(
            "Unexpected predict_damage() tuple length: "
            f"{len(result)}. Expected 4."
        )

    (
        before_result,
        after_result,
        damage_probability,
        damage_mask,
    ) = result

    # ------------------------------------------------------------
    # Validate returned images
    # ------------------------------------------------------------

    if not isinstance(before_result, np.ndarray):
        raise RuntimeError(
            "Returned BEFORE image is not a numpy array."
        )

    if not isinstance(after_result, np.ndarray):
        raise RuntimeError(
            "Returned AFTER image is not a numpy array."
        )

    if before_result.shape[:2] != before.shape[:2]:
        raise RuntimeError(
            "Returned BEFORE image dimensions do not match input."
        )

    if after_result.shape[:2] != after.shape[:2]:
        raise RuntimeError(
            "Returned AFTER image dimensions do not match input."
        )

    print("[OK] Returned BEFORE image validated")
    print("[OK] Returned AFTER image validated")

    # ------------------------------------------------------------
    # Validate probability map
    # ------------------------------------------------------------

    if not isinstance(
        damage_probability,
        np.ndarray,
    ):
        raise RuntimeError(
            "Damage probability output is not a numpy array."
        )

    if damage_probability.ndim != 2:
        raise RuntimeError(
            "Damage probability map must be 2D. "
            f"Got shape: {damage_probability.shape}"
        )

    if damage_probability.shape != (
        before_height,
        before_width,
    ):
        raise RuntimeError(
            "Damage probability map dimensions do not "
            "match input image dimensions."
        )

    if damage_probability.dtype != np.float32:
        print(
            "[WARNING] Probability map dtype is "
            f"{damage_probability.dtype}, expected float32."
        )

    if not np.isfinite(
        damage_probability
    ).all():
        raise RuntimeError(
            "Damage probability map contains NaN or infinity."
        )

    probability_min = float(
        damage_probability.min()
    )

    probability_max = float(
        damage_probability.max()
    )

    probability_mean = float(
        damage_probability.mean()
    )

    print("[OK] Damage probability map validated")

    print("\nDamage probability:")
    print(
        f"  Min  : {probability_min:.6f}"
    )
    print(
        f"  Max  : {probability_max:.6f}"
    )
    print(
        f"  Mean : {probability_mean:.6f}"
    )

    # Probability values should be in [0, 1].
    if probability_min < 0.0 or probability_max > 1.0:

        raise RuntimeError(
            "Damage probability values fall outside [0, 1]."
        )

    # ------------------------------------------------------------
    # Validate binary damage mask
    # ------------------------------------------------------------

    if not isinstance(
        damage_mask,
        np.ndarray,
    ):
        raise RuntimeError(
            "Damage mask is not a numpy array."
        )

    if damage_mask.ndim != 2:
        raise RuntimeError(
            "Damage mask must be 2D. "
            f"Got shape: {damage_mask.shape}"
        )

    if damage_mask.shape != (
        before_height,
        before_width,
    ):
        raise RuntimeError(
            "Damage mask dimensions do not match input image."
        )

    if damage_mask.size == 0:
        raise RuntimeError(
            "Damage mask is empty."
        )

    unique_values = np.unique(
        damage_mask
    )

    print("[OK] Damage mask validated")

    print("\nDamage mask:")
    print(
        f"  Shape : {damage_mask.shape}"
    )
    print(
        f"  Dtype : {damage_mask.dtype}"
    )
    print(
        f"  Unique values: {unique_values}"
    )

    # The inference implementation produces a binary uint8 mask.
    if not np.all(
        np.isin(
            unique_values,
            [0, 1, 255],
        )
    ):
        raise RuntimeError(
            "Unexpected values found in damage mask: "
            f"{unique_values}"
        )

    # ------------------------------------------------------------
    # Calculate actual predicted damage area
    # ------------------------------------------------------------

    # Support either 0/1 or 0/255 binary mask representation.
    binary_mask = damage_mask > 0

    damage_pixels = int(
        np.count_nonzero(binary_mask)
    )

    total_pixels = int(
        binary_mask.size
    )

    damage_ratio = (
        damage_pixels / total_pixels
        if total_pixels
        else 0.0
    )

    damage_percentage = (
        damage_ratio * 100.0
    )

    print("\nPredicted damage area:")
    print(
        f"  Damage pixels : {damage_pixels}"
    )
    print(
        f"  Total pixels  : {total_pixels}"
    )
    print(
        f"  Damage ratio  : {damage_ratio:.6f}"
    )
    print(
        f"  Damage area   : {damage_percentage:.4f}%"
    )

    # ------------------------------------------------------------
    # Cross-check probability → mask relationship
    # ------------------------------------------------------------

    expected_mask = (
        damage_probability >= 0.50
    )

    predicted_mask = (
        damage_mask > 0
    )

    agreement = float(
        np.mean(
            expected_mask == predicted_mask
        )
    )

    print("\nThreshold consistency:")
    print(
        f"  Threshold : 0.50"
    )
    print(
        f"  Agreement : {agreement:.4%}"
    )

    if agreement < 0.999:
        raise RuntimeError(
            "Damage mask is not consistent with the "
            "frozen 0.50 threshold."
        )

    print(
        "[OK] Damage mask agrees with probability "
        "threshold"
    )

    # ------------------------------------------------------------
    # Final report
    # ------------------------------------------------------------

    print("\n" + "=" * 72)
    print("DAMAGE DETECTOR REAL INFERENCE TEST PASSED")
    print("=" * 72)

    print("\nVerified:")

    print(
        "  [OK] Real xBD validation BEFORE image"
    )

    print(
        "  [OK] Real xBD validation AFTER image"
    )

    print(
        "  [OK] Matching input dimensions"
    )

    print(
        "  [OK] Frozen Siamese ResNet18 inference"
    )

    print(
        "  [OK] Four-element inference contract"
    )

    print(
        "  [OK] Returned BEFORE/AFTER images"
    )

    print(
        "  [OK] Damage probability map"
    )

    print(
        "  [OK] Probability values in [0, 1]"
    )

    print(
        "  [OK] Binary damage mask"
    )

    print(
        "  [OK] 0.50 damage threshold"
    )

    print(
        "  [OK] Damage-area calculation"
    )

    print(
        "  [OK] Probability/mask consistency"
    )

    print("\nNo training was performed.")
    print("No model files were modified.")


if __name__ == "__main__":
    main()