"""Domain errors that services raise without knowing about HTTP, and the one exception handler that turns them into JSON error responses."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class DomainError(Exception):
    """A request a service can't fulfil. Subclasses set the HTTP status the API answers with."""

    status_code = 400


class NotFoundError(DomainError):
    """The requested mod, file or record doesn't exist."""

    status_code = 404


class UpstreamError(DomainError):
    """A translation provider or external tool failed."""

    status_code = 502


async def _domain_error(_request: Request, exc: Exception) -> JSONResponse:
    """Answer a domain error with its status and the same `detail` body as `HTTPException`, so the frontend reads both alike.

    Args:
        _request: The failed request.
        exc: The service's error.

    Returns:
        The JSON error response.
    """
    status_code = exc.status_code if isinstance(exc, DomainError) else 500
    return JSONResponse(status_code=status_code, content={"detail": str(exc)})


def register_error_handler(app: FastAPI) -> None:
    """Map `DomainError` to HTTP on `app`.

    Args:
        app: The app, or a test app mounting a single router.
    """
    app.add_exception_handler(DomainError, _domain_error)
