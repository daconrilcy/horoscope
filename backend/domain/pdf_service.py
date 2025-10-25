"""Service de génération de PDF pour les thèmes astrologiques.

Ce module implémente la génération de PDF sommaire pour les thèmes natals avec mise en forme et
informations essentielles.
"""

from __future__ import annotations

from fpdf import FPDF


def _safe(s: str) -> str:
    return str(s).replace("\n", " ")[:200]


def render_natal_pdf(chart: dict) -> bytes:
    """Génère un PDF sommaire pour un thème natal.

    Args:
        chart: Dictionnaire contenant les données du thème natal.

    Returns:
        bytes: Contenu du PDF généré.
    """
    pdf = FPDF(unit="pt", format="A4")
    pdf.set_title("Horoscope Natal Chart")
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.text(x=50, y=80, text="Natal Chart Summary")
    pdf.set_font("Helvetica", "", 12)
    pdf.text(x=50, y=110, text=f"Owner: {_safe(chart.get('owner', '?'))}")
    pdf.text(
        x=50,
        y=130,
        text=f"Precision Score: {chart.get('chart', {}).get('precision_score', 1)}",
    )
    factors = ", ".join(
        _safe(f.get("axis", "?")) for f in chart.get("chart", {}).get("factors", [])
    )
    pdf.text(x=50, y=150, text=f"Factors: {factors}")
    # Return PDF bytes (dest parameter deprecated; output returns bytes)
    out = pdf.output()
    return out if isinstance(out, bytes | bytearray) else bytes(out)
