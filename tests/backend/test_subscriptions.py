"""
AERION — Tests for Phase 3H Subscription & Entitlement Architecture
"""

import unittest
import uuid

from app.core.errors import PermissionDeniedError, StandardErrorCode
from app.services.subscription_service import (
    EntitlementService,
    PlanTier,
    SubscriptionState,
    UsageDimension,
    UsageMeter,
)


class TestSubscriptionAndEntitlements(unittest.TestCase):

    def setUp(self):
        self.entitlement_service = EntitlementService()
        self.usage_meter = UsageMeter()
        self.org_id = str(uuid.uuid4())

    def test_plan_definitions_pricing_invariants(self):
        free_plan = self.entitlement_service.get_plan(PlanTier.FREE)
        self.assertEqual(free_plan.price_inr, 0)
        self.assertEqual(free_plan.currency, "INR")

        pro_plan = self.entitlement_service.get_plan(PlanTier.PRO)
        self.assertEqual(pro_plan.price_inr, 9)
        self.assertEqual(pro_plan.currency, "INR")

        # Invariant: Limits are bounded per Phase F quota definitions
        self.assertEqual(free_plan.usage_limits.get(UsageDimension.DRONE_IMAGE), 100)
        self.assertEqual(pro_plan.usage_limits.get(UsageDimension.DRONE_IMAGE), 10000)

    def test_feature_entitlement_access(self):
        free_sub = SubscriptionState(organization_id=self.org_id, plan=PlanTier.FREE)
        pro_sub = SubscriptionState(organization_id=self.org_id, plan=PlanTier.PRO)

        # Basic perception is permitted on both
        self.assertTrue(self.entitlement_service.check_feature_entitlement(free_sub, "drone_perception"))
        self.assertTrue(self.entitlement_service.check_feature_entitlement(pro_sub, "drone_perception"))

        # Advanced advisory is gated to PRO
        self.assertFalse(self.entitlement_service.check_feature_entitlement(free_sub, "advanced_advisory"))
        self.assertTrue(self.entitlement_service.check_feature_entitlement(pro_sub, "advanced_advisory"))

        # Validate feature access raises 403 for unauthorized feature
        with self.assertRaises(PermissionDeniedError) as ctx:
            self.entitlement_service.validate_feature_access(free_sub, "advanced_advisory")
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(ctx.exception.code, StandardErrorCode.PERMISSION_DENIED)

    def test_inactive_subscription_blocks_all_features(self):
        inactive_sub = SubscriptionState(
            organization_id=self.org_id,
            plan=PlanTier.PRO,
            is_active=False,
        )
        self.assertFalse(self.entitlement_service.check_feature_entitlement(inactive_sub, "drone_perception"))

    def test_auditable_usage_meter(self):
        job_id = str(uuid.uuid4())
        event = self.usage_meter.record_usage(
            organization_id=self.org_id,
            dimension=UsageDimension.DRONE_IMAGE,
            quantity=1,
            job_id=job_id,
        )
        self.assertEqual(event.organization_id, self.org_id)
        self.assertEqual(event.dimension, UsageDimension.DRONE_IMAGE)
        self.assertEqual(event.quantity, 1)

        # Record another event
        self.usage_meter.record_usage(
            organization_id=self.org_id,
            dimension=UsageDimension.DRONE_IMAGE,
            quantity=3,
        )

        total = self.usage_meter.get_monthly_usage(self.org_id, UsageDimension.DRONE_IMAGE)
        self.assertEqual(total, 4)

        # Different dimension is isolated
        total_video = self.usage_meter.get_monthly_usage(self.org_id, UsageDimension.VIDEO_MINUTE)
        self.assertEqual(total_video, 0)


if __name__ == "__main__":
    unittest.main()
