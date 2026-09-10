# AERION v1 — Shelter & Evacuation-Point Data Integration (Step 18)

## 1. Overview
Step 18 integrates authoritative, provenance-tracked emergency shelter and evacuation-point datasets into the AERION platform (Disaster Mode). This capability builds on the static administrative boundaries established in Step 17 to deliver proximity lookups, administrative containment enrichment, and operational status queries for emergency response operators.

---

## 2. Architecture & Design Principles

```
┌────────────────────────────────────────────────────────┐
│               AERION REST Clients / Frontend           │
└───────────────────────────┬────────────────────────────┘
                            │
              HTTP GET /api/v1/geospatial/shelters
              HTTP GET /api/v1/geospatial/shelters/nearby
              HTTP GET /api/v1/geospatial/shelters/{id}
                            │
┌───────────────────────────▼────────────────────────────┐
│         Shelter Service (app/services/shelter_service) │
├────────────────────────────────────────────────────────┤
│ - PostGIS ST_DWithin & ST_Distance (geography geodesic)│
│ - Attribute filtering (status, type, state, district)  │
│ - DERIVED EvidenceRecord emission with SHA-256 link    │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│      Shelter Ingestion (app/services/shelter_ingestion)│
├────────────────────────────────────────────────────────┤
│ - Boundary spatial containment via GeospatialService   │
│ - Validation (-90 <= lat <= 90, -180 <= lon <= 180)    │
│ - Deduplication by source_record_id / generated UUID   │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│           PostgreSQL / PostGIS (Port 5433)             │
├────────────────────────────────────────────────────────┤
│ - shelters table (SPATIAL INDEX ON geom_point_4326)    │
│ - composite indexes: (state_code, district_code), etc. │
│ - geospatial_datasets provenance registry              │
└────────────────────────────────────────────────────────┘
```

### Invariants Maintained:
1. **Single Database Table**: Reuses and extends the existing PostGIS `shelters` table without creating parallel or redundant tables.
2. **Geodesic Distance**: Uses PostGIS geography ST_Distance (`/ 1000.0` for km), never planar Euclidean approximations.
3. **Zero Fabrication**: When capacity, operational status, opening hours, or contact details are omitted in source records, they remain strictly `UNKNOWN` or `NOT_PROVIDED`.
4. **No Safety Scores**: Distance is presented purely as an objective spatial metric (`distance_km`). Fabricating subjective "safety scores" is strictly prohibited.
5. **Operational Disclaimer**: Every query response explicitly includes the mandatory disclaimer:
   > *"Presence of a shelter record does not establish that the shelter is currently operational. Distance is derived from coordinates; it is not a safety score."*
6. **No Routing Fabrication**: Step 18 does not calculate road-network routes or generate fake turn-by-turn navigation.

---

## 3. Data Model & Schema Extension

The `shelters` table in PostGIS was migrated (`58e2a3c4d5f6_extend_shelters_schema.py`) to support:
- `dataset_id` (UUID, nullable, FK to `geospatial_datasets.id`)
- `source_record_id` (VARCHAR(100), nullable, indexed)
- `shelter_type` (VARCHAR(100), default `'UNKNOWN'`, indexed)
- `operational_status` (VARCHAR(50), default `'UNKNOWN'`, indexed)
- `capacity_status` (VARCHAR(50), default `'NOT_PROVIDED'`, nullable=False)
- `capacity_total` (INTEGER, nullable=True)
- `capacity_occupied` (INTEGER, nullable=True)
- `accessibility` (TEXT, nullable=True)
- `contact_information` (VARCHAR(255), nullable=True)
- `opening_hours` (VARCHAR(255), nullable=True)
- `services` (JSONB, default `[]`)
- `address` (TEXT, nullable=True)
- `state_code` (VARCHAR(10), nullable=True, indexed)
- `district_code` (VARCHAR(10), nullable=True, indexed)
- `source_url` (VARCHAR(500), nullable=True)
- `metadata_json` (JSONB, default `{}`)
- `created_at` / `updated_at` (TIMESTAMPTZ)

### Status Enums:
- **OperationalStatus**:
  - `CONFIRMED_OPERATIONAL`: Verified by official managing body.
  - `REPORTED_OPERATIONAL`: Field-reported or third-party reported.
  - `CLOSED`: Known decommissioned or inactive facility.
  - `UNKNOWN`: Default when operational state is unverified.
  - `NOT_PROVIDED`: Source does not track operational status.
- **CapacityStatus**:
  - `VERIFIED`: Audited maximum capacity.
  - `SOURCE_REPORTED`: Unaudited estimate from source record.
  - `UNKNOWN`: Capacity unknown.
  - `NOT_PROVIDED`: Field omitted in source record.

---

## 4. Administrative Boundary Enrichment

During ingestion, the `ShelterIngestionEngine` calls `GeospatialService.resolve_admin_point(lat, lon)` to execute a PostGIS spatial containment query against the Step 17 `administrative_boundaries` table (`ADM1` state and `ADM2` district).
- Shelters located within Indian territory automatically have their `state_code`, `district_code`, `state_name`, and `district_name` populated.
- Points outside coverage (e.g. offshore or beyond surveyed boundaries) preserve `None` without failure or fabrication.

---

## 5. REST API Specifications

All endpoints are mounted under `/api/v1/geospatial/shelters` and require valid Bearer token authentication.

### `GET /api/v1/geospatial/shelters`
Search and filter shelters by attribute and optional spatial coordinates:
- `latitude`, `longitude` (optional float): Coordinates for geodesic distance calculation and sorting.
- `radius_km` (optional float): Proximity radius constraint (`ST_DWithin`).
- `operational_status` (optional str): Filter by operational state.
- `shelter_type` (optional str): Filter by facility type (`CYCLONE_SHELTER`, `RELIEF_CAMP`, etc.).
- `state_code`, `district_code` (optional str): Filter by administrative boundary code.
- `limit` (optional int, default 50): Page limit.

### `GET /api/v1/geospatial/shelters/nearby`
Convenience proximity query:
- `latitude` (required float): Anchor latitude.
- `longitude` (required float): Anchor longitude.
- `radius_km` (optional float, default 25.0): Search radius.
- `limit` (optional int, default 20): Maximum records.

### `GET /api/v1/geospatial/shelters/{shelter_id}`
Returns full verified detail for a specific shelter record or HTTP 404 if not found.

---

## 6. Provenance & Evidence Contracts
- **Dataset Provenance**: Registered in `geospatial_datasets` with dataset ID `AERION_SHELTER_REGISTRY_INDIA_V1`, deterministic SHA-256 checksum, GODL license, and NDMA/SDMA attribution.
- **Query Evidence**: Every spatial search generates an `EvidenceRecord` of modality `DERIVED`, source type `SHELTER_REGISTRY`, verification state `CALCULATED`, and sensor metadata containing query coordinates, search radius, and match counts.

---

## 7. Verification & Test Results
- **Shelter Integration Suite**: `tests/backend/test_shelter_integration.py` (10 tests, OK)
- **Database Schema Suite**: `tests/backend/test_database.py` (6 tests, OK)
- **All Backend Tests**: 158 tests, OK
- **Runtime Inference & OBB Suite**: 26 tests, OK (Real Border Video, Real Damage, Real Drone, Real Satellite OBB all passing)
- **Frontend Production Build**: `npm run build` completed cleanly (0 errors, 48 modules transformed)
- **Frozen Model Weights**: VisDrone (Drone), DOTA (Satellite OBB), xBD (Damage), and Unified Drone hashes verified 100% identical.
