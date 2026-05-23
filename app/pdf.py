import html
import os
import re
from datetime import datetime
from typing import Any, Dict, List

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.graphics.shapes import Circle, Drawing, Line, Rect, String
from reportlab.platypus import HRFlowable, Image, Paragraph, PageBreak, SimpleDocTemplate, Spacer, Table, TableStyle


FONT_REGULAR = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
BRAND_BLUE = "#0A4C86"
BRAND_DARK = "#263645"
BRAND_MUTED = "#53616F"
BRAND_LINE = "#D7DEE8"
BRAND_SOFT_BLUE = "#EAF2F8"
BRAND_GREEN = "#2E7D32"
BRAND_AMBER = "#F9A825"
BRAND_RED = "#C62828"
BOX_PALETTE = [
    ("#EAF2F8", "#0A4C86"),
    ("#F0F7F1", "#2E7D32"),
    ("#FFF7E0", "#B7791F"),
    ("#FDECEC", "#C62828"),
    ("#F2EFFB", "#5B4B9A"),
]


def _header_footer(canvas_obj, doc):
    canvas_obj.saveState()
    width, height = letter
    canvas_obj.setStrokeColor(colors.HexColor(BRAND_BLUE))
    canvas_obj.setLineWidth(0.5)
    canvas_obj.line(inch, height - 0.82 * inch, width - inch, height - 0.82 * inch)
    canvas_obj.setFont(FONT_REGULAR, 9.5)
    canvas_obj.drawString(inch, height - 0.65 * inch, getattr(doc, "project_name", "M&E Intelligence Report"))
    canvas_obj.drawRightString(width - inch, 0.65 * inch, f"Page {canvas_obj.getPageNumber()}")
    canvas_obj.setFont(FONT_REGULAR, 8.5)
    canvas_obj.drawCentredString(width / 2, 0.65 * inch, f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    canvas_obj.restoreState()


def _inline_markup(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    escaped = html.escape(text, quote=False)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"__([^_]+)__", r"<b>\1</b>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<i>\1</i>", escaped)
    escaped = re.sub(r"`([^`]+)`", r"<i>\1</i>", escaped)
    return escaped.replace("\\n", "<br/>")


def _clean_block_text(text: str) -> str:
    text = re.sub(r"^\s*>+\s?", "", text.strip())
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text)
    return text.strip()


def _emphasize_lead_in(text: str) -> str:
    match = re.match(r"^([A-Za-z][A-Za-z0-9 /&%()'-]{2,60}):\s+(.+)$", text)
    if not match:
        return text
    return f"**{match.group(1)}:** {match.group(2)}"


def _is_table_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2


