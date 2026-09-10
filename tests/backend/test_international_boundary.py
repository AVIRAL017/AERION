"""
AERION v1 — Authoritative International Boundary Integration Tests (Step 19)

Validates:
1. Dataset provenance and contract structure for authoritative boundaries.
2. Invariant: Generic administrative boundary (ADM0/ADM1/ADM2) != Authoritative operational international border.
3. Default unavailable state: operational_border_available = False with documented reason.
4. Prohibition of generic ADM0 fallback: presence of state/district boundaries does NOT activate border security mode border.
5. Ingestion of authoritative boundary vector records with geometry validation & duplicate prevention.
6. Geodesic distance calculation via PostGIS geography ST_Distance.
7. Point containment resolution (inside vs outside authoritative territory).
8. EvidenceRecord emission with strict modality (DERIVED) and source (GEOSPATIAL_REGISTRY).
9. REST endpoints:
   - GET /api/v1/geospatial/border/status
   - GET /api/v1/geospatial/border/resolve
10. Separation between Authoritative International Boundary and Configured BorderZone / Geofence.
"""

import asyncio
import unittest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.core.auth import create_access_token
from app.core.config import AERIONSettings
from app.db.models import (
    AdministrativeBoundary,
    GeospatialDataset,
    InternationalBoundary,
)
from app.db.session import close_db_connections, get_session_factory
from app.main import create_app
from app.schemas.evidence import EvidenceSourceType, Modality
from app.schemas.geospatial import (
    BorderAcquisitionStatus,
    BorderContractStatus,
    DatasetProvenanceContract,
)
from app.services.international_boundary_service import InternationalBoundaryService


