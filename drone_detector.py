"""
AERION v1 — Drone Detection Runtime Adapter

Purpose
-------
Stable inference interface around the frozen AERION v1 drone models.

Frozen models:
    1. VisDrone-only YOLOv8s
    2. Unified VisDrone + SeaDronesSee YOLOv8s

This module performs inference only.

It does NOT:
    - train models
    - modify model weights
    - create synthetic detections
    - fabricate confidence values
    - fabricate object counts
    - perform tracking
    - perform border intelligence

Tracking and border intelligence remain separate AERION subsystems.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ultralytics import YOLO


# ================================================================
# FROZEN MODEL PATHS
# ================================================================

MODEL_PATHS = {
    "visdrone_only": Path(
        r"D:\mp-1\runs\detect\visdrone_8s_1280_30ep\weights\best.pt"
    ),
    "unified": Path(
        r"D:\mp-1\runs\detect\unified_drone_20ep\weights\best.pt"
    ),
}


# ================================================================
# MODEL CONFIGURATION
# ================================================================

MODEL_CONFIG = {
    "visdrone_only": {
        "input_size": 1280,
        "classes": [
            "person",
            "light_vehicle",
            "bus",
            "truck",
            "motorbike",
            "other_transport",
        ],
    },

    "unified": {
        "input_size": 1280,
        "classes": [
            "person",
            "light_vehicle",
            "bus",
            "truck",
            "motorbike",
            "other_transport",
            "boat",
            "jetski",
            "life_saving_appliance",
            "buoy",
        ],
    },
}


# ================================================================
# RESULT TYPES
# ================================================================

@dataclass
class DroneDetection:
    """
    One detector output.

    bbox format:
        [x1, y1, x2, y2]

    Coordinates are pixel coordinates in the original image.
    """

    class_id: int
    class_name: str
    confidence: float
    bbox: List[float]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DroneDetectionResult:
    """
    Complete result for one image/frame.
    """

    model: str
    image_width: int
    image_height: int
    detections: List[DroneDetection]
    detection_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model": self.model,
            "image_width": self.image_width,
            "image_height": self.image_height,
            "detections": [
                detection.to_dict()
                for detection in self.detections
            ],
            "detection_count": self.detection_count,
        }


# ================================================================
# DETECTOR
# ================================================================

class DroneDetector:
    """
    AERION v1 drone inference adapter.

    Parameters
    ----------
    model_name:
        "visdrone_only" or "unified"

    device:
        Ultralytics device argument.
        Examples:
            0
            "cpu"
            "cuda:0"

    confidence:
        Minimum inference confidence.

    iou:
        NMS IoU threshold.

    imgsz:
        Inference image size.

        Defaults to the frozen model's validated 1280 input size.

    agnostic_nms:
        Whether to use class-agnostic NMS.

        AERION's validated border pipeline used agnostic NMS
        to reduce cross-class duplicate detections.
    """

    SUPPORTED_MODELS = frozenset(MODEL_PATHS.keys())

    def __init__(
        self,
        model_name: str = "visdrone_only",
        device: Union[int, str] = 0,
        confidence: float = 0.25,
        iou: float = 0.50,
        imgsz: Optional[int] = None,
        agnostic_nms: bool = True,
    ) -> None:

        if model_name not in self.SUPPORTED_MODELS:
            raise ValueError(
                f"Unsupported drone model '{model_name}'. "
                f"Supported models: {sorted(self.SUPPORTED_MODELS)}"
            )

        if not 0.0 <= confidence <= 1.0:
            raise ValueError(
                "confidence must be between 0.0 and 1.0"
            )

        if not 0.0 <= iou <= 1.0:
            raise ValueError(
                "iou must be between 0.0 and 1.0"
            )

        model_path = MODEL_PATHS[model_name]

        if not model_path.exists():
            raise FileNotFoundError(
                f"Frozen drone model not found:\n{model_path}"
            )

        self.model_name = model_name
        self.model_path = model_path
        self.device = device
        self.confidence = confidence
        self.iou = iou
        self.imgsz = imgsz or MODEL_CONFIG[model_name]["input_size"]
        self.agnostic_nms = agnostic_nms

        # Load the frozen model.
        #
        # YOLO() loads the weights for inference.
        # No training or saving operation occurs here.
        self.model = YOLO(str(self.model_path))

        self.class_names = MODEL_CONFIG[
            model_name
        ]["classes"]

    # ============================================================
    # IMAGE DETECTION
    # ============================================================

    def detect(
        self,
        image: Union[str, Path, Any],
    ) -> DroneDetectionResult:
        """
        Run detection on one image/frame.

        Parameters
        ----------
        image:
            Image path, numpy array, PIL image, or another
            Ultralytics-compatible image source.

        Returns
        -------
        DroneDetectionResult
        """

        results = self.model.predict(
            source=image,
            imgsz=self.imgsz,
            conf=self.confidence,
            iou=self.iou,
            device=self.device,
            agnostic_nms=self.agnostic_nms,
            verbose=False,
        )

        if not results:
            return DroneDetectionResult(
                model=self.model_name,
                image_width=0,
                image_height=0,
                detections=[],
                detection_count=0,
            )

        result = results[0]

        image_width = 0
        image_height = 0

        if result.orig_shape is not None:
            image_height = int(result.orig_shape[0])
            image_width = int(result.orig_shape[1])

        detections: List[DroneDetection] = []

        if result.boxes is not None:
            boxes = result.boxes

            for index in range(len(boxes)):

                class_id = int(
                    boxes.cls[index].item()
                )

                confidence = float(
                    boxes.conf[index].item()
                )

                bbox = [
                    float(value)
                    for value in boxes.xyxy[index]
                    .detach()
                    .cpu()
                    .tolist()
                ]

                class_name = self._get_class_name(
                    class_id
                )

                detections.append(
                    DroneDetection(
                        class_id=class_id,
                        class_name=class_name,
                        confidence=confidence,
                        bbox=bbox,
                    )
                )

        return DroneDetectionResult(
            model=self.model_name,
            image_width=image_width,
            image_height=image_height,
            detections=detections,
            detection_count=len(detections),
        )

    # ============================================================
    # CLASS NAME RESOLUTION
    # ============================================================

    def _get_class_name(
        self,
        class_id: int,
    ) -> str:

        if 0 <= class_id < len(self.class_names):
            return self.class_names[class_id]

        # This should never occur with a correctly configured
        # frozen model. Fail explicitly instead of inventing
        # a class name.
        raise RuntimeError(
            f"Model returned unknown class ID {class_id} "
            f"for model '{self.model_name}'."
        )

    # ============================================================
    # MODEL INFORMATION
    # ============================================================

    def info(self) -> Dict[str, Any]:
        """
        Return immutable runtime configuration information.
        """

        return {
            "project": "AERION",
            "version": "v1",
            "subsystem": "drone_detection",
            "model": self.model_name,
            "model_path": str(self.model_path),
            "input_size": self.imgsz,
            "confidence": self.confidence,
            "iou": self.iou,
            "agnostic_nms": self.agnostic_nms,
            "device": str(self.device),
            "classes": list(self.class_names),
            "status": "FROZEN_MODEL_RUNTIME",
        }


# ================================================================
# FACTORY
# ================================================================

def create_drone_detector(
    model_name: str = "visdrone_only",
    **kwargs,
) -> DroneDetector:
    """
    Factory function used by higher-level AERION services.
    """

    return DroneDetector(
        model_name=model_name,
        **kwargs,
    )


# ================================================================
# SELF TEST
# ================================================================

def _self_test() -> None:
    """
    Basic adapter/model loading test.

    This does NOT run inference on synthetic data and does NOT
    modify model files.

    It verifies that both frozen drone models can be loaded and
    expose the expected runtime configuration.
    """

    print("=" * 72)
    print("AERION v1 — DRONE DETECTOR ADAPTER SELF-TEST")
    print("=" * 72)

    for model_name in (
        "visdrone_only",
        "unified",
    ):

        print(f"\nTesting model: {model_name}")

        detector = DroneDetector(
            model_name=model_name,
            device=0,
        )

        info = detector.info()

        print("  [OK] Model file found")
        print("  [OK] Model loaded")
        print(
            f"  [OK] Input size: {info['input_size']}"
        )
        print(
            f"  [OK] Classes: {len(info['classes'])}"
        )
        print(
            f"  [OK] Status: {info['status']}"
        )

    print("\n" + "=" * 72)
    print("DRONE DETECTOR ADAPTER SELF-TEST PASSED")
    print("=" * 72)


if __name__ == "__main__":
    _self_test()