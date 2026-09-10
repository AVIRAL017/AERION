"""
AERION — Ingest Reference OSM Buildings and Infrastructure (Step 20)
Reads the acquired 321 building footprints and 81 infrastructure records for Central Delhi / Connaught Place,
registers dataset provenance contracts in geospatial_datasets, and populates PostGIS tables.

Strict semantic rules:
1. Operational status of infrastructure is strictly UNKNOWN.
2. Building damage status is strictly NOT_ASSESSED.
3. No occupancy, structural safety, or official designation is fabricated.
4. Preserves original OSM tags and IDs.
"""

import asyncio
import json
from pathlib import Path

from app.db.session import close_db_connections, get_session_factory
from app.schemas.geospatial import DatasetProvenanceContract
from app.services.building_service import BuildingService
from app.services.infrastructure_service import InfrastructureService


async def run_ingestion():
    buildings_path = Path("dataset/osm_reference/delhi_buildings_sample.json")
    infra_path = Path("dataset/osm_reference/delhi_infrastructure_sample.json")

    if not buildings_path.exists() or not infra_path.exists():
        print("Dataset files missing under dataset/osm_reference/")
        return

    with open(buildings_path, "r", encoding="utf-8") as f:
        buildings_data = json.load(f)

    with open(infra_path, "r", encoding="utf-8") as f:
        infra_data = json.load(f)

    print(f"Loaded {len(buildings_data)} building footprints and {len(infra_data)} infrastructure records.")

    # 1. Building contract
    building_contract = DatasetProvenanceContract(
        dataset_id="OSM_DELHI_CENTRAL_BUILDINGS_V1",
        dataset_name="OpenStreetMap Central Delhi Building Footprints (Sample)",
        source_name="OpenStreetMap Contributors / Overpass API",
        source_url="https://www.openstreetmap.org",
        version="2026-09-10",
        license="Open Database License (ODbL) 1.0",
        attribution="© OpenStreetMap contributors. Data available under the Open Database License.",
        geographic_scope="DELHI_CENTRAL_BOUNDED",
        geometry_type="POLYGON",
        crs="EPSG:4326",
        source_format="JSON",
        processing_status="INGESTED",
        checksum="bd94b4ed331ba35ecb1d5ed3a1c8523de0bebb9118e3ee7c37212587c4326280",
        notes="Externally provided reference building footprints for Central Delhi / Connaught Place. Does not establish occupancy, structural safety, or damage.",
        metadata_json={
            "bounding_box": [28.625, 77.213, 28.636, 77.225],
            "feature_count": len(buildings_data),
        },
    )

    # 2. Infrastructure contract
    infra_contract = DatasetProvenanceContract(
        dataset_id="OSM_DELHI_CENTRAL_INFRASTRUCTURE_V1",
        dataset_name="OpenStreetMap Central Delhi Critical Infrastructure (Sample)",
        source_name="OpenStreetMap Contributors / Overpass API",
        source_url="https://www.openstreetmap.org",
        version="2026-09-10",
        license="Open Database License (ODbL) 1.0",
        attribution="© OpenStreetMap contributors. Data available under the Open Database License.",
        geographic_scope="DELHI_CENTRAL_BOUNDED",
        geometry_type="GEOMETRY",
        crs="EPSG:4326",
        source_format="JSON",
        processing_status="INGESTED",
        checksum="0d4fb7a3326d7e54df0e941afa9176800bc30f09356c1ef4a006883dd7d799ec",
        notes="Externally provided reference critical infrastructure records (hospitals, police stations, fire stations, schools). Operational status strictly UNKNOWN unless explicitly verified.",
        metadata_json={
            "bounding_box": [28.615, 77.195, 28.645, 77.240],
            "feature_count": len(infra_data),
        },
    )

    factory = get_session_factory()
    async with factory() as session:
        b_service = BuildingService(session)
        res_b = await b_service.ingest_buildings(buildings_data, building_contract)
        print(f"Buildings ingestion: {res_b}")

    async with factory() as session:
        i_service = InfrastructureService(session)
        res_i = await i_service.ingest_infrastructure(infra_data, infra_contract)
        print(f"Infrastructure ingestion: {res_i}")

    await close_db_connections()
    print("Ingestion completed successfully.")


if __name__ == "__main__":
    asyncio.run(run_ingestion())
