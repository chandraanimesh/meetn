from typing import Annotated

from fastapi import APIRouter, Depends, Header

from app.api.dependencies.auth import (
    get_authenticated_principal,
    require_csrf,
)
from app.api.dependencies.media import MediaBody
from app.api.dependencies.services import (
    get_media_validation_service,
    get_required_request_id,
)
from app.api.schemas.multimodal import MediaValidationResponse
from app.application.dto.multimodal import MediaValidationCommand
from app.application.services.media_validation_service import (
    MediaValidationService,
)
from app.domain.value_objects.authorization_facts import AuthenticatedPrincipal


router = APIRouter(prefix="/api/multimodal", tags=["multimodal"])

Principal = Annotated[
    AuthenticatedPrincipal,
    Depends(get_authenticated_principal),
]
ValidationService = Annotated[
    MediaValidationService,
    Depends(get_media_validation_service),
]
RequestID = Annotated[str, Depends(get_required_request_id)]
CSRF = Annotated[None, Depends(require_csrf)]
Filename = Annotated[
    str,
    Header(alias="X-Media-Filename", min_length=1, max_length=255),
]
ConversationID = Annotated[
    str,
    Header(alias="X-Conversation-ID", min_length=1, max_length=128),
]
DeclaredMIME = Annotated[
    str,
    Header(alias="Content-Type", min_length=1, max_length=128),
]


@router.post(
    "/media/validate",
    response_model=MediaValidationResponse,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/octet-stream": {
                    "schema": {"type": "string", "format": "binary"}
                }
            },
        }
    },
)
async def validate_media(
    media: MediaBody,
    principal: Principal,
    service: ValidationService,
    request_id: RequestID,
    csrf_valid: CSRF,
    filename: Filename,
    conversation_id: ConversationID,
    declared_mime: DeclaredMIME,
) -> MediaValidationResponse:
    result = await service.validate(
        principal=principal,
        command=MediaValidationCommand(
            conversation_id=conversation_id,
            filename=filename,
            declared_mime=declared_mime,
            content=media,
        ),
        request_id=request_id,
    )
    return MediaValidationResponse(
        conversation_id=result.conversation_id,
        input_modality=result.input_modality,
        media_hash=result.media_hash,
        media_type=result.media_type,
        media_size=result.media_size,
        duration_ms=result.duration_ms,
        status="validated",
    )
