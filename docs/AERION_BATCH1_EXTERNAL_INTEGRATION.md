# AERION v1 — Batch 1 External Integration Documentation
**Steps 21–23: Verified Dataset Expansion & External Geospatial/Weather/Routing/Geocoding Services**

---

## 1. Executive Summary

Batch 1 establishes authoritative hazard data expansion, normalized external provider integrations, resilient in-memory TTL caching, and zero-fabrication guarantees across AERION's core geospatial layers:
1. **Step 21 (Verified Dataset Expansion)**: Acquired and transactionally ingested the authoritative USGS/ANSS ComCat Seismicity dataset ($M \ge 5.0$, 2010–2025) for India and South Asia into PostGIS with full provenance attribution.
2. **Step 22 (External API Layer & Caching Architecture)**: Established an asynchronous, thread-safe `InMemoryTTLCache` (no external Redis dependency) and strict Pydantic v2 normalized schemas (`app/schemas/external.py`) with explicit lifecycle states (`AVAILABLE`, `UNAVAILABLE`, `AUTH_REQUIRED`, `TIMEOUT`, `RATE_LIMITED`, `PROVIDER_ERROR`).
3. **Step 23 (Weather, Routing & Geocoding Services)**:
   - **Weather**: Open-Meteo current, forecast, and historical weather reconstruction with 15-second bounded timeouts and flight suitability classification (`OPTIMAL`, `MARGINAL`, `GROUNDED`).
   - **Routing**: OpenRouteService (primary) with Mapbox Navigation API (fallback). Strictly enforces genuine road network graph topology with step-by-step turn guidance and **zero straight-line route fabrication**.
   - **Geocoding**: Open-Meteo Geocoding API with OpenStreetMap Nominatim reverse geocoding fallback, respecting explicit User-Agent requirements.

---

## 2. Dataset Expansion & PostGIS Ingestion (Step 21)

### 2.1 USGS Seismicity Dataset Details
- **Source**: USGS/ANSS Comprehensive Earthquake Catalog (ComCat) API
- **Endpoint**: `https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson`
- **Geographic Extent**: Latitude $6.0^{\circ}\text{N}$ to $38.0^{\circ}\text{N}$, Longitude $68.0^{\circ}\text{E}$ to $98.0^{\circ}\text{E}$
- **Filter**: Magnitude $M \ge 5.0$, Time window `2010-01-01T00:00:00Z` to `2025-12-31T23:59:59Z`
- **Returned Event Count**: Exactly **802** earthquake events (dynamic count recorded during acquisition)
- **Local Artifact**: `data/geospatial/hazards/seismic/usgs_india_seismic_m5_2010_2025.geojson`
- **File Size**: 933,199 bytes
- **SHA-256 Digest**: `9c926947fd5cc810be77e63235ec435ce80bb4651599f25e8a1d7d28a34c24c6`

### 2.2 Database Schema & Migration
- **Alembic Revision**: `9c0d1e2f3a4b` (`add_hazard_seismic_fields.py`)
- **Table Alterations (`historical_hazard_records`)**:
  - `magnitude`: `Numeric(4, 2)` (indexed: `ix_hist_hazard_magnitude`)
  - `depth_km`: `Float`
  - `event_time`: `DateTime(timezone=True)`
- **Spatial Index**: Existing PostGIS GiST index on `geometry` (SRID 4326) covers all 802 Point features.
- **Dataset Registry**: Provenance recorded in `geospatial_datasets` with ID `USGS_INDIA_SEISMIC_M5_2010_2025`.

---

## 3. In-Memory TTL Cache Architecture (Step 22)

To satisfy the architecture constraint of avoiding Redis or extra infrastructure overhead, `app/core/cache.py` provides `InMemoryTTLCache`:
- **Thread Safety**: Uses `asyncio.Lock()` per cache instance.
- **Eviction Strategy**: Bounded max capacity (default 1000 items) using monotonic FIFO eviction and TTL-based invalidation.
- **Configured TTL Defaults**:
  - Weather: 1800 seconds (30 minutes)
  - Routing: 3600 seconds (1 hour)
  - Geocoding: 86400 seconds (24 hours)
- **Key Normalization**: Deterministic SHA-256 hash or float-rounded string coordinate signatures (`lat:.4f`, `lon:.4f`).

---

## 4. Provider Implementations & Invariants (Step 23)

### 4.1 Weather Integration (`external_weather_service.py`)
- **Provider**: Open-Meteo (`https://api.open-meteo.com/v1/forecast` and `archive-api.open-meteo.com`)
- **Authentication**: Unauthenticated public tier (no API key required).
- **Classification Engine**:
  - `GROUNDED`: Sustained wind $> 15.0\,\text{m/s}$ or precipitation $> 10.0\,\text{mm/hr}$.
  - `MARGINAL`: Sustained wind $> 10.0\,\text{m/s}$ or precipitation $> 2.0\,\text{mm/hr}$.
  - `OPTIMAL`: Calm weather below thresholds.

### 4.2 Routing Integration (`external_routing_service.py`)
- **Primary Provider**: OpenRouteService (`https://api.openrouteservice.org/v2/directions/driving-car/geojson`)
- **Fallback Provider**: Mapbox Navigation API (`https://api.mapbox.com/directions/v5/mapbox/driving`)
- **Zero-Fabrication Invariant**: Under no circumstance will a straight-line Euclidean distance or artificial coordinate line be generated if a provider fails or keys are missing. If both providers fail or are unconfigured, `ProviderStatus.AUTH_REQUIRED` or `ProviderStatus.UNAVAILABLE` is returned with `geometry_geojson=None` and `route_steps=[]`.
- **Credential Safety**: Existing keys `OPENROUTESERVICE_API_KEY` and `MAPBOX_ACCESS_TOKEN` in `.env` are loaded securely via `SecretStr` in `app/core/config.py`. Keys are never logged, printed, or exposed to clients.

### 4.3 Geocoding Integration (`external_geocoding_service.py`)
- **Forward Provider**: Open-Meteo Geocoding (`https://geocoding-api.open-meteo.com/v1/search`)
- **Reverse Provider**: OpenStreetMap Nominatim (`https://nominatim.openstreetmap.org/reverse`)
- **Compliance**: Custom identifiable `User-Agent: AERION-Disaster-Intelligence-Platform/1.0` header sent on all Nominatim queries with in-memory 24-hour caching to prevent rate-limiting.

---

## 5. API Endpoint Reference

| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/api/v1/geospatial/hazards/history` | Filterable historical hazard records (supports `hazard_type=EARTHQUAKE`, `min_magnitude=5.0`, bbox) |
| `GET` | `/api/v1/external/weather` | Current, forecast, or historical weather with flight suitability |
| `POST` | `/api/v1/external/route` | Road-graph route with step instructions and hazard polygon avoidance |
| `GET` | `/api/v1/external/geocode` | Forward geocoding query returning normalized coordinate results |
| `GET` | `/api/v1/external/reverse-geocode` | Reverse geocoding query returning administrative hierarchy |

---

## 6. Verification & Test Coverage Summary

- **Backend Test Suite**: 188 unit & integration tests passing (`Ran 188 tests in 34.122s, OK`).
- **Runtime Inference Suite**: 26 real-weight and pipeline tests passing (`Ran 26 tests in 37.103s, OK`).
- **Model Weight Verification**: 4/4 frozen model weight hashes strictly verified (`check_model_hashes.py`).
- **Frontend Production Bundle**: Compiled clean with zero TypeScript errors in 15.46s.
