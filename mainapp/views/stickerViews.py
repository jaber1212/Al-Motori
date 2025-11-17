import qrcode
from django.http import HttpResponse
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from django.conf import settings
import os
from mainapp.models import QRCode


def generate_qr_sticker_sheet(request, batch_name):

    qs = QRCode.objects.filter(batch=batch_name).order_by("code")
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    A4_W, A4_H = A4

    # === Sticker SIZE ===
    STICKER_W = 95 * mm
    STICKER_H = 55 * mm

    COLS = 2
    SPACING_X = 6 * mm
    SPACING_Y = 8 * mm

    margin_x = (A4_W - (COLS * STICKER_W) - (SPACING_X * (COLS - 1))) / 2
    margin_y = 15 * mm

    # === ELEMENT SIZES (UPDATED) ===
    QR_SIZE = 36 * mm
    QR_LEFT_PADDING = 4 * mm

    LOGO_SIZE = 12 * mm                  # ← SMALLER LOGO
    LOGO_RIGHT_PADDING = 8 * mm
    LOGO_TOP_PADDING = 8 * mm            # ← FIXED POSITION

    TEXT_LEFT_SPACE_FROM_QR = 2 * mm
    TEXT_TOP_PADDING_UNDER_LOGO = 8 * mm

    # Logo path
    logo_path = os.path.join(settings.BASE_DIR, "assets/logo1.png")
    logo_img = ImageReader(logo_path)

    x = margin_x
    y = A4_H - margin_y

    for i, q in enumerate(qs):

        # === Border ===
        c.setLineWidth(0.4)
        c.rect(x, y - STICKER_H, STICKER_W, STICKER_H)

        # === QR Code ===
        qr_img = qrcode.make(q.public_url)
        qr_buf = BytesIO()
        qr_img.save(qr_buf, format="PNG")
        qr_buf.seek(0)

        qr_x = x + QR_LEFT_PADDING
        qr_y = y - STICKER_H + (STICKER_H - QR_SIZE) / 2

        c.drawImage(ImageReader(qr_buf), qr_x, qr_y, QR_SIZE, QR_SIZE)

        # === Logo (fixed top-right) ===
        logo_x = x + STICKER_W - LOGO_SIZE - LOGO_RIGHT_PADDING
        logo_y = y - LOGO_TOP_PADDING - LOGO_SIZE

        c.drawImage(logo_img, logo_x, logo_y, LOGO_SIZE, LOGO_SIZE)

        # === Text starts UNDER the logo ===
        text_x = qr_x + QR_SIZE + TEXT_LEFT_SPACE_FROM_QR

        # Ensure text NEVER overlaps QR
        min_text_top = qr_y + QR_SIZE - 2 * mm
        logo_bottom = logo_y - TEXT_TOP_PADDING_UNDER_LOGO

        text_top = min(logo_bottom, min_text_top)

        # === Draw text ===
        c.setFont("Helvetica-Bold", 18)
        c.drawString(text_x, text_top, "MOTORIA")

        c.setFont("Helvetica", 9)
        c.drawString(text_x, text_top - 15, f"Batch: {q.batch}")
        c.drawString(text_x, text_top - 30, f"Created: {q.created_at.strftime('%Y-%m-%d')}")

        # === Move to next sticker ===
        x += STICKER_W + SPACING_X

        if (i + 1) % COLS == 0:
            x = margin_x
            y -= STICKER_H + SPACING_Y

        if y < 60 * mm:
            c.showPage()
            x = margin_x
            y = A4_H - margin_y

    c.save()
    buffer.seek(0)
    return HttpResponse(buffer, content_type='application/pdf')
