"""
report.py — PDF report generation for ACEest Fitness & Gym.

This module is intentionally decoupled from Flask and the database.
It exposes ONE public function: build_client_report(client, progress)
that returns raw PDF bytes.

Design choices:
    - Returns bytes, not a file path → container-friendly (no disk writes)
    - Subclasses FPDF to inject branded header/footer in one place
    - Uses ASCII-safe characters (Helvetica is Latin-1 only in fpdf2)
    - Handles None/empty values gracefully with a fallback dash
    - Uses new_x/new_y (not deprecated ln=True) for fpdf2 2.5.2+
    - Explicit widths everywhere so layout is deterministic across versions
"""

from datetime import datetime

from fpdf import FPDF
from fpdf.enums import XPos, YPos


# ---------------------------------------------------------------------------
# Layout constants (page is A4: 210 x 297 mm, default margins 10mm)
# ---------------------------------------------------------------------------
PAGE_W = 210
MARGIN = 15
CONTENT_W = PAGE_W - 2 * MARGIN   # 180 mm usable width

GOLD = (212, 175, 55)
DARK_GREY = (60, 60, 60)
LIGHT_GREY = (245, 245, 245)


class ClientReport(FPDF):
    """Custom PDF with a branded header and footer."""

    def header(self):
        # Gold brand bar at the very top
        self.set_fill_color(*GOLD)
        self.rect(0, 0, PAGE_W, 12, style="F")

        # Brand name — centered
        self.set_y(20)
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(0, 0, 0)
        self.cell(
            CONTENT_W, 10, "ACEest Functional Fitness",
            align="C",
            new_x=XPos.LMARGIN, new_y=YPos.NEXT,
        )

        # Subtitle — centered
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*DARK_GREY)
        self.cell(
            CONTENT_W, 6, "Client Performance Report",
            align="C",
            new_x=XPos.LMARGIN, new_y=YPos.NEXT,
        )
        self.ln(4)

        # Thin gold divider
        self.set_draw_color(*GOLD)
        self.set_line_width(0.6)
        self.line(MARGIN, self.get_y(), PAGE_W - MARGIN, self.get_y())
        self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(
            CONTENT_W, 10,
            f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  "
            f"Page {self.page_no()}",
            align="C",
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe(value, default: str = "-") -> str:
    """Convert None/empty values to a dash. Keep output ASCII-safe."""
    if value is None or value == "":
        return default
    text = str(value)
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    return text


def _write_kv_row(
    pdf: FPDF,
    label: str,
    value: str,
    label_width: float = 70,
):
    """
    Write a single label: value row on one line.

    Uses explicit widths and XPos/YPos so the cursor always advances
    to the left margin on the next line.
    """
    value_width = CONTENT_W - label_width

    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(
        label_width, 8, f"{label}:",
        border=0,
        new_x=XPos.RIGHT, new_y=YPos.TOP,
    )

    pdf.set_font("Helvetica", "", 11)
    pdf.cell(
        value_width, 8, value,
        border=0,
        new_x=XPos.LMARGIN, new_y=YPos.NEXT,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_client_report(client: dict, progress: list | None = None) -> bytes:
    """
    Build a PDF report for a single client.

    Args:
        client:   dict with keys name, age, height, weight, program,
                  calories, target_weight, target_adherence
        progress: optional list of {"week": str, "adherence": int}

    Returns:
        Raw PDF bytes ready to be streamed by Flask's send_file().
    """
    pdf = ClientReport()
    pdf.set_margins(MARGIN, MARGIN, MARGIN)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # ---- Client profile section -----------------------------------------
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(*GOLD)
    pdf.cell(
        CONTENT_W, 8, f"Client Profile: {_safe(client.get('name'))}",
        new_x=XPos.LMARGIN, new_y=YPos.NEXT,
    )
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)

    _write_kv_row(pdf, "Age", f"{_safe(client.get('age'))} years")
    _write_kv_row(pdf, "Height", f"{_safe(client.get('height'))} cm")
    _write_kv_row(pdf, "Weight", f"{_safe(client.get('weight'))} kg")
    _write_kv_row(pdf, "Program", _safe(client.get("program")))
    _write_kv_row(
        pdf, "Daily Calorie Target",
        f"{_safe(client.get('calories'))} kcal",
    )
    _write_kv_row(
        pdf, "Target Weight",
        f"{_safe(client.get('target_weight'))} kg",
    )
    _write_kv_row(
        pdf, "Target Adherence",
        f"{_safe(client.get('target_adherence'))}%",
    )

    # ---- Progress section -----------------------------------------------
    if progress:
        pdf.ln(6)
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(*GOLD)
        pdf.cell(
            CONTENT_W, 8, "Weekly Adherence History",
            new_x=XPos.LMARGIN, new_y=YPos.NEXT,
        )
        pdf.set_text_color(0, 0, 0)
        pdf.ln(2)

        # Table header
        col1_w = 90
        col2_w = 60
        pdf.set_fill_color(*GOLD)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(
            col1_w, 8, "Week",
            border=1, fill=True, align="C",
            new_x=XPos.RIGHT, new_y=YPos.TOP,
        )
        pdf.cell(
            col2_w, 8, "Adherence (%)",
            border=1, fill=True, align="C",
            new_x=XPos.LMARGIN, new_y=YPos.NEXT,
        )

        # Rows with alternating background
        pdf.set_font("Helvetica", "", 10)
        fill = False
        for entry in progress:
            pdf.set_fill_color(*LIGHT_GREY)
            pdf.cell(
                col1_w, 8, _safe(entry.get("week")),
                border=1, fill=fill,
                new_x=XPos.RIGHT, new_y=YPos.TOP,
            )
            pdf.cell(
                col2_w, 8, f"{_safe(entry.get('adherence'))}%",
                border=1, fill=fill, align="C",
                new_x=XPos.LMARGIN, new_y=YPos.NEXT,
            )
            fill = not fill

        # Summary average
        try:
            avg = (
                sum(int(e.get("adherence", 0)) for e in progress)
                / len(progress)
            )
            pdf.ln(4)
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(
                CONTENT_W, 8, f"Average Adherence: {avg:.1f}%",
                new_x=XPos.LMARGIN, new_y=YPos.NEXT,
            )
        except (TypeError, ValueError):
            pass

    # ---- Notes section --------------------------------------------------
    pdf.ln(8)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(*DARK_GREY)
    pdf.multi_cell(
        CONTENT_W, 5,
        "This report was generated automatically by the ACEest Fitness "
        "CI/CD pipeline. Data source: aceest_fitness.db (SQLite).",
    )

    return bytes(pdf.output())