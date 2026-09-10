# AERION — Geospatial Architecture & Data Integration (Step 17)

**Document Version**: 1.0.0  
**Phase**: Step 17 — Geospatial Data Integration (STATIC DATA INTEGRATION)  
**Authority**: AERION System Engineering Core  

---

## 1. Overview & Objective

Step 17 establishes an authoritative, provenance-aware geospatial data layer in PostGIS for the AERION intelligence platform. This foundation provides deterministic context for:
1. **Administrative boundary context** (India ADM0 country, ADM1 state/UT, ADM2 district containment queries).
2. **Disaster hazard context** (India Flood Inventory v3 reference hazard polygons).
3. **Border/geofence context** (operational international boundary contracts).
4. **Map visualization & future routing/shelter intelligence** (layers ready for downstream consumption).

---

## 2. Core Invariants & Semantic Distinctions

### 2.1 Coordinate Separation Invariant
> [!IMPORTANT]
> **PIXEL COORDINATES != GEOGRAPHIC COORDINATES.**  
> Ungeoreferenced imagery cannot produce verified geographic coordinates. If source imagery does not contain verified telemetry or EXIF tags, spatial geometry remains unavailable (`is_georeferenced = False`, coordinates in native pixel space).

### 2.2 Historical Hazard vs. Live Status Invariant
> [!CAUTION]
> **Historical flood inventory is reference evidence and must NOT be interpreted as live flood status.**  
> The India Flood Inventory v3 dataset (1967–2023) records past hazard events. Every feature is strictly tagged with `is_live_status = False` and `hazard_type = 'HISTORICAL_FLOOD'`. It must never be labeled as active inundation or a live emergency.

### 2.3 International Border Contract Invariant
> [!WARNING]
> Administrative boundaries (ADM1/ADM2) MUST NOT be substituted as authoritative operational borders for Border Security Mode. If an authoritative international border dataset (Survey of India official boundary) is not present, AERION explicitly reports `operational_border_available = False` rather than guessing or fabricating border demarcations.

### 2.4 Zero External API Keys Invariant
Step 17 is **STATIC DATA INTEGRATION ONLY**. No API keys (Mapbox, OpenRouteService, Weather API, Mistral AI) are introduced. Live routing, live geocoding, live weather, and building footprint extraction (reserved for Step 20) are excluded.

---

## 3. Integrated Datasets & Cryptographic Provenance

| Dataset Identifier | Dataset Name | Source Agency | Version | Source CRS | Target PostGIS CRS | Features Ingested | Cryptographic SHA-256 Checksum |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `NWIC_INDIA_STATE_BOUNDARY_V1` | India State Boundaries (NWIC) | National Water Informatics Centre / Survey of India | v1.0 | EPSG:7755 | EPSG:4326 | 36 States & UTs (ADM1) | `2ce4f8884a624f544623c76ea7002d7d12b8c673db9ee6f3ce568f1366cf4010` |
| `NWIC_INDIA_DISTRICT_BOUNDARY_V1` | India District Boundaries (NWIC) | National Water Informatics Centre / Survey of India | v1.0 | EPSG:7755 | EPSG:4326 | 733 Districts (ADM2) | `2b27a478e24d8c51b0655e74ce3f4f880e75c752e4597550d6fc925ed06ac201` |
| `INDIA_FLOOD_INVENTORY_V3` | India Flood Inventory | HydroSense Lab, IIT Delhi / IMD | v3.0 | EPSG:4326 | EPSG:4326 | 1006 Historical Events | `74766a467efdef1ff82fcbf1303ac0a0133d095ef711cbe817f29de373217fae` |
| `OSM_INDIA_ROAD_NETWORK_REGISTERED` | OSM India Road Extract | OpenStreetMap / Geofabrik | 260907 | EPSG:4326 | Contract Registered | Provenance Only (1.71 GB PBF) | `326ee224cd4b2783ee7b4acfeaf738b107f2a75873d2f091b423262bdd6891cd` |

---

## 4. PostGIS Storage Architecture

Three primary relational and spatial entities were added to the PostGIS schema in migration `49b71f92e401`:

