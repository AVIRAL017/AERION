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

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

import httpx

from app.core.config import get_settings
from app.schemas.external import AdvisoryPriority, NormalizedAdvisoryRecord, ProviderStatus
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

    _DEFAULT = object()

    def __init__(
        self,
        api_key: Any = _DEFAULT,
        model: str = "open-mistral-nemo",
        api_url: str = "https://api.mistral.ai/v1/chat/completions",
        timeout_seconds: float = 15.0,
    ):
        settings = get_settings()
        if api_key is self._DEFAULT:
            self.api_key = settings.MISTRAL_API_KEY.get_secret_value() if settings.MISTRAL_API_KEY else None
        else:
            self.api_key = api_key
        self.model = model or settings.MISTRAL_MODEL
        self.api_url = api_url
        self.timeout_seconds = timeout_seconds

    async def generate_grounded_advisory(
        self,
        mode: str,
        evidence_package: Dict[str, Any],
        standard_protocol: str,
        deterministic_priority: AdvisoryPriority = AdvisoryPriority.MEDIUM,
    ) -> NormalizedAdvisoryRecord:
        """
        Generate a strictly grounded advisory using Mistral AI or fallback deterministically.
        Invariant: Never hallucinates detections, coordinates, weather, or routes.
        Returns NormalizedAdvisoryRecord.
        """
        # Collect evidence IDs
        ev_refs = evidence_package.get("evidence_ids", [])
        if not ev_refs and "evidence_records" in evidence_package:
            ev_refs = [
                r.get("evidence_id") if isinstance(r, dict) else getattr(r, "evidence_id", "")
                for r in evidence_package["evidence_records"]
            ]
        ev_refs = [ref for ref in ev_refs if ref]

        # Extract explicit limitations from context
        limitations = list(evidence_package.get("limitations", []))
        if evidence_package.get("weather_status") in ("UNAVAILABLE", "AUTH_REQUIRED", "NOT_CONFIGURED"):
            limitations.append("Local weather observation data is unavailable.")
        if evidence_package.get("routing_status") in ("UNAVAILABLE", "AUTH_REQUIRED", "NOT_CONFIGURED"):
            limitations.append("Evacuation routing service is unavailable; no route is verified.")
        if evidence_package.get("georeferencing_status") == "UNAVAILABLE":
            limitations.append("Source asset lacks geographic coordinates; operations restricted to image-space.")
        if evidence_package.get("authoritative_border_status") == "NOT_ACQUIRED":
            limitations.append("Authoritative Survey of India international boundary data is not acquired.")

        if not self.api_key:
            logger.info("Mistral API key not configured; using deterministic fallback advisory.")
            return self._build_deterministic_fallback(
                mode=mode,
                evidence_package=evidence_package,
                standard_protocol=standard_protocol,
                priority=deterministic_priority,
                provider_status=ProviderStatus.AUTH_REQUIRED,
                evidence_refs=ev_refs,
                limitations=limitations,
            )

        prompt = self._build_strict_grounded_prompt(mode, evidence_package, standard_protocol)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "temperature": 0.15,
            "max_tokens": 400,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an operational intelligence advisory assistant for AERION. "
                        "RULES:\n"
                        "1. Use ONLY supplied AERION evidence.\n"
                        "2. If evidence is missing, state that it is unavailable.\n"
                        "3. Do NOT invent detections, coordinates, weather, routes, shelter status, "
                        "infrastructure status, hazard status, confidence, event counts, or timestamps.\n"
                        "4. Do NOT convert uncertainty into certainty.\n"
                        "5. Do NOT claim an event is confirmed unless the evidence explicitly establishes it.\n"
                        "6. Distinguish observed facts from derived values and external information.\n"
                        "7. Use 'Potential Unauthorized Crossing Indicator' terminology for border indicators.\n"
                        "8. Under no circumstance override deterministic priority or evidence.\n"
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
                    status_enum = ProviderStatus.RATE_LIMITED if resp.status_code == 429 else ProviderStatus.PROVIDER_ERROR
                    return self._build_deterministic_fallback(
                        mode=mode,
                        evidence_package=evidence_package,
                        standard_protocol=standard_protocol,
                        priority=deterministic_priority,
                        provider_status=status_enum,
                        evidence_refs=ev_refs,
                        limitations=limitations,
                    )

                data = resp.json()
                choices = data.get("choices", [])
                if not choices:
                    return self._build_deterministic_fallback(
                        mode=mode,
                        evidence_package=evidence_package,
                        standard_protocol=standard_protocol,
                        priority=deterministic_priority,
                        provider_status=ProviderStatus.PROVIDER_ERROR,
                        evidence_refs=ev_refs,
                        limitations=limitations,
                    )

                advisory_text = choices[0].get("message", {}).get("content", "").strip()

                # Derive findings and key points from evidence
                key_findings = self._extract_key_findings(mode, evidence_package)

                return NormalizedAdvisoryRecord(
                    mode=mode,
                    summary=advisory_text[:280] + ("..." if len(advisory_text) > 280 else ""),
                    priority=deterministic_priority,
                    key_findings=key_findings,
                    evidence_references=ev_refs,
                    recommended_actions=[standard_protocol],
                    limitations=limitations,
                    model=self.model,
                    provider_status=ProviderStatus.AVAILABLE,
                    grounded=True,
                )

        except httpx.TimeoutException:
            logger.warning("Mistral advisory request timed out.")
            return self._build_deterministic_fallback(
                mode=mode,
                evidence_package=evidence_package,
                standard_protocol=standard_protocol,
                priority=deterministic_priority,
                provider_status=ProviderStatus.TIMEOUT,
                evidence_refs=ev_refs,
                limitations=limitations,
            )
        except Exception as e:
            logger.warning(f"Mistral advisory generation failed ({e}); using deterministic fallback.")
            return self._build_deterministic_fallback(
                mode=mode,
                evidence_package=evidence_package,
                standard_protocol=standard_protocol,
                priority=deterministic_priority,
                provider_status=ProviderStatus.PROVIDER_ERROR,
                evidence_refs=ev_refs,
                limitations=limitations,
            )

    def _build_strict_grounded_prompt(
        self,
        mode: str,
        context: Dict[str, Any],
        protocol: str,
    ) -> str:
        return f"""
Operational Mode: {mode}
Verified Evidence Context:
{json.dumps(context, default=str, indent=2)}

Standard Operating Protocol:
{protocol}

Instructions:
1. Write a concise, plain-language advisory for the mission commander in 4-5 sentences.
2. State ONLY verified facts from the context.
3. Reference the standard operating protocol.
4. STRICT INVARIANT: DO NOT invent coordinates, casualties, property damage, or infiltration events.
5. If weather, routing, or shelters are unavailable, explicitly note the missing data.
6. Use 'Potential Unauthorized Crossing Indicator' for border indicators, never 'confirmed infiltration'.
"""

    def _build_grounded_prompt(
        self,
        mode: str,
        context: Dict[str, Any],
        protocol: str,
    ) -> str:
        return self._build_strict_grounded_prompt(mode, context, protocol)

    def _build_deterministic_fallback(
        self,
        mode: str,
        evidence_package: Dict[str, Any],
        standard_protocol: str,
        priority: AdvisoryPriority,
        provider_status: ProviderStatus,
        evidence_refs: List[str],
        limitations: List[str],
    ) -> NormalizedAdvisoryRecord:
        """Deterministic fallback advisory when Mistral AI is unavailable or unconfigured."""
        key_findings = self._extract_key_findings(mode, evidence_package)
        summary = (
            f"Advisory generated via deterministic operational rules ({provider_status.value}). "
            f"Mode: {mode}. Standard protocol: {standard_protocol}"
        )
        return NormalizedAdvisoryRecord(
            mode=mode,
            summary=summary,
            priority=priority,
            key_findings=key_findings,
            evidence_references=evidence_refs,
            recommended_actions=[standard_protocol],
            limitations=limitations,
            model="none (deterministic fallback)",
            provider_status=provider_status,
            grounded=True,
        )

    def _extract_key_findings(self, mode: str, evidence_package: Dict[str, Any]) -> List[str]:
        findings = []
        if mode == "BORDER_SECURITY":
            det_count = evidence_package.get("detection_count", 0)
            crossing_count = evidence_package.get("crossing_indicators_count", 0)
            if det_count > 0:
                findings.append(f"{det_count} verified object detections recorded by frozen detector.")
            if crossing_count > 0:
                findings.append(f"{crossing_count} Potential Unauthorized Crossing Indicator(s) evaluated.")
            else:
                findings.append("Zero Potential Unauthorized Crossing Indicators triggered.")
            border_status = evidence_package.get("authoritative_border_status")
            if border_status:
                findings.append(f"Authoritative boundary status: {border_status}.")
        else:
            damage_evals = evidence_package.get("damage_evaluations_count", 0)
            damage_ratio = evidence_package.get("mean_damage_ratio", 0.0)
            if damage_evals > 0:
                findings.append(
                    f"Structural damage assessment: mean damage ratio {damage_ratio:.2f} across {damage_evals} evaluation(s)."
                )
            hazards_count = evidence_package.get("historical_hazards_count", 0)
            if hazards_count > 0:
                findings.append(f"{hazards_count} historical hazard record(s) within operational radius.")
            shelters_count = evidence_package.get("shelters_count", 0)
            if shelters_count > 0:
                findings.append(f"{shelters_count} registered emergency shelter(s) referenced.")
        return findings

    async def generate_advisory(
        self,
        mode: str,
        structured_context: Dict[str, Any],
        standard_protocol: str,
    ) -> Optional[Dict[str, Any]]:
        """Legacy compatibility method returning dict."""
        record = await self.generate_grounded_advisory(
            mode=mode,
            evidence_package=structured_context,
            standard_protocol=standard_protocol,
        )
        return {
            "advisory_id": record.advisory_id,
            "generated_at_utc": record.generated_at_utc.isoformat(),
            "model_version": record.model,
            "status": record.provider_status.value,
            "tactical_advisory_text": record.summary,
            "recommended_action_priority": record.recommended_actions,
            "advisory_disclaimer": record.disclaimer,
            "key_findings": record.key_findings,
            "evidence_references": record.evidence_references,
            "limitations": record.limitations,
            "grounded": record.grounded,
        }


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
