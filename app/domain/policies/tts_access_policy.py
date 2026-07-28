from enum import Enum

from app.domain.value_objects.access_decision import AccessDecision


class TTSContentSource(str, Enum):
    SAFE_ASSISTANT_RESPONSE = "safe_assistant_response"
    CONFIDENTIAL_NOTE = "confidential_note"
    TRANSCRIPT = "transcript"
    RAW_MODEL_OUTPUT = "raw_model_output"
    UNKNOWN = "unknown"


class TTSAccessPolicy:
    VERSION = "multimodal-tts-access.v1"

    def can_synthesize(self, source: TTSContentSource) -> AccessDecision:
        scope = f"tts:{source.value}"
        if source is TTSContentSource.SAFE_ASSISTANT_RESPONSE:
            return AccessDecision(
                allowed=True,
                reason="safe_assistant_response",
                resource_scope=scope,
                policy_version=self.VERSION,
            )
        reasons = {
            TTSContentSource.CONFIDENTIAL_NOTE: "confidential_content_forbidden",
            TTSContentSource.TRANSCRIPT: "transcript_content_forbidden",
            TTSContentSource.RAW_MODEL_OUTPUT: "untrusted_model_output",
            TTSContentSource.UNKNOWN: "unsupported_tts_source",
        }
        return AccessDecision(
            allowed=False,
            reason=reasons.get(source, "unsupported_tts_source"),
            resource_scope=scope,
            policy_version=self.VERSION,
        )
