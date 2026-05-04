
import qrcode
from io import BytesIO
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from django.contrib.staticfiles import finders


def generate_qr_image(data, code):

    file_name = f"qr_{code}.png"
    path = f"qr/images/{file_name}"

    # ✅ If already exists — return directly
    if default_storage.exists(path):
        return default_storage.url(path), None

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=20,
        border=2,
    )

    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    # ✅ Add center logo
    try:
        from PIL import Image



        logo_path = finders.find("logo.png")

        if not logo_path:
            raise Exception("Logo NOT FOUND in static files")
        logo = Image.open(logo_path)

        # Resize logo (20% of QR size)
        qr_width, qr_height = img.size
        logo_size = int(qr_width * 0.2)
        logo = logo.resize((logo_size, logo_size))

        # Calculate position
        pos = ((qr_width - logo_size) // 2, (qr_height - logo_size) // 2)

        img.paste(logo, pos, mask=logo if logo.mode == 'RGBA' else None)
    except Exception as e:
        print("Logo not added:", e)

    buffer = BytesIO()
    img.save(buffer, format="PNG")

    default_storage.save(path, ContentFile(buffer.getvalue()))

    return default_storage.url(path), img

def generate_qr_pdf(qr_image, code):

    file_name = f"qr_{code}.pdf"
    path = f"qr/pdf/{file_name}"

    # ✅ If already exists — return directly
    if default_storage.exists(path):
        return default_storage.url(path)

    buffer = BytesIO()

    c = canvas.Canvas(buffer, pagesize=A4)

    size = 120 * mm

    c.drawInlineImage(
        qr_image,
        50 * mm,
        120 * mm,
        size,
        size
    )

    # ✅ Add branding text
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50 * mm, 100 * mm, "Powered by Ai Motoria")

    c.setFont("Helvetica", 12)
    c.drawString(50 * mm, 110 * mm, f"Code: {code}")

    c.save()

    pdf = buffer.getvalue()

    default_storage.save(path, ContentFile(pdf))

    return default_storage.url(path)