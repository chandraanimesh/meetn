from dataclasses import dataclass, field

from app.domain.value_objects.media import InputModality


@dataclass(frozen=True, slots=True)
class MediaValidationCommand:
    conversation_id: str
    filename: str
    declared_mime: str
    content: bytes = field(repr=False)


@dataclass(frozen=True, slots=True)
class MediaValidationResult:
    conversation_id: str
    input_modality: InputModality
    media_hash: str
    media_type: str
    media_size: int
    duration_ms: int | None
    status: str = "validated"
