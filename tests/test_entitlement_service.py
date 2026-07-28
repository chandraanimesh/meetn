from datetime import timedelta

import pytest

from app.application.services.entitlement_service import EntitlementService
from app.domain.entities.recording import (
    Membership,
    MembershipPlan,
    MembershipStatus,
)
from app.domain.time import utc_now_naive


@pytest.mark.parametrize(
    ("membership", "required_plan", "allowed"),
    [
        (None, MembershipPlan.STARTER, True),
        (None, MembershipPlan.PROFESSIONAL, False),
        (
            Membership(user_id="starter", plan=MembershipPlan.STARTER),
            MembershipPlan.PROFESSIONAL,
            False,
        ),
        (
            Membership(user_id="professional", plan=MembershipPlan.PROFESSIONAL),
            MembershipPlan.PROFESSIONAL,
            True,
        ),
        (
            Membership(user_id="organization", plan=MembershipPlan.ORGANIZATION),
            MembershipPlan.PROFESSIONAL,
            True,
        ),
        (
            Membership(
                user_id="inactive",
                plan=MembershipPlan.ORGANIZATION,
                status=MembershipStatus.INACTIVE,
            ),
            MembershipPlan.PROFESSIONAL,
            False,
        ),
        (
            Membership(
                user_id="expired",
                plan=MembershipPlan.ORGANIZATION,
                valid_until=utc_now_naive() - timedelta(minutes=1),
            ),
            MembershipPlan.PROFESSIONAL,
            False,
        ),
    ],
)
def test_recording_entitlement_matrix(
    membership: Membership | None,
    required_plan: MembershipPlan,
    allowed: bool,
) -> None:
    decision = EntitlementService().can_access_recording(
        membership, required_plan
    )

    assert decision.allowed is allowed
    assert decision.reason == (
        "plan_entitled" if allowed else "plan_restriction"
    )
    assert decision.resource_scope == "feature:recording_access"
    assert decision.policy_version == "recording-entitlement.v1"

