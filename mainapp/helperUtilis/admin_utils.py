from datetime import datetime
from django.http import HttpResponse
from openpyxl import Workbook

def autosize(ws):
    for col in ws.columns:
        max_len = 0
        col_letter = col[0].column_letter
        for cell in col:
            try:
                max_len = max(max_len, len(str(cell.value)))
            except Exception:
                pass
        ws.column_dimensions[col_letter].width = min(max_len + 2, 60)


def export_qr_excel_response(qs, filename_prefix="qr"):
    wb = Workbook()
    ws = wb.active
    ws.title = "QR Codes"

    # ONLY the 4 fields you want
    ws.append([
        "Code",
        "Public URL",
        "Batch",
        "Created At",
    ])

    for q in qs:
        ws.append([
            q.code,
            getattr(q, "public_url", f"/qr/{q.code}"),
            q.batch or "",
            q.created_at.strftime("%Y-%m-%d %H:%M") if q.created_at else "",
        ])

    autosize(ws)

    # File name as: day-month-year-batch.xlsx
    today = datetime.now().strftime("%d-%m-%Y")
    filename = f"{today}-batch.xlsx"

    resp = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    wb.save(resp)
    return resp