def _is_table_separator(line: str) -> bool:
    return bool(re.match(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$", line))


def _table_cells(line: str) -> List[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _performance_color(value: float) -> colors.Color:
    if value >= 100.0:
        return colors.HexColor(BRAND_GREEN)
    if value >= 80.0:
        return colors.HexColor(BRAND_AMBER)
    return colors.HexColor(BRAND_RED)


def _build_table(lines: List[str], styles: Dict[str, ParagraphStyle]) -> Table:
    source_rows = []
    rows = []
    for line in lines:
        if _is_table_separator(line):
            continue
        cells = _table_cells(line)
        source_rows.append(cells)
        rows.append([Paragraph(_inline_markup(cell), styles["table_cell"]) for cell in cells])
    table = Table(rows, hAlign="LEFT", repeatRows=1)
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(BRAND_SOFT_BLUE)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor(BRAND_BLUE)),
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor(BRAND_LINE)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for row_index, cells in enumerate(source_rows[1:], start=1):
        for col_index, cell in enumerate(cells):
            lowered = cell.lower()
            if "green" in lowered or "on track" in lowered:
                commands.append(("TEXTCOLOR", (col_index, row_index), (col_index, row_index), colors.HexColor(BRAND_GREEN)))
                commands.append(("FONTNAME", (col_index, row_index), (col_index, row_index), FONT_BOLD))
            elif "amber" in lowered or "at risk" in lowered:
                commands.append(("TEXTCOLOR", (col_index, row_index), (col_index, row_index), colors.HexColor("#B7791F")))
                commands.append(("FONTNAME", (col_index, row_index), (col_index, row_index), FONT_BOLD))
            elif "red" in lowered or "off track" in lowered:
                commands.append(("TEXTCOLOR", (col_index, row_index), (col_index, row_index), colors.HexColor(BRAND_RED)))
                commands.append(("FONTNAME", (col_index, row_index), (col_index, row_index), FONT_BOLD))
    table.setStyle(TableStyle(commands))
    return table


def _build_callout(lines: List[str], styles: Dict[str, ParagraphStyle]) -> Table:
    cleaned_lines = [_clean_block_text(line) for line in lines if _clean_block_text(line)]
    text = "<br/>".join(_inline_markup(_emphasize_lead_in(line)) for line in cleaned_lines)
    table = Table([[Paragraph(text, styles["table_cell"])]], colWidths=[6.7 * inch], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF7ED")),
        ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor(BRAND_RED)),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return table


def _content_box(text: str, styles: Dict[str, ParagraphStyle], box_index: int = 0) -> Table:
    background, accent = BOX_PALETTE[box_index % len(BOX_PALETTE)]
    cleaned = _emphasize_lead_in(_clean_block_text(text))
    table = Table(
        [[Paragraph(_inline_markup(cleaned), styles["box_body"])]],
        colWidths=[6.7 * inch],
        hAlign="LEFT",
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(background)),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor(accent)),
        ("LINEBEFORE", (0, 0), (0, -1), 4, colors.HexColor(accent)),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return table


def _markdown_to_flowables(text: str, styles: Dict[str, ParagraphStyle]) -> List[Any]:
    flowables: List[Any] = []
    paragraph_lines: List[str] = []
    table_lines: List[str] = []
    callout_lines: List[str] = []
    box_index = 0

    def flush_paragraph() -> None:
        nonlocal box_index
        if not paragraph_lines:
            return
        cleaned = " ".join(_clean_block_text(line) for line in paragraph_lines).strip()
        paragraph_lines.clear()
        if cleaned:
            flowables.append(_content_box(cleaned, styles, box_index))
            box_index += 1
            flowables.append(Spacer(1, 8))

    def flush_table() -> None:
        if not table_lines:
            return
        flowables.append(_build_table(table_lines, styles))
        flowables.append(Spacer(1, 10))
        table_lines.clear()

    def flush_callout() -> None:
        nonlocal box_index
        if not callout_lines:
            return
        flowables.append(_build_callout(callout_lines, styles))
        box_index += 1
        flowables.append(Spacer(1, 10))
        callout_lines.clear()

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()

        if not stripped:
            flush_paragraph()
            flush_table()
            flush_callout()
            continue
        if stripped in {"---", "***", "___"}:
            flush_paragraph()
            flush_table()
            flush_callout()
            flowables.append(HRFlowable(width="100%", color=colors.HexColor("#D7DEE8"), thickness=0.5))
            flowables.append(Spacer(1, 8))
            continue
        if stripped.startswith(">"):
            flush_paragraph()
            flush_table()
            callout_lines.append(stripped)
            continue
        if _is_table_line(stripped):
            flush_paragraph()
            flush_callout()
            table_lines.append(stripped)
            continue

        flush_table()
        flush_callout()

        heading = re.match(r"^\s{0,3}#{2,6}\s+(.+)$", line)
        bold_heading = re.match(r"^\s*\*\*(.+?)\*\*:?\s*$", line)
        bare_heading = re.match(r"^\s*([A-Z][A-Za-z0-9 /&%()'-]{3,64}):?\s*$", line)
        if heading or bold_heading or (bare_heading and "." not in stripped):
            flush_paragraph()
            heading_text = (heading or bold_heading or bare_heading).group(1)
            flowables.append(Paragraph(_inline_markup(_clean_block_text(heading_text)), styles["subheading"]))
            flowables.append(Spacer(1, 6))
            continue

        bullet = re.match(r"^\s*(?:[-*+\u2022\u2013\u2014]\s+|\d+[\.)]\s+)(.+)$", line)
        if bullet:
            flush_paragraph()
            item_text = _emphasize_lead_in(_clean_block_text(bullet.group(1)))
            flowables.append(_content_box(item_text, styles, box_index))
            box_index += 1
            flowables.append(Spacer(1, 8))
            continue

        paragraph_lines.append(line)

    flush_paragraph()
    flush_table()
    flush_callout()

    if not flowables:
        flowables.append(Paragraph("No narrative content was generated for this section.", styles["body"]))
    return flowables


def _summary_table(report: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> Table:
    summary = report.get("summary", {})
    counts = summary.get("project", {})
    analytics = summary.get("analytics", {})
    completion = analytics.get("completion", {})
    risk = analytics.get("risk", {})
    budget = analytics.get("budget", {})
    kpi = analytics.get("kpi", {})
    workplan = analytics.get("workplan", {})
    issues = analytics.get("issues", {})

    cards = [
        ("Activity Completion", f"{completion.get('percent_complete', 0)}%", f"{completion.get('completed_activities', 0)} of {completion.get('total_activities', counts.get('activities', 0))} complete", BRAND_BLUE),
        ("KPI Health", f"{kpi.get('on_track_count', 0)} / {kpi.get('indicator_count', counts.get('indicators', 0))}", "indicators on track", BRAND_GREEN),
        ("Risk Exposure", str(risk.get("high_risk_count", 0)), "high-severity risks", BRAND_RED),
        ("Open Issues", str(issues.get("open_issue_count", 0)), "requiring follow-up", "#7B3F00"),
        ("Budget Utilization", f"{budget.get('utilization_percent', 0)}%", f"{budget.get('total_expenditure', 0):,.0f} spent", BRAND_AMBER),
        ("Workplan Coverage", str(workplan.get("workplan_item_count", counts.get("workplan_items", 0))), "planned workplan items", "#5B4B9A"),
    ]

    rows = []
    for index in range(0, len(cards), 3):
        row = []
        for label, value, subtitle, accent in cards[index:index + 3]:
            cell = (
                f'<font color="{accent}"><b>{html.escape(value)}</b></font><br/>'
                f'<font color="{BRAND_DARK}"><b>{html.escape(label)}</b></font><br/>'
                f'<font color="{BRAND_MUTED}">{html.escape(subtitle)}</font>'
            )
            row.append(Paragraph(cell, styles["summary_card"]))
        rows.append(row)

    table = Table(rows, colWidths=[2.18 * inch, 2.18 * inch, 2.18 * inch], hAlign="CENTER")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor(BRAND_LINE)),
        ("INNERGRID", (0, 0), (-1, -1), 0.45, colors.HexColor(BRAND_LINE)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
    ]))
    return table


