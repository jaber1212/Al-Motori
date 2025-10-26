from django.db import transaction, IntegrityError
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from rest_framework import serializers, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError
from rest_framework.authtoken.models import Token
import random

# ----------------------------
# Utils
# ----------------------------
from rest_framework.exceptions import ValidationError, ErrorDetail

def success_response(message, data=None):
    return Response({"status": True, "message": message, "data": data or {}})
def success_responseArray(message, data=None):
    return Response({"status": True, "message": message, "data": data or []})


def error_response(message):
    if isinstance(message, dict):
        # flatten nested dict to first message
        first_key = next(iter(message))
        message = message[first_key]
    if isinstance(message, list) and message:
        message = message[0]
    return Response({"status": False, "message": str(message)}, status=status.HTTP_400_BAD_REQUEST)


def first_error_message(detail):
    """
    Recursively extract the first human-readable error message
    from DRF ValidationError.detail (dict/list/ErrorDetail/str).
    """
    if isinstance(detail, dict):
        # Take the first field's errors
        return first_error_message(next(iter(detail.values())))
    if isinstance(detail, (list, tuple)):
        # Take the first item in the list
        return first_error_message(detail[0]) if detail else "Invalid input."
    if isinstance(detail, ErrorDetail):
        return str(detail)
    # Fallback (string or unknown type)
    return str(detail)



def generate_otp():
    return f"{random.randint(100000, 999999)}"



# mainapp/utils.py
from rest_framework.response import Response
from rest_framework import status as http
from rest_framework.exceptions import ErrorDetail

# 👉 flip this to True if you really want errors to also return status: True
ALWAYS_TRUE_FOR_ERRORS = True

def api_ok(message: str = "OK", data=None, code: str = "OK", http_status=http.HTTP_200_OK):
    return Response({
        "status": True,
        "message": message,
        "code": code,
        "data": data if data is not None else {}
    }, status=http_status)

def api_err(message: str = "Issue.", errors=None, code: str = "ERROR", http_status=http.HTTP_200_OK):
    """
    Normalized error response.
    - By default returns HTTP 200 with your requested shape.
    - If you prefer real HTTP error codes, change http_status above (e.g., 400/401/403).
    """
    # If you want conventional behavior, set ALWAYS_TRUE_FOR_ERRORS = False
    status_field = True if ALWAYS_TRUE_FOR_ERRORS else False
    return Response({
        "status": status_field,
        "message": _flatten_message(message),
        "code": code,
        "errors": errors if errors is not None else {}
    }, status=http_status)

def _flatten_message(detail):
    """Extract first human-readable message from DRF/Django details."""
    if isinstance(detail, dict):
        return _flatten_message(next(iter(detail.values()), "Issue."))
    if isinstance(detail, (list, tuple)):
        return _flatten_message(detail[0]) if detail else "Issue."
    if isinstance(detail, ErrorDetail):
        return str(detail)
    return str(detail or "Issue.")
