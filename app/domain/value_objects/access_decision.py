from dataclasses import dataclass
from typing import TypedDict


class AccessDecisionPayload(TypedDict):
    allowed: bool
    reason: str


@dataclass(frozen=True, slots=True)
class AccessDecision:
    """Immutable authorization result with stable policy metadata."""

    allowed: bool
    reason: str
    resource_scope: str
    policy_version: str

    def to_dict(self) -> AccessDecisionPayload:
        """Return the transport-neutral decision shape exposed to callers."""

        return {"allowed": self.allowed, "reason": self.reason}

