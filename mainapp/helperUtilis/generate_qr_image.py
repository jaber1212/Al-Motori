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

    # ⚠️ IMPORTANT: disable this during testing if needed
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

    # =========================
    # ✅ Add center circular logo
    # =========================
    try:
        from PIL import Image, ImageDraw

        # 🔹 Get static file correctly (production-safe)
        logo_path = finders.find("logo.png")

        if not logo_path:
            raise Exception("Logo NOT FOUND in static files")

        logo = Image.open(logo_path).convert("RGBA")

        # 🔹 Resize logo (smaller for better scanning)
        qr_width, qr_height = img.size
        logo_size = int(qr_width * 0.18)   # reduced from 0.2

        logo = logo.resize((logo_size, logo_size))

        # 🔹 Create circular mask
        mask = Image.new("L", (logo_size, logo_size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, logo_size, logo_size), fill=255)

        # 🔹 Add white background (improves scan reliability)
        white_bg = Image.new("RGBA", (logo_size, logo_size), (255, 255, 255, 255))
        white_bg.paste(logo, (0, 0), mask=logo)

        # 🔹 Center position
        pos = ((qr_width - logo_size) // 2, (qr_height - logo_size) // 2)

        # 🔹 Paste final logo
        img.paste(white_bg, pos, mask=mask)

    except Exception as e:
        print("❌ Logo not added:", e)

    # =========================
    # Save QR
    # =========================
    buffer = BytesIO()
    img.save(buffer, format="PNG")

    default_storage.save(path, ContentFile(buffer.getvalue()))

    return default_storage.url(path), img


def generate_qr_pdf(qr_image, code):

    file_name = f"qr_{code}.pdf"
    path = f"qr/pdf/{file_name}"

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

    # ✅ Branding text
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50 * mm, 100 * mm, "Powered by Ai Motoria")


    c.save()

    pdf = buffer.getvalue()

    default_storage.save(path, ContentFile(pdf))

    return default_storage.url(path)