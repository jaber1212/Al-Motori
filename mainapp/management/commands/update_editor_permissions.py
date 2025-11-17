from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

from mainapp.models import (
    Ad, AdCategory, FieldDefinition,
    AdMedia, AdFieldValue, Profile, QRCode
)
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = "Create or update the Editor role with all required permissions"

    def handle(self, *args, **kwargs):
        editor, _ = Group.objects.get_or_create(name="Editor")
        allow = []

        # -----------------------------
        # 1 — View permissions for all Editor-accessible models
        # -----------------------------
        models = [
            Ad, AdCategory, FieldDefinition,
            AdMedia, AdFieldValue, Profile,
            QRCode, User
        ]

        for Model in models:
            ct = ContentType.objects.get_for_model(Model)
            codename = f"view_{Model._meta.model_name}"
            try:
                allow.append(Permission.objects.get(content_type=ct, codename=codename))
            except Permission.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"Missing permission: {codename}"))

        # -----------------------------
        # 2 — Allow add/change Ads only
        # -----------------------------
        ad_ct = ContentType.objects.get_for_model(Ad)
        for codename in ["add_ad", "change_ad"]:
            allow.append(Permission.objects.get(content_type=ad_ct, codename=codename))

        # -----------------------------
        # 3 — Allow Editors to update their own profile
        # (admin logic restricts to OWN profile only)
        # -----------------------------
        profile_ct = ContentType.objects.get_for_model(Profile)
        allow.append(Permission.objects.get(content_type=profile_ct, codename="change_profile"))

        # -----------------------------
        # 4 — No delete permissions added
        # -----------------------------

        # Remove duplicates & assign
        editor.permissions.set(list(set(allow)))
        editor.save()

        self.stdout.write(self.style.SUCCESS("Editor role permissions updated successfully!"))