def _logo_flowable(brand_logo_path: str) -> Image:
    logo = Image(brand_logo_path)
    logo._restrictSize(1.05 * inch, 1.05 * inch)
    logo.hAlign = "CENTER"
    return logo


def _short_label(value: Any, limit: int = 34) -> str:
    text = str(value or "").replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[: max(limit - 3, 0)].rstrip() + "..."


CHART_WIDTH = 500


def _panel_base(title: str, width: int, height: int) -> Drawing:
    d = Drawing(width, height)
    d.add(Rect(0, 0, width, height, strokeColor=colors.HexColor(BRAND_LINE), fillColor=colors.white, rx=5, ry=5))
    d.add(String(16, height - 23, title, fontName=FONT_BOLD, fontSize=12, fillColor=colors.HexColor(BRAND_DARK)))
    d.add(Line(16, height - 32, width - 16, height - 32, strokeColor=colors.HexColor("#E6EBF1"), strokeWidth=0.7))
    return d


def _progress_panel(title: str, value: float, subtitle: str, accent: colors.Color, width: int = CHART_WIDTH) -> Drawing:
    height = 92
    value = max(0.0, min(float(value or 0), 100.0))
    d = _panel_base(title, width, height)
    bar_x = 16
    bar_y = 22
    bar_width = width - 32
    d.add(String(16, 48, f"{value:.1f}%", fontName=FONT_BOLD, fontSize=22, fillColor=accent))
    d.add(String(112, 53, _short_label(subtitle, 80), fontName=FONT_REGULAR, fontSize=9.5, fillColor=colors.HexColor(BRAND_MUTED)))
    d.add(Rect(bar_x, bar_y, bar_width, 10, strokeColor=colors.HexColor(BRAND_LINE), fillColor=colors.HexColor("#EFF3F7")))
    d.add(Rect(bar_x, bar_y, bar_width * (value / 100.0), 10, strokeColor=accent, fillColor=accent))
    return d


