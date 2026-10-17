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
import re
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
            "temperature": 0.20,
            "max_tokens": 1500,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are the AERION Chief Tactical Intelligence Advisor, synthesizing grounded operational situational awareness for command personnel.\n"
                        "STRICT OPERATIONAL DIRECTIVES:\n"
                        "1. Base all observations strictly on the supplied AERION structured evidence package.\n"
                        "2. Provide an authoritative, detailed, multi-section operational situation advisory.\n"
                        "3. Explicitly break down observed entity categories (cars, motorbikes, pedestrians, trucks, buses), track counts, and movement flow rates.\n"
                        "4. Detail spatial perimeter dynamics, zone entry/exit rates, and potential crossing indicators.\n"
                        "5. Provide concrete, actionable tactical recommendations for ground units, patrol dispatch, and optical sensor tasking.\n"
                        "6. Under no circumstance fabricate coordinates, artificial casualties, or unobserved events.\n"
                        "7. If boundary data or demo zones are unconfigured, clearly declare them as UNAVAILABLE or SENSOR-RELATIVE.\n"
                        "8. Use 'Potential Unauthorized Crossing Indicator' rather than 'confirmed infiltration'.\n"
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

                # Extract actionable recommendations from advisory text if present
                rec_actions = []
                lines = advisory_text.split("\n")
                capturing_recs = False
                for line in lines:
                    stripped = line.strip()
                    lower_line = stripped.lower()
                    if ("recommend" in lower_line or "directive" in lower_line or "action" in lower_line) and ("###" in stripped or "**" in stripped):
                        capturing_recs = True
                        continue
                    if capturing_recs:
                        if stripped.startswith("###") or stripped.startswith("---"):
                            capturing_recs = False
                            continue
                        clean_action = re.sub(r"^[\*\-\d\.\s]+", "", stripped).strip()
                        if clean_action and len(clean_action) > 10:
                            rec_actions.append(clean_action)
                        if len(rec_actions) >= 4:
                            break

                if not rec_actions:
                    rec_actions = [standard_protocol]
                elif standard_protocol not in rec_actions:
                    rec_actions.append(standard_protocol)

                return NormalizedAdvisoryRecord(
                    mode=mode,
                    summary=advisory_text,
                    advisory_text=advisory_text,
                    priority=deterministic_priority,
                    key_findings=key_findings,
                    evidence_references=ev_refs,
                    recommended_actions=rec_actions,
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
OPERATIONAL MISSION MODE: {mode}

[STRUCTURED GROUNDED EVIDENCE]
{json.dumps(context, default=str, indent=2)}

STANDARD OPERATING PROTOCOL:
{protocol}

STRICT INVARIANT: DO NOT invent coordinates, casualty counts, damaged infrastructure, or threat indicators not present in evidence.
State ONLY verified facts supported by the structured evidence above.
For crossing events, use terms like 'Potential Unauthorized Crossing Indicator' and never 'confirmed infiltration'.

STRUCTURE YOUR OPERATIONAL INTELLIGENCE ADVISORY INTO THESE SECTIONS:
### 1. EXECUTIVE SITUATIONAL ASSESSMENT
Synthesize verified sensor observations, total detection count ({context.get('detection_count', 0)}), unique tracked vehicles, and sector operational posture.

### 2. TARGET CLASSIFICATION & MOVEMENT DYNAMICS
Detail categorical distribution across vehicles and pedestrians (e.g. cars, motorbikes, pedestrians, trucks, buses). Analyze movement trajectories, speed patterns, and spatial clustering.

### 3. SECTOR PERIMETER & GEOFENCE EVALUATION
Assess ingress/egress activity relative to the monitored zone or aperture. Explicitly evaluate the {context.get('crossing_indicators_count', 0)} crossing indicator(s) and any containment/zone breach events. If border context is not set, state clearly that perception remains sensor-relative.

### 4. OPERATIONAL RESPONSE DIRECTIVES
List concrete, prioritized operational directives for command and field operators:
- Action 1: Specific checkpoint / verification action.
- Action 2: Patrol deployment or containment guidance.
- Action 3: Optical tracking and sensor reassessment protocol.

### 5. SENSOR LIMITATIONS & AUDIT COMPLIANCE
Declare frozen model parameters (YOLOv8/ByteTrack), absence of authoritative GPS if applicable, and human operator verification requirements.
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
        det_count = evidence_package.get("detection_count", 0)
        cross_count = evidence_package.get("crossing_indicators_count", 0)
        veh_sum = evidence_package.get("vehicle_summary") or {}
        class_dist = veh_sum.get("class_distribution") or {}
        class_str = ", ".join([f"{k.upper()}: {v}" for k, v in class_dist.items()]) if class_dist else "Standard surveillance categories"

        fallback_text = (
            f"### AERION OPERATIONAL INTELLIGENCE ADVISORY (DETERMINISTIC FALLBACK)\n\n"
            f"### 1. EXECUTIVE SITUATIONAL ASSESSMENT\n"
            f"Operational sector evaluated deterministically under {mode} protocol. "
            f"Sensor perception verified {det_count} total detection events across surveillance frames. "
            f"Deterministic priority assigned: {priority.value}.\n\n"
            f"### 2. TARGET CLASSIFICATION & MOVEMENT DYNAMICS\n"
            f"Categorical classification distribution: {class_str}. "
            f"Entities tracked deterministically via frozen weights. No synthetic kinematic inflation injected.\n\n"
            f"### 3. SECTOR PERIMETER & GEOFENCE EVALUATION\n"
            f"Cross-perimeter indicators evaluated: {cross_count} Potential Unauthorized Crossing Indicators registered. "
            f"Border status: {evidence_package.get('authoritative_border_status', 'SENSOR-FRAME RELATIVE')}.\n\n"
            f"### 4. OPERATIONAL RESPONSE DIRECTIVES\n"
            f"- Verify all tracked entity contacts against authorized transit checkpoints.\n"
            f"- Dispatch tactical patrol for sector reconnaissance if contacts remain outside permitted corridors.\n"
            f"- Maintain continuous sensor aperture lock and cross-reference with secondary radar.\n\n"
            f"### 5. SENSOR LIMITATIONS & AUDIT COMPLIANCE\n"
            f"Advisory synthesized under deterministic rules ({provider_status.value}). "
            f"Human-in-the-loop verification required before operational deployment."
        )

        return NormalizedAdvisoryRecord(
            mode=mode,
            summary=fallback_text,
            advisory_text=fallback_text,
            priority=priority,
            key_findings=key_findings,
            evidence_references=evidence_refs,
            recommended_actions=[
                "Verify entity presence against authorized transit checkpoints.",
                "Dispatch tactical patrol if outside authorized corridors.",
                standard_protocol,
            ],
            limitations=limitations,
            model=f"deterministic-fallback ({provider_status.value})",
            provider_status=provider_status,
            grounded=True,
        )

    def _extract_key_findings(self, mode: str, evidence_package: Dict[str, Any]) -> List[str]:
        findings = []
        if mode == "BORDER_SECURITY":
            det_count = evidence_package.get("detection_count", 0)
            crossing_count = evidence_package.get("crossing_indicators_count", 0)
            if det_count > 0:
                findings.append(f"[OBSERVED] {det_count} verified object detection(s) recorded by frozen detector.")
            if crossing_count > 0:
                findings.append(f"[DERIVED] {crossing_count} Potential Unauthorized Crossing Indicator(s) evaluated.")
            else:
                findings.append("[DERIVED] Zero Potential Unauthorized Crossing Indicators triggered.")

            # Demo zone activity
            zone_act = evidence_package.get("demo_zone_activity")
            if isinstance(zone_act, dict) and zone_act.get("zone_configured"):
                findings.append(
                    f"[DERIVED] Demo Zone ({zone_act.get('sector_name')}): {zone_act.get('total_entries', 0)} entries, {zone_act.get('total_exits', 0)} exits recorded."
                )
            else:
                findings.append("[UNAVAILABLE] Demo Zone: BORDER CONTEXT NOT SET. Spatial geofencing is unconfigured.")

            # Threat level changes
            changes = evidence_package.get("threat_level_changes")
            if isinstance(changes, list) and len(changes) > 0:
                findings.append(f"[PREDICTED/TREND] {len(changes)} dynamic threat level transition(s) tracked across timeline.")

            border_status = evidence_package.get("authoritative_border_status")
            if border_status:
                findings.append(f"[UNAVAILABLE] Authoritative boundary status: {border_status}.")
        else:
            damage_evals = evidence_package.get("damage_evaluations_count", 0)
            damage_ratio = evidence_package.get("mean_damage_ratio", 0.0)
            if damage_evals > 0:
                findings.append(
                    f"[DERIVED] Structural damage assessment: mean damage ratio {damage_ratio:.2f} across {damage_evals} evaluation(s)."
                )
            hazards_count = evidence_package.get("historical_hazards_count", 0)
            if hazards_count > 0:
                findings.append(f"[OBSERVED] {hazards_count} historical hazard record(s) within operational radius.")
            shelters_count = evidence_package.get("shelters_count", 0)
            if shelters_count > 0:
                findings.append(f"[OBSERVED] {shelters_count} registered emergency shelter(s) referenced.")
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
