from typing import Annotated

from fastapi import Depends, Request

from app.application.exceptions import (
    InvalidMediaRequestError,
    MediaTooLargeError,
)
from app.domain.policies.media_validation_policy import MAX_UPLOAD_BYTES


async def get_bounded_media_body(request: Request) -> bytes:
    raw_content_length = request.headers.get("content-length")
    if raw_content_length is not None:
        try:
            content_length = int(raw_content_length)
        except ValueError as exc:
            raise InvalidMediaRequestError(
                "INVALID_CONTENT_LENGTH",
                "The media content length is invalid",
            ) from exc
        if content_length < 0:
            raise InvalidMediaRequestError(
                "INVALID_CONTENT_LENGTH",
                "The media content length is invalid",
            )
        if content_length > MAX_UPLOAD_BYTES:
            raise MediaTooLargeError("Media exceeds the absolute upload limit")

    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_UPLOAD_BYTES:
            raise MediaTooLargeError("Media exceeds the absolute upload limit")
    return bytes(body)


MediaBody = Annotated[bytes, Depends(get_bounded_media_body)]
