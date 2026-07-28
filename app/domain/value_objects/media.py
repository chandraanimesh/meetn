from dataclasses import dataclass
from enum import Enum


class InputModality(str, Enum):
    UNKNOWN = "unknown"
    TEXT = "text"
    AUDIO = "audio"
    IMAGE = "image"


@dataclass(frozen=True, slots=True)
class MediaDescriptor:
    filename: str
    declared_mime: str
    detected_mime: str | None
    size_bytes: int
    duration_ms: int | None
    input_modality: InputModality
