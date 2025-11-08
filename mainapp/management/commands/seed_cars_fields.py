from typing import Optional, List, Dict, Any
from django.core.management.base import BaseCommand
from django.utils import timezone
from mainapp.models import AdCategory, FieldType, FieldDefinition


class Command(BaseCommand):
    help = "Seed 'cars' category and common field definitions with dependent make/model choices (idempotent updater)"

    def handle(self, *args, **kwargs):
        # ---- Category --------------------------------------------------------
        cars, _ = AdCategory.objects.get_or_create(
            key="cars",
            defaults={"name_en": "Cars", "name_ar": "سيارات"},
        )

        # ---- FieldType cache --------------------------------------------------
        FT = {ft.key: ft for ft in FieldType.objects.all()}
        required_types = {"text", "textarea", "number", "select"}
        missing = required_types - set(FT.keys())
        if missing:
            raise SystemExit(
                f"Missing FieldType(s): {', '.join(sorted(missing))}. "
                "Run: python manage.py seed_field_types"
            )

        # ---- Choice helpers ---------------------------------------------------
        current_year = timezone.now().year
        start_year = 1970

        def year_choices_desc() -> List[Dict[str, Any]]:
            return [
                {"value": str(y), "label_en": str(y), "label_ar": str(y)}
                for y in range(current_year, start_year - 1, -1)
            ]

        def year_bucket_choices() -> List[Dict[str, Any]]:
            buckets = [
                ("2020-2025", "2020 - 2025"),
                ("2015-2019", "2015 - 2019"),
                ("2010-2014", "2010 - 2014"),
                ("2005-2009", "2005 - 2009"),
                ("2000-2004", "2000 - 2004"),
                ("1990-1999", "1990 - 1999"),
                ("1980-1989", "1980 - 1989"),
                ("<1980", "Before 1980"),
            ]
            return [{"value": v, "label_en": lbl, "label_ar": lbl} for v, lbl in buckets]

        def mileage_bucket_choices() -> List[Dict[str, Any]]:
            labels = [
                ("0-5000", "0 - 5,000 km"),
                ("5000-10000", "5,000 - 10,000 km"),
                ("10000-20000", "10,000 - 20,000 km"),
                ("20000-50000", "20,000 - 50,000 km"),
                ("50000-100000", "50,000 - 100,000 km"),
                ("100000-150000", "100,000 - 150,000 km"),
                ("150000-200000", "150,000 - 200,000 km"),
                ("200000+", "200,000+ km"),
            ]
            return [{"value": v, "label_en": lbl, "label_ar": lbl} for v, lbl in labels]

        # ---- Cars (make → model hierarchy) ------------------------------------
        CAR_MAKE_MODEL = {
            "mercedes": {
                "label_en": "Mercedes",
                "label_ar": "مرسيدس",
                "models": [
                    {"value": "s300", "label_en": "S300", "label_ar": "S300"},
                    {"value": "e200", "label_en": "E200", "label_ar": "E200"},
                    {"value": "c180", "label_en": "C180", "label_ar": "C180"},
                ],
            },
            "bmw": {
                "label_en": "BMW",
                "label_ar": "بي إم دبليو",
                "models": [
                    {"value": "320i", "label_en": "320i", "label_ar": "320i"},
                    {"value": "520i", "label_en": "520i", "label_ar": "520i"},
                    {"value": "x5", "label_en": "X5", "label_ar": "X5"},
                ],
            },
            "audi": {
                "label_en": "Audi",
                "label_ar": "أودي",
                "models": [
                    {"value": "a3", "label_en": "A3", "label_ar": "A3"},
                    {"value": "a4", "label_en": "A4", "label_ar": "A4"},
                    {"value": "q7", "label_en": "Q7", "label_ar": "Q7"},
                ],
            },
            "toyota": {
                "label_en": "Toyota",
                "label_ar": "تويوتا",
                "models": [
                    {"value": "camry", "label_en": "Camry", "label_ar": "كامري"},
                    {"value": "corolla", "label_en": "Corolla", "label_ar": "كورولا"},
                    {"value": "prado", "label_en": "Prado", "label_ar": "برادو"},
                ],
            },
            "hyundai": {
                "label_en": "Hyundai",
                "label_ar": "هيونداي",
                "models": [
                    {"value": "elantra", "label_en": "Elantra", "label_ar": "النترا"},
                    {"value": "sonata", "label_en": "Sonata", "label_ar": "سوناتا"},
                    {"value": "tucson", "label_en": "Tucson", "label_ar": "توسان"},
                ],
            },
            "kia": {
                "label_en": "Kia",
                "label_ar": "كيا",
                "models": [
                    {"value": "sportage", "label_en": "Sportage", "label_ar": "سبورتاج"},
                    {"value": "cerato", "label_en": "Cerato", "label_ar": "سيراتو"},
                    {"value": "seltos", "label_en": "Seltos", "label_ar": "سيلتوس"},
                ],
            },
        }

        MAKE_CHOICES = [
            {"value": k, "label_en": v["label_en"], "label_ar": v["label_ar"]}
            for k, v in CAR_MAKE_MODEL.items()
        ]

        MODEL_CHOICES = []
        for make_key, make_data in CAR_MAKE_MODEL.items():
            for model in make_data["models"]:
                MODEL_CHOICES.append({
                    "parent_value": make_key,
                    "value": model["value"],
                    "label_en": model["label_en"],
                    "label_ar": model["label_ar"],
                })

        GEARBOX_CHOICES = [
            {"value": "automatic",       "label_en": "Automatic",       "label_ar": "أوتوماتيك"},
            {"value": "manual",          "label_en": "Manual",          "label_ar": "عادي"},
            {"value": "semi_automatic",  "label_en": "Semi-Automatic",  "label_ar": "نصف أوتوماتيك"},
        ]

        FUEL_CHOICES = [
            {"value": "gasoline", "label_en": "Gasoline", "label_ar": "بنزين"},
            {"value": "diesel",   "label_en": "Diesel",   "label_ar": "ديزل"},
            {"value": "hybrid",   "label_en": "Hybrid",   "label_ar": "هايبرد"},
            {"value": "electric", "label_en": "Electric", "label_ar": "كهرباء"},
            {"value": "lpg",      "label_en": "LPG",      "label_ar": "غاز"},
        ]

        COLOR_CHOICES = [
            {"value": "white",  "label_en": "White",  "label_ar": "أبيض"},
            {"value": "black",  "label_en": "Black",  "label_ar": "أسود"},
            {"value": "silver", "label_en": "Silver", "label_ar": "فضي"},
            {"value": "gray",   "label_en": "Gray",   "label_ar": "رمادي"},
            {"value": "blue",   "label_en": "Blue",   "label_ar": "أزرق"},
            {"value": "red",    "label_en": "Red",    "label_ar": "أحمر"},
            {"value": "green",  "label_en": "Green",  "label_ar": "أخضر"},
            {"value": "beige",  "label_en": "Beige",  "label_ar": "بيج"},
            {"value": "brown",  "label_en": "Brown",  "label_ar": "بني"},
            {"value": "gold",   "label_en": "Gold",   "label_ar": "ذهبي"},
            {"value": "orange", "label_en": "Orange", "label_ar": "برتقالي"},
            {"value": "yellow", "label_en": "Yellow", "label_ar": "أصفر"},
        ]

        # ---- Upsert helper ----------------------------------------------------
        def upsert_field(
            key: str,
            tkey: str,
            label_en: str,
            label_ar: str,
            required: bool,
            order_index: int,
            visible_public: bool = True,
            validation: Optional[Dict[str, Any]] = None,
            choices: Optional[List[Dict[str, Any]]] = None,
            placeholder_en: Optional[str] = None,
            placeholder_ar: Optional[str] = None,
        ):
            obj, created = FieldDefinition.objects.get_or_create(
                category=cars, key=key,
                defaults=dict(
                    type=FT[tkey],
                    label_en=label_en,
                    label_ar=label_ar,
                    required=required,
                    order_index=order_index,
                    visible_public=visible_public,
                    validation=validation,
                    choices=choices,
                    placeholder_en=placeholder_en,
                    placeholder_ar=placeholder_ar,
                ),
            )
            if created:
                self.stdout.write(f"+ created {key}")
            else:
                obj.type = FT[tkey]
                obj.label_en = label_en
                obj.label_ar = label_ar
                obj.required = required
                obj.order_index = order_index
                obj.visible_public = visible_public
                obj.validation = validation
                obj.choices = choices
                obj.placeholder_en = placeholder_en
                obj.placeholder_ar = placeholder_ar
                obj.save()
                self.stdout.write(f"~ updated {key}")

        # ---- Core fields ------------------------------------------------------
        # --- Make (parent select) ---
        upsert_field(
            key="make", tkey="select",
            label_en="Make", label_ar="الماركة",
            required=True, order_index=10,
            choices=MAKE_CHOICES,
        )

        # --- Model (child select) ---
        upsert_field(
            key="model", tkey="select",
            label_en="Model", label_ar="الموديل",
            required=True, order_index=20,
            choices=MODEL_CHOICES,
            validation={"depends_on": "make"},
        )

        # Year as SELECT (1970..current)
        upsert_field(
            key="year", tkey="select",
            label_en="Year", label_ar="السنة",
            required=True, order_index=30,
            choices=year_choices_desc(), validation=None,
        )

        # Optional: Year range buckets (for filters)
        upsert_field(
            key="year_range", tkey="select",
            label_en="Year (Range)", label_ar="السنة (نطاق)",
            required=False, order_index=35,
            choices=year_bucket_choices(),
        )

        # Mileage as SELECT (bucketed)
        upsert_field(
            key="mileage_km", tkey="select",
            label_en="Mileage (km)", label_ar="المسافة المقطوعة (كم)",
            required=False, order_index=40,
            choices=mileage_bucket_choices(), validation=None,
        )

        upsert_field("gearbox", "select", "Gearbox", "ناقل الحركة", False, 50, choices=GEARBOX_CHOICES)
        upsert_field("fuel", "select", "Fuel Type", "نوع الوقود", False, 60, choices=FUEL_CHOICES)
        upsert_field("color", "select", "Color", "اللون", False, 70, choices=COLOR_CHOICES)

        upsert_field(
            key="description", tkey="textarea",
            label_en="Description", label_ar="الوصف",
            required=False, order_index=80,
            placeholder_en="Condition, options, service history...",
            placeholder_ar="الحالة، المواصفات، سجل الصيانة...",
        )

        self.stdout.write(self.style.SUCCESS("Cars category & fields seeded (updated)."))
