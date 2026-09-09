# AERION — Machine Learning Models & Freeze Specifications

**Status**: FROZEN (PRODUCTION IMMUTABLE)  
**Verification Manifest**: [`test_results/aerion_v1_ml_verification_manifest.json`](../../test_results/aerion_v1_ml_verification_manifest.json)  

---

## 1. Frozen Model Inventory & Cryptographic Hashes

| Model | Subsystem | Architecture | Weights Location | SHA-256 Checksum |
| :--- | :--- | :--- | :--- | :--- |
| **Drone** | Aerial Land Surveillance | YOLOv8s (1280px) | `runs/detect/visdrone_8s_1280_30ep/weights/best.pt` | `343215ac779c1683eef66801b9d0fbf315361074ea71be4356bcb2a40d7a8a2f` |
| **Unified Drone** | Land + Maritime Aerial | YOLOv8s (1280px) | `runs/detect/unified_drone_20ep/weights/best.pt` | `05281a43dc81ab015491fa1a7c821bdd9b9f13b1d78d80b2a0d549cf30a0a630` |
| **Satellite** | Satellite OBB Detection | YOLOv8n-OBB (1024px) | `runs/obb/train-6/weights/best.pt` | `d96c42323b83826db9781981ef34c4c8673ddee9cf84ea0117e473ab040560dd` |
| **Damage** | Bi-Temporal Damage | Siamese ResNet18 + U-Net | `change_detection_runs_v2/best_model.pth` | `0dc2d422693030f5e2446b54e58bda896bc3ecfc05a250e8df78bf2648d61f6b` |

---

## 2. Frozen Operational Thresholds

To prevent false claims or fluctuating detection quality, the runtime thresholds are locked:

- **Confidence Threshold**: `0.25`
- **IoU (Intersection-Over-Union) Threshold**: `0.50`
- **Damage Classification Decision Threshold**: `0.50`

---

## 3. GPU VRAM Budget (6 GB RTX 3050)

- **Lazy Loading**: Models are never instantiated at application startup. They are loaded strictly on first request into their respective operational modes.
- **Inference Mutex (`InferenceLock`)**: An asynchronous lock serializes all heavy PyTorch and Ultralytics GPU operations, preventing CUDA Out-Of-Memory (OOM) failures under concurrent client requests.
