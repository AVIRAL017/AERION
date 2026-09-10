"""
AERION — Building Footprint Query & Ingestion Service (Step 20)
Executes deterministic spatial queries against building footprints in PostGIS.

Invariants:
1. Geodesic distance & area: uses PostGIS ST_Distance and ST_Area on geography.
2. Zero fabrication: damage_status strictly defaults to NOT_ASSESSED.
3. No occupancy/structural safety inference.
4. Preserves DERIVED EvidenceRecord linked to the query.
5. Ingestion validates geometry, calculates area, and prevents duplicates.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from shapely.geometry import shape, mapping, Polygon, MultiPolygon
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BuildingFootprint, GeospatialDataset
from app.schemas.building import (
    BuildingDamageStatus,
    BuildingQueryResponse,
    BuildingRecord,
)
from app.schemas.evidence import (
    EvidenceRecord,
    EvidenceSourceType,
    GeoPoint,
    Modality,
    TemporalMode,
    VerificationState,
    utcnow,
)
from app.schemas.geospatial import DatasetProvenanceContract

logger = logging.getLogger("aerion.building.service")


class BuildingService:
    """
    Handles queries and ingestion for building footprints.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_building_by_id(self, building_id: str) -> Optional[BuildingRecord]:
        """Retrieves a single building footprint record by ID."""
        sql = text("""
            SELECT 
                b.id, b.dataset_id, b.source_record_id, b.building_type, b.damage_status,
                b.area_m2, b.area_provenance, b.height, b.levels, b.address, b.source_url,
                ST_AsGeoJSON(b.geom_4326)::json as geojson,
                b.metadata_json, b.created_at
            FROM building_footprints b
            WHERE b.id = CAST(:building_id AS UUID);
        """)
        res = await self.session.execute(sql, {"building_id": building_id})

        row = res.mappings().first()
        if not row:
            return None

        return BuildingRecord(
            id=str(row["id"]),
            dataset_id=str(row["dataset_id"]),
            source_record_id=row["source_record_id"],
            building_type=row["building_type"],
            damage_status=BuildingDamageStatus(row["damage_status"]),
            area_m2=float(row["area_m2"]) if row["area_m2"] is not None else None,
            area_provenance=row["area_provenance"],
            height=row["height"],
            levels=row["levels"],
            address=row["address"],
            source_url=row["source_url"],
            distance_to_query_km=None,
            geometry_geojson=row["geojson"],
            metadata_json=row["metadata_json"],
            created_at=row["created_at"],
        )

    async def query_buildings_proximity(
        self,
        latitude: float,
        longitude: float,
        radius_km: float = 1.0,
        limit: int = 100,
    ) -> BuildingQueryResponse:
        """
        Finds building footprints within radius_km of a coordinate using PostGIS ST_DWithin geography.
        """
        clamped_radius = min(max(radius_km, 0.05), 10.0)
        clamped_limit = min(max(limit, 1), 500)

        # Check if table has data
        count_stmt = select(text("COUNT(*) FROM building_footprints;"))
        count_res = await self.session.execute(count_stmt)
        total_in_db = count_res.scalar() or 0

        if total_in_db == 0:
            return BuildingQueryResponse(
                available=False,
                record_count=0,
                buildings=[],
                query_coordinates=GeoPoint(latitude=latitude, longitude=longitude),
                radius_km=clamped_radius,
                disclaimer="Building footprints represent externally sourced geometry and do not establish occupancy, structural safety, or damage. No building records are available in the registry.",
                evidence=None,
            )

        radius_meters = clamped_radius * 1000.0
        sql = text("""
            SELECT 
                b.id, b.dataset_id, b.source_record_id, b.building_type, b.damage_status,
                b.area_m2, b.area_provenance, b.height, b.levels, b.address, b.source_url,
                ST_Distance(b.geom_4326::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) / 1000.0 as dist_km,
                ST_AsGeoJSON(b.geom_4326)::json as geojson,
                b.metadata_json, b.created_at
            FROM building_footprints b
            WHERE ST_DWithin(b.geom_4326::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, :radius_meters)
            ORDER BY dist_km ASC
            LIMIT :limit;
        """)

        res = await self.session.execute(
            sql,
            {
                "lat": latitude,
                "lon": longitude,
                "radius_meters": radius_meters,
                "limit": clamped_limit,
            },
        )
        rows = res.mappings().all()

        buildings: List[BuildingRecord] = []
        for r in rows:
            buildings.append(
                BuildingRecord(
                    id=str(r["id"]),
                    dataset_id=str(r["dataset_id"]),
                    source_record_id=r["source_record_id"],
                    building_type=r["building_type"],
                    damage_status=BuildingDamageStatus(r["damage_status"]),
                    area_m2=float(r["area_m2"]) if r["area_m2"] is not None else None,
                    area_provenance=r["area_provenance"],
                    height=r["height"],
                    levels=r["levels"],
                    address=r["address"],
                    source_url=r["source_url"],
                    distance_to_query_km=round(float(r["dist_km"]), 3),
                    geometry_geojson=r["geojson"],
                    metadata_json=r["metadata_json"],
                    created_at=r["created_at"],
                )
            )

        evidence = EvidenceRecord(
            evidence_id=str(uuid.uuid4()),
            parent_evidence_ids=[],
            source_type=EvidenceSourceType.GEOSPATIAL_REGISTRY,
            created_at_utc=utcnow(),
            temporal_mode=TemporalMode.STATIC_IMAGE,
            crs="EPSG:4326",
            geo_location=GeoPoint(latitude=latitude, longitude=longitude),
            geo_footprint=None,
            confidence=1.0,
            verification_state=VerificationState.CALCULATED,
            modality=Modality.DERIVED,
            sensor_metadata={
                "service": "BuildingService",
                "query": "building_proximity",
                "radius_km": clamped_radius,
                "matches": len(buildings),
            },
        )


        return BuildingQueryResponse(
            available=True,
            record_count=len(buildings),
            buildings=buildings,
            query_coordinates=GeoPoint(latitude=latitude, longitude=longitude),
            radius_km=clamped_radius,
            evidence=evidence,
        )

    async def query_buildings_polygon_intersection(
        self,
        polygon_geojson: Dict[str, Any],
        limit: int = 100,
    ) -> BuildingQueryResponse:
        """
        Finds building footprints intersecting an incident or hazard polygon.
        """
        clamped_limit = min(max(limit, 1), 500)
        geojson_str = json.dumps(polygon_geojson)

        sql = text("""
            SELECT 
                b.id, b.dataset_id, b.source_record_id, b.building_type, b.damage_status,
                b.area_m2, b.area_provenance, b.height, b.levels, b.address, b.source_url,
                ST_AsGeoJSON(b.geom_4326)::json as geojson,
                b.metadata_json, b.created_at
            FROM building_footprints b
            WHERE ST_Intersects(b.geom_4326, ST_SetSRID(ST_GeomFromGeoJSON(:poly), 4326))
            LIMIT :limit;
        """)

        res = await self.session.execute(sql, {"poly": geojson_str, "limit": clamped_limit})
        rows = res.mappings().all()

        buildings: List[BuildingRecord] = []
        for r in rows:
            buildings.append(
                BuildingRecord(
                    id=str(r["id"]),
                    dataset_id=str(r["dataset_id"]),
                    source_record_id=r["source_record_id"],
                    building_type=r["building_type"],
                    damage_status=BuildingDamageStatus(r["damage_status"]),
                    area_m2=float(r["area_m2"]) if r["area_m2"] is not None else None,
                    area_provenance=r["area_provenance"],
                    height=r["height"],
                    levels=r["levels"],
                    address=r["address"],
                    source_url=r["source_url"],
                    distance_to_query_km=None,
                    geometry_geojson=r["geojson"],
                    metadata_json=r["metadata_json"],
                    created_at=r["created_at"],
                )
            )

        evidence = EvidenceRecord(
            evidence_id=str(uuid.uuid4()),
            parent_evidence_ids=[],
            source_type=EvidenceSourceType.GEOSPATIAL_REGISTRY,
            created_at_utc=utcnow(),
            temporal_mode=TemporalMode.STATIC_IMAGE,
            crs="EPSG:4326",
            geo_location=None,
            geo_footprint=None,
            confidence=1.0,
            verification_state=VerificationState.CALCULATED,
            modality=Modality.DERIVED,
            sensor_metadata={
                "service": "BuildingService",
                "query": "polygon_intersection",
                "matches": len(buildings),
            },
        )


        return BuildingQueryResponse(
            available=True,
            record_count=len(buildings),
            buildings=buildings,
            query_coordinates=None,
            radius_km=None,
            evidence=evidence,
        )

    async def ingest_buildings(
        self,
        features: List[Dict[str, Any]],
        dataset_contract: DatasetProvenanceContract,
    ) -> Dict[str, int]:
        """
        Validates, normalizes, and inserts building footprint features into PostGIS.
        Prevents duplicate ingestion via source_record_id and dataset_id.
        Calculates geodesic area via PostGIS ST_Area(geom::geography).
        """
        # Register or get dataset
        stmt_d = select(GeospatialDataset).where(GeospatialDataset.dataset_id == dataset_contract.dataset_id)
        res_d = await self.session.execute(stmt_d)
        dataset = res_d.scalar_one_or_none()

        if not dataset:
            dataset = GeospatialDataset(
                dataset_id=dataset_contract.dataset_id,
                dataset_name=dataset_contract.dataset_name,
                source_name=dataset_contract.source_name,
                source_url=dataset_contract.source_url,
                version=dataset_contract.version,
                acquisition_date=dataset_contract.acquisition_date or datetime.now(timezone.utc),
                license=dataset_contract.license,
                attribution=dataset_contract.attribution,
                geographic_scope=dataset_contract.geographic_scope,
                geometry_type=dataset_contract.geometry_type,
                crs=dataset_contract.crs,
                source_format=dataset_contract.source_format,
                checksum=dataset_contract.checksum,
                status=dataset_contract.processing_status,
                notes=dataset_contract.notes,
                metadata_json=dataset_contract.metadata_json,
            )
            self.session.add(dataset)
            await self.session.flush()

        inserted = 0
        skipped = 0

        for f in features:
            src_id = f.get("source_record_id")
            if src_id:
                stmt_exist = select(BuildingFootprint.id).where(
                    BuildingFootprint.dataset_id == dataset.id,
                    BuildingFootprint.source_record_id == src_id,
                )
                res_exist = await self.session.execute(stmt_exist)
                if res_exist.scalar_one_or_none():
                    skipped += 1
                    continue

            raw_geom = f.get("geometry")
            if not raw_geom:
                continue

            try:
                sh_geom = shape(raw_geom)
                if not sh_geom.is_valid:
                    sh_geom = sh_geom.buffer(0)
                if sh_geom.is_empty:
                    continue
                valid_geojson = json.dumps(mapping(sh_geom))
            except Exception as e:
                logger.warning(f"Invalid building geometry skipped: {e}")
                continue

            # Insert building with ST_Area calculation
            sql_ins = text("""
                INSERT INTO building_footprints (
                    id, dataset_id, source_record_id, building_type, damage_status,
                    area_m2, area_provenance, height, levels, address, source_url,
                    geom_4326, metadata_json, created_at, updated_at
                ) VALUES (
                    gen_random_uuid(),
                    :dataset_id,
                    :source_record_id,
                    :building_type,
                    :damage_status,
                    ST_Area(ST_SetSRID(ST_GeomFromGeoJSON(:geom_geojson), 4326)::geography),
                    :area_provenance,
                    :height,
                    :levels,
                    :address,
                    :source_url,
                    ST_SetSRID(ST_GeomFromGeoJSON(:geom_geojson), 4326),
                    :metadata_json,
                    now(),
                    now()
                );
            """)

            await self.session.execute(
                sql_ins,
                {
                    "dataset_id": dataset.id,
                    "source_record_id": src_id,
                    "building_type": f.get("building_type", "GENERAL"),
                    "damage_status": "NOT_ASSESSED",  # Strict semantic rule
                    "area_provenance": "DERIVED",
                    "height": f.get("height"),
                    "levels": f.get("levels"),
                    "address": f.get("address"),
                    "source_url": f.get("source_url"),
                    "geom_geojson": valid_geojson,
                    "metadata_json": json.dumps(f.get("tags", {})),
                },
            )
            inserted += 1

        await self.session.commit()
        return {"inserted": inserted, "skipped_duplicates": skipped}
