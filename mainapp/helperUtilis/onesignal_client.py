import requests
from django.conf import settings


def send_push_notification(player_ids, title, message):
    """
    Send a push notification via OneSignal using credentials from environment variables.
    """

    if not player_ids:
        return {"error": "No player IDs provided"}

    url = "https://onesignal.com/api/v1/notifications"

    headers = {
        # Use secure API key from settings (loaded from .env)
        "Authorization": f"Basic {settings.ONESIGNAL_API_KEY}",
        "Content-Type": "application/json; charset=utf-8",
    }

    payload = {
        # Use secure app ID from settings (loaded from .env)
        "app_id": settings.ONESIGNAL_APP_ID,
        "include_player_ids": player_ids,
        "headings": {"en": title},
        "contents": {"en": message},
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        # Return readable error for debugging or logging
        return {"error": str(e)}
