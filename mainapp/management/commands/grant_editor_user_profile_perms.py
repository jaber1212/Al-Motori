from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from mainapp.models import Profile

class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        editor, _ = Group.objects.get_or_create(name="Editor")

        # User perms
        from django.contrib.auth.models import User
        uct = ContentType.objects.get_for_model(User)
        user_perms = ["view_user"]  # add "change_user" if you want them editable
        # Profile perms
        pct = ContentType.objects.get_for_model(Profile)
        profile_perms = ["view_profile", "change_profile"]  # adjust as you like

        perms = []
        for codename in user_perms:
            perms.append(Permission.objects.get(content_type=uct, codename=codename))
        for codename in profile_perms:
            perms.append(Permission.objects.get(content_type=pct, codename=codename))

        editor.permissions.add(*perms)
        self.stdout.write(self.style.SUCCESS("Editor perms for User/Profile granted."))
