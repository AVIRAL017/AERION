"""
AERION — Subscription, Entitlements & Usage Metering Architecture
Phase 3H: Configurable Plans, Entitlements, and Auditable Usage Events.

Key Invariants:
1. Finalized Constants:
   - FREE = ₹0/month
   - PRO = ₹9/month (configurable via SubscriptionConfig)
   - Currency: INR
2. Limits & Quotas are strictly TBD / configurable. Do NOT invent final numerical limits.
3. PRO is strictly bounded, NEVER described or implemented as unlimited volume.
4. Payment gateway integration (Stripe/Razorpay) is deferred. No payment dependencies.
5. ML Runtime remains strictly subscription-agnostic.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import get_settings
from app.core.errors import PermissionDeniedError

logger = logging.getLogger("aerion.subscription")


class PlanTier(str, Enum):
    FREE = "FREE"
    PRO = "PRO"


class UsageDimension(str, Enum):
    DRONE_IMAGE = "drone_image"
    SATELLITE_TILE = "satellite_tile"
    DAMAGE_PAIR = "damage_pair"
    VIDEO_MINUTE = "video_minute"
    RAG_REQUEST = "rag_request"


class PlanDefinition(BaseModel):
    """
    Representation of an AERION subscription plan.
    Quotas remain explicitly configurable / TBD.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    plan_id: PlanTier
    price_inr: int
    currency: str = "INR"
    entitlements: Dict[str, bool] = Field(default_factory=dict)
    # Usage limits are configurable / TBD; None indicates limit pending benchmark finalization
    usage_limits: Dict[UsageDimension, Optional[int]] = Field(default_factory=dict)


class UsageEventRecord(BaseModel):
    """
    Auditable usage meter record.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    organization_id: str
    dimension: UsageDimension
    quantity: int = 1
    job_id: Optional[str] = None
    timestamp_utc: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SubscriptionState(BaseModel):
    """
    Active subscription status for a tenant organization.
    """
    subscription_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    organization_id: str
    plan: PlanTier = PlanTier.FREE
    price_inr: int = 0
    is_active: bool = True
    current_period_start_utc: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    current_period_end_utc: Optional[datetime] = None


class EntitlementService:
    """
    Evaluates tenant entitlements and enforces configurable feature and usage gates.
    """

    def __init__(self):
        settings = get_settings()
        self._plans: Dict[PlanTier, PlanDefinition] = {
            PlanTier.FREE: PlanDefinition(
                plan_id=PlanTier.FREE,
                price_inr=0,
                entitlements={
                    "drone_perception": True,
                    "satellite_obb_perception": True,
                    "damage_assessment": True,
                    "border_video_tracking": True,
                    "basic_advisory": True,
                    "advanced_advisory": False,
                    "geofence_management": True,
                },
                usage_limits={
                    UsageDimension.DRONE_IMAGE: None,  # TBD
                    UsageDimension.SATELLITE_TILE: None,  # TBD
                    UsageDimension.DAMAGE_PAIR: None,  # TBD
                    UsageDimension.VIDEO_MINUTE: None,  # TBD
                },
            ),
            PlanTier.PRO: PlanDefinition(
                plan_id=PlanTier.PRO,
                price_inr=settings.PLAN_PRO_PRICE_INR,
                entitlements={
                    "drone_perception": True,
                    "satellite_obb_perception": True,
                    "damage_assessment": True,
                    "border_video_tracking": True,
                    "basic_advisory": True,
                    "advanced_advisory": True,
                    "geofence_management": True,
                },
                usage_limits={
                    UsageDimension.DRONE_IMAGE: None,  # TBD (Higher tier, bounded, not unlimited)
                    UsageDimension.SATELLITE_TILE: None,  # TBD
                    UsageDimension.DAMAGE_PAIR: None,  # TBD
                    UsageDimension.VIDEO_MINUTE: None,  # TBD
                },
            ),
        }

    def get_plan(self, tier: PlanTier) -> PlanDefinition:
        return self._plans[tier]

    def check_feature_entitlement(self, subscription: SubscriptionState, feature_key: str) -> bool:
        if not subscription.is_active:
            return False
        plan = self.get_plan(subscription.plan)
        return plan.entitlements.get(feature_key, False)

    def validate_feature_access(self, subscription: SubscriptionState, feature_key: str) -> None:
        if not self.check_feature_entitlement(subscription, feature_key):
            raise PermissionDeniedError(
                message=f"Feature '{feature_key}' is not permitted under subscription plan '{subscription.plan.value}'."
            )


class UsageMeter:
    """
    In-memory / repository ledger for recording auditable usage events.
    """

    def __init__(self):
        self._events: List[UsageEventRecord] = []

    def record_usage(
        self,
        organization_id: str,
        dimension: UsageDimension,
        quantity: int = 1,
        job_id: Optional[str] = None,
    ) -> UsageEventRecord:
        event = UsageEventRecord(
            organization_id=organization_id,
            dimension=dimension,
            quantity=quantity,
            job_id=job_id,
        )
        self._events.append(event)
        return event

    def get_monthly_usage(
        self,
        organization_id: str,
        dimension: UsageDimension,
    ) -> int:
        total = 0
        for ev in self._events:
            if ev.organization_id == organization_id and ev.dimension == dimension:
                total += ev.quantity
        return total
