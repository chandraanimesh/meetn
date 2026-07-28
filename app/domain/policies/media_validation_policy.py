import re

from app.domain.value_objects.access_decision import AccessDecision
from app.domain.value_objects.media import InputModality, MediaDescriptor


MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_AUDIO_BYTES = 10 * 1024 * 1024
MAX_AUDIO_DURATION_MS = 30_000
MAX_UPLOAD_BYTES = MAX_AUDIO_BYTES

ALLOWED_EXTENSION_BY_MIME = {
    "image/jpeg": frozenset({".jpg", ".jpeg"}),
    "image/png": frozenset({".png"}),
    "image/webp": frozenset({".webp"}),
    "audio/wav": frozenset({".wav"}),
}
EXPECTED_MODALITY_BY_MIME = {
    "image/jpeg": InputModality.IMAGE,
    "image/png": InputModality.IMAGE,
    "image/webp": InputModality.IMAGE,
    "audio/wav": InputModality.AUDIO,
}
SAFE_FILENAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,254}$")


class MediaValidationPolicy:
    VERSION = "multimodal-media-validation.v1"

    def evaluate(self, descriptor: MediaDescriptor) -> AccessDecision:
        scope = f"media:{descriptor.input_modality.value}"
        filename = descriptor.filename
        if (
            not SAFE_FILENAME_PATTERN.fullmatch(filename)
            or ".." in filename
            or "/" in filename
            or "\\" in filename
            or "\x00" in filename
        ):
            return self._deny("invalid_filename", scope)
        if descriptor.size_bytes <= 0:
            return self._deny("empty_media", scope)

        declared_mime = descriptor.declared_mime.casefold()
        detected_mime = (
            descriptor.detected_mime.casefold()
            if descriptor.detected_mime is not None
            else None
        )
        if declared_mime not in ALLOWED_EXTENSION_BY_MIME:
            return self._deny("unsupported_media_type", scope)
        if detected_mime not in ALLOWED_EXTENSION_BY_MIME:
            return self._deny("actual_media_type_unknown", scope)
        if declared_mime != detected_mime:
            return self._deny("mime_type_mismatch", scope)

        extension = "." + filename.rsplit(".", maxsplit=1)[-1].casefold()
        if extension not in ALLOWED_EXTENSION_BY_MIME[detected_mime]:
            return self._deny("extension_mismatch", scope)
        if EXPECTED_MODALITY_BY_MIME[detected_mime] is not descriptor.input_modality:
            return self._deny("modality_mismatch", scope)

        maximum_size = (
            MAX_IMAGE_BYTES
            if descriptor.input_modality is InputModality.IMAGE
            else MAX_AUDIO_BYTES
        )
        if descriptor.size_bytes > maximum_size:
            return self._deny("media_too_large", scope)

        if descriptor.input_modality is InputModality.AUDIO:
            if descriptor.duration_ms is None or descriptor.duration_ms < 0:
                return self._deny("invalid_audio_container", scope)
            if descriptor.duration_ms > MAX_AUDIO_DURATION_MS:
                return self._deny("audio_duration_exceeded", scope)

        return AccessDecision(
            allowed=True,
            reason="media_validated",
            resource_scope=scope,
            policy_version=self.VERSION,
        )

    def _deny(self, reason: str, scope: str) -> AccessDecision:
        return AccessDecision(
            allowed=False,
            reason=reason,
            resource_scope=scope,
            policy_version=self.VERSION,
        )
