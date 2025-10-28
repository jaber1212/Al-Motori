# admin_utils.py
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

def export_qr_excel_response(qs, filename_prefix="qr-codes"):
    wb = Workbook()
    ws = wb.active
    ws.title = "QR Codes"

    ws.append([
        "Code",
        "Public Path",
        "Public URL",
        "Batch",
        "Assigned?",
        "Activated?",
        "Scans",
        "First Scan At",
        "Last Scan At",
        "Ad Code",
        "Created At",
    ])

    for q in qs:
        ws.append([
            q.code,
            getattr(q, "public_path", f"/qr/{q.code}"),
            getattr(q, "public_url", f"/qr/{q.code}"),
            q.batch or "",
            "Yes" if q.is_assigned else "No",
            "Yes" if q.is_activated else "No",
            q.scans_count,
            q.first_scan_at.isoformat() if q.first_scan_at else "",
            q.last_scan_at.isoformat() if q.last_scan_at else "",
            getattr(getattr(q, "ad", None), "code", "") or "",
            q.created_at.isoformat() if q.created_at else "",
        ])

    autosize(ws)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"{filename_prefix}-{ts}.xlsx"
    resp = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    wb.save(resp)
    return resp
