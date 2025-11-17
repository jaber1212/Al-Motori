import qrcode
from django.http import HttpResponse
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from mainapp.models import QRCode


def generate_qr_sticker_sheet(request, batch_name):
    qs = QRCode.objects.filter(batch=batch_name).order_by("code")

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    # Sticker size
    sticker_w = 60 * mm
    sticker_h = 40 * mm

    cols = 3   # 3 stickers per row
    rows = 8   # 8 rows → 24 stickers per page

    x_start = 10 * mm
    y_start = 280 * mm

    x = x_start
    y = y_start

    for index, q in enumerate(qs):
        # generate QR image
        qr_img = qrcode.make(q.public_url)
        qr_buffer = BytesIO()
        qr_img.save(qr_buffer, format="PNG")
        qr_buffer.seek(0)

        # draw box
        c.rect(x, y - sticker_h, sticker_w, sticker_h)

        # draw QR image
        c.drawImage(qr_buffer, x + 5, y - 35, 30 * mm, 30 * mm)

        # draw text
        c.setFont("Helvetica", 9)
        c.drawString(x + 40, y - 10, f"Code: {q.code}")
        c.drawString(x + 40, y - 17, f"Batch: {q.batch}")
        c.drawString(x + 40, y - 24, f"Date: {q.created_at.strftime('%Y-%m-%d')}")

        # move to next position
        x += sticker_w + 5 * mm
        if (index + 1) % cols == 0:
            x = x_start
            y -= sticker_h + 5 * mm

        # add new page if needed
        if (index + 1) % (cols * rows) == 0:
            c.showPage()
            x = x_start
            y = y_start

    c.save()
    buffer.seek(0)

    return HttpResponse(buffer, content_type='application/pdf')
