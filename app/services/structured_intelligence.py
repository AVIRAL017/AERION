"""
AERION — Structured Intelligence & Mistral Advisory Engine
Phase 3G: Deterministic Structured Reports & Mistral Advisory Integration.

Absolute Invariants:
1. Mistral is ADVISORY ONLY. It is never the source of truth for detections,
   coordinates, counts, damage, vulnerability, or road accessibility.
2. If Mistral API is unavailable, times out, or fails, the system provides
   deterministic standard protocol text and marks advisory status as UNAVAILABLE.
   The core report generation must NEVER fail due to an LLM outage.
3. Strict anti-fabrication prompt grounding: The prompt builder explicitly forbids
   hallucinating facts, locations, counts, damage, infiltration, or casualties.
4. MISTRAL_API_KEY is retrieved securely from environment / Pydantic config, never
   logged, and never echoed in API payloads.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

import httpx

from app.core.config import get_settings
from app.schemas.situation import (
    BorderSituationReport,
    DisasterSituationReport,
    OperationMode,
    TemporalMode,
    ThreatLevel,
)
from protocols import get_protocol

logger = logging.getLogger("aerion.intelligence")


class MistralAdvisoryClient:
    """
    Client for hosted Mistral AI (open-mistral-nemo).
    Operates strictly as an explanatory, bounded advisory synthesizer.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "open-mistral-nemo",
        api_url: str = "https://api.mistral.ai/v1/chat/completions",
        timeout_seconds: float = 15.0,
    ):
        settings = get_settings()
        self.api_key = api_key or (settings.MISTRAL_API_KEY.get_secret_value() if settings.MISTRAL_API_KEY else None)
        self.model = model or settings.MISTRAL_MODEL
        self.api_url = api_url
        self.timeout_seconds = timeout_seconds

    async def generate_advisory(
        self,
        mode: str,
        structured_context: Dict[str, Any],
        standard_protocol: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Generate grounded 5-6 sentence operational advisory from verified structured facts.
        Returns structured advisory dict, or None if Mistral is unreachable.
        """
        if not self.api_key:
            logger.info("Mistral API key not configured; advisory unavailable.")
            return None

        prompt = self._build_grounded_prompt(mode, structured_context, standard_protocol)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "temperature": 0.20,
            "max_tokens": 300,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an AI operational intelligence advisor for AERION. "
                        "Your mission is to provide concise, factual, grounded advisories strictly "
                        "derived from the verified structured evidence provided. "
                        "DO NOT invent or assume facts, coordinates, casualties, suspect identities, "
                        "counts, or conditions. If data is marked unavailable, state that clearly."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.post(self.api_url, json=payload, headers=headers)
                if resp.status_code != 200:
                    logger.warning(f"Mistral API returned error {resp.status_code}: {resp.text}")
                    return None

                data = resp.json()
                choices = data.get("choices", [])
                if not choices:
                    return None

                advisory_text = choices[0].get("message", {}).get("content", "").strip()

                return {
                    "advisory_id": str(uuid.uuid4()),
                    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                    "model_version": self.model,
                    "status": "AVAILABLE",
                    "tactical_advisory_text": advisory_text,
                    "recommended_action_priority": [standard_protocol],
                    "advisory_disclaimer": (
                        "AI advisory is derived from automated sensor feeds and deterministic risk thresholds. "
                        "Tactical deployment decisions require human operator verification."
                    ),
                }

        except Exception as e:
            logger.warning(f"Mistral advisory generation failed: {e}")
            return None

    def _build_grounded_prompt(
        self,
        mode: str,
        context: Dict[str, Any],
        protocol: str,
    ) -> str:
        return f"""
Operational Mode: {mode}
Verified Evidence Context:
{context}

Standard Operating Protocol:
{protocol}

Instructions:
1. Write a concise, plain-language advisory for the mission operator in 5-6 sentences.
2. State only verified facts from the context.
3. Reference the standard operating protocol.
4. STRICT INVARIANT: DO NOT invent coordinates, casualties, property damage, or infiltration events.
5. If weather, routing, or shelters are unavailable, explicitly note the missing data.
"""


class StructuredIntelligenceService:
    """
    Coordinates synthesis of deterministic operational situation reports
    and optional bounded Mistral AI advisories.
    """

    def __init__(self, mistral_client: Optional[MistralAdvisoryClient] = None):
        self.mistral_client = mistral_client or MistralAdvisoryClient()

    async def build_border_report(
        self,
        situation_id: str,
        session_id: str,
        temporal_mode: TemporalMode,
        tactical_overview: Dict[str, Any],
        detections_summary: Dict[str, Any],
        crossing_indicators: List[Dict[str, Any]],
        sector_assessments: List[Any],
        environmental_impact: Dict[str, Any],
        evidence_manifest: Dict[str, Any],
        confidence_and_limitations: Dict[str, Any],
    ) -> BorderSituationReport:
        # Determine dominant protocol
        primary_class = "person"
        by_class = detections_summary.get("by_class", {})
        if by_class:
            primary_class = max(by_class, key=by_class.get)
        std_protocol = get_protocol("border", primary_class)

        # Context for advisory
        context = {
            "overview": tactical_overview,
            "detections": detections_summary,
            "crossing_indicators_count": len(crossing_indicators),
            "environmental": environmental_impact,
        }

        mistral_advisory = await self.mistral_client.generate_advisory(
            mode="BORDER_SECURITY",
            structured_context=context,
            standard_protocol=std_protocol,
        )

        if mistral_advisory is None:
            mistral_advisory = {
                "advisory_id": str(uuid.uuid4()),
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "model_version": "none (deterministic fallback)",
                "status": "UNAVAILABLE",
                "tactical_advisory_text": f"Advisory unavailable. Standard protocol: {std_protocol}",
                "recommended_action_priority": [std_protocol],
                "advisory_disclaimer": (
                    "AI advisory service unavailable. Standard deterministic protocol displayed."
                ),
            }

        return BorderSituationReport(
            situation_id=situation_id,
            session_id=session_id,
            operation_mode=OperationMode.BORDER_SECURITY,
            temporal_mode=temporal_mode,
            tactical_overview=tactical_overview,
            detections_summary=detections_summary,
            potential_unauthorized_crossing_indicators=crossing_indicators,
            sector_assessments=sector_assessments,
            environmental_impact=environmental_impact,
            mistral_advisory=mistral_advisory,
            evidence_manifest=evidence_manifest,
            confidence_and_limitations=confidence_and_limitations,
        )

    async def build_disaster_report(
        self,
        situation_id: str,
        session_id: str,
        temporal_mode: TemporalMode,
        disaster_assessment: Dict[str, Any],
        infrastructure_damage: Dict[str, Any],
        evacuation_routes: List[Dict[str, Any]],
        shelter_assessments: List[Dict[str, Any]],
        environmental_conditions: Dict[str, Any],
        evidence_manifest: Dict[str, Any],
        confidence_and_limitations: Dict[str, Any],
    ) -> DisasterSituationReport:
        std_protocol = get_protocol("disaster", "building_damage")

        context = {
            "disaster": disaster_assessment,
            "damage": infrastructure_damage,
            "routes_count": len(evacuation_routes),
            "shelters_count": len(shelter_assessments),
            "weather": environmental_conditions,
        }

        mistral_advisory = await self.mistral_client.generate_advisory(
            mode="DISASTER_RESPONSE",
            structured_context=context,
            standard_protocol=std_protocol,
        )

        if mistral_advisory is None:
            mistral_advisory = {
                "advisory_id": str(uuid.uuid4()),
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "model_version": "none (deterministic fallback)",
                "status": "UNAVAILABLE",
                "tactical_advisory_text": f"Advisory unavailable. Standard protocol: {std_protocol}",
                "recommended_action_priority": [std_protocol],
                "advisory_disclaimer": (
                    "AI advisory service unavailable. Standard deterministic protocol displayed."
                ),
            }

        return DisasterSituationReport(
            situation_id=situation_id,
            session_id=session_id,
            operation_mode=OperationMode.DISASTER_RESPONSE,
            temporal_mode=temporal_mode,
            disaster_assessment=disaster_assessment,
            infrastructure_damage=infrastructure_damage,
            evacuation_routes=evacuation_routes,
            shelter_assessments=shelter_assessments,
            environmental_conditions=environmental_conditions,
            mistral_advisory=mistral_advisory,
            evidence_manifest=evidence_manifest,
            confidence_and_limitations=confidence_and_limitations,
        )
