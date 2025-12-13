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





# mainapp/utils.py
from rest_framework.response import Response
from rest_framework import status as http
from rest_framework.exceptions import ErrorDetail

# 👉 flip this to True if you really want errors to also return status: True

def api_ok(message: str = "OK", data=None, code: str = "OK", http_status=http.HTTP_200_OK):
    return Response({
        "status": True,
        "message": message,
        "code": code,
        "data": data if data is not None else {}
    }, status=http_status)

def api_err(message: str = "Issue.", errors=None, code: str = "ERROR", http_status=http.HTTP_400_BAD_REQUEST):
    """
    Normalized error response.
    - By default returns HTTP 200 with your requested shape.
    - If you prefer real HTTP error codes, change http_status above (e.g., 400/401/403).
    """
    # If you want conventional behavior, set ALWAYS_TRUE_FOR_ERRORS = False
    return Response({
        "status": False,
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



# utils.py (optional helpers)
def ok_obj(message="OK", data=None, code="OK", http_status=http.HTTP_200_OK):
    """Always return an object in data ({} if None)."""
    if data is None: data = {}
    return api_ok(message, data=data, code=code, http_status=http_status)

def ok_list(message="OK", data=None, code="OK", http_status=http.HTTP_200_OK):
    """Always return a list in data ([] if None)."""
    if data is None: data = []
    # api_ok accepts lists fine; only default in api_ok is {}, but we override it
    return api_ok(message, data=data, code=code, http_status=http_status)




from  .models import  AdCategory,FieldDefinition,CarModel,CarMake
def normalize(value: str) -> str:
    return value.lower().strip().replace(" ", "_")


def sync_car_fields():
    category = AdCategory.objects.get(key="cars")

    make_field = FieldDefinition.objects.get(category=category, key="make")
    model_field = FieldDefinition.objects.get(category=category, key="model")

    # =========================
    # MAKES
    # =========================
    make_choices = [{
        "value": "other",
        "label_en": "other",
        "label_ar": "اخرى"
    }]

    makes = CarMake.objects.filter(is_active=True)

    for make in makes:
        value = normalize(make.name_en)
        if value == "other":
            continue

        make_choices.append({
            "value": value,
            "label_en": make.name_en,
            "label_ar": make.name_ar
        })

    make_field.choices = make_choices
    make_field.save(update_fields=["choices"])

    # =========================
    # MODELS (PARENT / CHILD)
    # =========================
    model_choices = [{
        "value": "other",
        "label_en": "other",
        "label_ar": "اخرى",
        "parent_value": "other"
    }]

    seen = set()  # 🔒 منع التكرار

    models = CarModel.objects.filter(
        is_active=True,
        make__is_active=True
    ).select_related("make")

    for model in models:
        value = normalize(model.name_en)
        parent_value = normalize(model.make.name_en)

        key = (value, parent_value)
        if key in seen:
            continue
        seen.add(key)

        model_choices.append({
            "value": value,
            "label_en": model.name_en,
            "label_ar": model.name_ar,
            "parent_value": parent_value
        })

    model_field.choices = model_choices
    model_field.save(update_fields=["choices"])
