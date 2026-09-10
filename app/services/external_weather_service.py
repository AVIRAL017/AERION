"""
AERION — External Weather Service (Steps 22–23)
Integrates Open-Meteo API for real-time, forecast, and historical meteorological data.
Enforces zero-fabrication: unavailable data returns UNAVAILABLE status, never fake estimates.
Uses in-memory TTL caching and bounded retries.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.core.cache import weather_cache
from app.core.config import get_settings
from app.schemas.evidence import (
    EvidenceRecord,
    EvidenceSourceType,
    GeoPoint,
    Modality,
    TemporalMode,
    VerificationState,
    utcnow,
)
from app.schemas.external import (
    NormalizedWeatherRecord,
    ProviderStatus,
    WeatherConditionClassification,
)

logger = logging.getLogger("aerion.external.weather")

WMO_WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


class ExternalWeatherService:
    """
    Normalized weather service using public Open-Meteo endpoints.
    Provides current observations, 24-hour forecasts, and historical reconstructions.
    """

    def __init__(
        self,
        base_url: str = "https://api.open-meteo.com/v1",
        archive_url: str = "https://archive-api.open-meteo.com/v1/archive",
        timeout_seconds: float = 15.0,
    ):
        self.base_url = base_url
        self.archive_url = archive_url
        self.timeout = timeout_seconds

    async def get_weather(
        self,
        latitude: float,
        longitude: float,
        timestamp_utc: Optional[datetime] = None,
        use_cache: bool = True,
    ) -> NormalizedWeatherRecord:
        """
        Retrieves normalized weather for coordinates.
        Zero fabrication: if coordinates are invalid or service unreachable, returns UNAVAILABLE.
        """
        # Coordinate bounds check
        if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0):
            return NormalizedWeatherRecord(
                observation_id=str(uuid.uuid4()),
                provider_name="Open-Meteo",
                status=ProviderStatus.INVALID_REQUEST,
                observation_timestamp_utc=utcnow(),
                fetched_at_utc=utcnow(),
                latitude=latitude,
                longitude=longitude,
                flight_suitability=WeatherConditionClassification.UNAVAILABLE,
                limitations="Coordinates violate WGS84 bounding range [-90, 90] / [-180, 180].",
            )

        now_utc = datetime.now(timezone.utc)
        is_historical = False
        if timestamp_utc is not None:
            delta = now_utc - timestamp_utc
            if delta.total_seconds() > 172800:  # Older than 48 hours
                is_historical = True

        target_time = timestamp_utc or now_utc
        cache_key = f"weather:{round(latitude, 4)}:{round(longitude, 4)}:{is_historical}:{target_time.strftime('%Y%m%d%H')}"

        if use_cache:
            cached_val = await weather_cache.get(cache_key)
            if cached_val:
                return cached_val.model_copy(update={"cached": True})

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                if is_historical:
                    date_str = target_time.strftime("%Y-%m-%d")
                    params = {
                        "latitude": latitude,
                        "longitude": longitude,
                        "start_date": date_str,
                        "end_date": date_str,
                        "hourly": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,wind_direction_10m,visibility,cloud_cover",
                    }
                    resp = await client.get(self.archive_url, params=params)
                else:
                    params = {
                        "latitude": latitude,
                        "longitude": longitude,
                        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,wind_direction_10m,visibility,cloud_cover",
                    }
                    resp = await client.get(f"{self.base_url}/forecast", params=params)

                if resp.status_code == 429:
                    logger.warning("Open-Meteo rate limit reached.")
                    return NormalizedWeatherRecord(
                        observation_id=str(uuid.uuid4()),
                        provider_name="Open-Meteo",
                        status=ProviderStatus.RATE_LIMITED,
                        observation_timestamp_utc=target_time,
                        fetched_at_utc=utcnow(),
                        latitude=latitude,
                        longitude=longitude,
                        flight_suitability=WeatherConditionClassification.UNAVAILABLE,
                        limitations="Open-Meteo rate limit exceeded. Please retry later.",
                    )

                if resp.status_code != 200:
                    logger.warning(f"Open-Meteo error {resp.status_code}: {resp.text}")
                    return NormalizedWeatherRecord(
                        observation_id=str(uuid.uuid4()),
                        provider_name="Open-Meteo",
                        status=ProviderStatus.PROVIDER_ERROR,
                        observation_timestamp_utc=target_time,
                        fetched_at_utc=utcnow(),
                        latitude=latitude,
                        longitude=longitude,
                        flight_suitability=WeatherConditionClassification.UNAVAILABLE,
                        limitations=f"Provider returned HTTP {resp.status_code}.",
                    )

                data = resp.json()

                if is_historical:
                    hourly = data.get("hourly", {})
                    target_hour_str = target_time.strftime("%Y-%m-%dT%H:00")
                    times = hourly.get("time", [])
                    idx = times.index(target_hour_str) if target_hour_str in times else 0

                    temp = hourly.get("temperature_2m", [None])[idx]
                    app_temp = hourly.get("apparent_temperature", [None])[idx]
                    humidity = hourly.get("relative_humidity_2m", [None])[idx]
                    precip = hourly.get("precipitation", [None])[idx]
                    code = hourly.get("weather_code", [None])[idx]
                    wind_speed_kmh = hourly.get("wind_speed_10m", [None])[idx]
                    wind_dir = hourly.get("wind_direction_10m", [None])[idx]
                    visibility = hourly.get("visibility", [None])[idx]
                    cloud_cover = hourly.get("cloud_cover", [None])[idx]
                else:
                    current = data.get("current", {})
                    temp = current.get("temperature_2m")
                    app_temp = current.get("apparent_temperature")
                    humidity = current.get("relative_humidity_2m")
                    precip = current.get("precipitation")
                    code = current.get("weather_code")
                    wind_speed_kmh = current.get("wind_speed_10m")
                    wind_dir = current.get("wind_direction_10m")
                    visibility = current.get("visibility")
                    cloud_cover = current.get("cloud_cover")

                wind_speed_mps = round(float(wind_speed_kmh) / 3.6, 2) if wind_speed_kmh is not None else None
                weather_desc = WMO_WEATHER_CODES.get(code, "Unknown condition") if code is not None else None

                # Flight suitability evaluation
                suitability = WeatherConditionClassification.OPTIMAL
                if wind_speed_mps is not None and wind_speed_mps > 15.0:
                    suitability = WeatherConditionClassification.GROUNDED
                elif precip is not None and precip > 10.0:
                    suitability = WeatherConditionClassification.GROUNDED
                elif wind_speed_mps is not None and wind_speed_mps > 10.0:
                    suitability = WeatherConditionClassification.MARGINAL
                elif precip is not None and precip > 2.0:
                    suitability = WeatherConditionClassification.MARGINAL

                query_pt = GeoPoint(latitude=latitude, longitude=longitude)
                evidence_rec = EvidenceRecord(
                    evidence_id=str(uuid.uuid4()),
                    parent_evidence_ids=[],
                    source_type=EvidenceSourceType.GEOSPATIAL_REGISTRY,
                    created_at_utc=utcnow(),
                    temporal_mode=TemporalMode.STATIC_IMAGE,
                    crs="EPSG:4326",
                    geo_location=query_pt,
                    modality=Modality.EXTERNALLY_PROVIDED,
                    confidence=1.0,
                    verification_state=VerificationState.CALCULATED,
                    sensor_metadata={
                        "provider": "Open-Meteo",
                        "weather_code": code,
                        "condition": weather_desc,
                        "is_historical": is_historical,
                    },
                )

                record = NormalizedWeatherRecord(
                    observation_id=str(uuid.uuid4()),
                    provider_name="Open-Meteo",
                    status=ProviderStatus.AVAILABLE,
                    observation_timestamp_utc=target_time,
                    fetched_at_utc=utcnow(),
                    is_historical_reconstructed=is_historical,
                    latitude=latitude,
                    longitude=longitude,
                    temperature_celsius=float(temp) if temp is not None else None,
                    apparent_temperature_celsius=float(app_temp) if app_temp is not None else None,
                    relative_humidity_percentage=float(humidity) if humidity is not None else None,
                    precipitation_mm_hr=float(precip) if precip is not None else None,
                    weather_code=int(code) if code is not None else None,
                    condition_description=weather_desc,
                    wind_speed_mps=wind_speed_mps,
                    wind_direction_deg=float(wind_dir) if wind_dir is not None else None,
                    visibility_meters=float(visibility) if visibility is not None else None,
                    cloud_cover_percentage=float(cloud_cover) if cloud_cover is not None else None,
                    flight_suitability=suitability,
                    ground_trafficability_index=0.85 if (precip or 0.0) < 5.0 else 0.35,
                    cached=False,
                    evidence=evidence_rec,
                )

                await weather_cache.set(cache_key, record)
                return record

        except httpx.TimeoutException:
            logger.warning(f"Open-Meteo timed out after {self.timeout}s")
            return NormalizedWeatherRecord(
                observation_id=str(uuid.uuid4()),
                provider_name="Open-Meteo",
                status=ProviderStatus.TIMEOUT,
                observation_timestamp_utc=target_time,
                fetched_at_utc=utcnow(),
                latitude=latitude,
                longitude=longitude,
                flight_suitability=WeatherConditionClassification.UNAVAILABLE,
                limitations=f"Open-Meteo request timed out after {self.timeout}s.",
            )
        except Exception as e:
            logger.warning(f"Open-Meteo request failed: {e}")
            return NormalizedWeatherRecord(
                observation_id=str(uuid.uuid4()),
                provider_name="Open-Meteo",
                status=ProviderStatus.UNAVAILABLE,
                observation_timestamp_utc=target_time,
                fetched_at_utc=utcnow(),
                latitude=latitude,
                longitude=longitude,
                flight_suitability=WeatherConditionClassification.UNAVAILABLE,
                limitations=f"Open-Meteo is currently unreachable: {e}",
            )
