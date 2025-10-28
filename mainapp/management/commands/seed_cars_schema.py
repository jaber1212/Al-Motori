from django.core.management.base import BaseCommand
from mainapp.models import AdCategory, FieldType, FieldDefinition

class Command(BaseCommand):
    help = "Seed 'cars' category and common field definitions (legacy/simple)"

    def handle(self, *args, **kwargs):
        cars, _ = AdCategory.objects.get_or_create(
            key="cars", defaults={"name_en": "Cars", "name_ar": "cars"}
        )
        FT = {ft.key: ft for ft in FieldType.objects.all()}

        defs = [
            ("make",       "text",      True,  10, None, {"placeholder_en": "BMW"}),
            ("model",      "text",      True,  20, None, {"placeholder_en": "320i"}),
            ("year",       "number",    True,  30, {"minimum": 1980, "maximum": 2030}, None),
            ("mileage_km", "number",    False, 40, {"minimum": 0}, None),
            ("gearbox",    "select",    False, 50, None, {"choices": ["Automatic", "Manual"]}),
            ("fuel",       "select",    False, 60, None, {"choices": ["Gasoline", "Diesel", "Hybrid", "Electric"]}),
            ("color",      "text",      False, 70, None, None),
            ("description","textarea",  False, 80, None, None),
        ]

        for key, tkey, req, idx, validation, extra in defs:
            FieldDefinition.objects.get_or_create(
                category=cars, key=key,
                defaults={
                    "type": FT[tkey],
                    "label_en": key.capitalize(),
                    "label_ar": key,
                    "required": req,
                    "order_index": idx,
                    "visible_public": True,
                    "validation": validation,
                    "placeholder_en": (extra or {}).get("placeholder_en"),
                    "choices": (extra or {}).get("choices"),   # ← FIX ADDED
                }
            )
        self.stdout.write(self.style.SUCCESS("Cars category & fields seeded (legacy)."))
