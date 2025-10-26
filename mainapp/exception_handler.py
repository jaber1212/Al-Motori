# mainapp/exception_handler.py
from django.core.exceptions import ValidationError as DjangoValidationError, ObjectDoesNotExist
from django.db import IntegrityError
from rest_framework.views import exception_handler as drf_handler
from rest_framework.exceptions import ValidationError, AuthenticationFailed, NotAuthenticated, PermissionDenied
from rest_framework import status as http
from .utils import api_err

def custom_exception_handler(exc, context):
    # DRF native first (keeps debug info for browsable API if needed)
    response = drf_handler(exc, context)
    if response is not None:
        # Normalize any DRF-produced response
        message = getattr(response, "data", None) or "Issue."
        return api_err(message=message, code=_code_for_exc(exc), http_status=http.HTTP_200_OK)

    # Non-DRF exceptions we want to unify too:
    if isinstance(exc, (ValidationError, DjangoValidationError)):
        return api_err(message=str(exc), code="VALIDATION_ERROR", http_status=http.HTTP_200_OK)

    if isinstance(exc, (AuthenticationFailed, NotAuthenticated)):
        return api_err(message="Invalid credentials.", code="AUTH_FAILED", http_status=http.HTTP_200_OK)

    if isinstance(exc, PermissionDenied):
        return api_err(message="Permission denied.", code="FORBIDDEN", http_status=http.HTTP_200_OK)

    if isinstance(exc, ObjectDoesNotExist):
        return api_err(message="Not found.", code="NOT_FOUND", http_status=http.HTTP_200_OK)

    if isinstance(exc, IntegrityError):
        # Try to map unique constraints to friendly text
        msg = str(exc).lower()
        if "phone" in msg:
            return api_err(message="Phone already registered.", code="PHONE_EXISTS", http_status=http.HTTP_200_OK)
        if "email" in msg:
            return api_err(message="Email already registered.", code="EMAIL_EXISTS", http_status=http.HTTP_200_OK)
        return api_err(message="Account already exists with this phone/email.", code="UNIQUE_CONSTRAINT", http_status=http.HTTP_200_OK)

    # Fallback
    return api_err(message="Issue.", code="SERVER_ERROR", http_status=http.HTTP_200_OK)


def _code_for_exc(exc) -> str:
    if isinstance(exc, ValidationError):
        return "VALIDATION_ERROR"
    if isinstance(exc, AuthenticationFailed):
        return "AUTH_FAILED"
    if isinstance(exc, NotAuthenticated):
        return "NOT_AUTHENTICATED"
    if isinstance(exc, PermissionDenied):
        return "FORBIDDEN"
    return "ERROR"
