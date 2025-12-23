import json
from django import template
import json
import re
from django import template

register = template.Library()

@register.filter
def lang_value(value, lang):
    if not value:
        return ""

    val = value.strip()

    # Try JSON first
    try:
        data = json.loads(val)
        if isinstance(data, dict):
            return data.get(lang) or data.get("en") or ""
    except Exception:
        pass

    # Fallback: extract "en": or "ar":
    match = re.search(rf'"{lang}"\s*:\s*"([^"]+)"', val)
    if match:
        return match.group(1)

    return value
