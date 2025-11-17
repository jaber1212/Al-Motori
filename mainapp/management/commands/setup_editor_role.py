from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from mainapp.models import (
    Ad, AdCategory, FieldDefinition, AdMedia, AdFieldValue, Profile
)

class Command(BaseCommand):
    help = "Create Editor role with proper permissions"

    def handle(self, *args, **kwargs):
        editor, _ = Group.objects.get_or_create(name="Editor")
        allow = []

        # -----------------------------
        # 1️⃣ View ALL models
        # -----------------------------
        models = [Ad, AdCategory, FieldDefinition, AdMedia, AdFieldValue, Profile]
        for Model in models:
            ct = ContentType.objects.get_for_model(Model)
            codename = f"view_{Model._meta.model_name}"
            allow.append(Permission.objects.get(content_type=ct, codename=codename))

        # -----------------------------
        # 2️⃣ Ad permissions (Editor edits only OWN ads)
        # -----------------------------
        ad_ct = ContentType.objects.get_for_model(Ad)
        for codename in ["add_ad", "change_ad"]:
            allow.append(Permission.objects.get(content_type=ad_ct, codename=codename))

        # -----------------------------
        # 3️⃣ Profile — allow editor to edit ONLY his own profile
        # -----------------------------
        profile_ct = ContentType.objects.get_for_model(Profile)
        for codename in ["change_profile"]:
            allow.append(Permission.objects.get(content_type=profile_ct, codename=codename))

        # -----------------------------
        # 4️⃣ No delete permissions AT ALL
        # -----------------------------
        # (we simply do NOT add delete permissions)

        editor.permissions.set(allow)
        editor.save()

        self.stdout.write(self.style.SUCCESS("Editor role permissions updated!"))
