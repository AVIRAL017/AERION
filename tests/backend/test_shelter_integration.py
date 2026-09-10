"""
AERION v1 - Shelter and Evacuation-Point Integration Tests (Step 18)
Tests:
- Extended shelter model schema and attributes
- Geodesic distance calculation via PostGIS geography (ST_DWithin, ST_Distance)
- Administrative boundary enrichment (state/district)
- Operational and capacity status semantics (preservation of unknown/null without fabrication)
- Ingestion pipeline with validation, duplicate detection, and checksum
- REST endpoints (/api/v1/geospatial/shelters, /nearby, /{shelter_id})
- DERIVED EvidenceRecord creation and provenance linkage
"""

import asyncio
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.auth import create_access_token
from app.core.config import AERIONSettings
from app.db.session import close_db_connections, get_session_factory
from app.db.models import Shelter, EvidenceRecord
from app.main import create_app
from app.schemas.shelter import OperationalStatus, CapacityStatus
from app.schemas.geospatial import DatasetProvenanceContract
from app.services.shelter_service import ShelterService
from app.services.shelter_ingestion import ShelterIngestionEngine


class TestShelterIntegration(unittest.TestCase):

    def setUp(self):
        asyncio.run(close_db_connections())
        self.settings = AERIONSettings(ENVIRONMENT="test")
        self.app = create_app(settings=self.settings)
        self.client = TestClient(self.app)

        self.token = create_access_token({
            "sub": "00000000-0000-0000-0000-000000000001",
            "org": "00000000-0000-0000-0000-000000000001",
            "role": "operator",
            "email": "operator@aerion.mil",
        })
        self.auth_headers = {"Authorization": f"Bearer {self.token}"}

    def tearDown(self):
        asyncio.run(close_db_connections())

    def test_shelter_model_schema_extension(self):
        """Verify that the Shelter SQLAlchemy model and DB table contain all extended fields."""
        async def run():
            factory = get_session_factory()
            async with factory() as session:
                stmt = select(Shelter).limit(1)
                result = await session.execute(stmt)
                shelter = result.scalar_one_or_none()
                self.assertIsNotNone(shelter, "Shelters table should contain ingested data.")
                
                # Verify extended attributes exist on model
                self.assertTrue(hasattr(shelter, "dataset_id"))
                self.assertTrue(hasattr(shelter, "source_record_id"))
                self.assertTrue(hasattr(shelter, "shelter_type"))
                self.assertTrue(hasattr(shelter, "operational_status"))
                self.assertTrue(hasattr(shelter, "capacity_status"))
                self.assertTrue(hasattr(shelter, "accessibility"))
                self.assertTrue(hasattr(shelter, "contact_information"))
                self.assertTrue(hasattr(shelter, "opening_hours"))
                self.assertTrue(hasattr(shelter, "services"))
                self.assertTrue(hasattr(shelter, "address"))
                self.assertTrue(hasattr(shelter, "state_code"))
                self.assertTrue(hasattr(shelter, "district_code"))
                self.assertTrue(hasattr(shelter, "source_url"))
                self.assertTrue(hasattr(shelter, "metadata_json"))
                self.assertTrue(hasattr(shelter, "created_at"))
                self.assertTrue(hasattr(shelter, "updated_at"))

        asyncio.run(run())

    def test_shelter_admin_enrichment_and_provenance(self):
        """Verify that shelters in Delhi/Patna/Chennai have administrative attributes enriched."""
        async def run():
            factory = get_session_factory()
            async with factory() as session:
                stmt = select(Shelter).where(Shelter.source_record_id == "DELHI-NDMC-001")
                result = await session.execute(stmt)
                shelter = result.scalar_one_or_none()
                self.assertIsNotNone(shelter)
                self.assertIsNotNone(shelter.state_code)
                self.assertIsNotNone(shelter.district_code)
                self.assertEqual(shelter.operational_status, OperationalStatus.CONFIRMED_OPERATIONAL.value)
                self.assertEqual(shelter.capacity_status, CapacityStatus.SOURCE_REPORTED.value)

        asyncio.run(run())

    def test_shelter_semantics_no_fabrication(self):
        """Verify that unknown/null capacity and status are preserved without fabrication."""
        async def run():
            factory = get_session_factory()
            async with factory() as session:
                # Check Paradip Cyclone Shelter (verified operational)
                stmt = select(Shelter).where(Shelter.source_record_id == "ODISHA-PARADIP-CYC-001")
                result = await session.execute(stmt)
                shelter = result.scalar_one_or_none()
                self.assertIsNotNone(shelter)
                self.assertEqual(shelter.operational_status, OperationalStatus.CONFIRMED_OPERATIONAL.value)
                self.assertEqual(shelter.capacity_status, CapacityStatus.VERIFIED.value)

                # Check Rohini camp (unknown operational status)
                stmt = select(Shelter).where(Shelter.source_record_id == "DELHI-ROHINI-REF-003")
                result = await session.execute(stmt)
                shelter2 = result.scalar_one_or_none()
                self.assertIsNotNone(shelter2)
                self.assertEqual(shelter2.operational_status, OperationalStatus.UNKNOWN.value)
                self.assertIsNone(shelter2.capacity_occupied)

        asyncio.run(run())

    def test_shelter_nearby_proximity_query(self):
        """Verify PostGIS ST_DWithin and ST_Distance geodesic distance computation."""
        async def run():
            factory = get_session_factory()
            async with factory() as session:
                service = ShelterService(session)
                response = await service.query_shelters(
                    latitude=28.6139,
                    longitude=77.2090,
                    radius_km=25.0,
                    limit=10
                )
                self.assertTrue(response.available)
                self.assertGreaterEqual(response.record_count, 1)
                self.assertGreaterEqual(len(response.shelters), 1)
                
                first = response.shelters[0]
                self.assertIsNotNone(first.distance_km)
                self.assertGreater(first.distance_km, 0)
                self.assertLess(first.distance_km, 25.0)

        asyncio.run(run())

    def test_shelter_service_provenance_evidence_created(self):
        """Verify that shelter spatial query generates a DERIVED EvidenceRecord."""
        async def run():
            factory = get_session_factory()
            async with factory() as session:
                service = ShelterService(session)
                response = await service.query_shelters(
                    latitude=28.6139,
                    longitude=77.2090,
                    radius_km=15.0,
                    limit=5
                )
                self.assertIsNotNone(response.evidence)
                self.assertEqual(response.evidence.modality.value, "DERIVED")
                self.assertEqual(response.evidence.source_type.value, "SHELTER_REGISTRY")

        asyncio.run(run())

    def test_api_get_shelters_filter(self):
        """Test REST API GET /api/v1/geospatial/shelters with filters."""
        resp = self.client.get(
            "/api/v1/geospatial/shelters?operational_status=CONFIRMED_OPERATIONAL",
            headers=self.auth_headers,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["available"])
        self.assertGreaterEqual(len(data["shelters"]), 1)
        for s in data["shelters"]:
            self.assertEqual(s["operational_status"], "CONFIRMED_OPERATIONAL")

    def test_api_get_shelters_nearby(self):
        """Test REST API GET /api/v1/geospatial/shelters/nearby."""
        resp = self.client.get(
            "/api/v1/geospatial/shelters/nearby?latitude=25.6&longitude=85.15&radius_km=30",
            headers=self.auth_headers,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["available"])
        self.assertGreaterEqual(len(data["shelters"]), 1)
        self.assertIsNotNone(data["shelters"][0]["distance_km"])
        self.assertEqual(data["radius_km"], 30.0)

    def test_api_get_shelters_nearby_empty_radius(self):
        """Test REST API GET /api/v1/geospatial/shelters/nearby returns structured empty collection when no shelter is near."""
        resp = self.client.get(
            "/api/v1/geospatial/shelters/nearby?latitude=15.0&longitude=65.0&radius_km=10",
            headers=self.auth_headers,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data["available"])
        self.assertEqual(data["record_count"], 0)
        self.assertEqual(len(data["shelters"]), 0)

    def test_api_get_shelter_by_id(self):
        """Test REST API GET /api/v1/geospatial/shelters/{shelter_id}."""
        resp = self.client.get(
            "/api/v1/geospatial/shelters/SHELTER-DELHI-NDMC-001",
            headers=self.auth_headers,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["shelter_id"], "SHELTER-DELHI-NDMC-001")
        self.assertEqual(data["name"], "NDMC Community Hall & Relief Center (Connaught Place)")
        self.assertIn("location", data)

    def test_shelter_ingestion_validation_and_idempotency(self):
        """Test that re-ingesting existing data detects duplicates and skips them."""
        async def run():
            factory = get_session_factory()
            async with factory() as session:
                engine = ShelterIngestionEngine(session)
                contract = DatasetProvenanceContract(
                    dataset_id="AERION_SHELTER_REGISTRY_INDIA_V1",
                    dataset_name="India Emergency Shelters & Evacuation Points",
                    source_name="National Disaster Management Authority (NDMA) & State Disaster Management Authorities",
                    source_url="https://ndma.gov.in",
                    version="1.0",
                    license="Government Open Data License (GODL)",
                    attribution="NDMA / SDMA",
                    geographic_scope="INDIA_NATIONAL",
                    geometry_type="POINT",
                    crs="EPSG:4326",
                    source_format="GeoJSON",
                    checksum="placeholder",
                    notes="Test ingestion",
                )
                geojson_file = Path("data/geospatial/shelters/shelters.geojson")
                summary = await engine.ingest_shelters_geojson(
                    geojson_path=geojson_file,
                    dataset_contract=contract,
                )
                self.assertEqual(summary.inserted_records, 0)
                self.assertGreaterEqual(summary.skipped_duplicates, 6)

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
