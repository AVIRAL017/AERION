"""
AERION — Geospatial Query Service (Step 17)
Provides deterministic spatial queries against administrative boundaries
and historical flood hazard records in PostGIS.

Rules & Invariants:
1. Zero fabrication: if a point does not intersect any boundary or hazard, return explicit available=False or empty list.
2. Modality & Provenance: returns EXTERNALLY_PROVIDED for static datasets and DERIVED for spatial containment intersections.
3. Coordinate Separation: only operates on verified geographic coordinates (EPSG:4326). Pixel coordinates are strictly forbidden.
4. Historical flood hazard is reference evidence, never live status.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AdministrativeBoundary, GeospatialDataset, HistoricalHazardRecord
from app.schemas.evidence import (
    EvidenceRecord,
    EvidenceSourceType,
    GeoPoint,
    Modality,
    TemporalMode,
    VerificationState,
    utcnow,
)
from app.schemas.geospatial import (
    AdminBoundaryResolution,
    AdminUnitInfo,
    BorderContractStatus,
    DatasetProvenanceContract,
    HistoricalHazardItem,
    HistoricalHazardQueryResponse,
)

logger = logging.getLogger("aerion.geospatial.service")


class GeospatialService:
    """
    Executes PostGIS queries for administrative resolution and historical hazard intelligence.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all_datasets(self) -> List[DatasetProvenanceContract]:
        """Returns provenance contracts for all indexed geospatial datasets."""
        stmt = select(GeospatialDataset).order_by(GeospatialDataset.created_at.desc())
        res = await self.session.execute(stmt)
        records = res.scalars().all()
        return [
            DatasetProvenanceContract(
                dataset_id=r.dataset_id,
                dataset_name=r.dataset_name,
                source_name=r.source_name,
                source_url=r.source_url,
                version=r.version,
                acquisition_date=r.acquisition_date,
                license=r.license,
                attribution=r.attribution,
                geographic_scope=r.geographic_scope,
                geometry_type=r.geometry_type,
                crs=r.crs,
                source_format=r.source_format,
                processing_status=r.status,
                checksum=r.checksum,
                notes=r.notes,
                metadata_json=r.metadata_json or {},
            )
            for r in records
        ]

    async def resolve_admin_point(
        self,
        latitude: float,
        longitude: float,
    ) -> AdminBoundaryResolution:
        """
        Resolves WGS84 point into containing administrative hierarchy (Country -> State -> District).
        Executes PostGIS ST_Contains query.
        """
        query_pt = GeoPoint(latitude=latitude, longitude=longitude)

        # PostGIS spatial containment query
        sql = text("""
            SELECT 
                b.id, b.level, b.country_code, b.state_code, b.district_code,
                b.name, b.name_canonical, b.metadata_json,
                d.dataset_id, d.dataset_name, d.source_name, d.version, d.license, d.attribution,
                d.geographic_scope, d.geometry_type, d.crs, d.source_format, d.checksum
            FROM administrative_boundaries b
            JOIN geospatial_datasets d ON b.dataset_id = d.id
            WHERE ST_Contains(b.geom_4326, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
            ORDER BY 
                CASE b.level
                    WHEN 'ADM0' THEN 1
                    WHEN 'ADM1' THEN 2
                    WHEN 'ADM2' THEN 3
                    ELSE 4
                END ASC;
        """)

        res = await self.session.execute(sql, {"lon": longitude, "lat": latitude})
        rows = res.fetchall()

        if not rows:
            logger.info(f"Point ({latitude}, {longitude}) is outside indexed administrative boundaries.")
            return AdminBoundaryResolution(
                available=False,
                query_coordinates=query_pt,
                country=None,
                state=None,
                district=None,
                evidence=None,
                provenance=None,
            )

        country_unit = None
        state_unit = None
        district_unit = None
        top_dataset_meta = None

        for row in rows:
            level = row[1]
            country_code = row[2]
            state_code = row[3]
            district_code = row[4]
            name = row[5]
            canonical = row[6]
            meta = row[7] or {}

            unit = AdminUnitInfo(
                level=level,
                name=name,
                canonical_name=canonical,
                code=district_code if level == "ADM2" else (state_code if level == "ADM1" else country_code),
                country_code=country_code,
                source_agency=meta.get("src_agency"),
                metadata=meta,
            )

            if level == "ADM0":
                country_unit = unit
            elif level == "ADM1":
                state_unit = unit
                if not country_unit:
                    # In India NWIC dataset, state implies India
                    country_unit = AdminUnitInfo(
                        level="ADM0",
                        name="India",
                        canonical_name="India",
                        code="IND",
                        country_code="IND",
                        source_agency="Survey of India (SOI)",
                        metadata={"source": "Inferred from national state boundary dataset"},
                    )
            elif level == "ADM2":
                district_unit = unit

            if top_dataset_meta is None:
                top_dataset_meta = DatasetProvenanceContract(
                    dataset_id=row[8],
                    dataset_name=row[9],
                    source_name=row[10],
                    version=row[11],
                    license=row[12],
                    attribution=row[13],
                    geographic_scope=row[14],
                    geometry_type=row[15],
                    crs=row[16],
                    source_format=row[17],
                    checksum=row[18],
                )

        # Build DERIVED evidence record
        evidence_rec = EvidenceRecord(
            evidence_id=str(uuid.uuid4()),
            parent_evidence_ids=[],
            source_type=EvidenceSourceType.GEOSPATIAL_REGISTRY,
            created_at_utc=utcnow(),
            temporal_mode=TemporalMode.STATIC_IMAGE,
            crs="EPSG:4326",
            geo_location=query_pt,
            geo_footprint=None,
            confidence=1.0,
            verification_state=VerificationState.CALCULATED,
            modality=Modality.DERIVED,
            sensor_metadata={
                "query": "administrative_containment",
                "resolved_levels": [u.level for u in [country_unit, state_unit, district_unit] if u],
                "state": state_unit.name if state_unit else None,
                "district": district_unit.name if district_unit else None,
            },
        )

        return AdminBoundaryResolution(
            available=True,
            query_coordinates=query_pt,
            country=country_unit,
            state=state_unit,
            district=district_unit,
            evidence=evidence_rec,
            provenance=top_dataset_meta,
        )

    async def query_historical_hazards(
        self,
        latitude: float,
        longitude: float,
        radius_km: float = 25.0,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        hazard_type: str = "HISTORICAL_FLOOD",
    ) -> HistoricalHazardQueryResponse:
        """
        Queries historical hazard features within radius_km using PostGIS ST_DWithin on geography.
        """
        radius_meters = float(radius_km) * 1000.0
        query_pt = GeoPoint(latitude=latitude, longitude=longitude)

        sql = text("""
            SELECT 
                h.id, h.hazard_type, h.source_event_id, h.event_date_start, h.event_date_end,
                h.state_name, h.district_name, h.cause, h.severity_reported, h.impact_summary,
                h.is_live_status, ST_AsGeoJSON(h.geom_4326) as geom_json, h.metadata_json
            FROM historical_hazard_records h
            WHERE h.hazard_type = :hazard_type
              AND ST_DWithin(h.geom_4326::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, :radius_meters)
            ORDER BY h.event_date_start DESC NULLS LAST
            LIMIT 100;
        """)

        res = await self.session.execute(
            sql,
            {
                "hazard_type": hazard_type,
                "lon": longitude,
                "lat": latitude,
                "radius_meters": radius_meters,
            },
        )
        rows = res.fetchall()

        items = []
        for r in rows:
            geom = json.loads(r[11]) if r[11] else None
            items.append(
                HistoricalHazardItem(
                    id=str(r[0]),
                    hazard_type=r[1],
                    source_event_id=r[2],
                    event_date_start=r[3],
                    event_date_end=r[4],
                    state_name=r[5],
                    district_name=r[6],
                    cause=r[7],
                    severity_reported=r[8] or "UNAVAILABLE",
                    impact_summary=r[9],
                    is_live_status=False,  # Strict Invariant
                    geometry_geojson=geom,
                    metadata=r[12] or {},
                )
            )

        evidence_rec = EvidenceRecord(
            evidence_id=str(uuid.uuid4()),
            parent_evidence_ids=[],
            source_type=EvidenceSourceType.HISTORICAL_HAZARD_INVENTORY,
            created_at_utc=utcnow(),
            temporal_mode=TemporalMode.STATIC_IMAGE,
            crs="EPSG:4326",
            geo_location=query_pt,
            geo_footprint=None,
            confidence=1.0,
            verification_state=VerificationState.CORROBORATED,
            modality=Modality.EXTERNALLY_PROVIDED,
            sensor_metadata={
                "query": "historical_hazard_proximity",
                "radius_km": radius_km,
                "matches_found": len(items),
                "is_live_status": False,
            },
        )

        return HistoricalHazardQueryResponse(
            is_historical_reference_only=True,
            record_count=len(items),
            records=items,
            query_point=query_pt,
            radius_km=radius_km,
            evidence=evidence_rec,
        )

    async def get_border_contract_status(self) -> BorderContractStatus:
        """
        Reports operational international boundary availability.
        Delegates to InternationalBoundaryService to enforce the rule that ADM0/ADM1/ADM2
        boundaries are never used as a substitute for the authoritative operational international border.
        """
        from app.services.international_boundary_service import InternationalBoundaryService
        svc = InternationalBoundaryService(self.session)
        return await svc.get_border_contract_status()
