from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.application.exceptions import (
    InvalidMediaRequestError,
    LLMProviderResponseError,
    LLMProviderUnavailableError,
    MediaTooLargeError,
    ResourceAccessDeniedError,
    ResourceConflictError,
    ResourceNotFoundError,
    UnsupportedMediaTypeError,
)
from app.core.exceptions import AppError
from app.core.request_context import get_request_id
import logging

logger = logging.getLogger("app.api")


def add_exception_handlers(app: FastAPI):
    @app.exception_handler(InvalidMediaRequestError)
    async def invalid_media_request_handler(
        request: Request, exc: InvalidMediaRequestError
    ):
        req_id = get_request_id()
        logger.info(
            "media_validation_rejected",
            extra={"request_id": req_id, "error_code": exc.code},
        )
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "request_id": req_id,
                    "details": None,
                }
            },
        )

    @app.exception_handler(MediaTooLargeError)
    async def media_too_large_handler(request: Request, exc: MediaTooLargeError):
        req_id = get_request_id()
        logger.info(
            "media_validation_rejected",
            extra={"request_id": req_id, "error_code": "MEDIA_TOO_LARGE"},
        )
        return JSONResponse(
            status_code=413,
            content={
                "error": {
                    "code": "MEDIA_TOO_LARGE",
                    "message": "Media exceeds the configured size limit",
                    "request_id": req_id,
                    "details": None,
                }
            },
        )

    @app.exception_handler(UnsupportedMediaTypeError)
    async def unsupported_media_type_handler(
        request: Request, exc: UnsupportedMediaTypeError
    ):
        req_id = get_request_id()
        logger.info(
            "media_validation_rejected",
            extra={"request_id": req_id, "error_code": "UNSUPPORTED_MEDIA_TYPE"},
        )
        return JSONResponse(
            status_code=415,
            content={
                "error": {
                    "code": "UNSUPPORTED_MEDIA_TYPE",
                    "message": "The media type is unsupported or inconsistent",
                    "request_id": req_id,
                    "details": None,
                }
            },
        )

    @app.exception_handler(ResourceNotFoundError)
    async def resource_not_found_handler(request: Request, exc: ResourceNotFoundError):
        req_id = get_request_id()
        logger.info("resource_not_found", extra={"request_id": req_id})
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "RESOURCE_NOT_FOUND",
                    "message": "Resource not found",
                    "request_id": req_id,
                    "details": None,
                }
            },
        )

    @app.exception_handler(ResourceAccessDeniedError)
    async def resource_access_denied_handler(
        request: Request, exc: ResourceAccessDeniedError
    ):
        req_id = get_request_id()
        logger.warning(
            "resource_access_denied",
            extra={"request_id": req_id, "error_code": exc.code},
        )
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "request_id": req_id,
                    "details": None,
                }
            },
        )

    @app.exception_handler(ResourceConflictError)
    async def resource_conflict_handler(request: Request, exc: ResourceConflictError):
        req_id = get_request_id()
        logger.info(
            "resource_conflict",
            extra={"request_id": req_id, "error_code": exc.code},
        )
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "request_id": req_id,
                    "details": None,
                }
            },
        )

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        req_id = get_request_id()
        logger.error(
            "application_error",
            extra={"request_id": req_id, "error_code": exc.code},
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "request_id": req_id,
                    "details": exc.details,
                }
            },
        )

    @app.exception_handler(LLMProviderUnavailableError)
    async def llm_provider_unavailable_handler(
        request: Request, exc: LLMProviderUnavailableError
    ):
        req_id = get_request_id()
        logger.error(
            "external_provider_failed",
            extra={
                "request_id": req_id,
                "provider": "groq",
                "exception_type": type(exc).__name__,
            },
        )
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "LLM_PROVIDER_UNAVAILABLE",
                    "message": "The assistant is temporarily unavailable",
                    "request_id": req_id,
                    "details": None,
                }
            },
        )

    @app.exception_handler(LLMProviderResponseError)
    async def llm_provider_response_handler(
        request: Request, exc: LLMProviderResponseError
    ):
        req_id = get_request_id()
        logger.error(
            "external_provider_failed",
            extra={
                "request_id": req_id,
                "provider": "groq",
                "exception_type": type(exc).__name__,
            },
        )
        return JSONResponse(
            status_code=502,
            content={
                "error": {
                    "code": "LLM_PROVIDER_INVALID_RESPONSE",
                    "message": "The assistant returned an invalid response",
                    "request_id": req_id,
                    "details": None,
                }
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        req_id = get_request_id()
        logger.exception(
            "request_failed",
            extra={
                "request_id": req_id,
                "exception_type": type(exc).__name__,
            },
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred",
                    "request_id": req_id,
                    "details": None,
                }
            },
        )
