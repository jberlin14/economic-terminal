"""
API Error Handlers

Centralized error handling for consistent API responses.
"""

from typing import Optional, Dict, Any
from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from loguru import logger


class APIError(HTTPException):
    """Base API error with consistent format"""

    def __init__(
        self,
        status_code: int,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None
    ):
        super().__init__(status_code=status_code, detail=message)
        self.message = message
        self.details = details or {}
        self.error_code = error_code or self._get_error_code(status_code)

    @staticmethod
    def _get_error_code(status_code: int) -> str:
        """Get error code from status code"""
        codes = {
            400: 'BAD_REQUEST',
            401: 'UNAUTHORIZED',
            403: 'FORBIDDEN',
            404: 'NOT_FOUND',
            409: 'CONFLICT',
            422: 'VALIDATION_ERROR',
            500: 'INTERNAL_ERROR',
            502: 'BAD_GATEWAY',
            503: 'SERVICE_UNAVAILABLE',
        }
        return codes.get(status_code, 'UNKNOWN_ERROR')


class NotFoundError(APIError):
    """Resource not found error"""

    def __init__(self, resource: str, identifier: Optional[str] = None):
        message = f"{resource} not found"
        if identifier:
            message += f": {identifier}"

        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            message=message,
            details={'resource': resource, 'identifier': identifier}
        )


class ValidationError(APIError):
    """Validation error"""

    def __init__(self, message: str, field: Optional[str] = None):
        details = {'field': field} if field else {}
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message=message,
            details=details
        )


class DatabaseError(APIError):
    """Database operation error"""

    def __init__(self, operation: str, error: Optional[str] = None):
        message = f"Database error during {operation}"
        if error:
            message += f": {error}"

        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=message,
            details={'operation': operation, 'error': error}
        )


class ExternalAPIError(APIError):
    """External API error"""

    def __init__(self, service: str, error: Optional[str] = None):
        message = f"External API error ({service})"
        if error:
            message += f": {error}"

        super().__init__(
            status_code=status.HTTP_502_BAD_GATEWAY,
            message=message,
            details={'service': service, 'error': error}
        )


def create_error_response(
    status_code: int,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    error_code: Optional[str] = None
) -> JSONResponse:
    """
    Create a standardized error response.

    Args:
        status_code: HTTP status code
        message: Human-readable error message
        details: Additional error details
        error_code: Machine-readable error code

    Returns:
        JSONResponse with error information
    """
    error_code = error_code or APIError._get_error_code(status_code)

    response_data = {
        'error': {
            'code': error_code,
            'message': message,
            'status': status_code
        }
    }

    if details:
        response_data['error']['details'] = details

    return JSONResponse(
        status_code=status_code,
        content=response_data
    )


def log_error(
    error: Exception,
    context: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None
):
    """
    Log an error with context.

    Args:
        error: The exception
        context: Additional context about where/when the error occurred
        extra: Additional data to log
    """
    log_message = str(error)
    if context:
        log_message = f"[{context}] {log_message}"

    logger.error(log_message)

    if extra:
        logger.debug(f"Error details: {extra}")


def handle_database_error(error: Exception, operation: str) -> HTTPException:
    """
    Handle database errors consistently.

    Args:
        error: The database exception
        operation: Description of the operation that failed

    Returns:
        HTTPException to raise
    """
    log_error(error, f"Database - {operation}")
    return DatabaseError(operation, str(error))


def handle_external_api_error(error: Exception, service: str) -> HTTPException:
    """
    Handle external API errors consistently.

    Args:
        error: The API exception
        service: Name of the external service

    Returns:
        HTTPException to raise
    """
    log_error(error, f"External API - {service}")
    return ExternalAPIError(service, str(error))
