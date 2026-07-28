from collections.abc import Callable
import hashlib

from app.domain.policies.media_validation_policy import MAX_IMAGE_BYTES
from tests.conftest import MeetingAPITestContext
from tests.security.conftest import media_headers


def _post_media(
    context: MeetingAPITestContext,
    content: bytes,
    *,
    filename: str,
    media_type: str,
    request_id: str,
):
    context.authenticate(context.organizer_token)
    return context.client.post(
        "/api/multimodal/media/validate",
        content=content,
        headers=media_headers(
            context,
            filename=filename,
            media_type=media_type,
            request_id=request_id,
        ),
    )


def test_fake_mime_jpg_containing_executable_data_is_rejected(
    meeting_api_context: MeetingAPITestContext,
) -> None:
    response = _post_media(
        meeting_api_context,
        b"MZ\x90\x00executable-payload",
        filename="attack.jpg",
        media_type="image/jpeg",
        request_id="fake-mime",
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_oversized_image_is_rejected_with_413(
    meeting_api_context: MeetingAPITestContext,
) -> None:
    content = b"\x89PNG\r\n\x1a\n" + (b"\x00" * (MAX_IMAGE_BYTES - 7))
    response = _post_media(
        meeting_api_context,
        content,
        filename="large.png",
        media_type="image/png",
        request_id="oversized-image",
    )

    assert len(content) == MAX_IMAGE_BYTES + 1
    assert response.status_code == 413


def test_audio_duration_limit_is_rejected_with_400(
    meeting_api_context: MeetingAPITestContext,
    wav_bytes: Callable[[float], bytes],
) -> None:
    response = _post_media(
        meeting_api_context,
        wav_bytes(31),
        filename="long.wav",
        media_type="audio/wav",
        request_id="long-audio",
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "AUDIO_DURATION_EXCEEDED"


def test_path_traversal_filename_is_rejected_with_400(
    meeting_api_context: MeetingAPITestContext,
    png_bytes: bytes,
) -> None:
    response = _post_media(
        meeting_api_context,
        png_bytes,
        filename="../secret.png",
        media_type="image/png",
        request_id="path-traversal",
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_FILENAME"


def test_valid_media_persists_hash_and_metadata_but_not_content(
    meeting_api_context: MeetingAPITestContext,
    png_bytes: bytes,
) -> None:
    context = meeting_api_context
    response = _post_media(
        context,
        png_bytes,
        filename="safe.png",
        media_type="image/png",
        request_id="valid-media",
    )

    assert response.status_code == 200
    assert response.json()["media_hash"] == hashlib.sha256(png_bytes).hexdigest()
    record = context.multimodal_audit_records()[0]
    assert record["request_id"] == "valid-media"
    assert record["actor_user_id"] == context.organizer_id
    assert record["conversation_id"] == "security-conversation"
    assert record["input_modality"] == "image"
    assert record["media_size"] == len(png_bytes)
    assert record["provider"] == "not_invoked"
    assert record["authorization_decision"] == "allowed"
    assert record["entitlement_decision"] == "not_applicable"
    assert record["tts_allowed"] is False
    assert record["status"] == "validated"
    assert png_bytes not in repr(record).encode()
