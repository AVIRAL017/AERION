# AERION — Dataset Management Policy & Registry

**Document Version**: 1.0.0  
**Phase**: Phase 5 — Real Application Integration + Repository Organization  
**Authority**: AERION Engineering Core  

---

## 1. Absolute Dataset Rules

1. **Zero Git Tracking for Large Datasets**: Raw computer vision datasets (VisDrone, SeaDronesSee, UAVDT, DOTA, xBD), large GeoTIFF satellite scenes, OSM PBF road extracts, and multi-megabyte shapefile archives MUST NOT be committed to Git.
2. **Metadata & Provenance Preservation**: For every dataset present in local storage or required by the runtime, the repository tracks:
   - Official Dataset Name
   - Source Organization & Origin URL
   - Download Date & Version
   - Spatial Reference System (CRS) where applicable
   - File Sizes and Cryptographic SHA-256 Checksums
   - License & Terms of Use
3. **Deterministic Preprocessing**: Datasets requiring normalization, bounding box translation, or change detection pair generation must have auditable, deterministic scripts in the repository (`scripts/` or root pipeline scripts).
4. **Zero Fabrication Policy**: If a dataset is missing locally, operational intelligence outputs must explicitly state `UNAVAILABLE` or `INSUFFICIENT EVIDENCE`. Never fabricate operational, geospatial, or sensor data.

---

## 2. Geospatial Datasets Inventory

| Dataset | Source Agency | Local Location | Size | CRS | SHA-256 Checksum |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **India State Boundaries (NWIC)** | National Water Informatics Centre / Survey of India | `dataset/india boundries/state_nwic_geojson/state_NWIC.GeoJSON` | 49.7 MB | EPSG:7755 | `2ce4f8884a624f544623c76ea7002d7d12b8c673db9ee6f3ce568f1366cf4010` |
| **India State Boundaries (Shapefile)** | NWIC / Survey of India | `dataset/india boundries/state_nwic_shp/state_NWIC.shp` | 14.8 MB | EPSG:7755 | `8636077f2326889ceb02ae39021f07d37abfa5c731e4d9c8e53d47cd6de557a6` |
| **India District Boundaries (NWIC)** | NWIC / Survey of India | `dataset/india boundries/district_nwic_geojson/district_nwic.GeoJSON` | 168.4 MB | EPSG:7755 | `2b27a478e24d8c51b0655e74ce3f4f880e75c752e4597550d6fc925ed06ac201` |
| **India District Boundaries (Shapefile)**| NWIC / Survey of India | `dataset/india boundries/district_nwic_shp/district_nwic.shp` | 50.1 MB | EPSG:7755 | `01fa4cb2ee4e672402a808efaec5354c3c20e3e6cc57d819c6764016d0158f90` |
| **India Flood Inventory (V3)** | IMD / National Disaster Authorities | `dataset/INDIA_FLOOD_INVENTORY_V3.geojson` | 30.0 MB | EPSG:4326 | `74766a467efdef1ff82fcbf1303ac0a0133d095ef711cbe817f29de373217fae` |
| **OSM India Road Network** | OpenStreetMap / Geofabrik | `dataset/india-260907.osm.pbf` | 1.71 GB | EPSG:4326 | `326ee224cd4b2783ee7b4acfeaf738b107f2a75873d2f091b423262bdd6891cd` |

---

## 3. Computer Vision & Machine Learning Datasets

### 3.1 VisDrone-DET
- **Source**: Tianjin University Lab of Machine Learning and Data Mining
- **Purpose**: Aerial drone object detection training and validation for land vehicles and persons.
- **Classes Mapped**: 6 classes (`pedestrian`, `people`, `bicycle`, `car`, `van`, `truck`, `tricycle`, `awning-tricycle`, `bus`, `motor`).
- **Production Weights**: `runs/detect/visdrone_8s_1280_30ep/weights/best.pt` (FROZEN).

### 3.2 SeaDronesSee
- **Source**: University of Rostock / Fraunhofer IOSB
- **Purpose**: Maritime search and rescue, boat, swimmer, and life buoy detection.
- **Usage**: Combined with VisDrone to produce the 10-class `unified_drone_20ep` model.

### 3.3 DOTA v1.5
- **Source**: Wuhan University / CAPE
- **Purpose**: Oriented Bounding Box (OBB) satellite aerial detection across 16 categories.
- **Production Weights**: `runs/obb/train-6/weights/best.pt` (FROZEN).

### 3.4 xBD (xView2)
- **Source**: Defense Innovation Unit (DIU) / Carnegie Mellon University
- **Purpose**: Bi-temporal disaster damage classification from optical satellite pairs across earthquake, flood, wildfire, and cyclone disaster events.
- **Production Weights**: `change_detection_runs_v2/best_model.pth` (FROZEN).

---

## 4. Expected Directory Organization

```text
data/
├── raw/                      # Unmodified downloads (excluded from git via .gitignore)
├── processed/                # Preprocessed tiles and normalized label manifests
├── geospatial/
│   ├── administrative/
│   │   ├── state/            # State boundary metadata and vector layers
│   │   └── district/         # District boundary metadata and vector layers
│   ├── international_boundary/
│   │   └── survey_of_india/  # Official Survey of India international boundary demarcations
│   ├── hazards/
│   │   └── flood/            # Flood inventory polygons and active hazard boundaries
│   └── roads/
│       └── osm/              # Road network topology protocols and extracts
└── README.md                 # This dataset policy document
```
