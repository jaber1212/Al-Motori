# mainapp/management/commands/seed_cars_fields.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from mainapp.models import AdCategory, FieldType, FieldDefinition

class Command(BaseCommand):
    help = "Seed 'cars' category and common field definitions with choices"

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
                "Run your FieldType seeder first."
            )

        # ---- Choice helpers ---------------------------------------------------
        current_year = timezone.now().year
        start_year = 1970

        def year_choices_desc():
            # ["2025","2024",...,"1970"] as label/value pairs
            return [{"value": str(y), "label_en": str(y), "label_ar": str(y)}
                    for y in range(current_year, start_year - 1, -1)]

        def year_bucket_choices():
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

        def mileage_bucket_choices():
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
            # Arabic labels mirror English numerals for clarity in classifieds
            return [{"value": v, "label_en": lbl, "label_ar": lbl} for v, lbl in labels]

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
            {"value": "white",     "label_en": "White",     "label_ar": "أبيض"},
            {"value": "black",     "label_en": "Black",     "label_ar": "أسود"},
            {"value": "silver",    "label_en": "Silver",    "label_ar": "فضي"},
            {"value": "gray",      "label_en": "Gray",      "label_ar": "رمادي"},
            {"value": "blue",      "label_en": "Blue",      "label_ar": "أزرق"},
            {"value": "red",       "label_en": "Red",       "label_ar": "أحمر"},
            {"value": "green",     "label_en": "Green",     "label_ar": "أخضر"},
            {"value": "beige",     "label_en": "Beige",     "label_ar": "بيج"},
            {"value": "brown",     "label_en": "Brown",     "label_ar": "بني"},
            {"value": "gold",      "label_en": "Gold",      "label_ar": "ذهبي"},
            {"value": "orange",    "label_en": "Orange",    "label_ar": "برتقالي"},
            {"value": "yellow",    "label_en": "Yellow",    "label_ar": "أصفر"},
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
            validation: dict | None = None,
            choices: list | None = None,
            placeholder_en: str | None = None,
            placeholder_ar: str | None = None,
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
            if not created:
                # keep things fresh on repeated runs
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

        # ---- Core fields ------------------------------------------------------
        upsert_field(
            key="make", tkey="text",
            label_en="Make", label_ar="الماركة",
            required=True, order_index=10,
            placeholder_en="BMW", placeholder_ar="بي إم دبليو",
        )
        upsert_field(
            key="model", tkey="text",
            label_en="Model", label_ar="الموديل",
            required=True, order_index=20,
            placeholder_en="320i", placeholder_ar="320i",
        )
        # Year as number with validation (1970..current year)

        # Year as SELECT (1970..current), no validation
        upsert_field(
            key="year", tkey="select",
            label_en="Year", label_ar="السنة",
            required=True, order_index=30,
            choices=year_choices_desc(),  # ← 1970..current
            validation={"minimum": start_year, "maximum": current_year},
        )




        # Optional: year_range select for filtering UIs
        upsert_field(
            key="year_range", tkey="select",
            label_en="Year (Range)", label_ar="السنة (نطاق)",
            required=False, order_index=35,
            choices=year_bucket_choices(),
        )
        # Mileage number + range
        # Mileage as SELECT (buckets), no validation
        upsert_field(
            key="mileage_km", tkey="select",
            label_en="Mileage (km)", label_ar="المسافة المقطوعة (كم)",
            required=False, order_index=40,
            choices=mileage_bucket_choices(),
            validation={"minimum": 0},
        )
        upsert_field(
            key="mileage_range", tkey="select",
            label_en="Mileage (Range)", label_ar="المسافة (نطاق)",
            required=False, order_index=45,
            choices=mileage_bucket_choices(),
        )
        # Gearbox / Fuel
        upsert_field(
            key="gearbox", tkey="select",
            label_en="Gearbox", label_ar="ناقل الحركة",
            required=False, order_index=50,
            choices=GEARBOX_CHOICES,
        )
        upsert_field(
            key="fuel", tkey="select",
            label_en="Fuel Type", label_ar="نوع الوقود",
            required=False, order_index=60,
            choices=FUEL_CHOICES,
        )
        # Color (select of common values)
        upsert_field(
            key="color", tkey="select",
            label_en="Color", label_ar="اللون",
            required=False, order_index=70,
            choices=COLOR_CHOICES,
        )
        # Free text description
        upsert_field(
            key="description", tkey="textarea",
            label_en="Description", label_ar="الوصف",
            required=False, order_index=80,
            placeholder_en="Condition, options, service history...",
            placeholder_ar="الحالة، المواصفات، سجل الصيانة...",
        )

        # Optionally: expose a flat list of year choices (descending)
        # for apps that prefer a select instead of free number input
        upsert_field(
            key="year_select", tkey="select",
            label_en="Year (Select)", label_ar="السنة (قائمة)",
            required=False, order_index=31,
            choices=year_choices_desc(),
            visible_public=False,  # keep hidden in public UI if you only need it for filters
        )

        self.stdout.write(self.style.SUCCESS("Cars category & fields seeded (with choices)."))
