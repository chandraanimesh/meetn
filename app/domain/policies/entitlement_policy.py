from app.domain.entities.recording import Membership, MembershipPlan
from app.domain.time import utc_now_naive
from app.domain.value_objects.access_decision import AccessDecision


PLAN_LEVEL = {
    MembershipPlan.STARTER: 0,
    MembershipPlan.PROFESSIONAL: 1,
    MembershipPlan.ORGANIZATION: 2,
}


class EntitlementPolicy:
    VERSION = "recording-entitlement.v1"

    def can_access_recording(
        self,
        membership: Membership | None,
        required_plan: MembershipPlan,
    ) -> AccessDecision:
        evaluated_at = utc_now_naive()
        current_plan = MembershipPlan.STARTER
        if membership is not None and membership.is_active_at(evaluated_at):
            current_plan = membership.plan

        allowed = PLAN_LEVEL[current_plan] >= PLAN_LEVEL[required_plan]
        return AccessDecision(
            allowed=allowed,
            reason="plan_entitled" if allowed else "plan_restriction",
            resource_scope="feature:recording_access",
            policy_version=self.VERSION,
        )
