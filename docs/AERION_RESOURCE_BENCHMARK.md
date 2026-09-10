# AERION Resource Benchmark & Instance Sizing Report (Steps 29–30)

**Date**: 2026-09-10  
**Phase**: AERION v1 — Batch 3 Engineering Benchmark  
**Status**: Step 29 Complete / Step 30 Complete (Provisional Sizing Decision Documented)

---

## 1. Executive Summary

This engineering benchmark report records empirical measurements of the AERION system running on real frozen model weights and representative assets. No metrics have been fabricated or extrapolated from toy functions.

Key Findings:
- **Baseline Idle RSS**: ~483.0 MiB (FastAPI + PyTorch runtime + DB connection pool).
- **Peak Process RSS under ML Inference**:
  - Drone Detection (VisDrone): **1,236.8 MiB** (delta: +750.95 MiB on initial model load/CUDA context initialization).
  - Satellite OBB (YOLOv8-OBB): **1,338.7 MiB** (delta: +99.0 MiB).
  - Damage Assessment (Siamese ConvNet): **1,452.7 MiB** (delta: +114.0 MiB).
  - Bounded 4K Drone Video Processing (20 sampled frames, stride 5): **1,527.8 MiB** peak RSS.
- **Video Throughput**: 3.41 processing FPS on 4K source (Source: 24.0 FPS). Processing FPS is **not real-time**; it is batched/asynchronous.
- **Instance Sizing Decision**: **`c7i-flex.large`** (2 vCPU, 4 GiB RAM, x86_64) is selected as the **Cheapest Viable Production Candidate**. 2 GiB instances (`t3.small` and `t4g.small`) present severe Out-Of-Memory (OOM) risks under combined OS + PostgreSQL/PostGIS + AERION worker loads (~1.5–1.8 GiB RSS), leaving less than 200–400 MiB headroom.

---

## 2. Test Environment & System Specifications

| Component | Value / Specification |
| :--- | :--- |
| **Operating System** | Windows 11 Pro (10.0.26200-SP0) |
| **Processor** | Intel Core (12 logical cores, 8 physical cores) |
| **Total Host Memory** | 16,024.5 MiB (16 GiB) |
| **Python Runtime** | Python 3.13.13 (AMD64) |
| **PyTorch Version** | 2.6.0+cu124 |
| **CUDA Available** | True (NVIDIA GeForce RTX 3050 6GB Laptop GPU) |
| **Database Engine** | PostgreSQL 17.2 with PostGIS 3.5.2 (port 5433) |
| **External Providers** | Open-Meteo, OpenRouteService, Mapbox, Mistral AI (`open-mistral-nemo`) |

---

## 3. Frozen Model Integrity Verification

All model hashes were verified before and during benchmark execution:

| Model | Path | Required SHA-256 Hash | Status |
| :--- | :--- | :--- | :--- |
| **Drone (VisDrone)** | `runs/detect/visdrone_8s_1280_30ep/weights/best.pt` | `343215ac779c1683eef66801b9d0fbf315361074ea71be4356bcb2a40d7a8a2f` | **MATCH** |
| **Satellite (OBB)** | `runs/obb/train-6/weights/best.pt` | `d96c42323b83826db9781981ef34c4c8673ddee9cf84ea0117e473ab040560dd` | **MATCH** |
| **Damage (Siamese)** | `change_detection_runs_v2/best_model.pth` | `0dc2d422693030f5e2446b54e58bda896bc3ecfc05a250e8df78bf2648d61f6b` | **MATCH** |
| **Unified Drone** | `runs/detect/unified_drone_20ep/weights/best.pt` | `05281a43dc81ab015491fa1a7c821bdd9b9f13b1d78d80b2a0d549cf30a0a630` | **MATCH** |

---

## 4. Empirical Benchmark Measurements

### 4.1 Process Baseline & Storage Overhead

| State | Process RSS | System RAM Available | Notes |
| :--- | :--- | :--- | :--- |
| **Process Baseline (Idle)** | 483.01 MiB | 3,688.89 MiB | FastAPI app, config, DB pool initialized |
| **PostgreSQL / PostGIS Ping** | 485.87 MiB | 3,686.00 MiB | Ping latency: 173.52 ms |

### 4.2 ML Model Loading & Single Inference Latency

