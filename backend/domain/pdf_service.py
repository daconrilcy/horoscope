import io
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.lib.pagesizes import A4


def _safe(s: str) -> str:
    return str(s).replace("\n", " ")[:200]


def render_natal_pdf(chart: dict) -> bytes:
    buf = io.BytesIO()
    c = pdfcanvas.Canvas(buf, pagesize=A4)
    w, h = A4
    c.setTitle("Horoscope Natal Chart")
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, h - 80, "Natal Chart Summary")
    c.setFont("Helvetica", 12)
    c.drawString(50, h - 110, f"Owner: {_safe(chart.get('owner','?'))}")
    c.drawString(50, h - 130, f"Precision Score: {chart.get('chart',{}).get('precision_score', 1)}")
    factors = ", ".join(_safe(f.get('axis', '?')) for f in chart.get('chart', {}).get('factors', []))
    c.drawString(50, h - 150, f"Factors: {factors}")
    c.showPage()
    c.save()
    return buf.getvalue()

