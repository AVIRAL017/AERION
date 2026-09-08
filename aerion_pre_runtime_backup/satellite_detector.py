"""
AERION v1 — Satellite Detection Runtime Adapter

Stable inference interface for the frozen AERION v1
YOLOv8n-OBB satellite model trained on DOTA-v1.5.

This adapter performs inference only.

It does NOT:
    - train models
    - modify model weights
    - fabricate detections
    - fabricate confidence values
    - perform change detection
    - perform damage analysis
    - perform intelligence/RAG
    - perform geographic reasoning

Important:
    Satellite detection uses Oriented Bounding Boxes (OBB).
    The adapter preserves the four OBB corner points rather than
    converting them into ordinary horizontal bounding boxes.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Union

from ultralytics import YOLO


# ================================================================
# FROZEN MODEL
# ================================================================

MODEL_PATH = Path(
    r"D:\mp-1\runs\obb\train-6\weights\best.pt"
)


# ================================================================
# MODEL CONFIGURATION
# ================================================================

INPUT_SIZE = 1024

SATELLITE_CLASSES = [
    "plane",
    "ship",
    "storage_tank",
    "baseball_diamond",
    "tennis_court",
    "basketball_court",
    "ground_track_field",
    "harbor",
    "bridge",
    "large_vehicle",
    "small_vehicle",
    "helicopter",
    "roundabout",
    "soccer_ball_field",
    "swimming_pool",
    "container_crane",
]


# ================================================================
# RESULT TYPES
# ================================================================

@dataclass
class SatelliteDetection:
    """
    One satellite OBB detection.

    obb_points contains four corner points:

        [
            [x1, y1],
            [x2, y2],
            [x3, y3],
            [x4, y4]
        ]

    Coordinates are pixel coordinates in the original image.
    """

    class_id: int
    class_name: str
    confidence: float
    obb_points: List[List[float]]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SatelliteDetectionResult:
    """
    Complete result for one satellite image.
    """

    model: str
    image_width: int
    image_height: int
    detections: List[SatelliteDetection]
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

class SatelliteDetector:
    """
    AERION v1 satellite OBB inference adapter.

    Parameters
    ----------
    device:
        Ultralytics device argument.

    confidence:
        Minimum inference confidence.

    iou:
        NMS IoU threshold.

    imgsz:
        Inference image size.

        Defaults to the selected model's 1024px configuration.
    """

    def __init__(
        self,
        device: Union[int, str] = 0,
        confidence: float = 0.25,
        iou: float = 0.50,
        imgsz: int = INPUT_SIZE,
    ) -> None:

        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Frozen satellite model not found:\n"
                f"{MODEL_PATH}"
            )

        if not 0.0 <= confidence <= 1.0:
            raise ValueError(
                "confidence must be between 0.0 and 1.0"
            )

        if not 0.0 <= iou <= 1.0:
            raise ValueError(
                "iou must be between 0.0 and 1.0"
            )

        if imgsz <= 0:
            raise ValueError(
                "imgsz must be greater than zero"
            )

        self.model_path = MODEL_PATH
        self.device = device
        self.confidence = confidence
        self.iou = iou
        self.imgsz = imgsz

        # Load frozen OBB model for inference only.
        self.model = YOLO(str(self.model_path))

        self.class_names = SATELLITE_CLASSES

    # ============================================================
    # IMAGE DETECTION
    # ============================================================

    def detect(
        self,
        image: Union[str, Path, Any],
    ) -> SatelliteDetectionResult:
        """
        Run OBB detection on one satellite image.

        Parameters
        ----------
        image:
            Image path, numpy array, PIL image, or another
            Ultralytics-compatible image source.

        Returns
        -------
        SatelliteDetectionResult
        """

        results = self.model.predict(
            source=image,
            imgsz=self.imgsz,
            conf=self.confidence,
            iou=self.iou,
            device=self.device,
            verbose=False,
        )

        if not results:
            return SatelliteDetectionResult(
                model="satellite_dota_v15",
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

        detections: List[SatelliteDetection] = []

        # --------------------------------------------------------
        # OBB OUTPUT
        # --------------------------------------------------------

        if result.obb is not None:

            obb = result.obb

            for index in range(len(obb)):

                class_id = int(
                    obb.cls[index].item()
                )

                confidence = float(
                    obb.conf[index].item()
                )

                # Ultralytics OBB provides xyxyxyxy points.
                points = (
                    obb.xyxyxyxy[index]
                    .detach()
                    .cpu()
                    .tolist()
                )

                # Normalize into:
                # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                obb_points = [
                    [
                        float(point[0]),
                        float(point[1]),
                    ]
                    for point in points
                ]

                class_name = self._get_class_name(
                    class_id
                )

                detections.append(
                    SatelliteDetection(
                        class_id=class_id,
                        class_name=class_name,
                        confidence=confidence,
                        obb_points=obb_points,
                    )
                )

        return SatelliteDetectionResult(
            model="satellite_dota_v15",
            image_width=image_width,
            image_height=image_height,
            detections=detections,
            detection_count=len(detections),
        )

    # ============================================================
    # CLASS RESOLUTION
    # ============================================================

    def _get_class_name(
        self,
        class_id: int,
    ) -> str:

        if 0 <= class_id < len(self.class_names):
            return self.class_names[class_id]

        raise RuntimeError(
            f"Model returned unknown satellite class ID "
            f"{class_id}."
        )

    # ============================================================
    # MODEL INFORMATION
    # ============================================================

    def info(self) -> Dict[str, Any]:
        """
        Return runtime configuration information.
        """

        return {
            "project": "AERION",
            "version": "v1",
            "subsystem": "satellite_detection",
            "model": "satellite_dota_v15",
            "model_path": str(self.model_path),
            "architecture": "YOLOv8n-OBB",
            "dataset": "DOTA-v1.5",
            "input_size": self.imgsz,
            "confidence": self.confidence,
            "iou": self.iou,
            "device": str(self.device),
            "classes": list(self.class_names),
            "output_type": "oriented_bounding_box",
            "status": "FROZEN_MODEL_RUNTIME",
        }


# ================================================================
# FACTORY
# ================================================================

def create_satellite_detector(
    **kwargs,
) -> SatelliteDetector:
    """
    Factory function for higher-level AERION services.
    """

    return SatelliteDetector(
        **kwargs,
    )


# ================================================================
# SELF TEST
# ================================================================

def _self_test() -> None:
    """
    Basic model-loading and configuration test.

    No inference is performed here.
    No model files are modified.
    """

    print("=" * 72)
    print("AERION v1 — SATELLITE DETECTOR ADAPTER SELF-TEST")
    print("=" * 72)

    print("\nChecking frozen model:")
    print(MODEL_PATH)

    detector = SatelliteDetector(
        device=0,
    )

    info = detector.info()

    print("\n[OK] Model file found")
    print("[OK] Model loaded")
    print(
        f"[OK] Architecture: {info['architecture']}"
    )
    print(
        f"[OK] Dataset: {info['dataset']}"
    )
    print(
        f"[OK] Input size: {info['input_size']}"
    )
    print(
        f"[OK] Classes: {len(info['classes'])}"
    )
    print(
        f"[OK] Output type: {info['output_type']}"
    )
    print(
        f"[OK] Status: {info['status']}"
    )

    print("\n" + "=" * 72)
    print("SATELLITE DETECTOR ADAPTER SELF-TEST PASSED")
    print("=" * 72)

    print("\nNo model files were modified.")
    print("No training was performed.")


if __name__ == "__main__":
    _self_test()
    