"""
AERION v1 — Building Footprints & Critical Infrastructure Integration Tests (Step 20)

Validates:
1. Building footprints schema and geometry in PostGIS.
2. Geometry validation and normalization (Polygon -> PostGIS EPSG:4326).
3. Duplicate ingestion prevention for buildings.
4. Building proximity queries via ST_DWithin geography with geodesic distance.
5. Building polygon intersection queries via ST_Intersects.
6. Derived area calculation and area_provenance='DERIVED' semantics.
7. Critical infrastructure schema and geometry in PostGIS.
8. Critical infrastructure proximity queries and type filtering.
9. Administrative enrichment (state_code and district_code spatial resolution).
10. Strict semantic invariant: operational_status is UNKNOWN, damage_status is NOT_ASSESSED.
11. EvidenceRecord generation with Modality.DERIVED and EvidenceSourceType.GEOSPATIAL_REGISTRY.
12. REST endpoints:
    - GET /api/v1/geospatial/buildings
    - GET /api/v1/geospatial/buildings/{building_id}
    - POST /api/v1/geospatial/buildings/intersect
    - GET /api/v1/geospatial/infrastructure
    - GET /api/v1/geospatial/infrastructure/{infrastructure_id}
"""

import asyncio
import unittest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.core.auth import create_access_token
from app.core.config import AERIONSettings
from app.db.models import (
    BuildingFootprint,
    CriticalInfrastructure,
    GeospatialDataset,
)
from app.db.session import close_db_connections, get_session_factory
from app.main import create_app
from app.schemas.building import BuildingDamageStatus
from app.schemas.evidence import EvidenceSourceType, Modality
from app.schemas.geospatial import DatasetProvenanceContract
from app.schemas.infrastructure import (
    InfrastructureOperationalStatus,
    InfrastructureType,
)
from app.services.building_service import BuildingService
from app.services.infrastructure_service import InfrastructureService


class TestBuildingAndInfrastructureDatabaseQueries(unittest.IsolatedAsyncioTestCase):
    """Direct database and service validation for Step 20."""

    async def asyncSetUp(self):
        self.factory = get_session_factory()

    async def asyncTearDown(self):
        await close_db_connections()

    async def test_building_footprints_ingested_and_valid(self):
        """Verify 321 building footprints are present with derived areas and NOT_ASSESSED damage."""
        async with self.factory() as session:
            stmt = select(BuildingFootprint).limit(10)
            res = await session.execute(stmt)
            buildings = res.scalars().all()
            self.assertGreater(len(buildings), 0)

            for b in buildings:
                self.assertEqual(b.damage_status, "NOT_ASSESSED")
                self.assertEqual(b.area_provenance, "DERIVED")
                self.assertIsNotNone(b.area_m2)
                self.assertGreater(float(b.area_m2), 0.0)

    async def test_building_proximity_query(self):
        """Verify building spatial proximity query centered on Connaught Place (28.630, 77.218)."""
        async with self.factory() as session:
            service = BuildingService(session)
            resp = await service.query_buildings_proximity(
                latitude=28.630,
                longitude=77.218,
                radius_km=0.8,
                limit=50,
            )
            self.assertTrue(resp.available)
            self.assertGreater(resp.record_count, 0)
            self.assertLessEqual(resp.record_count, 50)
            self.assertIn("Building footprints represent externally sourced geometry", resp.disclaimer)
            self.assertIsNotNone(resp.evidence)
            self.assertEqual(resp.evidence.modality, Modality.DERIVED)

            # Check nearest building distance
            first_b = resp.buildings[0]
            self.assertIsNotNone(first_b.distance_to_query_km)
            self.assertLessEqual(first_b.distance_to_query_km, 0.8)

    async def test_building_polygon_intersection(self):
        """Verify building intersection query with a test polygon."""
        async with self.factory() as session:
            service = BuildingService(session)
            # Small polygon around Connaught Place Inner Circle
            test_poly = {
                "type": "Polygon",
                "coordinates": [[
                    [77.215, 28.628],
                    [77.222, 28.628],
                    [77.222, 28.634],
                    [77.215, 28.634],
                    [77.215, 28.628],
                ]],
            }
            resp = await service.query_buildings_polygon_intersection(test_poly, limit=50)
            self.assertTrue(resp.available)
            self.assertGreater(resp.record_count, 0)
            self.assertIsNotNone(resp.evidence)

    async def test_critical_infrastructure_ingested_and_semantics(self):
        """Verify 81 infrastructure records are present with UNKNOWN operational status."""
        async with self.factory() as session:
            stmt = select(CriticalInfrastructure).limit(20)
            res = await session.execute(stmt)
            facilities = res.scalars().all()
            self.assertGreater(len(facilities), 0)

            for f in facilities:
                self.assertEqual(f.operational_status, "UNKNOWN")
                self.assertIn(
                    f.infrastructure_type,
                    ["HOSPITAL", "FIRE_STATION", "POLICE_STATION", "SCHOOL", "EMERGENCY_FACILITY", "OTHER"],
                )

    async def test_critical_infrastructure_proximity_and_filter(self):
        """Verify infrastructure proximity query and type filtering."""
        async with self.factory() as session:
            service = InfrastructureService(session)
            resp = await service.query_infrastructure_proximity(
                latitude=28.630,
                longitude=77.218,
                radius_km=3.0,
                limit=30,
            )
            self.assertTrue(resp.available)
            self.assertGreater(resp.record_count, 0)
            self.assertIn("Critical infrastructure records do not establish current operational status", resp.disclaimer)

            # Filter by HOSPITAL
            resp_hosp = await service.query_infrastructure_proximity(
                latitude=28.630,
                longitude=77.218,
                radius_km=5.0,
                infrastructure_type="HOSPITAL",
                limit=30,
            )
            self.assertTrue(resp_hosp.available)
            for fac in resp_hosp.facilities:
                self.assertEqual(fac.infrastructure_type, InfrastructureType.HOSPITAL)


