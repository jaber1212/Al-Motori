from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

from mainapp.models import (
    Profile, Ad, AdMedia, QRCode, QRScanLog, Notification
)

class Command(BaseCommand):
    help = "Create Admin role with safe permissions"

    def handle(self, *args, **kwargs):

        admin_group, _ = Group.objects.get_or_create(name="Admin")

        allow = []

        # ALLOWED VIEW MODELS
        view_models = [
            Profile, Ad, AdMedia,
            QRCode, QRScanLog,
            Notification
        ]

        for Model in view_models:
            ct = ContentType.objects.get_for_model(Model)
            allow.append(
                Permission.objects.get(
                    content_type=ct,
                    codename=f"view_{Model._meta.model_name}"
                )
            )

        # Allow change_profile only
        pct = ContentType.objects.get_for_model(Profile)
        allow.append(
            Permission.objects.get(content_type=pct, codename="change_profile")
        )

        # Allow add_notification
        nct = ContentType.objects.get_for_model(Notification)
        allow.append(
            Permission.objects.get(content_type=nct, codename="add_notification")
        )

        # Apply permissions
        admin_group.permissions.set(allow)
        admin_group.save()

        self.stdout.write(self.style.SUCCESS("Admin role fixed successfully"))