```
┌───────────────────────────────────────┐
│          geospatial_datasets          │
├───────────────────────────────────────┤
│ id (UUID, PK)                         │
│ dataset_id (VARCHAR(100), UNIQUE)     │
│ dataset_name, source_name, source_url │
│ version, license, attribution         │
│ geographic_scope, geometry_type       │
│ crs, source_format, checksum (SHA-256)│
│ status, notes, metadata_json (JSONB)  │
└──────────────────┬────────────────────┘
                   │ 1:N
         ┌─────────┴───────────────────────────────┐
         ▼                                         ▼
┌─────────────────────────────────────────┐  ┌─────────────────────────────────────────┐
│        administrative_boundaries        │  │        historical_hazard_records        │
├─────────────────────────────────────────┤  ├─────────────────────────────────────────┤
│ id (UUID, PK)                           │  │ id (UUID, PK)                           │
│ dataset_id (UUID, FK)                   │  │ dataset_id (UUID, FK)                   │
│ level ('ADM0', 'ADM1', 'ADM2')          │  │ hazard_type ('HISTORICAL_FLOOD')       │
│ country_code ('IND'), state_code        │  │ source_event_id (VARCHAR(100))          │
│ district_code (VARCHAR(50))             │  │ event_date_start, event_date_end        │
│ name, name_canonical (VARCHAR(255))     │  │ state_name, district_name, cause        │
│ source_id (VARCHAR(100))                │  │ severity_reported, impact_summary       │
│ geom_4326 (MULTIPOLYGON, SRID=4326,GiST)│  │ is_live_status (BOOLEAN, ALWAYS FALSE)  │
│ metadata_json (JSONB)                   │  │ geom_4326 (GEOMETRY, SRID=4326, GiST)   │
└─────────────────────────────────────────┘  └─────────────────────────────────────────┘
```

---

## 5. Ingestion Engine & Coordinate Normalization

1. **Projection Handling**: State and District boundaries from NWIC / Survey of India are natively projected in `EPSG:7755` (India National Coordinate System, meters). Ingestion uses PostGIS `ST_Transform(ST_SetSRID(..., 7755), 4326)` to guarantee exact, lossless projection into WGS84 decimal degrees.
2. **Deterministic Deduplication**: Ingestion verifies the SHA-256 cryptographic hash of the input file before processing. If a dataset matching `dataset_id` has already been loaded, ingestion is skipped.
3. **Memory Bounding**: Large vector collections are chunked into 50-feature batches to minimize memory overhead.

---

## 6. Query Services & REST API Contracts

### 6.1 Endpoints Implemented

#### `GET /api/v1/geospatial/datasets`
Returns provenance contracts and cryptographic checksums for all indexed datasets.

#### `GET /api/v1/geospatial/admin/resolve?latitude={lat}&longitude={lon}`
Executes a PostGIS `ST_Contains` spatial query. Returns:
```json
{
  "available": true,
  "query_coordinates": { "latitude": 28.6139, "longitude": 77.2090 },
  "country": { "level": "ADM0", "name": "India", "code": "IND" },
  "state": { "level": "ADM1", "name": "Delhi", "code": "07" },
  "district": { "level": "ADM2", "name": "New Delhi", "code": "079" },
  "evidence": {
    "source_type": "GEOSPATIAL_REGISTRY",
    "modality": "DERIVED",
    "confidence": 1.0,
    "verification_state": "CALCULATED"
  }
}
```

#### `GET /api/v1/geospatial/hazards/history?latitude={lat}&longitude={lon}&radius_km={radius}`
Executes a PostGIS `ST_DWithin` geography query. Returns:
```json
{
  "is_historical_reference_only": true,
  "record_count": 2,
  "disclaimer": "Historical flood inventory is reference evidence and must not be interpreted as live flood status.",
  "records": [ ... ],
  "evidence": {
    "source_type": "HISTORICAL_HAZARD_INVENTORY",
    "modality": "EXTERNALLY_PROVIDED",
    "confidence": 1.0
  }
}
```

#### `GET /api/v1/geospatial/border/status`
Reports operational border status:
```json
{
  "operational_border_available": false,
  "authoritative_source_name": "Survey of India (SOI) / Ministry of External Affairs",
  "status_message": "Authoritative international border vector geometry is UNAVAILABLE in local registry.",
  "notes": "Administrative boundaries (ADM1/ADM2) MUST NOT be substituted as authoritative operational borders for Border Security Mode."
}
```

---

## 7. Operational Limitations & Future Roadmap

1. **Road Network Routing**: The 1.71 GB OSM extract (`india-260907.osm.pbf`) is registered in provenance records. In Step 17, it is intentionally NOT parsed into pgRouting tables to preserve compute resources. Routing engines will be integrated in subsequent roadmap phases.
2. **Building Footprints**: No building polygon dataset was ingested; building and floor plans are strictly reserved for Step 20.
3. **Authoritative Border**: Operational geofencing currently relies on user-defined geofences in pixel coordinates or georeferenced operational zones until the official Survey of India international boundary layer is provided.
