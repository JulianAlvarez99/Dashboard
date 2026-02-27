"""
Export — DataFrame serialization to CSV and Excel.

Single Responsibility: convert enriched DataFrames to downloadable
byte formats.  No business logic, no DB access.
"""

from __future__ import annotations

import io

import pandas as pd


def to_csv(df: pd.DataFrame) -> str:
    """Export a DataFrame to a CSV string."""
    if df.empty:
        return ""
    return df.to_csv(index=False)


def to_excel_bytes(df: pd.DataFrame, sheet_name: str = "Detecciones") -> bytes:
    """Export a DataFrame to Excel bytes (xlsx)."""
    if df.empty:
        return b""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return buffer.getvalue()


def format_datetime_columns(df: pd.DataFrame, fmt: str = "%Y-%m-%dT%H:%M:%S") -> pd.DataFrame:
    """
    Convert all datetime64 columns to formatted strings for JSON serialization.

    Returns the modified DataFrame (mutated in place).
    """
    for col in df.select_dtypes(include=["datetime64"]).columns:
        df[col] = df[col].dt.strftime(fmt)
    return df

# ── PDF Export ───────────────────────────────────────────────────────────────

def to_pdf_bytes(
    widgets: dict,
    metadata: dict,
    detections_df=None,
    downtime_df=None,
    charts: dict = None,
    tenant_name: str = "Dashboard",
) -> bytes:
    """
    Exportar datos del dashboard a PDF usando reportlab.

    Args:
        widgets:       widgetResults del API response.
        metadata:      metadata del API response (total_detections, period, ...).
        detections_df: DataFrame de detecciones (opcional).
        downtime_df:   DataFrame de paradas (opcional).
        tenant_name:   Nombre a mostrar en el encabezado.

    Returns:
        bytes del PDF generado.

    Raises:
        ImportError si reportlab no está instalado.
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            HRFlowable, PageBreak, Paragraph,
            SimpleDocTemplate, Spacer, Table, TableStyle,
        )
    except ImportError as exc:
        raise ImportError(
            "reportlab requerido para exportar PDF. "
            "Instalar con: pip install reportlab>=4.0"
        ) from exc

    import io
    from datetime import datetime

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=1.5 * cm, leftMargin=1.5 * cm,
        topMargin=2 * cm,     bottomMargin=2 * cm,
        title=f"{tenant_name} — Reporte",
    )

    styles    = getSampleStyleSheet()
    HDR_COLOR = colors.HexColor("#1e293b")
    ROW_ALT   = colors.HexColor("#f8fafc")
    ACCENT    = colors.HexColor("#6366f1")
    GREEN     = colors.HexColor("#22c55e")
    RED       = colors.HexColor("#ef4444")
    WHITE     = colors.white

    title_s = ParagraphStyle("T", parent=styles["Title"],   fontSize=18, spaceAfter=4)
    sub_s   = ParagraphStyle("S", parent=styles["Normal"],  fontSize=9,  textColor=colors.HexColor("#64748b"))
    sec_s   = ParagraphStyle("H", parent=styles["Heading2"],fontSize=12, textColor=ACCENT, spaceBefore=12, spaceAfter=5)

    def base_ts():
        return TableStyle([
            ("BACKGROUND",    (0,0),(-1,0), HDR_COLOR),
            ("TEXTCOLOR",     (0,0),(-1,0), WHITE),
            ("FONTNAME",      (0,0),(-1,0), "Helvetica-Bold"),
            ("FONTSIZE",      (0,0),(-1,0), 8),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[WHITE, ROW_ALT]),
            ("FONTNAME",      (0,1),(-1,-1),"Helvetica"),
            ("FONTSIZE",      (0,1),(-1,-1), 7.5),
            ("GRID",          (0,0),(-1,-1), 0.3, colors.HexColor("#e2e8f0")),
            ("ALIGN",         (0,0),(-1,-1), "LEFT"),
            ("TOPPADDING",    (0,0),(-1,-1), 4),
            ("BOTTOMPADDING", (0,0),(-1,-1), 4),
            ("LEFTPADDING",   (0,0),(-1,-1), 6),
            ("RIGHTPADDING",  (0,0),(-1,-1), 6),
        ])

    story = []
    now_str  = datetime.now().strftime("%d/%m/%Y %H:%M")
    period   = metadata.get("period", {})
    total    = metadata.get("total_detections", 0)

    story.append(Paragraph(f"{tenant_name} — Reporte de Producción", title_s))
    story.append(Paragraph(
        f"Período: {period.get('start','')} → {period.get('end','')}  |  "
        f"Detecciones: {total:,}  |  Generado: {now_str}",
        sub_s,
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT, spaceAfter=8))

    # KPIs
    kpi_rows = [["Indicador", "Valor", "Unidad"]]
    for wdata in widgets.values():
        data = wdata.get("data") or {}
        val  = data.get("value") or data.get("total") or data.get("oee") or ""
        unit = data.get("unit") or data.get("suffix") or ""
        if val != "":
            kpi_rows.append([wdata.get("widget_name",""), str(val), str(unit)])
    if len(kpi_rows) > 1:
        story.append(Paragraph("KPIs", sec_s))
        t = Table(kpi_rows, colWidths=[8*cm, 4*cm, 3*cm])
        t.setStyle(base_ts())
        story.append(t)
        story.append(Spacer(1, 0.4*cm))

    # Gráficos
    if charts:
        import base64
        from reportlab.platypus import Image
        for wid, wdata in widgets.items():
            if wdata.get("widget_type") != "chart":
                continue
            if wid in charts:
                try:
                    img_data = base64.b64decode(charts[wid])
                    # Determinar si es pie_chart para hacer un grafico mas chico
                    w_cm = 12 if wdata.get("chart_type") == "pie_chart" else 21
                    h_cm = 7 if wdata.get("chart_type") == "pie_chart" else 8
                    img = Image(io.BytesIO(img_data), width=w_cm*cm, height=h_cm*cm)
                    story.append(Paragraph(wdata.get("widget_name", f"Gráfico {wid}"), sec_s))
                    
                    t_img = Table([[img]], colWidths=[24*cm])
                    t_img.setStyle(TableStyle([
                        ("BACKGROUND", (0,0), (0,0), WHITE),
                        ("ALIGN", (0,0), (0,0), "CENTER"),
                        ("VALIGN", (0,0), (0,0), "MIDDLE"),
                        ("BOTTOMPADDING", (0,0), (0,0), 6),
                        ("TOPPADDING", (0,0), (0,0), 6),
                    ]))
                    story.append(t_img)
                    story.append(Spacer(1, 0.4*cm))
                    
                    # Si el grafico tiene una tabla asociada (ej. distribucion de productos)
                    if wdata.get("data") and wdata["data"].get("table_rows"):
                        table_data = [["Producto", "Color", "Cantidad", "Peso (kg)", "Porcentaje (%)"]]
                        for tr in wdata["data"]["table_rows"]:
                            table_data.append([
                                str(tr.get("label", "")),
                                str(tr.get("color", "")),
                                str(tr.get("count", 0)),
                                str(tr.get("weight_kg", 0.0)),
                                str(tr.get("pct", 0.0)) + "%"
                            ])
                        # Usar anchos proporcionales
                        t_tbl = Table(table_data, colWidths=[7*cm, 3*cm, 3*cm, 4*cm, 4*cm])
                        t_tbl.setStyle(base_ts())
                        story.append(t_tbl)
                        story.append(Spacer(1, 0.4*cm))
                        
                except Exception as e:
                    story.append(Paragraph(f"Error cargando imagen de gráfico {wid}: {str(e)}", sub_s))

    # Tabla de paradas (buscar por estructura de datos en lugar de nombre exacto)
    dt_widget = None
    for w in widgets.values():
        if w.get("widget_type") == "table" and w.get("data") and w["data"].get("columns"):
            wkeys = [c.get("key") for c in w["data"]["columns"]]
            if "source_badge" in wkeys or "failure_type" in wkeys:
                dt_widget = w
                break

    if dt_widget and dt_widget.get("data") and dt_widget["data"].get("rows"):
        story.append(PageBreak())
        story.append(Paragraph("Detalle de Paradas", sec_s))
        
        cols = dt_widget["data"].get("columns", [])
        headers = [c["label"] for c in cols]
        keys = [c["key"] for c in cols]
        
        dt_data = [headers]
        for row in dt_widget["data"]["rows"]:
            row_data = []
            for key in keys:
                val = row.get(key, "")
                if key == "source_badge":
                    # Traducir el badge a texto legible para PDF
                    if val == "db_confirmed": val = "Registrada ✓"
                    elif val == "db_unconfirmed": val = "Registrada"
                    elif val == "calculated": val = "Calculada"
                row_data.append(str(val))
            dt_data.append(row_data)
            
        ts = base_ts()
        
        if "source_badge" in keys:
            badge_idx = keys.index("source_badge")
            for i, r in enumerate(dt_data[1:], 1):
                raw_badge = dt_widget["data"]["rows"][i-1].get("source_badge")
                if raw_badge == "db_confirmed": color = GREEN
                elif raw_badge == "db_unconfirmed": color = colors.HexColor("#f97316")
                else: color = RED
                ts.add("TEXTCOLOR", (badge_idx,i), (badge_idx,i), color)
        
        # Ajustar anchos de columnas proporcionalmente (hay 10 columnas en la def actual)
        # Asignar anchos relativos
        total_cm = 25.5
        col_widths = []
        for key in keys:
            if key in ("tipo", "start_time", "end_time"): col_widths.append(2.5*cm)
            elif key == "duration_min": col_widths.append(2*cm)
            elif key in ("failure_type", "incident_code", "line_name", "source_badge"): col_widths.append(2.5*cm)
            elif key in ("failure_desc", "incident_desc"): col_widths.append(4*cm)
            else: col_widths.append(2.5*cm)
            
        # Normalizar si no es exacto
        t = Table(dt_data, colWidths=col_widths, repeatRows=1)
        t.setStyle(ts)
        story.append(t)
        story.append(Spacer(1, 0.4*cm))

    # Detecciones (preview)
    if detections_df is not None and not detections_df.empty:
        story.append(PageBreak())
        limit = 500
        cols  = [c for c in ["detected_at","product_name","area_type","line_name","shift_id"] if c in detections_df.columns]
        if cols:
            preview = format_datetime_columns(detections_df[cols].head(limit).copy())
            story.append(Paragraph(f"Detecciones (primeras {min(limit, len(detections_df))})", sec_s))
            det_data = [[c.replace("_"," ").title() for c in cols]] + preview.values.tolist()
            w = (28/len(cols))*cm
            t = Table(det_data, colWidths=[w]*len(cols), repeatRows=1)
            t.setStyle(base_ts())
            story.append(t)

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#94a3b8"))
        pw, _ = landscape(A4)
        canvas.drawString(1.5*cm, 0.8*cm, f"Generado: {now_str}")
        canvas.drawRightString(pw-1.5*cm, 0.8*cm, f"Pág. {doc.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
