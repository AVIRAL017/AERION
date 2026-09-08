"""
AERION — Central Configuration Management
Strictly typed configuration using Pydantic Settings.
Guarantees environment validation, secret masking, and fail-fast production rules.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import List, Literal, Optional, Union
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


EnvironmentMode = Literal["development", "test", "production"]


class AERIONSettings(BaseSettings):
    """
    Authoritative application configuration for AERION.
    Reads from environment variables and optional .env file.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------
    # APPLICATION SETTINGS
    # ------------------------------------------------------------
    APP_NAME: str = Field(default="AERION Platform", description="Application service name")
    ENVIRONMENT: EnvironmentMode = Field(default="development", description="Runtime environment mode")
    DEBUG: bool = Field(default=False, description="Enable verbose debugging mode")
    API_VERSION: str = Field(default="v1", description="Current API major version")

    # ------------------------------------------------------------
    # SERVER SETTINGS
    # ------------------------------------------------------------
    HOST: str = Field(default="127.0.0.1", description="Binding host for Uvicorn")
    PORT: int = Field(default=8000, description="Binding port for Uvicorn")

    # ------------------------------------------------------------
    # SECURITY & CORS SETTINGS
    # ------------------------------------------------------------
    ALLOWED_ORIGINS: Union[List[str], str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        description="Allowed CORS origins (list of strings or comma-separated string)",
    )
    REQUEST_ID_HEADER: str = Field(default="X-Request-ID", description="Header used for correlation tracking")
    MAX_REQUEST_ID_LENGTH: int = Field(default=64, description="Maximum permitted length for incoming request IDs")

    # ------------------------------------------------------------
    # RATE LIMITING SETTINGS
    # ------------------------------------------------------------
    RATE_LIMIT_ENABLED: bool = Field(default=True, description="Enable backend API rate limiting")
    RATE_LIMIT_PER_MINUTE: int = Field(default=60, description="Maximum requests permitted per minute per client key")
    RATE_LIMIT_WINDOW_SECONDS: int = Field(default=60, description="Sliding window duration in seconds")

    # ------------------------------------------------------------
    # RUNTIME & INFERENCE MUTEX SETTINGS
    # ------------------------------------------------------------
    DEVICE: str = Field(default="0", description="Ultralytics/PyTorch device identifier (0, cuda:0, cpu)")
    LAZY_LOAD_MODELS: bool = Field(default=True, description="Ensure heavy models are only loaded on demand")
    INFERENCE_TIMEOUT_SECONDS: float = Field(default=60.0, description="GPU mutex lock acquisition timeout in seconds")

    # ------------------------------------------------------------
    # STORAGE PLACEHOLDERS (Phase 3E Infrastructure)
    # ------------------------------------------------------------
    STORAGE_BACKEND: str = Field(default="local", description="Active storage driver (local, s3, minio)")
    STORAGE_LOCAL_ROOT: str = Field(default="storage", description="Root path for local filesystem storage")
    S3_ENDPOINT_URL: Optional[str] = Field(default=None, description="Optional custom S3/MinIO endpoint URL")
    S3_BUCKET_NAME: Optional[str] = Field(default=None, description="S3 storage bucket name")
    S3_REGION: str = Field(default="us-east-1", description="AWS S3 region")
    S3_ACCESS_KEY: Optional[SecretStr] = Field(default=None, description="S3 access key credential")
    S3_SECRET_KEY: Optional[SecretStr] = Field(default=None, description="S3 secret key credential")

    # ------------------------------------------------------------
    # EXTERNAL PROVIDER PLACEHOLDERS (Phases 3F & 3G)
    # ------------------------------------------------------------
    MISTRAL_API_KEY: Optional[SecretStr] = Field(default=None, description="Mistral AI API credential")
    MISTRAL_MODEL: str = Field(default="open-mistral-nemo", description="Designated Mistral LLM model")
    MAPBOX_ACCESS_TOKEN: Optional[SecretStr] = Field(default=None, description="Mapbox GL integration token")
    OPENROUTESERVICE_API_KEY: Optional[SecretStr] = Field(default=None, description="OpenRouteService routing token")
    WEATHER_API_KEY: Optional[SecretStr] = Field(default=None, description="Weather provider API key if required")

    # ------------------------------------------------------------
    # SUBSCRIPTION PLACEHOLDERS (Phase 3H)
    # ------------------------------------------------------------
    PLAN_FREE_NAME: str = Field(default="FREE", description="Free tier plan name")
    PLAN_PRO_NAME: str = Field(default="PRO", description="Pro tier plan name")
    PLAN_PRO_PRICE_INR: int = Field(default=9, description="Pro tier subscription monthly price in INR")

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: Union[List[str], str]) -> List[str]:
        """Support comma-separated string or list of strings for ALLOWED_ORIGINS."""
        if isinstance(value, str):
            parts = [p.strip() for p in value.split(",") if p.strip()]
            return parts
        return value

    @model_validator(mode="after")
    def validate_production_invariants(self) -> "AERIONSettings":
        """
        Fail fast if production environment violates essential security invariants.
        """
        if self.ENVIRONMENT == "production":
            if self.DEBUG:
                raise ValueError("Security Violation: DEBUG cannot be enabled in production environment.")
            if not self.ALLOWED_ORIGINS:
                raise ValueError("Security Violation: ALLOWED_ORIGINS must contain explicit origin URLs in production.")
            if "*" in self.ALLOWED_ORIGINS:
                raise ValueError("Security Violation: Wildcard origin '*' is strictly prohibited in production CORS.")
        return self


@lru_cache
def get_settings() -> AERIONSettings:
    """
    Cached application settings accessor.
    Reads configuration once per process lifecycle unless cleared for tests.
    """
    return AERIONSettings()
