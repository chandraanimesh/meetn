class ResourceNotFoundError(Exception):
    """Raised when the requested application resource does not exist."""


class ResourceAccessDeniedError(Exception):
    """Raised when an authenticated principal cannot access a resource."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class ResourceConflictError(Exception):
    """Raised when a valid write conflicts with existing resource state."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class LLMProviderUnavailableError(Exception):
    """Raised when the configured LLM provider cannot serve a request."""


class LLMProviderResponseError(Exception):
    """Raised when an LLM provider returns an unusable response."""


class InvalidMediaRequestError(Exception):
    """Raised when media metadata or duration is invalid."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class MediaTooLargeError(Exception):
    """Raised when media exceeds the configured bounded size."""


class UnsupportedMediaTypeError(Exception):
    """Raised when declared, detected, and extension media types disagree."""
