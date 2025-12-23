import json
from django import template

register = template.Library()

@register.filter
def lang_value(value, lang):
    if not value:
        return ""

    if isinstance(value, str):
        val = value.strip()
        if val.startswith("{") and val.endswith("}"):
            try:
                data = json.loads(val)
                if isinstance(data, dict):
                    return data.get(lang) or data.get("en") or ""
            except Exception:
                pass

    return value
