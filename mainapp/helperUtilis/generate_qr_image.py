
import qrcode
from io import BytesIO
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm


def generate_qr_image(data, code):

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=20,
        border=2,
    )

    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buffer = BytesIO()
    img.save(buffer, format="PNG")

    file_name = f"qr_{code}.png"
    path = f"qr/images/{file_name}"

    default_storage.save(path, ContentFile(buffer.getvalue()))

    return default_storage.url(path), buffer


def generate_qr_pdf(qr_buffer, code):

    file_name = f"qr_{code}.pdf"
    path = f"qr/pdf/{file_name}"

    buffer = BytesIO()

    c = canvas.Canvas(buffer, pagesize=A4)

    size = 120 * mm

    c.drawInlineImage(
        qr_buffer,
        50 * mm,
        120 * mm,
        size,
        size
    )

    c.setFont("Helvetica", 12)
    c.drawString(50 * mm, 110 * mm, f"Code: {code}")

    c.save()

    pdf = buffer.getvalue()

    default_storage.save(path, ContentFile(pdf))

    return default_storage.url(path)