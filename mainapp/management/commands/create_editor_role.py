from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

from mainapp.models import (
    Ad, AdCategory, FieldDefinition, AdMedia,
    AdFieldValue, Profile
)

class Command(BaseCommand):
    help = "Create or update the Editor role with correct permissions"

    def handle(self, *args, **kwargs):
        editor, _ = Group.objects.get_or_create(name="Editor")
        allow = []

        # -----------------------------
        # 1 — Allow view permission for ALL these models
        # -----------------------------
        models = [Ad, AdCategory, FieldDefinition, AdMedia, AdFieldValue, Profile]

        for Model in models:
            ct = ContentType.objects.get_for_model(Model)
            perm = Permission.objects.get(
                content_type=ct, codename=f"view_{Model._meta.model_name}"
            )
            allow.append(perm)

        # -----------------------------
        # 2 — Allow Editors to add/change Ads
        # -----------------------------
        ad_ct = ContentType.objects.get_for_model(Ad)
        for codename in ["add_ad", "change_ad"]:
            allow.append(Permission.objects.get(content_type=ad_ct, codename=codename))

        # -----------------------------
        # 3 — Allow Editors to edit ONLY their own Profile
        # (Admin code will enforce "own profile only")
        # -----------------------------
        prof_ct = ContentType.objects.get_for_model(Profile)
        allow.append(Permission.objects.get(content_type=prof_ct, codename="change_profile"))

        # -----------------------------
        # 4 — No delete permissions are added
        # -----------------------------

        # Assign permissions to group
        editor.permissions.set(allow)
        editor.save()

        self.stdout.write(self.style.SUCCESS("Editor role has been updated successfully!"))
