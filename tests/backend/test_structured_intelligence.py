"""
AERION — Tests for Phase 3G Structured Intelligence & Mistral Advisory
"""

import unittest
from datetime import datetime, timezone
import uuid

from app.schemas.situation import (
    BorderSituationReport,
    DisasterSituationReport,
    OperationMode,
    TemporalMode,
    ThreatLevel,
)
from app.services.structured_intelligence import (
    MistralAdvisoryClient,
    StructuredIntelligenceService,
)


class MockMistralClient(MistralAdvisoryClient):
    def __init__(self, should_succeed: bool = True):
        self.should_succeed = should_succeed

    async def generate_advisory(self, mode, structured_context, standard_protocol):
        if not self.should_succeed:
            return None
        return {
            "advisory_id": str(uuid.uuid4()),
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "model_version": "mock-mistral",
            "status": "AVAILABLE",
            "tactical_advisory_text": f"Mock operational advisory for {mode}. Protocol: {standard_protocol}.",
            "recommended_action_priority": [standard_protocol],
            "advisory_disclaimer": "AI advisory is grounded in evidence.",
        }


class TestStructuredIntelligence(unittest.IsolatedAsyncioTestCase):

    async def test_border_report_generation_with_advisory(self):
        service = StructuredIntelligenceService(mistral_client=MockMistralClient(should_succeed=True))

        report = await service.build_border_report(
            situation_id=str(uuid.uuid4()),
            session_id=str(uuid.uuid4()),
            temporal_mode=TemporalMode.LIVE_STREAM,
            tactical_overview={"threat_level": "HIGH", "sectors_monitored_count": 3},
            detections_summary={"total_detections_count": 5, "by_class": {"person": 3, "car": 2}},
            crossing_indicators=[],
            sector_assessments=[],
            environmental_impact={"weather_available": True},
            evidence_manifest={"total_records": 5},
            confidence_and_limitations={"overall_confidence": 0.88},
        )

        self.assertIsInstance(report, BorderSituationReport)
        self.assertEqual(report.operation_mode, OperationMode.BORDER_SECURITY)
        self.assertIsNotNone(report.mistral_advisory)
        self.assertEqual(report.mistral_advisory["status"], "AVAILABLE")
        self.assertIn("Mock operational advisory", report.mistral_advisory["tactical_advisory_text"])

    async def test_border_report_degraded_when_mistral_unavailable(self):
        # When Mistral is unavailable, the report generation must succeed with fallback standard protocol
        service = StructuredIntelligenceService(mistral_client=MockMistralClient(should_succeed=False))

        report = await service.build_border_report(
            situation_id=str(uuid.uuid4()),
            session_id=str(uuid.uuid4()),
            temporal_mode=TemporalMode.RECORDED_FOOTAGE,
            tactical_overview={"threat_level": "LOW", "sectors_monitored_count": 1},
            detections_summary={"total_detections_count": 1, "by_class": {"motorbike": 1}},
            crossing_indicators=[],
            sector_assessments=[],
            environmental_impact={"weather_available": False},
            evidence_manifest={"total_records": 1},
            confidence_and_limitations={"overall_confidence": 0.9},
        )

        self.assertIsInstance(report, BorderSituationReport)
        self.assertIsNotNone(report.mistral_advisory)
        self.assertEqual(report.mistral_advisory["status"], "UNAVAILABLE")
        self.assertIn("motorbikes are a common fast-crossing vector", report.mistral_advisory["tactical_advisory_text"])

    async def test_disaster_report_generation(self):
        service = StructuredIntelligenceService(mistral_client=MockMistralClient(should_succeed=True))

        report = await service.build_disaster_report(
            situation_id=str(uuid.uuid4()),
            session_id=str(uuid.uuid4()),
            temporal_mode=TemporalMode.STATIC_IMAGE,
            disaster_assessment={"disaster_type": "FLOOD", "severity_score": 65.0, "threat_level": "HIGH"},
            infrastructure_damage={"siamese_damage_evaluations_count": 1, "damage_index_mean": 0.42},
            evacuation_routes=[],
            shelter_assessments=[],
            environmental_conditions={"weather_available": True},
            evidence_manifest={"total_records": 2},
            confidence_and_limitations={"overall_confidence": 0.85},
        )

        self.assertIsInstance(report, DisasterSituationReport)
        self.assertEqual(report.operation_mode, OperationMode.DISASTER_RESPONSE)
        self.assertIsNotNone(report.mistral_advisory)
        self.assertEqual(report.mistral_advisory["status"], "AVAILABLE")

    def test_prompt_grounding_builder(self):
        client = MistralAdvisoryClient()
        prompt = client._build_grounded_prompt(
            mode="BORDER_SECURITY",
            context={"tracks": 2, "class": "car"},
            protocol="Dispatch checkpoint alert.",
        )
        self.assertIn("STRICT INVARIANT: DO NOT invent coordinates", prompt)
        self.assertIn("Dispatch checkpoint alert", prompt)


if __name__ == "__main__":
    unittest.main()
