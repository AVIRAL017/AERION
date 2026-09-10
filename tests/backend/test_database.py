"""
AERION — Database Layer Tests (Phase 3B)
Tests configuration, entity definitions, PostGIS column registrations,
repository abstractions, and offline migration SQL generation.
"""

import unittest
import uuid
from datetime import datetime, timezone

from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql
from geoalchemy2.types import Geometry

from app.core.config import AERIONSettings, get_settings
from app.db.session import Base
import app.db.models as models
from app.db.models import (
    Organization,
    User,
    Project,
    Asset,
    Geofence,
    AnalysisJob,
    AnalysisResult,
    Detection,
    Track,
    BorderEvent,
    DamageAnalysis,
    UsageEvent,
    Subscription,
    EvidenceRecord,
    Situation,
    SituationEvent,
    SituationReport,
    Shelter,
    HazardZone,
    IntelligenceItemModel,
)


class TestDatabaseConfiguration(unittest.TestCase):
    """Test database settings and connection URL builders."""

    def test_default_database_settings(self):
        settings = AERIONSettings()
        self.assertEqual(settings.POSTGRES_DB, "aerion")
        self.assertEqual(settings.POSTGRES_PORT, 5433)
        self.assertIn("postgresql+asyncpg://", settings.async_database_url)
        self.assertIn("postgresql+psycopg2://", settings.sync_database_url)

    def test_database_url_override(self):
        settings = AERIONSettings(DATABASE_URL_OVERRIDE="sqlite+aiosqlite:///:memory:")
        self.assertEqual(settings.async_database_url, "sqlite+aiosqlite:///:memory:")


class TestDatabaseSchemaEntities(unittest.TestCase):
    """Verify all 19 required architecture entities are defined and have correct table names."""

    EXPECTED_TABLES = {
        "organizations",
        "users",
        "projects",
        "assets",
        "geofences",
        "analysis_jobs",
        "analysis_results",
        "detections",
        "tracks",
        "border_events",
        "damage_analyses",
        "usage_events",
        "subscriptions",
        "evidence_records",
        "situations",
        "situation_events",
        "situation_reports",
        "shelters",
        "hazard_zones",
        "intelligence_items",
        "geospatial_datasets",
        "administrative_boundaries",
        "historical_hazard_records",
        "international_boundaries",
    }

    def test_all_entities_registered_in_metadata(self):
        registered = set(Base.metadata.tables.keys())
        for expected in self.EXPECTED_TABLES:
            self.assertIn(expected, registered, f"Table {expected} missing from SQLAlchemy metadata")

    def test_international_boundaries_columns(self):
        """Verify Step 19 columns on international_boundaries table."""
        table = Base.metadata.tables["international_boundaries"]
        expected_cols = [
            "id", "dataset_id", "source_record_id", "name",
            "boundary_type", "geom_4326", "source_url",
            "metadata_json", "created_at", "updated_at"
        ]
        for col in expected_cols:
            self.assertIn(col, table.columns, f"Column {col} missing from international_boundaries table")

    def test_coordinate_separation_invariance(self):
        """Verify strict separation of image/pixel space vs EPSG:4326 PostGIS geometry columns."""
        # 1. Geofence
        geofence_table = Base.metadata.tables["geofences"]
        self.assertIn("pixel_polygon", geofence_table.columns)
        self.assertIn("geom_polygon_4326", geofence_table.columns)
        self.assertIn("is_georeferenced", geofence_table.columns)
        self.assertIsInstance(geofence_table.columns["geom_polygon_4326"].type, Geometry)
        self.assertEqual(geofence_table.columns["geom_polygon_4326"].type.srid, 4326)

        # 2. Detections
        det_table = Base.metadata.tables["detections"]
        self.assertIn("pixel_bbox_x1", det_table.columns)
        self.assertIn("geom_point_4326", det_table.columns)
        self.assertIsInstance(det_table.columns["geom_point_4326"].type, Geometry)
        self.assertEqual(det_table.columns["geom_point_4326"].type.srid, 4326)

        # 3. Tracks
        track_table = Base.metadata.tables["tracks"]
        self.assertIn("pixel_center_x", track_table.columns)
        self.assertIn("geom_point_4326", track_table.columns)
        self.assertIn("geom_trajectory_4326", track_table.columns)

        # 4. Border Events
        border_table = Base.metadata.tables["border_events"]
        self.assertIn("pixel_location_x", border_table.columns)
        self.assertIn("geom_point_4326", border_table.columns)

        # 5. Evidence Records
        ev_table = Base.metadata.tables["evidence_records"]
        self.assertIn("pixel_bbox", ev_table.columns)
        self.assertIn("geom_point_4326", ev_table.columns)
        self.assertIn("geom_polygon_4326", ev_table.columns)

    def test_shelter_extended_columns(self):
        """Verify Step 18 extended operational and capacity columns on shelters table."""
        shelter_table = Base.metadata.tables["shelters"]
        expected_cols = [
            "id", "project_id", "dataset_id", "source_record_id", "name",
            "geom_point_4326", "shelter_type", "operational_status", "status",
            "capacity_total", "capacity_occupied", "capacity_status",
            "is_generator_powered", "medical_support_available",
            "accessibility", "contact_information", "opening_hours",
            "services", "address", "state_code", "district_code",
            "source_registry", "source_url", "last_reported_utc",
            "metadata_json", "created_at", "updated_at"
        ]
        for col in expected_cols:
            self.assertIn(col, shelter_table.columns, f"Column {col} missing from shelters table")

    def test_building_footprints_schema(self):
        """Verify building_footprints table and columns in SQLAlchemy metadata."""
        self.assertIn("building_footprints", Base.metadata.tables)
        table = Base.metadata.tables["building_footprints"]
        expected_cols = [
            "id", "dataset_id", "source_record_id", "building_type", "damage_status",
            "area_m2", "area_provenance", "height", "levels", "address",
            "source_url", "geom_4326", "metadata_json", "created_at", "updated_at"
        ]
        for col in expected_cols:
            self.assertIn(col, table.columns, f"Column {col} missing from building_footprints table")
        self.assertIsInstance(table.columns["geom_4326"].type, Geometry)
        self.assertEqual(table.columns["geom_4326"].type.srid, 4326)

    def test_critical_infrastructure_schema(self):
        """Verify critical_infrastructure table and columns in SQLAlchemy metadata."""
        self.assertIn("critical_infrastructure", Base.metadata.tables)
        table = Base.metadata.tables["critical_infrastructure"]
        expected_cols = [
            "id", "dataset_id", "source_record_id", "name", "infrastructure_type",
            "subtype", "operational_status", "address", "state_code", "district_code",
            "source_url", "geom_4326", "metadata_json", "created_at", "updated_at"
        ]
        for col in expected_cols:
            self.assertIn(col, table.columns, f"Column {col} missing from critical_infrastructure table")
        self.assertIsInstance(table.columns["geom_4326"].type, Geometry)
        self.assertEqual(table.columns["geom_4326"].type.srid, 4326)

    def test_ddl_compilation_for_postgresql(self):
        """Ensure all table DDL compiles cleanly against the PostgreSQL dialect."""
        dialect = postgresql.dialect()
        for table in Base.metadata.sorted_tables:
            stmt = str(CreateTable(table).compile(dialect=dialect)).strip()
            self.assertTrue(stmt.startswith("CREATE TABLE"), f"Table {table.name} failed DDL compilation")



if __name__ == "__main__":
    unittest.main()
