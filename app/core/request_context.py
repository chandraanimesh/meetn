import contextvars

_request_id_ctx_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)
_authenticated_user_id_ctx_var: contextvars.ContextVar[str | None] = (
    contextvars.ContextVar("authenticated_user_id", default=None)
)


def get_request_id() -> str | None:
    return _request_id_ctx_var.get()


def set_request_id(request_id: str) -> contextvars.Token[str | None]:
    return _request_id_ctx_var.set(request_id)


def reset_request_id(token: contextvars.Token[str | None]) -> None:
    _request_id_ctx_var.reset(token)


def get_authenticated_user_id() -> str | None:
    return _authenticated_user_id_ctx_var.get()


def set_authenticated_user_id(
    user_id: str | None,
) -> contextvars.Token[str | None]:
    return _authenticated_user_id_ctx_var.set(user_id)


def reset_authenticated_user_id(
    token: contextvars.Token[str | None],
) -> None:
    _authenticated_user_id_ctx_var.reset(token)
