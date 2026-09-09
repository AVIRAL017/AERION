# AERION — Geospatial Architecture & Data Foundation

**Authority**: AERION Geospatial Intelligence Engineering  
**Primary Standards**: OGC WGS84 (EPSG:4326), PostGIS 3.x, GeoJSON, India LCC (EPSG:7755)  

---

## 1. Absolute Geospatial Invariants

1. **Camera/Pixel Space vs WGS84 Separation**:
   - Detections, tracks, and raw camera coordinates reside in pixel Cartesian space (`[0, 0]` to `[W, H]`).
   - PostGIS geometry columns (`geom_point_4326`, `geom_polygon_4326`) are populated **ONLY** when verified sensor attitude, gimbal orientation, and calibrated GPS metadata exist.
   - **DO NOT convert pixel coordinates to latitude/longitude without verified georeferencing.**
2. **Administrative vs International Boundaries**:
   - State and district boundaries (NWIC / SOI administrative layers) represent internal governance borders.
   - Administrative boundary perimeters **MUST NOT** be treated as the authoritative International Border.
   - Border crossing events require human operator verification and must be designated as:
     `POTENTIAL UNAUTHORIZED CROSSING INDICATOR`
3. **Evacuation Routing**:
   - Evacuation corridors are generated across real road network topology via `OpenRouteService` avoiding active hazard polygons.
   - Decorative lines or direct Euclidean connections are strictly prohibited from being described as routes.
   - If routing is obstructed or unavailable, report: `NO FEASIBLE ROUTE AVAILABLE`.
4. **Road Blockage Invariant**:
   - Nearby structural damage alone does not confirm road blockage without verified hazard or ground observation.
