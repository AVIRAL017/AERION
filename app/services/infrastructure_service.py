"""
AERION — Critical Infrastructure Query & Ingestion Service (Step 20)
Executes deterministic spatial queries against critical infrastructure in PostGIS.

Invariants:
1. Operational status strictly defaults to UNKNOWN for externally provided reference data.
2. Capacity and emergency readiness are NEVER fabricated.
3. Administrative enrichment resolves state and district codes via PostGIS spatial containment.
4. Preserves DERIVED EvidenceRecord linked to the query.
5. Ingestion validates geometry, enriches administrative attributes, and prevents duplicates.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from shapely.geometry import shape, mapping
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CriticalInfrastructure, GeospatialDataset
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
from app.schemas.infrastructure import (
    CriticalInfrastructureRecord,
    InfrastructureOperationalStatus,
    InfrastructureQueryResponse,
    InfrastructureType,
)

logger = logging.getLogger("aerion.infrastructure.service")


class InfrastructureService:
    """
    Handles queries and ingestion for critical infrastructure facilities.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_infrastructure_by_id(self, infra_id: str) -> Optional[CriticalInfrastructureRecord]:
        """Retrieves a single critical infrastructure facility by ID."""
        sql = text("""
            SELECT 
                ci.id, ci.dataset_id, ci.source_record_id, ci.name, ci.infrastructure_type,
                ci.subtype, ci.operational_status, ci.address, ci.state_code, ci.district_code,
                ci.source_url, ST_Y(ST_Centroid(ci.geom_4326)) as lat, ST_X(ST_Centroid(ci.geom_4326)) as lon,
                ST_AsGeoJSON(ci.geom_4326)::json as geojson,
                ci.metadata_json, ci.created_at,
                b_state.name as state_name, b_dist.name as district_name
            FROM critical_infrastructure ci
            LEFT JOIN administrative_boundaries b_state ON ci.state_code = b_state.state_code AND b_state.level = 'ADM1'
            LEFT JOIN administrative_boundaries b_dist ON ci.district_code = b_dist.district_code AND b_dist.level = 'ADM2'
            WHERE ci.id = CAST(:infra_id AS UUID);
        """)
        res = await self.session.execute(sql, {"infra_id": infra_id})

        row = res.mappings().first()
        if not row:
            return None

        return CriticalInfrastructureRecord(
            id=str(row["id"]),
            dataset_id=str(row["dataset_id"]),
            source_record_id=row["source_record_id"],
            name=row["name"],
            infrastructure_type=InfrastructureType(row["infrastructure_type"]),
            subtype=row["subtype"],
            operational_status=InfrastructureOperationalStatus(row["operational_status"]),
            address=row["address"],
            state_code=row["state_code"],
            state_name=row["state_name"],
            district_code=row["district_code"],
            district_name=row["district_name"],
            latitude=float(row["lat"]),
            longitude=float(row["lon"]),
            distance_to_query_km=None,
            source_url=row["source_url"],
            geometry_geojson=row["geojson"],
            metadata_json=row["metadata_json"],
            created_at=row["created_at"],
        )

    async def query_infrastructure_proximity(
        self,
        latitude: float,
        longitude: float,
        radius_km: float = 5.0,
        infrastructure_type: Optional[str] = None,
        state_code: Optional[str] = None,
        district_code: Optional[str] = None,
        limit: int = 50,
    ) -> InfrastructureQueryResponse:
        """
        Finds critical infrastructure facilities within radius_km of coordinates.
        Supports filtering by infrastructure_type, state_code, and district_code.
        """
        clamped_radius = min(max(radius_km, 0.1), 50.0)
        clamped_limit = min(max(limit, 1), 200)

        count_stmt = select(text("COUNT(*) FROM critical_infrastructure;"))
        count_res = await self.session.execute(count_stmt)
        total_in_db = count_res.scalar() or 0

        if total_in_db == 0:
            return InfrastructureQueryResponse(
                available=False,
                record_count=0,
                facilities=[],
                query_coordinates=GeoPoint(latitude=latitude, longitude=longitude),
                radius_km=clamped_radius,
                disclaimer="Critical infrastructure records do not establish current operational status unless the source explicitly provides such status. No records available in the registry.",
                evidence=None,
            )

        radius_meters = clamped_radius * 1000.0
        filter_clauses = [
            "ST_DWithin(ci.geom_4326::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, :radius_meters)"
        ]
        params: Dict[str, Any] = {
            "lat": latitude,
            "lon": longitude,
            "radius_meters": radius_meters,
            "limit": clamped_limit,
        }

        if infrastructure_type:
            filter_clauses.append("ci.infrastructure_type = :infra_type")
            params["infra_type"] = infrastructure_type.upper()

        if state_code:
            filter_clauses.append("ci.state_code = :state_code")
            params["state_code"] = state_code

        if district_code:
            filter_clauses.append("ci.district_code = :district_code")
            params["district_code"] = district_code

        where_sql = " AND ".join(filter_clauses)

        sql = text(f"""
            SELECT 
                ci.id, ci.dataset_id, ci.source_record_id, ci.name, ci.infrastructure_type,
                ci.subtype, ci.operational_status, ci.address, ci.state_code, ci.district_code,
                ci.source_url, ST_Y(ST_Centroid(ci.geom_4326)) as lat, ST_X(ST_Centroid(ci.geom_4326)) as lon,
                ST_Distance(ci.geom_4326::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) / 1000.0 as dist_km,
                ST_AsGeoJSON(ci.geom_4326)::json as geojson,
                ci.metadata_json, ci.created_at,
                b_state.name as state_name, b_dist.name as district_name
            FROM critical_infrastructure ci
            LEFT JOIN administrative_boundaries b_state ON ci.state_code = b_state.state_code AND b_state.level = 'ADM1'
            LEFT JOIN administrative_boundaries b_dist ON ci.district_code = b_dist.district_code AND b_dist.level = 'ADM2'
            WHERE {where_sql}
            ORDER BY dist_km ASC
            LIMIT :limit;
        """)

        res = await self.session.execute(sql, params)
        rows = res.mappings().all()

        facilities: List[CriticalInfrastructureRecord] = []
        for r in rows:
            facilities.append(
                CriticalInfrastructureRecord(
                    id=str(r["id"]),
                    dataset_id=str(r["dataset_id"]),
                    source_record_id=r["source_record_id"],
                    name=r["name"],
                    infrastructure_type=InfrastructureType(r["infrastructure_type"]),
                    subtype=r["subtype"],
                    operational_status=InfrastructureOperationalStatus(r["operational_status"]),
                    address=r["address"],
                    state_code=r["state_code"],
                    state_name=r["state_name"],
                    district_code=r["district_code"],
                    district_name=r["district_name"],
                    latitude=float(r["lat"]),
                    longitude=float(r["lon"]),
                    distance_to_query_km=round(float(r["dist_km"]), 3),
                    source_url=r["source_url"],
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
                "service": "InfrastructureService",
                "query": "infrastructure_proximity",
                "radius_km": clamped_radius,
                "matches": len(facilities),
            },
        )


        return InfrastructureQueryResponse(
            available=True,
            record_count=len(facilities),
            facilities=facilities,
            query_coordinates=GeoPoint(latitude=latitude, longitude=longitude),
            radius_km=clamped_radius,
            evidence=evidence,
        )

    async def ingest_infrastructure(
        self,
        features: List[Dict[str, Any]],
        dataset_contract: DatasetProvenanceContract,
    ) -> Dict[str, int]:
        """
        Validates, normalizes, enriches with administrative codes, and inserts critical infrastructure records into PostGIS.
        Prevents duplicate ingestion via source_record_id and dataset_id.
        """
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
                stmt_exist = select(CriticalInfrastructure.id).where(
                    CriticalInfrastructure.dataset_id == dataset.id,
                    CriticalInfrastructure.source_record_id == src_id,
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
                logger.warning(f"Invalid infrastructure geometry skipped: {e}")
                continue

            # Resolve administrative boundaries (state and district) via PostGIS containment
            enrich_sql = text("""
                SELECT 
                    (SELECT state_code FROM administrative_boundaries WHERE level = 'ADM1' AND ST_Contains(geom_4326, ST_SetSRID(ST_GeomFromGeoJSON(:geom_geojson), 4326)) LIMIT 1) as state_code,
                    (SELECT district_code FROM administrative_boundaries WHERE level = 'ADM2' AND ST_Contains(geom_4326, ST_SetSRID(ST_GeomFromGeoJSON(:geom_geojson), 4326)) LIMIT 1) as district_code;
            """)
            enrich_res = await self.session.execute(enrich_sql, {"geom_geojson": valid_geojson})
            admin_row = enrich_res.mappings().first()
            state_code = admin_row["state_code"] if admin_row else None
            district_code = admin_row["district_code"] if admin_row else None

            sql_ins = text("""
                INSERT INTO critical_infrastructure (
                    id, dataset_id, source_record_id, name, infrastructure_type,
                    subtype, operational_status, address, state_code, district_code,
                    source_url, geom_4326, metadata_json, created_at, updated_at
                ) VALUES (
                    gen_random_uuid(),
                    :dataset_id,
                    :source_record_id,
                    :name,
                    :infrastructure_type,
                    :subtype,
                    :operational_status,
                    :address,
                    :state_code,
                    :district_code,
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
                    "name": f.get("name", "Unnamed Facility"),
                    "infrastructure_type": f.get("infrastructure_type", "OTHER"),
                    "subtype": f.get("subtype"),
                    "operational_status": "UNKNOWN",  # Strict semantic rule: never infer operational status
                    "address": f.get("address"),
                    "state_code": state_code,
                    "district_code": district_code,
                    "source_url": f.get("source_url"),
                    "geom_geojson": valid_geojson,
                    "metadata_json": json.dumps(f.get("tags", {})),
                },
            )
            inserted += 1

        await self.session.commit()
        return {"inserted": inserted, "skipped_duplicates": skipped}
