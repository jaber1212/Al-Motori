from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from mainapp.models import Ad, AdCategory, FieldDefinition, AdMedia, AdFieldValue

class Command(BaseCommand):
    help = "Create 'Editor' role with limited permissions"

    def handle(self, *args, **kwargs):
        editor, _ = Group.objects.get_or_create(name="Editor")

        allow = []
        # Editors manage Ads (add/change/view), but NOT delete
        ad_ct = ContentType.objects.get_for_model(Ad)
        for codename in ["add_ad", "change_ad", "view_ad"]:
            allow.append(Permission.objects.get(content_type=ad_ct, codename=codename))

        # Read-only for schema models
        for Model in [AdCategory, FieldDefinition]:
            ct = ContentType.objects.get_for_model(Model)
            allow.append(Permission.objects.get(content_type=ct, codename=f"view_{Model._meta.model_name}"))

        # Media & values (change/view only via Ad inlines)
        for Model in [AdMedia, AdFieldValue]:
            ct = ContentType.objects.get_for_model(Model)
            for codename in [f"view_{Model._meta.model_name}"]:
                allow.append(Permission.objects.get(content_type=ct, codename=codename))

        editor.permissions.set(allow)
        editor.save()

        self.stdout.write(self.style.SUCCESS("Editor role configured."))
        self.stdout.write(self.style.SUCCESS("Assign staff users to the 'Editor' group."))