def _horizontal_bar_chart(title: str, values: Dict[str, Any], accent: colors.Color, limit: int = 8, suffix: str = "", sort: bool = True) -> Drawing:
    entries = [(str(key), float(value or 0)) for key, value in values.items()]
    entries = [entry for entry in entries if entry[1] > 0]
    if sort:
        entries = sorted(entries, key=lambda item: item[1], reverse=True)
    entries = entries[:limit]
    width = CHART_WIDTH
    row_height = 22
    height = max(96, 44 + row_height * max(len(entries), 1))
    max_value = max([value for _, value in entries] + [1])
    d = _panel_base(title, width, height)

    if not entries:
        d.add(String(16, height - 58, "No values available", fontName=FONT_REGULAR, fontSize=9.5, fillColor=colors.HexColor(BRAND_MUTED)))
        return d

    label_x = 16
    bar_x = 205
    bar_width = 220
    value_x = 438
    for index, (label, value) in enumerate(entries):
        y = height - 56 - index * row_height
        d.add(String(label_x, y + 2, _short_label(label, 39), fontName=FONT_REGULAR, fontSize=8.6, fillColor=colors.HexColor(BRAND_MUTED)))
        d.add(Rect(bar_x, y, bar_width, 9, strokeColor=colors.HexColor(BRAND_LINE), fillColor=colors.HexColor("#EFF3F7")))
        d.add(Rect(bar_x, y, bar_width * (value / max_value), 9, strokeColor=accent, fillColor=accent))
        d.add(String(value_x, y, f"{value:g}{suffix}", fontName=FONT_BOLD, fontSize=8.6, fillColor=colors.HexColor(BRAND_DARK)))
    return d


def _stacked_bar_chart(title: str, values: Dict[str, Any], palette: Dict[str, colors.Color]) -> Drawing:
    entries = [(str(key), float(value or 0)) for key, value in values.items() if float(value or 0) > 0]
    total = sum(value for _, value in entries)
    width = CHART_WIDTH
    height = 108
    d = _panel_base(title, width, height)
    if not entries or not total:
        d.add(String(16, 51, "No values available", fontName=FONT_REGULAR, fontSize=9.5, fillColor=colors.HexColor(BRAND_MUTED)))
        return d

    x = 16
    y = 48
    bar_width = width - 32
    cursor = x
    for label, value in entries:
        segment_width = bar_width * (value / total)
        color = palette.get(label, colors.HexColor("#0A4C86"))
        d.add(Rect(cursor, y, segment_width, 14, strokeColor=color, fillColor=color))
        cursor += segment_width

    legend_x = 16
    legend_y = 24
    for label, value in entries:
        color = palette.get(label, colors.HexColor("#0A4C86"))
        d.add(Rect(legend_x, legend_y, 8, 8, strokeColor=color, fillColor=color))
        d.add(String(legend_x + 12, legend_y - 1, f"{_short_label(label, 18)}: {value:g}", fontName=FONT_REGULAR, fontSize=8.2, fillColor=colors.HexColor(BRAND_MUTED)))
        legend_x += 116
        if legend_x > width - 95:
            legend_x = 16
            legend_y -= 15
    return d


def _kpi_lollipop_chart(performance: List[Dict[str, Any]]) -> Drawing:
    entries = [
        (str(item.get("indicator", f"KPI {index + 1}")), float(item.get("performance_percent", 0) or 0))
        for index, item in enumerate(performance[:8])
    ]
    width = CHART_WIDTH
    row_height = 24
    height = max(110, 48 + row_height * max(len(entries), 1))
    d = _panel_base("KPI Performance Against Target", width, height)
    if not entries:
        d.add(String(16, height - 58, "No KPI values available", fontName=FONT_REGULAR, fontSize=9.5, fillColor=colors.HexColor(BRAND_MUTED)))
        return d

    axis_x = 230
    axis_width = 200
    for index, (label, value) in enumerate(entries):
        y = height - 57 - index * row_height
        clipped = max(0.0, min(value, 100.0))
        dot_x = axis_x + axis_width * (clipped / 100.0)
        accent = _performance_color(value)
        d.add(String(16, y - 2, _short_label(label, 43), fontName=FONT_REGULAR, fontSize=8.4, fillColor=colors.HexColor(BRAND_MUTED)))
        d.add(Line(axis_x, y, axis_x + axis_width, y, strokeColor=colors.HexColor(BRAND_LINE), strokeWidth=2))
        d.add(Line(axis_x, y, dot_x, y, strokeColor=accent, strokeWidth=2.5))
        d.add(Circle(dot_x, y, 4, strokeColor=accent, fillColor=accent))
        d.add(String(444, y - 3, f"{value:.0f}%", fontName=FONT_BOLD, fontSize=8.8, fillColor=accent))
    return d


