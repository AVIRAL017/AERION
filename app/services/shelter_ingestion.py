"""
AERION — Shelter Ingestion Engine (Step 18)
Provides deterministic, provenance-aware vector ingestion for shelter records.

Invariants:
1. Validates coordinates (-90 <= lat <= 90, -180 <= lon <= 180). Rejects invalid geometry.
2. Administrative enrichment: uses Step 17 PostGIS administrative boundary containment
   to resolve official state_code, district_code, state_name, district_name.
3. Provenance tracking: computes SHA-256 hash, registers in geospatial_datasets,
   preserves raw properties into metadata_json.
4. Duplicate prevention: detects existing records by source_record_id and dataset_id.
5. Ingestion summary: provides auditable counts of valid, invalid, inserted, and skipped records.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import GeospatialDataset, Shelter as DBShelter
from app.schemas.geospatial import DatasetProvenanceContract
from app.schemas.shelter import (
    CapacityStatus,
    OperationalStatus,
    ShelterIngestionSummary,
    ShelterType,
)
from app.services.geospatial_ingestion import compute_file_sha256
from app.services.geospatial_service import GeospatialService

logger = logging.getLogger("aerion.shelter.ingestion")


class ShelterIngestionEngine:
    """
    Ingests shelter data (GeoJSON FeatureCollection or JSON records) into PostGIS.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.geo_service = GeospatialService(session)

    async def register_shelter_dataset(
        self,
        contract: DatasetProvenanceContract,
    ) -> GeospatialDataset:
        """Registers dataset-level provenance in geospatial_datasets."""
        stmt = select(GeospatialDataset).where(GeospatialDataset.dataset_id == contract.dataset_id)
        res = await self.session.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            return existing

        dataset = GeospatialDataset(
            dataset_id=contract.dataset_id,
            dataset_name=contract.dataset_name,
            source_name=contract.source_name,
            source_url=contract.source_url,
            version=contract.version,
            acquisition_date=contract.acquisition_date or datetime.now(timezone.utc),
            license=contract.license,
            attribution=contract.attribution,
            geographic_scope=contract.geographic_scope,
            geometry_type=contract.geometry_type,
            crs=contract.crs,
            source_format=contract.source_format,
            checksum=contract.checksum,
            status=contract.processing_status,
            notes=contract.notes,
            metadata_json=contract.metadata_json,
        )
        self.session.add(dataset)
        await self.session.flush()
        return dataset

    async def ingest_shelters_geojson(
        self,
        geojson_path: Path,
        dataset_contract: DatasetProvenanceContract,
        batch_size: int = 50,
    ) -> ShelterIngestionSummary:
        """
        Parses GeoJSON FeatureCollection of Point features, enriches with administrative codes,
        and persists to the shelters table.
        """
        if not geojson_path.exists():
            raise FileNotFoundError(f"Shelter file not found: {geojson_path}")

        calc_sha = compute_file_sha256(geojson_path)
        dataset_contract = dataset_contract.model_copy(update={"checksum": calc_sha})
        dataset_rec = await self.register_shelter_dataset(dataset_contract)

        with open(geojson_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        features = data.get("features", [])
        total_source = len(features)
        logger.info(f"Ingesting {total_source} shelter features from {geojson_path.name}...")

        valid_count = 0
        invalid_count = 0
        inserted_count = 0
        skipped_duplicates = 0
        missing_coords = 0
        missing_names = 0
        missing_ids = 0
        geom_errors = 0
        enriched_count = 0

        # Query existing IDs and source_record_ids to prevent primary key collisions & duplicate ingestion
        stmt_existing = select(DBShelter.id, DBShelter.source_record_id)
        existing_res = await self.session.execute(stmt_existing)
        existing_rows = existing_res.all()
        existing_ids = set(r[0] for r in existing_rows if r[0])
        existing_source_ids = set(r[1] for r in existing_rows if r[1])

        for i in range(0, total_source, batch_size):
            chunk = features[i : i + batch_size]
            for feat in chunk:
                props = feat.get("properties", {}) or {}
                geom = feat.get("geometry") or {}

                # 1. Validate coordinates
                if geom.get("type") != "Point" or not geom.get("coordinates"):
                    invalid_count += 1
                    missing_coords += 1
                    continue

                coords = geom.get("coordinates")
                try:
                    lon, lat = float(coords[0]), float(coords[1])
                except (ValueError, TypeError, IndexError):
                    invalid_count += 1
                    geom_errors += 1
                    continue

                if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
                    invalid_count += 1
                    geom_errors += 1
                    continue

                # 2. Extract identifiers
                source_id = str(
                    props.get("id")
                    or props.get("source_id")
                    or props.get("osm_id")
                    or props.get("shelter_id")
                    or ""
                ).strip()
                if not source_id:
                    missing_ids += 1
                    # Generate deterministic fallback ID from coordinates & name
                    source_id = f"GEN-{hashlib.md5(f'{lat}_{lon}_{props.get('name')}'.encode()).hexdigest()[:10]}"

                shelter_uuid = f"SHELTER-{source_id}"
                if source_id in existing_source_ids or shelter_uuid in existing_ids:
                    skipped_duplicates += 1
                    continue

                # 3. Extract name
                name = str(props.get("name") or props.get("shelter_name") or "").strip()
                if not name:
                    missing_names += 1
                    name = f"Shelter Facility ({source_id})"

                # 4. Extract operational status & capacity semantics
                op_status_str = str(props.get("operational_status", "UNKNOWN")).upper()
                if op_status_str not in OperationalStatus.__members__:
                    op_status_str = OperationalStatus.UNKNOWN.value

                cap_status_str = str(props.get("capacity_status", "NOT_PROVIDED")).upper()
                if cap_status_str not in CapacityStatus.__members__:
                    cap_status_str = CapacityStatus.NOT_PROVIDED.value

                shelter_type_str = str(props.get("shelter_type", "UNKNOWN")).upper()
                if shelter_type_str not in ShelterType.__members__:
                    shelter_type_str = ShelterType.UNKNOWN.value

                cap_total = props.get("capacity_total") or props.get("capacity")
                try:
                    cap_total = int(cap_total) if cap_total is not None else None
                except (ValueError, TypeError):
                    cap_total = None

                cap_occ = props.get("capacity_occupied") or props.get("current_occupancy")
                try:
                    cap_occ = int(cap_occ) if cap_occ is not None else None
                except (ValueError, TypeError):
                    cap_occ = None

                services_list = props.get("services", [])
                if not isinstance(services_list, list):
                    services_list = []

                # 5. Administrative enrichment using Step 17 PostGIS boundaries
                admin_res = await self.geo_service.resolve_admin_point(latitude=lat, longitude=lon)
                state_code = None
                district_code = None
                if admin_res.available:
                    state_code = admin_res.state.code if admin_res.state else None
                    district_code = admin_res.district.code if admin_res.district else None
                    enriched_count += 1

                # 6. Insert using PostGIS ST_SetSRID
                shelter_uuid = f"SHELTER-{source_id}"
                sql = text("""
                    INSERT INTO shelters (
                        id, project_id, dataset_id, source_record_id, name,
                        geom_point_4326, shelter_type, operational_status, status,
                        capacity_total, capacity_occupied, capacity_status,
                        is_generator_powered, medical_support_available,
                        accessibility, contact_information, opening_hours,
                        services, address, state_code, district_code,
                        source_registry, source_url, metadata_json,
                        last_reported_utc, created_at, updated_at
                    ) VALUES (
                        :id, NULL, :dataset_id, :source_record_id, :name,
                        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                        :shelter_type, :operational_status, :status,
                        :capacity_total, :capacity_occupied, :capacity_status,
                        :is_generator_powered, :medical_support_available,
                        :accessibility, :contact_information, :opening_hours,
                        :services, :address, :state_code, :district_code,
                        :source_registry, :source_url, :metadata_json,
                        NOW(), NOW(), NOW()
                    )
                """)

                await self.session.execute(
                    sql,
                    {
                        "id": shelter_uuid,
                        "dataset_id": dataset_rec.id,
                        "source_record_id": source_id,
                        "name": name,
                        "lon": lon,
                        "lat": lat,
                        "shelter_type": shelter_type_str,
                        "operational_status": op_status_str,
                        "status": "OPEN" if op_status_str == "CONFIRMED_OPERATIONAL" else "UNKNOWN",
                        "capacity_total": cap_total,
                        "capacity_occupied": cap_occ,
                        "capacity_status": cap_status_str,
                        "is_generator_powered": bool(props.get("is_generator_powered", False)),
                        "medical_support_available": bool(props.get("medical_support_available", False)),
                        "accessibility": props.get("accessibility"),
                        "contact_information": props.get("contact_information") or props.get("phone"),
                        "opening_hours": props.get("opening_hours"),
                        "services": services_list,
                        "address": props.get("address"),
                        "state_code": state_code,
                        "district_code": district_code,
                        "source_registry": dataset_contract.source_name,
                        "source_url": dataset_contract.source_url,
                        "metadata_json": json.dumps(props),
                    },
                )
                existing_source_ids.add(source_id)
                valid_count += 1
                inserted_count += 1

            await self.session.flush()

        logger.info(
            f"Shelter ingestion completed: {inserted_count} inserted, {skipped_duplicates} duplicates skipped, {invalid_count} invalid."
        )

        return ShelterIngestionSummary(
            dataset_id=dataset_contract.dataset_id,
            total_source_records=total_source,
            valid_records=valid_count,
            invalid_records=invalid_count,
            inserted_records=inserted_count,
            skipped_duplicates=skipped_duplicates,
            missing_coordinates=missing_coords,
            missing_names=missing_names,
            missing_source_ids=missing_ids,
            transformation_performed="WGS84 EPSG:4326 PostGIS Point validation and administrative containment enrichment",
            geometry_errors=geom_errors,
            enriched_with_admin_boundaries=enriched_count,
        )
