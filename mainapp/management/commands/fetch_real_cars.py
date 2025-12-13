import requests
from django.core.management.base import BaseCommand
from django.db import transaction

from mainapp.models import (
    CarMakeS,
    CarModelS,
)
from mainapp.utils import sync_car_fields

REAL_MAKES = [
    "acura","alfa romeo","aston martin","audi","bentley","bmw","bugatti","cadillac","chevrolet",
    "chrysler","citroen","dodge","ferrari","fiat","ford","gmc","honda","hyundai","infiniti",
    "jaguar","jeep","kia","koenigsegg","lamborghini","land rover","lexus","lincoln","lotus",
    "maserati","mazda","mclaren","mercedes-benz","mini","mitsubishi","nissan","pagani","peugeot",
    "porsche","ram","renault","rolls-royce","saab","subaru","suzuki","tesla","toyota","volkswagen",
    "volvo"
]


class Command(BaseCommand):
    help = "Seed CarMake and CarModel tables from VPIC (source of truth)"

    @transaction.atomic
    def handle(self, *args, **kwargs):
        self.stdout.write("🔄 Fetching car makes from VPIC...")

        url = "https://vpic.nhtsa.dot.gov/api/vehicles/getallmakes?format=json"
        raw = requests.get(url, timeout=30).json().get("Results", [])

        # -----------------------------
        # 1) Filter real makes
        # -----------------------------
        makes = set()
        for item in raw:
            name = item["Make_Name"].strip()
            if name.lower() in REAL_MAKES:
                makes.add(name)

        makes = sorted(makes)

        self.stdout.write(f"✅ Found {len(makes)} real makes")

        # -----------------------------
        # 2) Insert / Update CarMake
        # -----------------------------
        make_map = {}  # EN name -> CarMake instance

        for name in makes:
            make, created = CarMakeS.objects.get_or_create(
                name_en=name,
                defaults={
                    "name_ar": name,  # لاحقًا ممكن تعريب حقيقي
                    "is_active": True
                }
            )
            make_map[name] = make

        self.stdout.write("✅ CarMake table synced")

        # -----------------------------
        # 3) Fetch & Insert CarModel
        # -----------------------------
        total_models = 0

        for make_name, make_obj in make_map.items():
            self.stdout.write(f"↳ Fetching models for {make_name}")

            url = f"https://vpic.nhtsa.dot.gov/api/vehicles/GetModelsForMake/{make_name}?format=json"
            models = requests.get(url, timeout=30).json().get("Results", [])

            for m in models:
                model_name = m["Model_Name"].strip()

                CarModelS.objects.get_or_create(
                    make=make_obj,
                    name_en=model_name,
                    defaults={
                        "name_ar": model_name,
                        "is_active": True
                    }
                )
                total_models += 1

        self.stdout.write(f"✅ Inserted / Updated {total_models} models")

        # -----------------------------
        # 4) Sync to FieldDefinition
        # -----------------------------
        sync_car_fields()
        self.stdout.write(self.style.SUCCESS("🎉 Car schema seeded and synced successfully"))
#          python manage.py fetch_real_cars
