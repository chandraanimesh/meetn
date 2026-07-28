from dataclasses import dataclass, field

from app.domain.entities.recording import Membership, MembershipPlan
from app.domain.policies.entitlement_policy import EntitlementPolicy
from app.domain.value_objects.access_decision import AccessDecision


@dataclass(frozen=True, slots=True)
class EntitlementService:
    policy: EntitlementPolicy = field(default_factory=EntitlementPolicy)

    def can_access_recording(
        self,
        membership: Membership | None,
        required_plan: MembershipPlan,
    ) -> AccessDecision:
        return self.policy.can_access_recording(membership, required_plan)
