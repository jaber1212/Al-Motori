from django.core.management.base import BaseCommand
from mainapp.models import FieldType

DEFAULTS = [
    {"key": "text",        "name": "Text"},
    {"key": "textarea",    "name": "Text Area"},
    {"key": "number",      "name": "Number", "config": {"step": 1}},
    {"key": "date",        "name": "Date"},
    {"key": "select",      "name": "Select"},
    {"key": "multiselect", "name": "Multi Select"},
    {"key": "currency",    "name": "Currency"},
    {"key": "boolean",     "name": "Boolean"},
]

class Command(BaseCommand):
    help = "Seed default FieldType rows"

    def handle(self, *args, **kwargs):
        for ft in DEFAULTS:
            obj, created = FieldType.objects.get_or_create(
                key=ft["key"],
                defaults={"name": ft["name"], "config": ft.get("config")}
            )
            if not created:
                obj.name = ft["name"]
                obj.config = ft.get("config")
                obj.save()
                self.stdout.write(f"~ updated FieldType {obj.key}")
            else:
                self.stdout.write(f"+ created FieldType {obj.key}")
        self.stdout.write(self.style.SUCCESS("Field types seeded."))
