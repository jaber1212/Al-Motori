import logging, traceback, uuid
from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError, ObjectDoesNotExist
from django.db import IntegrityError
from rest_framework.views import exception_handler as drf_handler
from rest_framework.exceptions import (
    ValidationError, AuthenticationFailed, NotAuthenticated, PermissionDenied
)
from rest_framework import status as http
from .utils import api_err

log = logging.getLogger(__name__)

def _want_debug(context) -> bool:
    # Enable details if: DEBUG=True, or client asks via header or query (?debug=1)
    request = context.get("request")
    if settings.DEBUG:
        return True
    if request is not None:
        if request.headers.get("X-Debug") == "1":
            return True
        if request.GET.get("debug") == "1":
            return True
    return False

def custom_exception_handler(exc, context):
    """
    Always returns our unified shape.
    - If DRF built a Response, we pass-through its data in `errors` and flatten `message`.
    - If it's unhandled, we log, attach trace_id, and show details only if debug allowed.
    """
    request = context.get("request")
    view = context.get("view")
    want_debug = _want_debug(context)
    trace_id = str(uuid.uuid4())

    # 1) Let DRF build a response if it can (ValidationError, 404, etc.)
    drf_response = drf_handler(exc, context)
    if drf_response is not None:
        # Keep details! Use a friendly top-line message but preserve original payload in `errors`.
        payload = getattr(drf_response, "data", {}) or {}
        # Try to extract a human message
        msg = _first_message(payload) or str(exc) or "Issue."
        code = _code_for_exc(exc)

        # You can choose to keep the original HTTP code in production logs; response stays 200 by design.
        return api_err(
            message=msg,
            errors=payload,                    # ← details you were missing
            code=code,
            http_status=http.HTTP_200_OK       # keep 200 as you wanted
        )

    # 2) Unhandled server errors
    base_msg = "Issue."
    code = "SERVER_ERROR"

    # Log with trace_id for correlation
    log.exception("Unhandled exception (%s) on %s %s", trace_id, getattr(request, "method", "?"), getattr(request, "path", "?"))

    # IntegrityError specialization
    if isinstance(exc, IntegrityError):
        lower = str(exc).lower()
        if "phone" in lower:
            base_msg, code = "Phone already registered.", "PHONE_EXISTS"
        elif "email" in lower:
            base_msg, code = "Email already registered.", "EMAIL_EXISTS"
        else:
            base_msg, code = "Account already exists with this phone/email.", "UNIQUE_CONSTRAINT"

    errors = {"trace_id": trace_id}
    if want_debug:
        # Safe to expose details in dev / when explicitly requested
        errors.update({
            "exception": exc.__class__.__name__,
            "detail": str(exc),
            "view": getattr(view, "__class__", type("?", (), {})).__name__,
            "endpoint": getattr(request, "path", None),
            "method": getattr(request, "method", None),
            "traceback": traceback.format_exc(),
        })
        # If exception has args (e.g., ValidationError list/dict) add them
        if isinstance(exc, (ValidationError, DjangoValidationError)) and hasattr(exc, "detail"):
            errors["detail"] = exc.detail

    return api_err(
        message=base_msg if not want_debug else (str(exc) or base_msg),
        errors=errors,
        code=code,
        http_status=http.HTTP_200_OK
    )

def _first_message(detail):
    """Extract first human-readable message from nested dict/list/strings."""
    if isinstance(detail, dict) and detail:
        return _first_message(next(iter(detail.values())))
    if isinstance(detail, (list, tuple)) and detail:
        return _first_message(detail[0])
    if isinstance(detail, str):
        return detail
    return None

def _code_for_exc(exc) -> str:
    if isinstance(exc, ValidationError):      return "VALIDATION_ERROR"
    if isinstance(exc, AuthenticationFailed): return "AUTH_FAILED"
    if isinstance(exc, NotAuthenticated):     return "NOT_AUTHENTICATED"
    if isinstance(exc, PermissionDenied):     return "FORBIDDEN"
    if isinstance(exc, ObjectDoesNotExist):   return "NOT_FOUND"
    return "ERROR"
