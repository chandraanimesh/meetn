from dataclasses import dataclass

from app.agent.action_registry import BackendActionRegistry
from app.application.dto.assistant import PageManifestDTO
from app.domain.entities.user import User


@dataclass(frozen=True, slots=True)
class SafeContextBuilder:
    """Build the minimum content-free context visible to the LLM."""

    def build(
        self,
        *,
        authenticated_user: User,
        page_manifest: PageManifestDTO,
        registry: BackendActionRegistry,
    ) -> dict[str, object]:
        return {
            "authenticated_user": {
                "display_name": authenticated_user.display_name,
            },
            "page_manifest": {
                "page_id": page_manifest.page_id,
                "active_meeting_id": page_manifest.active_meeting_id,
                "visible_meeting_ids": page_manifest.visible_meeting_ids,
            },
            "registered_actions": registry.llm_descriptors(),
        }
