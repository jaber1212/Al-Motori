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