| Operation | Model Load Time | Inference Latency | Peak Process RSS | RSS Delta |
| :--- | :--- | :--- | :--- | :--- |
| **Drone Detection (VisDrone)** | 0.129 s | 3.324 s (first call) | 1,236.82 MiB | +750.95 MiB (runtime init) |
| **Satellite OBB Detection** | 0.076 s | 0.273 s | 1,338.67 MiB | +99.00 MiB |
| **Damage Siamese ConvNet** | 0.463 s | 0.079 s | 1,452.69 MiB | +114.02 MiB |
| **Sequential Model Switching** | — | 0.367 s (total) | 1,405.29 MiB | -47.40 MiB (GC/cleanup) |

### 4.3 Evidence Artifacts & External Services

| Service / Component | Duration / Latency | Key Metric / Output | Result Status |
| :--- | :--- | :--- | :--- |
| **Annotated Image Generation** | 0.112 s | 835,629 bytes | Artifact generated and hashed |
| **Open-Meteo Weather API** | 1,072.38 ms | Temp: 29.1°C | AVAILABLE |
| **Mistral Intelligence (`open-mistral-nemo`)** | 1,759.76 ms | 283 chars generated | AVAILABLE |

### 4.4 Bounded 4K Video Inference Benchmark

Representative test asset: `data/sample_border_patrol.mp4` (3840x2160, 24.0 source FPS, 725 frames total).
Workload: 20 sampled frames, frame stride = 5.

| Metric | Measured Value | Analysis |
| :--- | :--- | :--- |
| **Source Video Resolution** | 3840 x 2160 (4K UHD) | Bounded real footage |
| **Source Frame Rate** | 24.0 FPS | Camera native |
| **Processed Frames** | 20 frames | Representative bounded stride |
| **Total Wall-Clock Time** | 5.858 s | Decode + VisDrone inference + tracking |
| **Processing Throughput** | **3.41 FPS** | Bounded asynchronous batching |
| **Real-time Status** | **False (Not Real-time)** | Processing FPS (3.41) < Source FPS (24.0) |
| **Peak Process RSS** | 1,527.77 MiB | Video frames + model weights in RAM |

### 4.5 Concurrency Benchmark (Low-Volume 1 vs 2 Requests)

| Concurrency Level | Total Latency | Peak Process RSS | Concurrency Behavior |
| :--- | :--- | :--- | :--- |
| **1 Request (Single)** | 0.381 s | 1,528.01 MiB | Direct single pipeline execution |
| **2 Requests (Concurrent)** | 0.109 s | 1,528.01 MiB | Serialized through GPU/ML mutex |

*Finding*: Concurrent ML inference requests share the loaded model in memory without duplicating model weight footprint (0.0 MiB RSS delta). However, CPU/GPU execution must remain serialized via runtime locks to prevent resource thrashing.

---

## 5. Candidate Instance Sizing Evaluation (Step 30)

| Criteria | Candidate A: `t4g.small` | Candidate B: `t3.small` | Candidate C: `c7i-flex.large` (Recommended) | Candidate D: `m7i-flex.large` |
| :--- | :--- | :--- | :--- | :--- |
| **Architecture** | ARM64 (Graviton2) | x86_64 | x86_64 | x86_64 |
| **vCPU** | 2 | 2 | 2 | 2 |
| **RAM (GiB)** | 2.0 GiB (2,048 MiB) | 2.0 GiB (2,048 MiB) | 4.0 GiB (4,096 MiB) | 8.0 GiB (8,192 MiB) |
| **Peak Observed RSS** | 1,528 MiB | 1,528 MiB | 1,528 MiB | 1,528 MiB |
| **PostgreSQL+OS Budget** | ~600 MiB | ~600 MiB | ~800 MiB | ~1,200 MiB |
| **Total Memory Required** | ~2,128 MiB | ~2,128 MiB | ~2,328 MiB | ~2,728 MiB |
| **OOM Risk** | **CRITICAL (Exceeds 2 GiB)** | **CRITICAL (Exceeds 2 GiB)** | **LOW (1.7 GiB Headroom)** | **ZERO (5.4 GiB Headroom)** |
| **CPU Credit Exhaustion** | N/A (Burstable) | High risk on sustained video | None (Compute-optimized flex) | None (General-purpose flex) |
| **ARM Dependency Risk** | High (PyTorch/OpenCV ARM wheels) | None | None | None |
| **Provisional Viability** | **NOT VIABLE** | **NOT VIABLE** | **VIABLE (BEST FIT)** | **VIABLE (Overspecified)** |

