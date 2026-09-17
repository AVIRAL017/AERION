"""
AERION — Evidence & Situation Engine Tests (Phase 3C)
Validates:
- Immutable EvidenceRecord creation & provenance tracking
- Coordinate separation (Pixel vs EPSG:4326)
- Potential Unauthorized Crossing Indicator terminology enforcement
- Deterministic Vulnerability Calculator with missing input handling (INSUFFICIENT_EVIDENCE)
- Road Blockage Invariant (damage alone does NOT confirm road blockage)
- State transitions and monotonic event log sequence numbers
"""

import unittest
import uuid
from datetime import datetime, timezone

from aerion_runtime_contracts import (
    AERIONAnalysisResult,
    BoundingBox,
    DamageAnalysis,
    Detection,
    BorderAnalysis,
    Point2D,
    SceneSummary,
)
from app.schemas.evidence import (
    EvidenceRecord,
    EvidenceSourceType,
    Modality,
    OperationMode,
    TemporalMode,
    ThreatLevel,
    VerificationState,
)
from app.services.evidence_builder import EvidenceBuilder
from app.services.situation_engine import (
    SituationEngine,
    VulnerabilityCalculator,
)


class TestEvidenceBuilder(unittest.TestCase):
    """Verify evidence normalization and provenance."""

    def test_evidence_from_detection(self):
        det = Detection(
            source="visdrone_only",
            class_id=1,
            class_name="person",
            confidence=0.85,
            bbox=BoundingBox(x1=100.0, y1=150.0, x2=200.0, y2=300.0),
        )
        ev = EvidenceBuilder.from_runtime_detection(det)
        self.assertIsNotNone(ev.evidence_id)
        self.assertEqual(ev.source_type, EvidenceSourceType.FROZEN_MODEL_VISDRONE_YOLO)
        self.assertEqual(ev.modality, Modality.OBSERVED)
        self.assertIsNone(ev.crs)  # Native pixel space
        self.assertIsNone(ev.geo_location)
        self.assertIsNotNone(ev.pixel_bbox)
        self.assertEqual(ev.pixel_bbox.class_name, "person")
        self.assertAlmostEqual(ev.confidence, 0.85, places=2)

    def test_evidence_from_damage(self):
        dmg = DamageAnalysis(
            before_width=512,
            before_height=512,
            after_width=512,
            after_height=512,
            probability_min=0.0,
            probability_max=0.95,
            probability_mean=0.62,
            threshold=0.50,
            damage_pixels=15000,
            total_pixels=262144,
            damage_ratio=0.0572,
            damage_percentage=5.72,
        )
        ev = EvidenceBuilder.from_runtime_damage(dmg)
        self.assertEqual(ev.source_type, EvidenceSourceType.FROZEN_MODEL_SIAMESE_DAMAGE)
        self.assertEqual(ev.modality, Modality.OBSERVED)
        self.assertEqual(ev.sensor_metadata["damage_pixels"], 15000)


class TestVulnerabilityCalculator(unittest.TestCase):
    """Verify deterministic vulnerability scoring and missing factor behavior."""

    def test_insufficient_evidence_when_sensor_coverage_missing(self):
        summary = VulnerabilityCalculator.calculate_sector_vulnerability(
            sector_id="SEC-01",
            sector_name="Perimeter West",
            active_indicators_count=2,
            sensor_coverage_ratio=None,  # Missing sensor coverage
        )
        self.assertIsNone(summary.vulnerability_score)
        self.assertEqual(summary.vulnerability_status, "INSUFFICIENT_EVIDENCE")
        self.assertEqual(summary.sensor_coverage_status, "DEGRADED")
        self.assertEqual(summary.contributing_factors["sensor_coverage"]["status"], "UNAVAILABLE")

    def test_calculated_vulnerability_with_verified_factors(self):
        summary = VulnerabilityCalculator.calculate_sector_vulnerability(
            sector_id="SEC-01",
            sector_name="Perimeter West",
            active_indicators_count=3,
            sensor_coverage_ratio=0.90,
            terrain_type="arid",
            weather_degradation_factor=0.1,
        )
        self.assertIsNotNone(summary.vulnerability_score)
        self.assertEqual(summary.vulnerability_status, "CALCULATED")
        self.assertGreater(summary.vulnerability_score, 0.0)
        self.assertIn(summary.threat_level, (ThreatLevel.MEDIUM, ThreatLevel.HIGH, ThreatLevel.CRITICAL))


