"""
AERION — Shelter Query Service (Step 18)
Provides deterministic spatial queries against shelter records in PostGIS.

Invariants:
1. Geodesic distance calculation: uses PostGIS ST_Distance on geography, never Euclidean approximation.
2. Zero fabrication: if no shelters are found in radius or database, returns available=False with count=0.
3. No safety score generation: exposed metric is distance_km; safety_score is strictly forbidden.
4. Operational uncertainty: exposes operational_status and capacity_status truthfully.
5. Preserves DERIVED EvidenceRecord linked to the query.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import GeospatialDataset, Shelter as DBShelter
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
from app.schemas.shelter import (
    CapacityStatus,
    OperationalStatus,
    ShelterQueryResponse,
    ShelterRecord,
    ShelterType,
)

logger = logging.getLogger("aerion.shelter.service")


class ShelterService:
    """
    Executes PostGIS queries for shelters and evacuation points.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_shelter_by_id(self, shelter_id: str) -> Optional[ShelterRecord]:
        """Retrieves a single shelter record by its unique ID."""
        sql = text("""
            SELECT 
                s.id, s.name, ST_Y(s.geom_point_4326) as lat, ST_X(s.geom_point_4326) as lon,
                s.shelter_type, s.operational_status, s.capacity_total, s.capacity_occupied,
                s.capacity_status, s.is_generator_powered, s.medical_support_available,
                s.accessibility, s.contact_information, s.opening_hours, s.services,
                s.address, s.state_code, s.district_code, s.source_registry,
                s.source_record_id, s.source_url, s.dataset_id, s.last_reported_utc,
                s.created_at, s.metadata_json,
                d.dataset_name, b_state.name as state_name, b_dist.name as district_name
            FROM shelters s
            LEFT JOIN geospatial_datasets d ON s.dataset_id = d.id
            LEFT JOIN administrative_boundaries b_state ON s.state_code = b_state.state_code AND b_state.level = 'ADM1'
            LEFT JOIN administrative_boundaries b_dist ON s.district_code = b_dist.district_code AND b_dist.level = 'ADM2'
            WHERE s.id = :shelter_id;
        """)

        res = await self.session.execute(sql, {"shelter_id": shelter_id})
        r = res.fetchone()
        if not r:
            return None

        return ShelterRecord(
            shelter_id=r[0],
            name=r[1],
            location=GeoPoint(latitude=float(r[2]), longitude=float(r[3])),
            shelter_type=ShelterType(r[4]) if r[4] in ShelterType.__members__ else ShelterType.UNKNOWN,
            operational_status=OperationalStatus(r[5]) if r[5] in OperationalStatus.__members__ else OperationalStatus.UNKNOWN,
            capacity_total=r[6],
            capacity_occupied=r[7],
            capacity_status=CapacityStatus(r[8]) if r[8] in CapacityStatus.__members__ else CapacityStatus.NOT_PROVIDED,
            is_generator_powered=bool(r[9]),
            medical_support_available=bool(r[10]),
            accessibility=r[11],
            contact_information=r[12],
            opening_hours=r[13],
            services=r[14] or [],
            address=r[15],
            state_code=r[16],
            district_code=r[17],
            state_name=r[26],
            district_name=r[27],
            distance_km=None,
            source_registry=r[18],
            source_record_id=r[19],
            source_url=r[20],
            dataset_id=str(r[21]) if r[21] else None,
            last_reported_utc=r[22] or datetime.now(timezone.utc),
            created_at_utc=r[23] or datetime.now(timezone.utc),
            metadata_json=r[24] or {},
        )

    async def query_shelters(
        self,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        radius_km: Optional[float] = None,
        shelter_type: Optional[str] = None,
        operational_status: Optional[str] = None,
        state_code: Optional[str] = None,
        district_code: Optional[str] = None,
        limit: int = 50,
    ) -> ShelterQueryResponse:
        """
        Executes proximity or attribute-filtered shelter search using PostGIS.
        Calculates exact geodesic distance in km when coordinates are provided.
        """
        params: Dict[str, Any] = {"limit": limit}
        where_clauses = ["1=1"]

        has_coords = latitude is not None and longitude is not None
        query_pt = None

        if has_coords:
            query_pt = GeoPoint(latitude=latitude, longitude=longitude)
            params["lat"] = latitude
            params["lon"] = longitude
            if radius_km is not None:
                params["radius_meters"] = float(radius_km) * 1000.0
                where_clauses.append(
                    "ST_DWithin(s.geom_point_4326::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, :radius_meters)"
                )

        if shelter_type:
            params["shelter_type"] = shelter_type.upper()
            where_clauses.append("s.shelter_type = :shelter_type")

        if operational_status:
            params["operational_status"] = operational_status.upper()
            where_clauses.append("s.operational_status = :operational_status")

        if state_code:
            params["state_code"] = state_code
            where_clauses.append("s.state_code = :state_code")

        if district_code:
            params["district_code"] = district_code
            where_clauses.append("s.district_code = :district_code")

        distance_sql = (
            "ST_Distance(s.geom_point_4326::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) / 1000.0 as dist_km"
            if has_coords
            else "NULL as dist_km"
        )
        order_sql = "dist_km ASC NULLS LAST, s.name ASC" if has_coords else "s.name ASC"

        where_sql = " AND ".join(where_clauses)
        sql = text(f"""
            SELECT 
                s.id, s.name, ST_Y(s.geom_point_4326) as lat, ST_X(s.geom_point_4326) as lon,
                s.shelter_type, s.operational_status, s.capacity_total, s.capacity_occupied,
                s.capacity_status, s.is_generator_powered, s.medical_support_available,
                s.accessibility, s.contact_information, s.opening_hours, s.services,
                s.address, s.state_code, s.district_code, s.source_registry,
                s.source_record_id, s.source_url, s.dataset_id, s.last_reported_utc,
                s.created_at, s.metadata_json, {distance_sql}
            FROM shelters s
            WHERE {where_sql}
            ORDER BY {order_sql}
            LIMIT :limit;
        """)

        res = await self.session.execute(sql, params)
        rows = res.fetchall()

        if not rows:
            return ShelterQueryResponse(
                available=False,
                record_count=0,
                shelters=[],
                query_point=query_pt,
                radius_km=radius_km,
                evidence=None,
                provenance=None,
            )

        shelters = []
        for r in rows:
            dist = float(r[25]) if r[25] is not None else None
            shelters.append(
                ShelterRecord(
                    shelter_id=r[0],
                    name=r[1],
                    location=GeoPoint(latitude=float(r[2]), longitude=float(r[3])),
                    shelter_type=ShelterType(r[4]) if r[4] in ShelterType.__members__ else ShelterType.UNKNOWN,
                    operational_status=OperationalStatus(r[5]) if r[5] in OperationalStatus.__members__ else OperationalStatus.UNKNOWN,
                    capacity_total=r[6],
                    capacity_occupied=r[7],
                    capacity_status=CapacityStatus(r[8]) if r[8] in CapacityStatus.__members__ else CapacityStatus.NOT_PROVIDED,
                    is_generator_powered=bool(r[9]),
                    medical_support_available=bool(r[10]),
                    accessibility=r[11],
                    contact_information=r[12],
                    opening_hours=r[13],
                    services=r[14] or [],
                    address=r[15],
                    state_code=r[16],
                    district_code=r[17],
                    distance_km=dist,
                    source_registry=r[18],
                    source_record_id=r[19],
                    source_url=r[20],
                    dataset_id=str(r[21]) if r[21] else None,
                    last_reported_utc=r[22] or datetime.now(timezone.utc),
                    created_at_utc=r[23] or datetime.now(timezone.utc),
                    metadata_json=r[24] or {},
                )
            )

        # Build DERIVED evidence record
        evidence_rec = EvidenceRecord(
            evidence_id=str(uuid.uuid4()),
            parent_evidence_ids=[],
            source_type=EvidenceSourceType.SHELTER_REGISTRY,
            created_at_utc=utcnow(),
            temporal_mode=TemporalMode.STATIC_IMAGE,
            crs="EPSG:4326",
            geo_location=query_pt,
            geo_footprint=None,
            confidence=1.0,
            verification_state=VerificationState.CALCULATED,
            modality=Modality.DERIVED,
            sensor_metadata={
                "query": "shelter_spatial_lookup",
                "radius_km": radius_km,
                "matches_returned": len(shelters),
                "nearest_distance_km": shelters[0].distance_km if shelters and shelters[0].distance_km is not None else None,
            },
        )

        return ShelterQueryResponse(
            available=True,
            record_count=len(shelters),
            shelters=shelters,
            query_point=query_pt,
            radius_km=radius_km,
            evidence=evidence_rec,
        )
