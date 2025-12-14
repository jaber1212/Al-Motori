import json, logging, time, requests
from django.conf import settings


WHATSAPP_PHONE_NUMBER_ID = "885985071265943"  # استبدله من الإعدادات إن شئت
GRAPH_URL = f"https://graph.facebook.com/v21.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"

def send_whatsapp_template(
    to_e164: str,
    template_name: str,
    lang_code: str,
    body_params=None,            # مثال: [{"type":"text","text":"123456"}]
    url_button_params=None       # dict: { "0": "ABCDEF", "1": "..." } حسب أزرارك
):
    body_params = body_params or []
    url_button_params = url_button_params or {}

    headers = {
        "Authorization": f"Bearer EAAfm5UumvzIBPYe6fFPGlNtiwSYUe1YpbAbsF5jxxAXXFgAXs8ZArRWMFZBaXiJ3vDxZA0KS0X8220DvwjWTZBOI3x3JzIyvNAutvrnnqShkKwM2blvFujbia2ROxFKSvWqgAh3fq9Q9z2QflS7gX6UATZCkEZCghw5cav6qhZCSc51Q44dZA5qtWhaL4t9PDqPbZBAZDZD",
        "Content-Type": "application/json",
    }

    components = []
    if body_params:
        components.append({"type": "body", "parameters": body_params})

    # أزرار URL الديناميكية (لكل زر بمؤشره)
    for idx, val in url_button_params.items():
        components.append({
            "type": "button",
            "sub_type": "url",
            "index": str(idx),
            "parameters": [{"type": "text", "text": str(val)}]
        })

    payload = {
        "messaging_product": "whatsapp",
        "to": to_e164,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": lang_code},
            "components": components
        }
    }

    for attempt in range(3):
        resp = requests.post(GRAPH_URL, headers=headers, data=json.dumps(payload), timeout=20)
        try:
            data = resp.json()
        except Exception:
            data = {"_raw": resp.text}

        if resp.ok:
            return data

        if resp.status_code in (429, 500, 502, 503, 504):
            time.sleep(1.5 * (attempt + 1))
            continue

        raise RuntimeError(f"WhatsApp send failed {resp.status_code}: {json.dumps(data)}")

    raise RuntimeError("WhatsApp send failed after retries")
from typing import Any, Dict, List, Optional, Union
