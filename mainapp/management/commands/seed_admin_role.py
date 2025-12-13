from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

from mainapp.models import (
    Profile, Ad, AdMedia,
    QRCode, QRScanLog, Notification,
    CarMake, CarModel
)

class Command(BaseCommand):
    help = "Create Admin role with safe permissions"

    def handle(self, *args, **kwargs):

        admin_group, _ = Group.objects.get_or_create(name="Admin")

        allow = []

        # ----------------------------------
        # VIEW permissions (read-only)
        # ----------------------------------
        view_models = [
            Profile, Ad, AdMedia,
            QRCode, QRScanLog,
            Notification,
            CarMake, CarModel
        ]

        for Model in view_models:
            ct = ContentType.objects.get_for_model(Model)
            allow.append(
                Permission.objects.get(
                    content_type=ct,
                    codename=f"view_{Model._meta.model_name}"
                )
            )

        # ----------------------------------
        # EDIT Profile
        # ----------------------------------
        profile_ct = ContentType.objects.get_for_model(Profile)
        allow.append(
            Permission.objects.get(
                content_type=profile_ct,
                codename="change_profile"
            )
        )

        # ----------------------------------
        # ADD Notification
        # ----------------------------------
        notif_ct = ContentType.objects.get_for_model(Notification)
        allow.append(
            Permission.objects.get(
                content_type=notif_ct,
                codename="add_notification"
            )
        )

        # ----------------------------------
        # MANAGE CarMake / CarModel
        # (add + change, no delete)
        # ----------------------------------
        for Model in (CarMake, CarModel):
            ct = ContentType.objects.get_for_model(Model)
            allow.extend([
                Permission.objects.get(content_type=ct, codename=f"add_{Model._meta.model_name}"),
                Permission.objects.get(content_type=ct, codename=f"change_{Model._meta.model_name}"),
            ])

        # ----------------------------------
        # DELETE Ad only
        # ----------------------------------
        ad_ct = ContentType.objects.get_for_model(Ad)
        allow.append(
            Permission.objects.get(
                content_type=ad_ct,
                codename="delete_ad"
            )
        )

        # ----------------------------------
        # Apply permissions
        # ----------------------------------
        admin_group.permissions.set(allow)
        admin_group.save()

        self.stdout.write(self.style.SUCCESS("✅ Admin role fixed successfully"))
