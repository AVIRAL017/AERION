"""
AERION — Geospatial Static Data Ingestion CLI (Step 17)
Deterministic ingestion script to populate PostGIS with:
1. India State Boundaries (NWIC / Survey of India) -> ADM1
2. India District Boundaries (NWIC / Survey of India) -> ADM2
3. India Flood Inventory v3 (HydroSense Lab, IIT Delhi / IMD) -> Historical Hazard Evidence

Usage:
    python scripts/ingest_geospatial_data.py
"""

import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from app.db.session import get_session_factory
from app.schemas.geospatial import DatasetProvenanceContract
from app.services.geospatial_ingestion import GeospatialIngestionEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ingest_geospatial")


async def main():
    logger.info("Starting AERION Step 17 Geospatial Static Data Ingestion...")

    # Define Dataset Contracts
    state_contract = DatasetProvenanceContract(
        dataset_id="NWIC_INDIA_STATE_BOUNDARY_V1",
        dataset_name="India State Boundaries (NWIC)",
        source_name="National Water Informatics Centre (NWIC) / Survey of India",
        source_url="https://indiawris.gov.in/",
        version="v1.0",
        acquisition_date=datetime(2026, 9, 7, 0, 0, 0, tzinfo=timezone.utc),
        license="Government Open Data License - India (GODL)",
        attribution="National Water Informatics Centre / Survey of India",
        geographic_scope="INDIA_NATIONAL",
        geometry_type="MULTIPOLYGON",
        crs="EPSG:7755",
        source_format="GeoJSON",
        processing_status="ACTIVE",
        checksum="2ce4f8884a624f544623c76ea7002d7d12b8c673db9ee6f3ce568f1366cf4010",
        notes="Administrative state boundary polygons for all 36 States and Union Territories.",
        metadata_json={"level": "ADM1", "authority": "NWIC / SOI"},
    )

    district_contract = DatasetProvenanceContract(
        dataset_id="NWIC_INDIA_DISTRICT_BOUNDARY_V1",
        dataset_name="India District Boundaries (NWIC)",
        source_name="National Water Informatics Centre (NWIC) / Survey of India",
        source_url="https://indiawris.gov.in/",
        version="v1.0",
        acquisition_date=datetime(2026, 9, 7, 0, 0, 0, tzinfo=timezone.utc),
        license="Government Open Data License - India (GODL)",
        attribution="National Water Informatics Centre / Survey of India",
        geographic_scope="INDIA_NATIONAL",
        geometry_type="MULTIPOLYGON",
        crs="EPSG:7755",
        source_format="GeoJSON",
        processing_status="ACTIVE",
        checksum="2b27a478e24d8c51b0655e74ce3f4f880e75c752e4597550d6fc925ed06ac201",
        notes="Administrative district boundary polygons across Indian states.",
        metadata_json={"level": "ADM2", "authority": "NWIC / SOI"},
    )

    flood_contract = DatasetProvenanceContract(
        dataset_id="INDIA_FLOOD_INVENTORY_V3",
        dataset_name="India Flood Inventory (v3)",
        source_name="HydroSense Lab, IIT Delhi / Disaster Management Authorities / IMD",
        source_url="https://hydrosense.iitd.ac.in/",
        version="v3.0",
        acquisition_date=datetime(2026, 9, 7, 0, 0, 0, tzinfo=timezone.utc),
        license="Public Disaster Inventory Records for Scientific and Humanitarian Research",
        attribution="HydroSense Lab, IIT Delhi / IMD",
        geographic_scope="INDIA_NATIONAL",
        geometry_type="POLYGON",
        crs="EPSG:4326",
        source_format="GeoJSON",
        processing_status="ACTIVE",
        checksum="74766a467efdef1ff82fcbf1303ac0a0133d095ef711cbe817f29de373217fae",
        notes="Historical flood inventory (1967-2023). Reference hazard evidence, NOT live operational flood status.",
        metadata_json={"hazard_type": "HISTORICAL_FLOOD", "is_live_status": False},
    )

    shelter_contract = DatasetProvenanceContract(
        dataset_id="INDIA_EMERGENCY_SHELTERS_V1",
        dataset_name="India Emergency Shelters & Evacuation Points Registry",
        source_name="OpenStreetMap Contributors / National Disaster Management Framework",
        source_url="https://www.openstreetmap.org/",
        version="v1.0",
        acquisition_date=datetime(2026, 9, 10, 0, 0, 0, tzinfo=timezone.utc),
        license="Open Database License (ODbL) 1.0",
        attribution="OpenStreetMap Contributors / AERION Geospatial Intelligence",
        geographic_scope="INDIA_NATIONAL",
        geometry_type="POINT",
        crs="EPSG:4326",
        source_format="GeoJSON",
        processing_status="ACTIVE",
        checksum="",
        notes="Verified emergency shelter points. Reference data only; presence does not confirm live operational status.",
        metadata_json={"domain": "emergency_shelters"},
    )

    # Filepaths
    state_path = root_dir / "dataset" / "india boundries" / "state_nwic_geojson" / "state_NWIC.GeoJSON"
    district_path = root_dir / "dataset" / "india boundries" / "district_nwic_geojson" / "district_nwic.GeoJSON"
    flood_path = root_dir / "dataset" / "INDIA_FLOOD_INVENTORY_V3.geojson"
    shelter_path = root_dir / "data" / "geospatial" / "shelters" / "shelters.geojson"

    session_factory = get_session_factory()
    async with session_factory() as session:
        ingestion_engine = GeospatialIngestionEngine(session)
        from app.services.shelter_ingestion import ShelterIngestionEngine
        shelter_engine = ShelterIngestionEngine(session)

        # 1. Ingest States (ADM1)
        logger.info(f"Checking state boundary file at: {state_path}")
        if state_path.exists():
            st_ing, st_skip = await ingestion_engine.ingest_administrative_geojson(
                geojson_path=state_path,
                dataset_contract=state_contract,
                level="ADM1",
                name_prop="state_name",
                source_srid=7755,
            )
            logger.info(f"State boundaries: {st_ing} ingested, {st_skip} skipped.")
        else:
            logger.warning(f"State boundary file not found at {state_path}")

        # 2. Ingest Districts (ADM2)
        logger.info(f"Checking district boundary file at: {district_path}")
        if district_path.exists():
            dt_ing, dt_skip = await ingestion_engine.ingest_administrative_geojson(
                geojson_path=district_path,
                dataset_contract=district_contract,
                level="ADM2",
                name_prop="district",
                code_prop="dtcode",
                source_srid=7755,
                batch_size=50,
            )
            logger.info(f"District boundaries: {dt_ing} ingested, {dt_skip} skipped.")
        else:
            logger.warning(f"District boundary file not found at {district_path}")

        # 3. Ingest Historical Flood Inventory
        logger.info(f"Checking flood inventory file at: {flood_path}")
        if flood_path.exists():
            fl_ing, fl_skip = await ingestion_engine.ingest_india_flood_inventory(
                geojson_path=flood_path,
                dataset_contract=flood_contract,
                batch_size=50,
            )
            logger.info(f"Historical flood inventory: {fl_ing} ingested, {fl_skip} skipped.")
        else:
            logger.warning(f"Flood inventory file not found at {flood_path}")

        # 4. Ingest Emergency Shelters
        logger.info(f"Checking shelter file at: {shelter_path}")
        if shelter_path.exists():
            sh_summary = await shelter_engine.ingest_shelters_geojson(
                geojson_path=shelter_path,
                dataset_contract=shelter_contract,
                batch_size=50,
            )
            logger.info(
                f"Shelters: {sh_summary.inserted_records} inserted, {sh_summary.skipped_duplicates} duplicates skipped, {sh_summary.enriched_with_admin_boundaries} enriched."
            )
        else:
            logger.warning(f"Shelter file not found at {shelter_path}")

        await session.commit()
        logger.info("All geospatial datasets committed successfully to PostGIS.")


if __name__ == "__main__":
    asyncio.run(main())
