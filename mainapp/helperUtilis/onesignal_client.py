# notifications/utils/onesignal_client.py
import requests
from django.conf import settings

def send_push_notification(player_ids, title, message):
    if not player_ids:
        return {"error": "No player IDs provided"}

    url = "https://onesignal.com/api/v1/notifications"
    headers = {
        "Authorization": f"Basic os_v2_app_roz2vmwof5esplt5qrbw5cno7nglookiewqeu7eaje4lz62prrv7yojfu2h565iqwlexeosfnfiaexvn2fsxffclbzgofcnebovoh5y",
        "Content-Type": "application/json; charset=utf-8",
    }
    payload = {
        "app_id": "8bb3aab2-ce2f-4927-ae7d-84436e89aefb",
        "include_player_ids": ["8a39faa1-1f00-4ab1-9cf6-6abc031cd65c"],
        "headings": {"en": title},
        "contents": {"en": message},
    }

    response = requests.post(url, json=payload, headers=headers)
    return response.json()
