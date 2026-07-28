import logging
from time import perf_counter
import re
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.request_context import (
    reset_authenticated_user_id,
    reset_request_id,
    set_authenticated_user_id,
    set_request_id,
)


REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
logger = logging.getLogger("app.request")


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        supplied_request_id = request.headers.get("X-Request-ID")
        request_id = (
            supplied_request_id
            if supplied_request_id is not None
            and REQUEST_ID_PATTERN.fullmatch(supplied_request_id)
            else str(uuid.uuid4())
        )
        request_token = set_request_id(request_id)
        user_token = set_authenticated_user_id(None)
        started_at = perf_counter()
        safe_metadata = {
            "request_id": request_id,
            "route": request.url.path,
            "method": request.method,
        }
        logger.info("request_started", extra=safe_metadata)

        try:
            response = await call_next(request)
        except Exception as exc:
            logger.exception(
                "request_failed",
                extra={
                    **safe_metadata,
                    "duration_ms": max(0, round((perf_counter() - started_at) * 1000)),
                    "exception_type": type(exc).__name__,
                },
            )
            raise
        else:
            response.headers["X-Request-ID"] = request_id
            logger.info(
                "request_completed",
                extra={
                    **safe_metadata,
                    "duration_ms": max(0, round((perf_counter() - started_at) * 1000)),
                    "status_code": response.status_code,
                },
            )
            return response
        finally:
            reset_authenticated_user_id(user_token)
            reset_request_id(request_token)
