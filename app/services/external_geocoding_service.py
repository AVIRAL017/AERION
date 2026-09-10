"""
AERION — External Geocoding Service (Steps 22–23)
Provides forward geocoding (place query -> coordinates) and reverse geocoding
(coordinates -> location metadata).
Uses OpenStreetMap Nominatim and Open-Meteo Geocoding with strict User-Agent policies,
in-memory TTL caching, input length bounds, and coordinate bounds validation.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional
import httpx

from app.core.cache import geocoding_cache
from app.schemas.evidence import (
    EvidenceRecord,
    EvidenceSourceType,
    GeoPoint,
    Modality,
    TemporalMode,
    VerificationState,
    utcnow,
)
from app.schemas.external import NormalizedGeocodeResult, ProviderStatus

logger = logging.getLogger("aerion.external.geocoding")


class ExternalGeocodingService:
    """
    Normalized geocoding service connecting to OpenStreetMap Nominatim and Open-Meteo Geocoding.
    """

    def __init__(
        self,
        nominatim_url: str = "https://nominatim.openstreetmap.org",
        open_meteo_url: str = "https://geocoding-api.open-meteo.com/v1",
        timeout_seconds: float = 10.0,
    ):
        self.nominatim_url = nominatim_url
        self.open_meteo_url = open_meteo_url
        self.timeout = timeout_seconds
        self.headers = {
            "User-Agent": "AERION-Geospatial-Platform/1.0 (aerion-ops@internal.local)"
        }

    async def forward_geocode(
        self,
        query: str,
        limit: int = 1,
        use_cache: bool = True,
    ) -> List[NormalizedGeocodeResult]:
        """
        Forward geocoding: converts textual place/address query into WGS84 coordinates and administrative context.
        """
        cleaned_query = query.strip()
        if not cleaned_query or len(cleaned_query) > 200:
            logger.warning("Geocoding query empty or exceeds 200 characters.")
            return []

        cache_key = f"geocode:forward:{cleaned_query.lower()}:{limit}"
        if use_cache:
            cached_val = await geocoding_cache.get(cache_key)
            if cached_val:
                return [c.model_copy(update={"cached": True}) for c in cached_val]

        results: List[NormalizedGeocodeResult] = []

        # Try Open-Meteo Geocoding first (fast, generous rate limits)
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(
                    f"{self.open_meteo_url}/search",
                    params={"name": cleaned_query, "count": limit, "language": "en"},
                    headers=self.headers,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get("results", []):
                        lat = float(item["latitude"])
                        lon = float(item["longitude"])
                        name = item.get("name", "")
                        admin1 = item.get("admin1", "")
                        country = item.get("country", "India")
                        country_code = item.get("country_code", "IN")

                        display_name = f"{name}, {admin1}, {country}" if admin1 else f"{name}, {country}"

                        evidence_rec = EvidenceRecord(
                            evidence_id=str(uuid.uuid4()),
                            parent_evidence_ids=[],
                            source_type=EvidenceSourceType.GEOSPATIAL_REGISTRY,
                            created_at_utc=utcnow(),
                            temporal_mode=TemporalMode.STATIC_IMAGE,
                            crs="EPSG:4326",
                            geo_location=GeoPoint(latitude=lat, longitude=lon),
                            modality=Modality.EXTERNALLY_PROVIDED,
                            confidence=0.9,
                            verification_state=VerificationState.CALCULATED,
                            sensor_metadata={"provider": "Open-Meteo-Geocoding"},
                        )

                        results.append(
                            NormalizedGeocodeResult(
                                provider_name="Open-Meteo-Geocoding",
                                status=ProviderStatus.AVAILABLE,
                                query=cleaned_query,
                                latitude=lat,
                                longitude=lon,
                                display_name=display_name,
                                locality=name,
                                state=admin1 or None,
                                country=country,
                                country_code=country_code,
                                confidence=0.9,
                                fetched_at_utc=utcnow(),
                                raw_properties=item,
                                cached=False,
                                evidence=evidence_rec,
                            )
                        )
        except Exception as e:
            logger.warning(f"Open-Meteo geocoding failed: {e}. Falling back to Nominatim...")

        # Fallback to Nominatim if no results
        if not results:
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.get(
                        f"{self.nominatim_url}/search",
                        params={"q": cleaned_query, "format": "jsonv2", "limit": limit, "addressdetails": 1},
                        headers=self.headers,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        for item in data:
                            lat = float(item["lat"])
                            lon = float(item["lon"])
                            addr = item.get("address", {})
                            display = item.get("display_name", "")

                            evidence_rec = EvidenceRecord(
                                evidence_id=str(uuid.uuid4()),
                                parent_evidence_ids=[],
                                source_type=EvidenceSourceType.GEOSPATIAL_REGISTRY,
                                created_at_utc=utcnow(),
                                temporal_mode=TemporalMode.STATIC_IMAGE,
                                crs="EPSG:4326",
                                geo_location=GeoPoint(latitude=lat, longitude=lon),
                                modality=Modality.EXTERNALLY_PROVIDED,
                                confidence=0.85,
                                verification_state=VerificationState.CALCULATED,
                                sensor_metadata={"provider": "OSM-Nominatim"},
                            )

                            results.append(
                                NormalizedGeocodeResult(
                                    provider_name="OSM-Nominatim",
                                    status=ProviderStatus.AVAILABLE,
                                    query=cleaned_query,
                                    latitude=lat,
                                    longitude=lon,
                                    display_name=display,
                                    locality=addr.get("city") or addr.get("town") or addr.get("village") or addr.get("suburb"),
                                    district=addr.get("state_district") or addr.get("county"),
                                    state=addr.get("state"),
                                    country=addr.get("country", "India"),
                                    country_code=(addr.get("country_code") or "in").upper(),
                                    postcode=addr.get("postcode"),
                                    confidence=0.85,
                                    fetched_at_utc=utcnow(),
                                    raw_properties=item,
                                    cached=False,
                                    evidence=evidence_rec,
                                )
                            )
            except Exception as e:
                logger.warning(f"Nominatim search failed: {e}")

        if results:
            await geocoding_cache.set(cache_key, results)
        return results

    async def reverse_geocode(
        self,
        latitude: float,
        longitude: float,
        use_cache: bool = True,
    ) -> Optional[NormalizedGeocodeResult]:
        """
        Reverse geocoding: resolves WGS84 coordinates into human-readable place description and administrative hierarchy.
        """
        if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0):
            logger.warning(f"Reverse geocode coordinates ({latitude}, {longitude}) out of WGS84 bounds.")
            return None

        cache_key = f"geocode:reverse:{round(latitude, 4)}:{round(longitude, 4)}"
        if use_cache:
            cached_val = await geocoding_cache.get(cache_key)
            if cached_val:
                return cached_val.model_copy(update={"cached": True})

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(
                    f"{self.nominatim_url}/reverse",
                    params={
                        "lat": latitude,
                        "lon": longitude,
                        "format": "jsonv2",
                        "addressdetails": 1,
                    },
                    headers=self.headers,
                )
                if resp.status_code != 200:
                    logger.warning(f"Nominatim reverse returned status {resp.status_code}")
                    return None

                data = resp.json()
                addr = data.get("address", {})
                display = data.get("display_name", f"{latitude}, {longitude}")

                evidence_rec = EvidenceRecord(
                    evidence_id=str(uuid.uuid4()),
                    parent_evidence_ids=[],
                    source_type=EvidenceSourceType.GEOSPATIAL_REGISTRY,
                    created_at_utc=utcnow(),
                    temporal_mode=TemporalMode.STATIC_IMAGE,
                    crs="EPSG:4326",
                    geo_location=GeoPoint(latitude=latitude, longitude=longitude),
                    modality=Modality.EXTERNALLY_PROVIDED,
                    confidence=0.9,
                    verification_state=VerificationState.CALCULATED,
                    sensor_metadata={"provider": "OSM-Nominatim", "osm_id": data.get("osm_id")},
                )

                result = NormalizedGeocodeResult(
                    provider_name="OSM-Nominatim",
                    status=ProviderStatus.AVAILABLE,
                    query=f"{latitude},{longitude}",
                    latitude=latitude,
                    longitude=longitude,
                    display_name=display,
                    locality=addr.get("city") or addr.get("town") or addr.get("village") or addr.get("suburb"),
                    district=addr.get("state_district") or addr.get("county"),
                    state=addr.get("state"),
                    country=addr.get("country", "India"),
                    country_code=(addr.get("country_code") or "in").upper(),
                    postcode=addr.get("postcode"),
                    confidence=0.9,
                    fetched_at_utc=utcnow(),
                    raw_properties=data,
                    cached=False,
                    evidence=evidence_rec,
                )

                await geocoding_cache.set(cache_key, result)
                return result

        except Exception as e:
            logger.warning(f"Nominatim reverse geocode failed: {e}")
            return None
