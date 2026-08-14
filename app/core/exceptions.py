from __future__ import annotations

import logging
from functools import wraps
from typing import Any, Awaitable, Callable, TypeVar

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Awaitable[Any]])


class AppException(Exception):
    """Base exception interne non-HTTP (transformée en 500 côté route)."""

    def __init__(self, message: str = "Erreur interne") -> None:
        super().__init__(message)
        self.message = message


def handle_exceptions(func: F) -> F:
    """
    Décorateur de route : attrape les AppException, les HTTPException (déjà
    levées avec le bon statut) et les erreurs inattendues (500).
    """

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await func(*args, **kwargs)
        except HTTPException:
            raise
        except AppException as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=exc.message,
            ) from exc
        except Exception as exc:
            logger.exception("Unhandled error in %s", getattr(func, "__name__", "route"))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erreur interne : {exc}",
            ) from exc

    return wrapper  # type: ignore[return-value]


class NotFoundException(HTTPException):
    """Raised when a requested resource does not exist (HTTP 404)"""

    def __init__(self, detail: str = "Ressource non trouvée") -> None:
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class UnauthorizedException(HTTPException):
    """Raised when authentication is required or has failed (HTTP 401)."""

    def __init__(self, detail: str = "Non autorisé") -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class ForbiddenException(HTTPException):
    """Raised when the authenticated user lacks the required permissions (HTTP 403)."""

    def __init__(self, detail: str = "Accès refusé") -> None:
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class BadRequestException(HTTPException):
    """Raised when the request payload or parameters are invalid (HTTP 400)."""

    def __init__(self, detail: str) -> None:
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class ConflictException(HTTPException):
    """Raised when the request conflicts with existing data (HTTP 409)."""

    def __init__(self, detail: str) -> None:
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)