---

## 6. ARM64 (t4g.small) Compatibility Assessment

| Dependency | ARM64 Status | Evidence & Notes |
| :--- | :--- | :--- |
| **Python (3.11/3.12/3.13)** | VERIFIED | Standard official Python Linux aarch64 binaries available on Ubuntu 24.04 LTS. |
| **PyTorch (torch / torchvision)** | PARTIALLY_VERIFIED | PyTorch provides Linux aarch64 wheels for CPU, but builds frequently have OpenMP/MKL compilation differences and lack pre-built wheel parity for some minor versions. |
| **Ultralytics (YOLOv8)** | PARTIALLY_VERIFIED | Pure Python package, but depends on OpenCV headless and NumPy C-extensions on ARM64. |
| **OpenCV (`opencv-python-headless`)** | PARTIALLY_VERIFIED | `opencv-python-headless` has aarch64 wheels on PyPI, but video encoding/decoding performance on Graviton without hardware acceleration is significantly slower. |
| **NumPy** | VERIFIED | Binary aarch64 wheels available on PyPI. |
| **FastAPI / Uvicorn** | VERIFIED | Pure Python / standard C extensions compile cleanly on ARM64. |
| **PostgreSQL / PostGIS** | VERIFIED | Debian/Ubuntu `postgresql-16-postgis-3` packages exist natively for aarch64. |
| **Overall ARM Compatibility** | **PARTIALLY_VERIFIED** | Not recommended for immediate deployment without dedicated ARM staging verification in Step 31. |

---

## 7. Planning Cost Model (AWS EC2 On-Demand Estimates)

*Note: Pricing figures are planning estimates based on US-East-1 on-demand list pricing and exclude data transfer, EBS storage, and external API consumption.*

| Candidate | Hourly Rate | 30-Day 24/7 Compute | 8h/day (Office Hours) | 4h/day (On-Demand Dev) | Monthly Viability |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`t4g.small` (2 vCPU, 2 GiB)** | ~$0.0168 / hr | ~$12.10 / mo | ~$4.03 / mo | ~$2.02 / mo | Inviable (OOM Risk) |
| **`t3.small` (2 vCPU, 2 GiB)** | ~$0.0208 / hr | ~$14.98 / mo | ~$4.99 / mo | ~$2.50 / mo | Inviable (OOM Risk + CPU Credits) |
| **`c7i-flex.large` (2 vCPU, 4 GiB)** | **~$0.0725 / hr** | **~$52.20 / mo** | **~$17.40 / mo** | **~$8.70 / mo** | **Optimal Budget / Stability Match** |
| **`m7i-flex.large` (2 vCPU, 8 GiB)** | ~$0.1008 / hr | ~$72.58 / mo | ~$24.19 / mo | ~$12.10 / mo | Stable but higher monthly cost |

---

## 8. Provisional Instance Sizing Decision (Step 30)

### Primary Recommendation: `c7i-flex.large`
1. **Memory Safety**: 4 GiB physical RAM provides a safe 1.7 GiB headroom buffer above AERION's peak observed ~2.3 GiB combined memory footprint (AERION app peak RSS 1.53 GiB + PostgreSQL/PostGIS 0.5 GiB + OS 0.3 GiB).
2. **CPU Architecture Compatibility**: x86_64 architecture eliminates all risk of PyTorch/OpenCV aarch64 wheel incompatibilities or compilation failures.
3. **No Burstable Credit Starvation**: Compute-optimized flex instances do not throttle CPU down to a low baseline during intensive video inference tasks (unlike `t3.small`).
4. **Cost-Effective**: Under an 8h/day operational schedule, compute cost is ~$17.40/month, well within development credit budgets.

### What Remains to Be Tested in Step 31:
- Measure actual CPU-only inference execution times on AWS `c7i-flex.large` (since current benchmark utilized local CUDA acceleration).
- Confirm swap space configuration and Linux memory tuning for PostgreSQL on 4 GiB EC2 instances.
