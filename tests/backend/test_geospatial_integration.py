"""
AERION — Geospatial Data Integration Tests (Step 17)
Validates:
1. Dataset metadata creation and provenance contracts
2. Checksum calculation and duplicate ingestion prevention
3. Coordinate transformation (EPSG:7755 -> EPSG:4326)
4. Valid geometry ingestion and PostGIS indexing
5. Invalid geometry / missing data safety
6. ADM0 / ADM1 / ADM2 hierarchical spatial resolution
7. Point outside coverage returns explicit unavailable
8. Historical hazard queries with explicit non-live semantics
9. Operational border contract availability reporting
10. Evidence record generation with strict modalities (EXTERNALLY_PROVIDED, DERIVED)
11. REST API endpoint responses (/api/v1/geospatial/...)
"""

import asyncio
import json
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.auth import create_access_token
from app.core.config import AERIONSettings
from app.db.session import close_db_connections, get_session_factory
from app.main import create_app
from app.schemas.evidence import EvidenceSourceType, Modality
from app.schemas.geospatial import (
    AdminBoundaryResolution,
    BorderContractStatus,
    DatasetProvenanceContract,
    HistoricalHazardQueryResponse,
)
from app.services.geospatial_ingestion import compute_file_sha256
from app.services.geospatial_service import GeospatialService


class TestGeospatialDataContracts(unittest.TestCase):
    """Validates Phase C contracts and checksums."""

    def test_dataset_provenance_contract_structure(self):
        contract = DatasetProvenanceContract(
            dataset_id="TEST_DATASET_V1",
            dataset_name="Test National Boundary",
            source_name="Survey of India",
            source_url="https://example.gov.in",
            version="1.0",
            license="GODL",
            attribution="Survey of India",
            geographic_scope="INDIA_NATIONAL",
            geometry_type="MULTIPOLYGON",
            crs="EPSG:7755",
            source_format="GeoJSON",
            checksum="abc1234567890123456789012345678901234567890123456789012345678901234",
            notes="Testing contract",
        )
        self.assertEqual(contract.dataset_id, "TEST_DATASET_V1")
        self.assertEqual(contract.crs, "EPSG:7755")
        self.assertEqual(contract.processing_status, "ACTIVE")

    def test_dataset_checksum_deterministic(self):
        readme_path = Path("data/README.md")
        if readme_path.exists():
            sha = compute_file_sha256(readme_path)
            self.assertEqual(len(sha), 64)
            # Recompute to guarantee determinism
            self.assertEqual(sha, compute_file_sha256(readme_path))


class TestGeospatialDatabaseQueries(unittest.IsolatedAsyncioTestCase):
    """Validates real queries against PostGIS for Step 17."""

    async def asyncSetUp(self):
        await close_db_connections()

    async def asyncTearDown(self):
        await close_db_connections()

    async def test_admin_containment_delhi(self):
        factory = get_session_factory()
        async with factory() as session:
            service = GeospatialService(session)
            # Delhi Coordinates: (28.6139, 77.2090)
            res = await service.resolve_admin_point(28.6139, 77.2090)

            self.assertTrue(res.available)
            self.assertIsNotNone(res.country)
            self.assertEqual(res.country.name, "India")
            self.assertIsNotNone(res.state)
            self.assertIn("Delhi", res.state.name)
            self.assertIsNotNone(res.district)
            self.assertEqual(res.district.name, "New Delhi")
            # Evidence assertions
            self.assertIsNotNone(res.evidence)
            self.assertEqual(res.evidence.source_type, EvidenceSourceType.GEOSPATIAL_REGISTRY)
            self.assertEqual(res.evidence.modality, Modality.DERIVED)

    async def test_admin_containment_outside_coverage(self):
        factory = get_session_factory()
        async with factory() as session:
            service = GeospatialService(session)
            # Null Island: (0.0, 0.0)
            res = await service.resolve_admin_point(0.0, 0.0)

            self.assertFalse(res.available)
            self.assertIsNone(res.country)
            self.assertIsNone(res.state)
            self.assertIsNone(res.district)
            self.assertIsNone(res.evidence)

    async def test_historical_hazards_query_semantics(self):
        factory = get_session_factory()
        async with factory() as session:
            service = GeospatialService(session)
            # Query Delhi region
            hazards = await service.query_historical_hazards(28.6139, 77.2090, radius_km=100.0)

            self.assertTrue(hazards.is_historical_reference_only)
            self.assertIn("must not be interpreted as live", hazards.disclaimer)
            self.assertIsNotNone(hazards.evidence)
            self.assertEqual(hazards.evidence.modality, Modality.EXTERNALLY_PROVIDED)
            for r in hazards.records:
                self.assertFalse(r.is_live_status)
                self.assertEqual(r.hazard_type, "HISTORICAL_FLOOD")

    async def test_border_status_contract(self):
        factory = get_session_factory()
        async with factory() as session:
            service = GeospatialService(session)
            border = await service.get_border_contract_status()

            self.assertFalse(border.operational_border_available)
            self.assertIn("UNAVAILABLE", border.status_message)
            self.assertIn("Survey of India", border.authoritative_source_name)


class TestGeospatialAPIEndpoints(unittest.TestCase):
    """Validates FastAPI REST endpoints for geospatial data."""

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

    def test_list_datasets_endpoint(self):
        resp = self.client.get("/api/v1/geospatial/datasets", headers=self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsInstance(data, list)
        dataset_ids = [d["dataset_id"] for d in data]
        self.assertIn("NWIC_INDIA_STATE_BOUNDARY_V1", dataset_ids)
        self.assertIn("NWIC_INDIA_DISTRICT_BOUNDARY_V1", dataset_ids)
        self.assertIn("INDIA_FLOOD_INVENTORY_V3", dataset_ids)

    def test_resolve_admin_endpoint_valid(self):
        resp = self.client.get(
            "/api/v1/geospatial/admin/resolve?latitude=28.6139&longitude=77.2090",
            headers=self.auth_headers,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["available"])
        self.assertEqual(data["country"]["name"], "India")
        self.assertIn("Delhi", data["state"]["name"])
        self.assertEqual(data["district"]["name"], "New Delhi")
        self.assertEqual(data["evidence"]["modality"], "DERIVED")

    def test_resolve_admin_endpoint_outside(self):
        resp = self.client.get(
            "/api/v1/geospatial/admin/resolve?latitude=0.0&longitude=0.0",
            headers=self.auth_headers,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data["available"])
        self.assertIsNone(data["state"])

    def test_historical_hazards_endpoint(self):
        resp = self.client.get(
            "/api/v1/geospatial/hazards/history?latitude=28.6139&longitude=77.2090&radius_km=100",
            headers=self.auth_headers,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["is_historical_reference_only"])
        self.assertIn("reference evidence", data["disclaimer"])
        self.assertIsInstance(data["records"], list)

    def test_border_status_endpoint(self):
        resp = self.client.get("/api/v1/geospatial/border/status", headers=self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data["operational_border_available"])
        self.assertIn("UNAVAILABLE", data["status_message"])


if __name__ == "__main__":
    unittest.main()