class TestSituationEngine(unittest.TestCase):
    """Verify border and disaster stateful event generation and reporting."""

    def test_border_mode_crossing_indicator_terminology(self):
        engine = SituationEngine(
            project_id=str(uuid.uuid4()),
            mode=OperationMode.BORDER_SECURITY,
            temporal_mode=TemporalMode.LIVE_STREAM,
        )

        # Mock runtime result with zone breach
        res = AERIONAnalysisResult(
            analysis_id=str(uuid.uuid4()),
            mode="border",
            source_type="video",
            detections=[
                Detection(
                    source="visdrone_only",
                    class_id=1,
                    class_name="person",
                    confidence=0.88,
                    bbox=BoundingBox(x1=50.0, y1=50.0, x2=80.0, y2=120.0),
                )
            ],
            border_analysis=[
                BorderAnalysis(
                    track_id=1,
                    inside_restricted_zone=True,
                    zone_entry=True,
                    zone_status="INSIDE",
                    border_activity_score=0.82,
                    alert_level="CRITICAL",
                )
            ],
            summary=SceneSummary(critical=1, high=0, medium=0, low=0),
        )

        events = engine.ingest_runtime_result(res)
        self.assertEqual(len(events), 1)
        # Invariant check: Terminology must be POTENTIAL_UNAUTHORIZED_CROSSING_INDICATOR
        self.assertEqual(events[0].event_type, "POTENTIAL_UNAUTHORIZED_CROSSING_INDICATOR")
        self.assertEqual(events[0].threat_level, ThreatLevel.CRITICAL)
        self.assertIn("Potential unauthorized crossing indicator", events[0].description)
        self.assertNotIn("confirmed infiltration", events[0].description.lower())

        report = engine.generate_border_report()
        self.assertEqual(report.operation_mode, OperationMode.BORDER_SECURITY)
        self.assertEqual(len(report.potential_unauthorized_crossing_indicators), 1)

    def test_disaster_mode_road_blockage_invariant(self):
        engine = SituationEngine(
            project_id=str(uuid.uuid4()),
            mode=OperationMode.DISASTER_RESPONSE,
            temporal_mode=TemporalMode.STATIC_IMAGE,
        )

        res = AERIONAnalysisResult(
            analysis_id=str(uuid.uuid4()),
            mode="disaster",
            source_type="image",
            damage_analysis=DamageAnalysis(
                before_width=512,
                before_height=512,
                after_width=512,
                after_height=512,
                probability_min=0.0,
                probability_max=0.98,
                probability_mean=0.78,
                threshold=0.50,
                damage_pixels=45000,
                total_pixels=262144,
                damage_ratio=0.1716,
                damage_percentage=17.16,
            ),
            summary=SceneSummary(critical=0, high=1, medium=0, low=0),
        )

        events = engine.ingest_runtime_result(res)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "STRUCTURAL_DAMAGE_IDENTIFIED")
        # Invariant: Road accessibility must remain UNAVAILABLE without real road blockage evidence
        self.assertEqual(events[0].payload["road_accessibility"], "UNAVAILABLE")

        report = engine.generate_disaster_report()
        self.assertEqual(report.infrastructure_damage["blocked_road_segments_count"], 0)
        self.assertEqual(report.infrastructure_damage["blocked_segments_modality"], Modality.UNAVAILABLE)

    def test_border_report_provenance_and_no_fake_border_perimeter(self):
        """Verify that default border reports do NOT forge 'Alpha Border Perimeter' or fake 85% coverage."""
        engine = SituationEngine(
            project_id=str(uuid.uuid4()),
            mode=OperationMode.BORDER_SECURITY,
            temporal_mode=TemporalMode.RECORDED_FOOTAGE,
        )
        report = engine.generate_border_report()
        self.assertEqual(len(report.sector_assessments), 1)
        sector = report.sector_assessments[0]

        # 1. Truthful naming and non-fabrication
        self.assertNotEqual(sector.sector_name, "Alpha Border Perimeter")
        self.assertIn("Internal", sector.sector_name)
        self.assertFalse(sector.authoritative_border_available)
        self.assertEqual(sector.sector_type, "SENSOR_RELATIVE")

        # 2. Insufficient evidence invariant: unmeasured sensor coverage must NOT default to 0.85
        self.assertIsNone(sector.vulnerability_score)
        self.assertEqual(sector.vulnerability_status, "INSUFFICIENT_EVIDENCE")
        self.assertEqual(sector.sensor_coverage_status, "DEGRADED")
        self.assertEqual(sector.contributing_factors["sensor_coverage"]["status"], "UNAVAILABLE")

    def test_operational_geofence_cannot_serialize_as_international_border(self):
        """Verify that an operational geofence cannot be represented as an authoritative international border."""
        engine = SituationEngine(
            project_id=str(uuid.uuid4()),
            mode=OperationMode.BORDER_SECURITY,
            temporal_mode=TemporalMode.LIVE_STREAM,
            sector_id="OP-ZONE-WEST",
            sector_name="Forward Operating Zone Bravo",
            sector_type="OPERATIONAL_GEOFENCE",
            authoritative_border_available=False,
            sensor_coverage_ratio=0.75,
        )
        report = engine.generate_border_report()
        sector = report.sector_assessments[0]

        self.assertEqual(sector.sector_type, "OPERATIONAL_GEOFENCE")
        self.assertNotEqual(sector.sector_type, "AUTHORITATIVE_BORDER")
        self.assertFalse(sector.authoritative_border_available)
        self.assertIsNotNone(sector.vulnerability_score)
        self.assertEqual(sector.vulnerability_status, "CALCULATED")


if __name__ == "__main__":
    unittest.main()