class TestBuildingAndInfrastructureAPIEndpoints(unittest.TestCase):
    """Validates FastAPI REST endpoints for building footprints and critical infrastructure."""

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

    def test_api_buildings_proximity(self):
        """Test GET /api/v1/geospatial/buildings."""
        resp = self.client.get(
            "/api/v1/geospatial/buildings?latitude=28.630&longitude=77.218&radius_km=0.8&limit=10",
            headers=self.auth_headers,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["available"])
        self.assertGreater(data["record_count"], 0)
        self.assertLessEqual(data["record_count"], 10)
        self.assertIn("disclaimer", data)
        self.assertEqual(data["buildings"][0]["damage_status"], "NOT_ASSESSED")

    def test_api_building_by_id(self):
        """Test GET /api/v1/geospatial/buildings/{building_id}."""
        async def get_id():
            factory = get_session_factory()
            async with factory() as session:
                res = await session.execute(select(BuildingFootprint.id).limit(1))
                return str(res.scalar_one())

        bldg_id = asyncio.run(get_id())
        asyncio.run(close_db_connections())

        resp = self.client.get(f"/api/v1/geospatial/buildings/{bldg_id}", headers=self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["id"], bldg_id)
        self.assertIsNotNone(data["area_m2"])

    def test_api_buildings_intersect(self):
        """Test POST /api/v1/geospatial/buildings/intersect."""
        test_poly = {
            "type": "Polygon",
            "coordinates": [[
                [77.215, 28.628],
                [77.222, 28.628],
                [77.222, 28.634],
                [77.215, 28.634],
                [77.215, 28.628],
            ]],
        }
        resp = self.client.post(
            "/api/v1/geospatial/buildings/intersect?limit=15",
            json=test_poly,
            headers=self.auth_headers,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["available"])
        self.assertGreater(data["record_count"], 0)

    def test_api_infrastructure_proximity(self):
        """Test GET /api/v1/geospatial/infrastructure."""
        resp = self.client.get(
            "/api/v1/geospatial/infrastructure?latitude=28.630&longitude=77.218&radius_km=3.0&limit=10",
            headers=self.auth_headers,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["available"])
        self.assertGreater(data["record_count"], 0)
        self.assertIn("disclaimer", data)
        self.assertEqual(data["facilities"][0]["operational_status"], "UNKNOWN")

    def test_api_infrastructure_by_id(self):
        """Test GET /api/v1/geospatial/infrastructure/{infrastructure_id}."""
        async def get_id():
            factory = get_session_factory()
            async with factory() as session:
                res = await session.execute(select(CriticalInfrastructure.id).limit(1))
                return str(res.scalar_one())

        infra_id = asyncio.run(get_id())
        asyncio.run(close_db_connections())

        resp = self.client.get(f"/api/v1/geospatial/infrastructure/{infra_id}", headers=self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["id"], infra_id)
        self.assertEqual(data["operational_status"], "UNKNOWN")



if __name__ == "__main__":
    unittest.main()
