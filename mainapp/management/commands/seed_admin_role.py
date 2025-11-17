from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

from mainapp.models import (
    Profile, FieldType, AdCategory, FieldDefinition,
    Ad, AdFieldValue, AdMedia, QRCode, QRScanLog,Notification
)


class Command(BaseCommand):
    help = "Create Admin group with very specific permissions"

    def handle(self, *args, **kwargs):

        # Create or get the group
        admin_group, _ = Group.objects.get_or_create(name="Admin")

        # ----- ALWAYS ALLOW VIEW permission for ALL models -----
        all_models = [
            Profile, FieldType, AdCategory, FieldDefinition,
            Ad, AdFieldValue, AdMedia, QRCode, QRScanLog,
            Notification
        ]

        view_permissions = []
        for model in all_models:
            ct = ContentType.objects.get_for_model(model)
            perm = Permission.objects.get(content_type=ct, codename=f"view_{model.__name__.lower()}")
            view_permissions.append(perm)

        admin_group.permissions.add(*view_permissions)

        # ----- Profile: allow EDIT (change_profile) -----
        pct = ContentType.objects.get_for_model(Profile)
        change_profile = Permission.objects.get(content_type=pct, codename="change_profile")
        admin_group.permissions.add(change_profile)

        # ----- QRCode: allow ADD only -----
        qct = ContentType.objects.get_for_model(QRCode)
        add_qr = Permission.objects.get(content_type=qct, codename="add_qrcode")
        admin_group.permissions.add(add_qr)

        # ----- DONE -----
        self.stdout.write(self.style.SUCCESS("Admin role created with correct permissions."))
