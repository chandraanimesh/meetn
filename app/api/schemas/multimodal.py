from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.value_objects.media import InputModality


class MediaValidationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    conversation_id: str = Field(min_length=1, max_length=128)
    input_modality: InputModality
    media_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    media_type: str = Field(min_length=1, max_length=128)
    media_size: int = Field(ge=1)
    duration_ms: int | None = Field(default=None, ge=0)
    status: Literal["validated"]
