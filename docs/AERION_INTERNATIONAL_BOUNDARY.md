# AERION v1 — Authoritative International Boundary Documentation (Step 19)

## 1. Executive Summary & Regulatory Authority

Under the Indian **National Map Policy (NMP)** and directives of the Ministry of Science and Technology, the **Survey of India (SOI)** is the designated National Mapping Agency and the sole authority empowered to produce, certify, and publish authoritative international boundary demarcations for the Republic of India.

In AERION v1:
> **CORE INVARIANT**:
> Generic administrative boundary datasets (e.g. OpenStreetMap, Natural Earth ADM0, Mapbox Boundaries, Google Maps polygons) **MUST NOT** be substituted for or conflated with authoritative operational international borders.
>
> If official, accredited Survey of India boundary vectors cannot be accessed or licensed without bypassing access controls, the system defaults to:
> `operational_border_available = False`
> and documents the exact legal/credential reasons.

---

## 2. Invariant & Separation of Concerns

### Administrative Boundaries vs. Authoritative Operational Border
* **Administrative Boundaries (`administrative_boundaries`)**: Used for civilian jurisdiction, district-level disaster relief coordination, flood awareness, and administrative partitioning (ADM1: State, ADM2: District).
* **Authoritative International Boundary (`international_boundaries`)**: Represents strictly demarcated international operational boundaries under SOI accreditation. Used in Border Security Mode for proximity analysis and sector alerts.
* **Prohibition of Fallback**: AERION never falls back from missing operational border data to civilian ADM0 country boundary polygons. Doing so would violate cartographic integrity and legal requirements under the Criminal Law Amendment Act.

### Authoritative Border vs. Configured BorderZone
* **Authoritative International Boundary**: Fixed cartographic ground truth certified by the Survey of India.
* **Configured BorderZone (`border_zones`)**: Operational surveillance envelopes, geofences, and alert buffers configured by field commanders and security operators.
* These two concepts are completely decoupled in the schema and query layers:
  - An operator may configure a 5 km buffer zone along a sector.
  - The international boundary remains the invariant cartographic datum against which distances are computed.

---

## 3. Database Schema & PostGIS Architecture

### Table: `international_boundaries`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | Primary Key, default `gen_random_uuid()` | Unique boundary segment identifier |
| `dataset_id` | `UUID` | Foreign Key -> `geospatial_datasets.id`, Indexed | Associated authoritative dataset registry record |
| `source_record_id` | `VARCHAR(128)` | Unique, Nullable | Original record identifier from SOI source file |
| `boundary_type` | `VARCHAR(64)` | Default `'INTERNATIONAL_OPERATIONAL'`, Indexed | Boundary categorization |
| `name` | `VARCHAR(255)` | Not Null | Descriptive sector or boundary name |
| `country_code` | `VARCHAR(8)` | Default `'IND'` | ISO country code |
| `neighbor_country_code` | `VARCHAR(8)` | Nullable | Adjacent country ISO code (e.g., `'PAK'`, `'BGD'`) |
| `disputed_status` | `VARCHAR(64)` | Default `'UNDISPUTED'` | Operational border status |
| `geom_4326` | `GEOMETRY(MultiPolygon, 4326)` | Spatial Index (GIST) | MultiPolygon geometry in WGS-84 / EPSG:4326 |
| `metadata_json` | `JSONB` | Default `{}` | Extensible source metadata & verification attributes |
| `created_at` | `TIMESTAMPTZ` | Default `now()` | Record creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | Default `now()` | Record last update timestamp |

### Geodesic Distance Computation
AERION calculates spatial distance to the operational border using PostGIS spheroidal/geodesic distance:
```sql
SELECT
    ST_Distance(geom_4326::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) / 1000.0 AS distance_km,
    ST_Contains(geom_4326, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)) AS is_within
FROM international_boundaries
ORDER BY distance_km ASC
LIMIT 1;
```
This guarantees accurate metric distances (in kilometers) over the WGS-84 ellipsoid without planar projection distortion.

---

## 4. Ingestion Engine & Contract Enforcement

The `InternationalBoundaryService` provides transactional ingestion:
1. **Provenance Contract Verification**: Ingestion requires a valid `DatasetProvenanceContract` explicitly citing `Survey of India (SOI)` as the provider.
2. **Geometry Validation & MultiPolygon Normalization**: Validates geometry via Shapely and converts Polygon / MultiPolygon into strict `MultiPolygon(SRID=4326)`.
3. **Duplicate Prevention**: Computes SHA-256 geometry hash and checks `source_record_id` to prevent duplicate ingestion.
4. **Acquisition Status Enum**:
   - `NOT_ACQUIRED`: No official dataset loaded (default state).
   - `ACQUIRED`: Vector package acquired from authority.
   - `INGESTED`: Validated and loaded into PostGIS.
   - `INGESTATION_FAILED`: Verification failed during ingestion.

---

## 5. REST API Endpoints

### `GET /api/v1/geospatial/border/status`
Returns the status of the authoritative international boundary dataset:
```json
{
  "operational_border_available": false,
  "acquisition_status": "NOT_ACQUIRED",
  "authoritative_source_name": "Survey of India (SOI)",
  "reason_unavailable": "Survey of India (SOI) authoritative international boundary vector package has not been ingested. Official SOI boundary data requires authorized departmental registration under the National Map Policy.",
  "disclaimer": "CRITICAL NOTICE: Survey of India (SOI) is the designated authority under the National Map Policy. Generic administrative boundaries (ADM0) or third-party polygons are legally and operationally NOT acceptable substitutes for operational border security decision-making."
}
```

### `GET /api/v1/geospatial/border/resolve?latitude=...&longitude=...`
Computes geodesic proximity to the operational international boundary:
- If operational border is unavailable:
  ```json
  {
    "available": false,
    "distance_to_border_km": null,
    "is_within_border": null,
    "disclaimer": "Operational international border dataset is currently unavailable..."
  }
  ```
- If operational border is ingested:
  ```json
  {
    "available": true,
    "distance_to_border_km": 12.45,
    "is_within_border": true,
    "evidence_id": "9f7b1c4e-...",
    "disclaimer": "ANALYTICAL NOTICE: Border proximity is an analytical indicator..."
  }
  ```

---

## 6. Analytical Indicator vs. Infiltration Disclaimer

> **IMPORTANT OPERATIONAL NOTICE**:
> Spatial proximity to the international boundary is an analytical indicator ("Potential Unauthorized Crossing Indicator") calculated from geospatial coordinates. It does **NOT** constitute definitive proof of infiltration or unauthorized crossing. All operational decisions must be corroborated by multi-source intelligence, sensor feeds, and authorized personnel.