def _indicator_performance_table(performance: List[Dict[str, Any]], styles: Dict[str, ParagraphStyle]) -> Table:
    rows = [["Indicator", "Actual Value", "Performance vs Target", "Status"]]
    source_statuses = []
    for item in performance[:8]:
        value = float(item.get("performance_percent", 0) or 0)
        target = float(item.get("target", 0) or 0)
        actual = float(item.get("actual", 0) or 0)
        if value >= 100.0:
            status = "Green / On track"
        elif value >= 80.0:
            status = "Amber / At risk"
        else:
            status = "Red / Off track"
        source_statuses.append(status)
        rows.append([
            _short_label(item.get("indicator", ""), 60),
            f"{actual:,.2f}",
            f"{value:.1f}% achievement against {target:,.2f} target",
            status,
        ])
    if len(rows) == 1:
        rows.append(["No indicator values available", "", "", ""])
        source_statuses.append("")
    formatted = []
    for row_index, row in enumerate(rows):
        formatted_row = []
        for cell in row:
            text = _inline_markup(str(cell))
            if row_index == 0:
                text = f'<font color="#FFFFFF"><b>{text}</b></font>'
            formatted_row.append(Paragraph(text, styles["table_cell"]))
        formatted.append(formatted_row)
    table = Table(formatted, colWidths=[2.5 * inch, 1.0 * inch, 2.0 * inch, 1.2 * inch], hAlign="LEFT", repeatRows=1)
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(BRAND_BLUE)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
        ("FONTNAME", (0, 1), (-1, -1), FONT_REGULAR),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor(BRAND_LINE)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for index, status in enumerate(source_statuses, start=1):
        if status.startswith("Green"):
            commands.append(("TEXTCOLOR", (3, index), (3, index), colors.HexColor(BRAND_GREEN)))
        elif status.startswith("Amber"):
            commands.append(("TEXTCOLOR", (3, index), (3, index), colors.HexColor("#B7791F")))
        elif status.startswith("Red"):
            commands.append(("TEXTCOLOR", (3, index), (3, index), colors.HexColor(BRAND_RED)))
        commands.append(("FONTNAME", (3, index), (3, index), FONT_BOLD))
    table.setStyle(TableStyle(commands))
    return table


def _quarter_timeline_chart(values: Dict[str, Any]) -> Drawing:
    entries = [(str(key).upper().replace("_", " "), float(value or 0)) for key, value in values.items()]
    entries = sorted(entries, key=lambda item: item[0])
    width = CHART_WIDTH
    height = 145
    d = _panel_base("Workplan Distribution by Quarter", width, height)
    if not entries:
        d.add(String(16, 68, "No quarter markers available", fontName=FONT_REGULAR, fontSize=9.5, fillColor=colors.HexColor(BRAND_MUTED)))
        return d

    max_value = max(value for _, value in entries) or 1
    bar_area_x = 24
    bar_area_y = 36
    bar_area_width = width - 48
    bar_area_height = 66
    gap = 8
    bar_width = max(16, (bar_area_width - gap * (len(entries) - 1)) / len(entries))
    d.add(Line(bar_area_x, bar_area_y, bar_area_x + bar_area_width, bar_area_y, strokeColor=colors.HexColor(BRAND_LINE), strokeWidth=0.8))
    for index, (label, value) in enumerate(entries):
        x = bar_area_x + index * (bar_width + gap)
        bar_height = bar_area_height * (value / max_value)
        d.add(Rect(x, bar_area_y, bar_width, bar_height, strokeColor=colors.HexColor("#6A5ACD"), fillColor=colors.HexColor("#6A5ACD")))
        d.add(String(x + 2, bar_area_y + bar_height + 4, f"{value:g}", fontName=FONT_BOLD, fontSize=8.2, fillColor=colors.HexColor(BRAND_DARK)))
        d.add(String(x - 1, 18, _short_label(label, 8), fontName=FONT_REGULAR, fontSize=7.2, fillColor=colors.HexColor(BRAND_MUTED)))
    return d


