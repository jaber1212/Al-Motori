import csv, secrets, string
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from models import QRCode

def make_code(length=8):
    # A-Z + 0-9 (no ambiguous chars if you want)
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

class Command(BaseCommand):
    help = "Generate a batch of pre-printed QR codes and export as CSV."

    def add_arguments(self, parser):
        parser.add_argument("--batch", required=True, help="Batch label, e.g. OCT-2025")
        parser.add_argument("--count", type=int, default=100, help="How many codes")
        parser.add_argument("--outfile", default="qr_batch.csv", help="CSV output path")
        parser.add_argument("--domain", default="https://motori.a.alce-qa.com", help="Public domain")

    def handle(self, *args, **opts):
        batch = opts["batch"]
        count = opts["count"]
        outfile = opts["outfile"]
        domain = opts["domain"]

        created = []
        for _ in range(count):
            # ensure uniqueness
            for _attempt in range(10):
                code = make_code(8)  # tweak length if you want
                if not QRCode.objects.filter(code=code).exists():
                    q = QRCode.objects.create(code=code, batch=batch)
                    created.append(q)
                    break
            else:
                raise CommandError("Failed to generate a unique code after many attempts.")

        with open(outfile, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["code", "url"])
            for q in created:
                w.writerow([q.code, f"{domain}/qr/{q.code}"])

        self.stdout.write(self.style.SUCCESS(f"Generated {len(created)} QR codes → {outfile}"))