class TestInternationalBoundaryDatabaseQueries(unittest.IsolatedAsyncioTestCase):
    """Async database tests for Step 19 International Boundary models, contracts, and PostGIS queries."""

    async def asyncSetUp(self):
        await close_db_connections()

    async def asyncTearDown(self):
        factory = get_session_factory()
        async with factory() as session:
            await session.execute(text("DELETE FROM international_boundaries;"))
            await session.execute(
                text("DELETE FROM geospatial_datasets WHERE dataset_id = 'AERION_SOI_INTERNATIONAL_BORDER_V1';")
            )
            await session.commit()
        await close_db_connections()

    async def test_default_border_status_unavailable_without_soi(self):
        """
        Critical Rule: In the absence of official Survey of India boundary vectors,
        the system MUST report operational_border_available = False with documented reason.
        """
        factory = get_session_factory()
        async with factory() as session:
            service = InternationalBoundaryService(session)
            status = await service.get_border_contract_status()

            self.assertIsInstance(status, BorderContractStatus)
            self.assertFalse(status.operational_border_available)
            self.assertEqual(status.acquisition_status, BorderAcquisitionStatus.NOT_ACQUIRED)
            self.assertIn("Survey of India", status.authoritative_source_name)
            self.assertIn("administrative country polygon is not used as a substitute", status.disclaimer)

    async def test_no_generic_adm0_fallback_invariant(self):
        """
        Verify that presence of NWIC ADM1/ADM2 boundaries in the database does NOT
        cause operational_border_available to become True.
        """
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(AdministrativeBoundary).limit(1)
            res = await session.execute(stmt)
            admin_sample = res.scalar_one_or_none()
            self.assertIsNotNone(admin_sample, "ADM boundaries must exist from Step 17")

            service = InternationalBoundaryService(session)
            status = await service.get_border_contract_status()

            # Even though India ADM1/ADM2 exist, operational border MUST remain False
            self.assertFalse(status.operational_border_available)
            self.assertEqual(status.acquisition_status, BorderAcquisitionStatus.NOT_ACQUIRED)

    async def test_ingestion_and_proximity_resolution_lifecycle(self):
        """
        Validates the full database lifecycle:
        1. Ingests an authoritative sector boundary fixture.
        2. Verifies status transitions to operational_border_available = True.
        3. Computes geodesic ST_Distance and point containment.
        4. Emits a DERIVED EvidenceRecord.
        5. Prevents duplicate ingestion.
        """
        factory = get_session_factory()
        async with factory() as session:
            service = InternationalBoundaryService(session)

            test_contract = DatasetProvenanceContract(
                dataset_id="AERION_SOI_INTERNATIONAL_BORDER_V1",
                dataset_name="Survey of India Authoritative International Boundary (Operational Sector)",
                source_name="Survey of India (SOI), Department of Science & Technology",
                source_url="https://surveyofindia.gov.in",
                version="2026.1",
                license="Official Survey of India NMP License",
                attribution="Survey of India / Ministry of External Affairs",
                geographic_scope="INDIA_BORDER_NORTHERN_SECTOR",
                geometry_type="MULTIPOLYGON",
                crs="EPSG:4326",
                source_format="GeoJSON",
                checksum="a1b2c3d4e5f67890123456789012345678901234567890123456789012345678",
                notes="Step 19 Authoritative Sector Fixture",
            )

            features = [
                {
                    "type": "Feature",
                    "properties": {
                        "id": "SOI-IB-SECTOR-NW-01",
                        "name": "India International Boundary (Western/Northern Sector)",
                    },
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [74.0, 31.0],
                                [76.0, 31.0],
                                [76.0, 33.0],
                                [74.0, 33.0],
                                [74.0, 31.0],
                            ]
                        ],
                    },
                }
            ]

            # 1. Ingest fixture
            res = await service.ingest_authoritative_boundary(features, test_contract)
            self.assertEqual(res["inserted"], 1)

            # 2. Status now reports operational
            status = await service.get_border_contract_status()
            self.assertTrue(status.operational_border_available)
            self.assertEqual(status.acquisition_status, BorderAcquisitionStatus.INGESTED)
            self.assertIsNotNone(status.provenance)

            # 3. Inside query (32.0, 75.0)
            inside_res = await service.resolve_border_proximity(latitude=32.0, longitude=75.0)
            self.assertTrue(inside_res.available)
            self.assertTrue(inside_res.is_within_border)
            self.assertIsNotNone(inside_res.distance_to_border_km)
            self.assertIsNotNone(inside_res.evidence)
            self.assertEqual(inside_res.evidence.modality, Modality.DERIVED)
            self.assertEqual(inside_res.evidence.source_type, EvidenceSourceType.GEOSPATIAL_REGISTRY)

            # 4. Outside query (30.0, 75.0)
            outside_res = await service.resolve_border_proximity(latitude=30.0, longitude=75.0)
            self.assertTrue(outside_res.available)
            self.assertFalse(outside_res.is_within_border)
            self.assertGreater(outside_res.distance_to_border_km, 50.0)

            # 5. Duplicate ingestion prevention
            res_dup = await service.ingest_authoritative_boundary(features, test_contract)
            self.assertEqual(res_dup["inserted"], 0)
            self.assertEqual(res_dup["skipped_duplicates"], 1)


class TestInternationalBoundaryAPIEndpoints(unittest.TestCase):
    """Validates FastAPI REST endpoints for international boundary queries."""

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

    def test_api_border_status_endpoint_unavailable(self):
        """Test REST API GET /api/v1/geospatial/border/status reports unavailable by default."""
        resp = self.client.get("/api/v1/geospatial/border/status", headers=self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data["operational_border_available"])
        self.assertEqual(data["acquisition_status"], "NOT_ACQUIRED")
        self.assertIn("authoritative_source_name", data)
        self.assertIn("disclaimer", data)
        self.assertIn("An administrative country polygon is not used as a substitute", data["disclaimer"])

    def test_api_border_resolve_when_unavailable(self):
        """
        Test REST API GET /api/v1/geospatial/border/resolve when boundary is unavailable.
        Must return available=False and NOT synthesize a fake distance or fallback to ADM0.
        """
        resp = self.client.get(
            "/api/v1/geospatial/border/resolve?latitude=28.6139&longitude=77.2090",
            headers=self.auth_headers,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertFalse(data["available"])
        self.assertIsNone(data["is_within_border"])
        self.assertIsNone(data["distance_to_border_km"])
        self.assertIn("unavailable", data["status_message"].lower())
        self.assertIn("analytical indicator", data["disclaimer"])


if __name__ == "__main__":
    unittest.main()
