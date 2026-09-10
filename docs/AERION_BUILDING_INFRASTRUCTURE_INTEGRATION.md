# AERION v1 — Building Footprints & Critical Infrastructure Integration (Step 20)

## 1. Overview & Objectives

Step 20 integrates static building footprints and critical infrastructure facilities into AERION's PostGIS geospatial database layer, establishing foundations for:
1. **Building footprint exposure** (`building_footprints`) — geographic polygons of structural assets.
2. **Critical infrastructure facilities** (`critical_infrastructure`) — hospitals, fire stations, police stations, schools, emergency facilities, power and water lifelines.
3. **Spatial queries & incident overlap** — proximity radius search, incident polygon intersection, and nearest facility metrics.
4. **Administrative boundary enrichment** — spatial joins with Step 17 `administrative_boundaries` to tag facilities with ADM1 state and ADM2 district codes.

---

## 2. Strict Semantic Rules & Invariants

> [!IMPORTANT]
> **1. BUILDING FOOTPRINTS DO NOT IMPLY OCCUPANCY, DAMAGE, OR SAFETY**  
> A building footprint represents an externally sourced geometric boundary of a physical structure. It does **not** establish occupancy, structural soundness, safety, or damage.
>
> All newly ingested buildings strictly default to:
> `damage_status = 'NOT_ASSESSED'`
>
> **2. CRITICAL INFRASTRUCTURE DOES NOT IMPLY LIVE OPERATIONAL STATUS**  
> An externally sourced infrastructure record represents the recorded existence of a facility. It does **not** establish that the facility is currently operational, staffed, structurally sound, or accessible for evacuation.
>
> All newly ingested infrastructure records strictly default to:
> `operational_status = 'UNKNOWN'`
>
> **3. HISTORICAL HAZARD OVERLAP != CURRENT DAMAGE**  
> Spatial intersection with historical flood inventory (Step 17) is an analytical reference indicator and must **never** be labeled as "current inundation" or "damaged building".

---

## 3. Dataset Registry & Cryptographic Provenance

Reusing the Step 17 `geospatial_datasets` provenance contract registry:

| Dataset ID | Name | Source & License | Scope & Bounding Box | Geometry | Records | SHA-256 Checksum |
|---|---|---|---|---|---|---|
| `OSM_DELHI_CENTRAL_BUILDINGS_V1` | OpenStreetMap Central Delhi Building Footprints (Sample) | OpenStreetMap contributors, Open Database License (ODbL) 1.0 | Central Delhi / Connaught Place `[28.625, 77.213, 28.636, 77.225]` | `POLYGON` (EPSG:4326) | 321 | `bd94b4ed331ba35ecb1d5ed3a1c8523de0bebb9118e3ee7c37212587c4326280` |
| `OSM_DELHI_CENTRAL_INFRASTRUCTURE_V1` | OpenStreetMap Central Delhi Critical Infrastructure (Sample) | OpenStreetMap contributors, Open Database License (ODbL) 1.0 | Central Delhi Bounded `[28.615, 77.195, 28.645, 77.240]` | `GEOMETRY` (EPSG:4326) | 81 | `0d4fb7a3326d7e54df0e941afa9176800bc30f09356c1ef4a006883dd7d799ec` |

---

## 4. Database Schema & PostGIS Storage Architecture

Migration: `8b9c0d1e2f3a_create_buildings_and_infrastructure_tables.py`

### Table: `building_footprints`
- `id` (UUID PK, default `gen_random_uuid()`)
- `dataset_id` (UUID FK -> `geospatial_datasets.id`, ondelete `CASCADE`)
- `source_record_id` (VARCHAR(100), indexed, preserves original OSM ID e.g. `OSM_WAY_123`)
- `building_type` (VARCHAR(100), default `'GENERAL'`)
- `damage_status` (VARCHAR(50), default `'NOT_ASSESSED'`)
- `area_m2` (NUMERIC(12, 2), derived geodesic area)
- `area_provenance` (VARCHAR(50), default `'DERIVED'`)
- `height` (FLOAT, nullable)
- `levels` (INTEGER, nullable)
- `address` (TEXT, nullable)
- `source_url` (VARCHAR(1024), nullable)
- `geom_4326` (`GEOMETRY(GEOMETRY, 4326)`, GIST spatial index)
- `metadata_json` (JSONB, preserves full OSM tags)
- `created_at`, `updated_at` (TIMESTAMPTZ)

### Table: `critical_infrastructure`
- `id` (UUID PK, default `gen_random_uuid()`)
- `dataset_id` (UUID FK -> `geospatial_datasets.id`, ondelete `CASCADE`)
- `source_record_id` (VARCHAR(100), indexed, preserves original OSM ID e.g. `OSM_NODE_123`)
- `name` (VARCHAR(255), facility title)
- `infrastructure_type` (VARCHAR(100), `'HOSPITAL'`, `'FIRE_STATION'`, `'POLICE_STATION'`, `'SCHOOL'`, `'EMERGENCY_FACILITY'`, `'OTHER'`)
- `subtype` (VARCHAR(100), e.g. `'clinic'`, `'college'`)
- `operational_status` (VARCHAR(50), strictly `'UNKNOWN'`)
- `address` (TEXT, nullable)
- `state_code` (VARCHAR(50), enriched via ADM1 spatial join)
- `district_code` (VARCHAR(50), enriched via ADM2 spatial join)
- `source_url` (VARCHAR(1024), nullable)
- `geom_4326` (`GEOMETRY(GEOMETRY, 4326)`, GIST spatial index)
- `metadata_json` (JSONB, preserves full OSM tags)
- `created_at`, `updated_at` (TIMESTAMPTZ)

---

## 5. REST API Endpoints

### Buildings:
1. `GET /api/v1/geospatial/buildings?latitude={lat}&longitude={lon}&radius_km={radius}&limit={limit}`
   - Computes spheroidal geodesic distance via `ST_Distance(geom::geography, pt::geography) / 1000.0`
   - Bounded by `ST_DWithin` on geography.
2. `GET /api/v1/geospatial/buildings/{building_id}`
   - Returns individual footprint with GeoJSON geometry and calculated dimensions.
3. `POST /api/v1/geospatial/buildings/intersect`
   - Computes `ST_Intersects(geom_4326, ST_GeomFromGeoJSON(:polygon))` to discover structures within hazard or incident zones.

### Critical Infrastructure:
1. `GET /api/v1/geospatial/infrastructure?latitude={lat}&longitude={lon}&radius_km={radius}&infrastructure_type={type}&state_code={state}&district_code={district}&limit={limit}`
   - Finds facilities near coordinates with geodesic distance.
   - Enriches state and district names.
2. `GET /api/v1/geospatial/infrastructure/{infrastructure_id}`
   - Returns individual facility with GeoJSON geometry and metadata.

---

## 6. Resource Control & Boundary Verification

- Data acquisition was strictly bounded to a compact central urban sample (321 buildings, 81 facilities, < 500 KB total file storage).
- National-scale bulk ingestion was avoided to preserve database and compute resources.
- Zero external API keys (no Mapbox, no OpenRouteService, no live routing, no live weather).
- ML models remain strictly frozen.