def _metadata_table(report: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> Table:
    metadata = report.get("summary", {}).get("analytics", {}).get("metadata", {})
    rows = [
        ["Project", metadata.get("project_name", "")],
        ["Code", metadata.get("project_code", "")],
        ["Implementing Partner", metadata.get("implementing_partner", "")],
        ["Donor", metadata.get("donor", "")],
        ["Reporting Period", metadata.get("reporting_period", "")],
        ["Geography", metadata.get("country", "")],
    ]
    formatted = [[Paragraph(_inline_markup(str(cell)), styles["table_cell"]) for cell in row] for row in rows if row[1]]
    table = Table(formatted, colWidths=[1.8 * inch, 4.9 * inch], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor(BRAND_SOFT_BLUE)),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor(BRAND_BLUE)),
        ("FONTNAME", (0, 0), (0, -1), FONT_BOLD),
        ("FONTNAME", (1, 0), (1, -1), FONT_REGULAR),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor(BRAND_LINE)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


def _open_issues_table(report: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> Table:
    issues = report.get("summary", {}).get("analytics", {}).get("issues", {}).get("open_issues", [])
    rows = [["Issue", "Severity", "Status", "Target Date"]]
    for item in issues[:6]:
        rows.append([
            item.get("issue", ""),
            item.get("severity", ""),
            item.get("status", ""),
            item.get("target_date", ""),
        ])
    formatted = []
    for row_index, row in enumerate(rows):
        formatted_row = []
        for cell in row:
            text = _inline_markup(_short_label(str(cell), 72))
            if row_index == 0:
                text = f'<font color="#FFFFFF"><b>{text}</b></font>'
            formatted_row.append(Paragraph(text, styles["table_cell"]))
        formatted.append(formatted_row)
    table = Table(formatted, colWidths=[3.4 * inch, 0.9 * inch, 1.05 * inch, 1.05 * inch], hAlign="LEFT", repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7B3F00")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
        ("FONTNAME", (0, 1), (-1, -1), FONT_REGULAR),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor(BRAND_LINE)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def _dashboard_flowables(report: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> List[Any]:
    summary = report.get("summary", {})
    analytics = summary.get("analytics", {})
    completion = analytics.get("completion", {})
    budget = analytics.get("budget", {})
    workplan = analytics.get("workplan", {})
    kpi = analytics.get("kpi", {})
    risk = analytics.get("risk", {})
    schedule = analytics.get("schedule", {})
    issues = analytics.get("issues", {})

    visuals = [
        _progress_panel(
            "Activity Completion",
            completion.get("percent_complete", 0),
            f"{completion.get('completed_activities', 0)} of {completion.get('total_activities', 0)} activities complete",
            colors.HexColor("#0A4C86"),
        ),
        _progress_panel(
            "Budget Utilization",
            budget.get("utilization_percent", 0),
            f"{budget.get('total_expenditure', 0):,.0f} spent of {budget.get('total_budget', 0):,.0f}",
            colors.HexColor("#C62828"),
        ),
        _progress_panel(
            "Workplan Marker Completion",
            workplan.get("quarter_completion_percent", 0),
            f"{workplan.get('completed_quarter_markers', 0)} of {workplan.get('planned_quarter_markers', 0)} quarter markers complete",
            colors.HexColor("#6A5ACD"),
        ),
        _horizontal_bar_chart("Activity Status Distribution", schedule.get("status_counts", {}), colors.HexColor("#0A4C86")),
        _stacked_bar_chart(
            "Risk Severity Composition",
            risk.get("severity_counts", {}),
            {"High": colors.HexColor("#C62828"), "Medium": colors.HexColor("#F9A825"), "Low": colors.HexColor("#2E7D32")},
        ),
        _stacked_bar_chart(
            "Issues by Resolution Status",
            issues.get("status_counts", {}),
            {
                "Resolved": colors.HexColor("#2E7D32"),
                "In Progress": colors.HexColor("#0A4C86"),
                "Open": colors.HexColor("#C62828"),
                "Under Investigation": colors.HexColor("#7B3F00"),
            },
        ),
        _quarter_timeline_chart(workplan.get("quarter_counts", {})),
    ]

    flowables: List[Any] = [
        Paragraph("Visual Performance Dashboard", styles["section"]),
        HRFlowable(width="100%", color=colors.HexColor("#D7DEE8"), thickness=0.4),
        Spacer(1, 8),
    ]
    for visual in visuals:
        flowables.append(visual)
        flowables.append(Spacer(1, 12))
    flowables.append(PageBreak())
    return flowables


def _front_kpi_flowables(report: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> List[Any]:
    performance = report.get("summary", {}).get("analytics", {}).get("kpi", {}).get("performance", [])
    return [
        Spacer(1, 14),
        _kpi_lollipop_chart(performance),
        Spacer(1, 12),
        _indicator_performance_table(performance, styles),
        PageBreak(),
    ]


def _section_header(title: str, styles: Dict[str, ParagraphStyle], index: int) -> Table:
    _, accent = BOX_PALETTE[index % len(BOX_PALETTE)]
    table = Table(
        [[Paragraph(_inline_markup(title), styles["section_header"])]],
        colWidths=[6.7 * inch],
        hAlign="LEFT",
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(accent)),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 11),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 11),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return table


def _section_visual_flowables(section_title: str, report: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> List[Any]:
    analytics = report.get("summary", {}).get("analytics", {})
    completion = analytics.get("completion", {})
    budget = analytics.get("budget", {})
    workplan = analytics.get("workplan", {})
    kpi = analytics.get("kpi", {})
    risk = analytics.get("risk", {})
    schedule = analytics.get("schedule", {})
    issues = analytics.get("issues", {})
    dependency = analytics.get("dependency", {})
    quality = analytics.get("data_quality", [])

    visuals: List[Any] = []
    if section_title == "Project Metadata & Governance Context":
        visuals.append(_metadata_table(report, styles))
    elif section_title == "Activity Implementation Analysis":
        visuals.extend([
            _progress_panel(
                "Section Visual: Activity Completion",
                completion.get("percent_complete", 0),
                f"{completion.get('completed_activities', 0)} complete; {completion.get('remaining_activities', 0)} remaining",
                colors.HexColor("#0A4C86"),
            ),
            _horizontal_bar_chart("Section Visual: Activity Status", schedule.get("status_counts", {}), colors.HexColor("#0A4C86")),
        ])
    elif section_title == "Workplan Analysis":
        visuals.extend([
            _quarter_timeline_chart(workplan.get("quarter_counts", {})),
            _horizontal_bar_chart("Section Visual: Responsible Teams", workplan.get("responsible_counts", {}), colors.HexColor("#6A5ACD")),
        ])
    elif section_title == "Indicator Performance Analysis":
        visuals.extend([
            _indicator_performance_table(kpi.get("performance", []), styles),
            _kpi_lollipop_chart(kpi.get("performance", [])),
        ])
    elif section_title == "Risk & Bottleneck Analysis":
        visuals.extend([
            _stacked_bar_chart(
                "Section Visual: Risk Severity",
                risk.get("severity_counts", {}),
                {"High": colors.HexColor("#C62828"), "Medium": colors.HexColor("#F9A825"), "Low": colors.HexColor("#2E7D32")},
            ),
            _horizontal_bar_chart("Section Visual: Dependency Bottlenecks", {item.get("dependency"): item.get("count") for item in dependency.get("bottlenecks", [])}, colors.HexColor("#C62828")),
        ])
    elif section_title == "Issues Log Analysis":
        visuals.extend([
            _stacked_bar_chart(
                "Section Visual: Issue Resolution Status",
                issues.get("status_counts", {}),
                {
                    "Resolved": colors.HexColor("#2E7D32"),
                    "In Progress": colors.HexColor("#0A4C86"),
                    "Open": colors.HexColor("#C62828"),
                    "Under Investigation": colors.HexColor("#7B3F00"),
                },
            ),
            _open_issues_table(report, styles),
        ])
    elif section_title == "Budget & Resource Utilization":
        visuals.append(
            _progress_panel(
                "Section Visual: Budget Utilization",
                budget.get("utilization_percent", 0),
                f"{budget.get('total_expenditure', 0):,.0f} spent; {budget.get('remaining_budget', 0):,.0f} remaining",
                colors.HexColor("#C62828"),
            )
        )
    elif section_title == "Data Quality Assessment":
        visuals.append(
            _progress_panel(
                "Section Visual: Workbook Module Coverage",
                100.0 if not quality else 65.0,
                "All expected workbook modules detected" if not quality else f"{len(quality)} quality issues require review",
                colors.HexColor("#2E7D32") if not quality else colors.HexColor("#F9A825"),
            )
        )
    elif section_title == "Dependency & Impact Analysis":
        visuals.append(
            _horizontal_bar_chart("Section Visual: Dependency Bottlenecks", {item.get("dependency"): item.get("count") for item in dependency.get("bottlenecks", [])}, colors.HexColor("#0A4C86"))
        )

    if not visuals:
        return []

    flowables: List[Any] = []
    for visual in visuals:
        flowables.append(visual)
        flowables.append(Spacer(1, 10))
    return flowables


def build_pdf_report(report: Dict[str, Any], output_path: str, brand_logo_path: str, project_name: str) -> str:
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        title=project_name,
        leftMargin=0.78 * inch,
        rightMargin=0.78 * inch,
        topMargin=1.02 * inch,
        bottomMargin=0.9 * inch,
    )
    doc.project_name = project_name
    base_styles = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle(
            "ReportTitle",
            parent=base_styles["Title"],
            alignment=TA_CENTER,
            textColor=colors.HexColor(BRAND_BLUE),
            fontName=FONT_BOLD,
            fontSize=23,
            leading=28,
            spaceAfter=8,
        ),
        "subtitle": ParagraphStyle(
            "ReportSubtitle",
            parent=base_styles["BodyText"],
            alignment=TA_CENTER,
            textColor=colors.HexColor(BRAND_MUTED),
            fontName=FONT_REGULAR,
            fontSize=12,
            leading=15,
            spaceAfter=16,
        ),
        "section": ParagraphStyle(
            "SectionHeading",
            parent=base_styles["Heading2"],
            alignment=TA_LEFT,
            textColor=colors.HexColor(BRAND_BLUE),
            fontName=FONT_BOLD,
            fontSize=16,
            leading=20,
            spaceBefore=14,
            spaceAfter=7,
        ),
        "section_header": ParagraphStyle(
            "SectionHeaderBand",
            parent=base_styles["Heading2"],
            alignment=TA_LEFT,
            textColor=colors.white,
            fontName=FONT_BOLD,
            fontSize=17,
            leading=21,
        ),
        "subheading": ParagraphStyle(
            "Subheading",
            parent=base_styles["Heading3"],
            alignment=TA_LEFT,
            textColor=colors.HexColor(BRAND_DARK),
            fontName=FONT_BOLD,
            fontSize=12.5,
            leading=16,
            spaceBefore=8,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "JustifiedBody",
            parent=base_styles["BodyText"],
            alignment=TA_JUSTIFY,
            fontName=FONT_REGULAR,
            fontSize=11,
            leading=15.5,
            firstLineIndent=0,
            spaceAfter=8,
            splitLongWords=0,
            wordWrap="LTR",
        ),
        "box_body": ParagraphStyle(
            "BoxBody",
            parent=base_styles["BodyText"],
            alignment=TA_LEFT,
            fontName=FONT_REGULAR,
            fontSize=11,
            leading=15.6,
            firstLineIndent=0,
            spaceAfter=0,
            splitLongWords=0,
            wordWrap="LTR",
        ),
        "bullet": ParagraphStyle(
            "JustifiedBullet",
            parent=base_styles["BodyText"],
            alignment=TA_JUSTIFY,
            fontName=FONT_REGULAR,
            fontSize=11,
            leading=15.5,
            leftIndent=22,
            firstLineIndent=0,
            bulletIndent=8,
            spaceAfter=4,
            splitLongWords=0,
            wordWrap="LTR",
        ),
        "table_cell": ParagraphStyle(
            "TableCell",
            parent=base_styles["BodyText"],
            alignment=TA_LEFT,
            fontName=FONT_REGULAR,
            fontSize=10,
            leading=13,
        ),
        "summary_card": ParagraphStyle(
            "SummaryCard",
            parent=base_styles["BodyText"],
            alignment=TA_LEFT,
            fontName=FONT_REGULAR,
            fontSize=10.5,
            leading=14,
        ),
    }

    story = []
    if os.path.exists(brand_logo_path):
        story.append(_logo_flowable(brand_logo_path))
        story.append(Spacer(1, 16))
    story.append(Paragraph(_inline_markup(project_name), styles["title"]))
    story.append(Paragraph("Monitoring & Evaluation Intelligence Report", styles["subtitle"]))
    story.append(_summary_table(report, styles))
    story.extend(_front_kpi_flowables(report, styles))
    story.extend(_dashboard_flowables(report, styles))

    for index, section in enumerate(report.get("sections", [])):
        if index > 0:
            story.append(PageBreak())
        story.append(_section_header(section["title"], styles, index))
        story.append(Spacer(1, 12))
        story.extend(_section_visual_flowables(section.get("title", ""), report, styles))
        story.extend(_markdown_to_flowables(section.get("body", ""), styles))

    if not story:
        story.append(Paragraph("No report content available.", styles["body"]))

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return output_path
