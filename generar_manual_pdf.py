#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para convertir docs/manual_usuario.md en docs/manual_usuario_zunin.pdf
utilizando la biblioteca ReportLab instalada en el entorno.
"""

import os
import re
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
    HRFlowable,
)
from reportlab.pdfgen import canvas


class NumberedCanvas(canvas.Canvas):
    """Canvas de dos pasadas para calcular el número total de páginas."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))  # slate-500

        # Omitir encabezado y pie en portada si página == 1
        if self._pageNumber > 1:
            # Encabezado
            self.drawString(
                2 * cm,
                A4[1] - 1.3 * cm,
                "Sistema Zunin &bull; Manual de Usuario Integral",
            )
            self.drawRightString(
                A4[0] - 2 * cm, A4[1] - 1.3 * cm, "IESETyFP - Bedelía y Personal"
            )
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.5)
            self.line(2 * cm, A4[1] - 1.5 * cm, A4[0] - 2 * cm, A4[1] - 1.5 * cm)

            # Pie de página
            self.line(2 * cm, 1.8 * cm, A4[0] - 2 * cm, 1.8 * cm)
            self.drawString(
                2 * cm,
                1.3 * cm,
                "IESETyFP - Instituto de Educación Superior "
                "&bull; Versión 2.0 (Sprint 3)",
            )
            page_text = f"Página {self._pageNumber} de {page_count}"
            self.drawRightString(A4[0] - 2 * cm, 1.3 * cm, page_text)

        self.restoreState()


def inline_markdown_to_xml(text):
    """Convierte negrita, cursiva y código inline a formato XML de ReportLab."""
    # Escapar entidades XML básicas
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;").replace(">", "&gt;")

    # Reemplazar flechas y entidades comunes
    text = text.replace("&amp;rarr;", "→").replace("&rarr;", "→")
    text = text.replace("&amp;bull;", "•").replace("&bull;", "•")
    text = text.replace("&amp;ndash;", "–").replace("&ndash;", "–")

    # Negrita + Cursiva ***texto***
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"<b><i>\1</i></b>", text)
    # Negrita **texto**
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    # Cursiva *texto*
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    # Código `texto`
    text = re.sub(
        r"`(.+?)`",
        r'<font face="Courier" color="#1e293b" size="8.5"><b>\1</b></font>',
        text,
    )

    return text


def parse_markdown_to_flowables(md_path, styles):
    """Parsea el archivo markdown y genera la lista de flowables para ReportLab."""
    with open(md_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    story = []
    i = 0
    n = len(lines)

    in_table = False
    table_lines = []

    def flush_table():
        nonlocal in_table, table_lines
        if not table_lines:
            return
        # Procesar tabla markdown
        rows = []
        for line in table_lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("| :") or stripped.startswith("|:"):
                continue  # Línea separadora de encabezado
            # Dividir columnas
            cols = [c.strip() for c in stripped.split("|")[1:-1]]
            if cols:
                rows.append(cols)

        if rows:
            # Convertir celdas a Paragraph
            formatted_data = []
            num_cols = len(rows[0])
            for r_idx, row in enumerate(rows):
                formatted_row = []
                for c_idx, cell in enumerate(row):
                    style = styles["TableHeader"] if r_idx == 0 else styles["TableCell"]
                    formatted_row.append(
                        Paragraph(inline_markdown_to_xml(cell), style)
                    )
                # Rellenar si faltan columnas
                while len(formatted_row) < num_cols:
                    formatted_row.append(Paragraph("", styles["TableCell"]))
                formatted_data.append(formatted_row)

            # Anchos proporcionales de columnas
            total_width = A4[0] - 4 * cm  # 17 cm aprox
            col_width = total_width / max(1, num_cols)
            col_widths = [col_width] * num_cols

            # Estilo de tabla profesional
            t = Table(formatted_data, colWidths=col_widths, repeatRows=1)
            t.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                    ("TOPPADDING", (0, 0), (-1, 0), 6),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
                        colors.HexColor("#ffffff"),
                        colors.HexColor("#f8fafc"),
                    ]),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ("TOPPADDING", (0, 1), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
                ])
            )
            story.append(Spacer(1, 0.2 * cm))
            story.append(t)
            story.append(Spacer(1, 0.3 * cm))

        in_table = False
        table_lines = []

    while i < n:
        raw_line = lines[i]
        line = raw_line.strip()

        # Detección de tablas markdown
        if line.startswith("|") and line.endswith("|"):
            in_table = True
            table_lines.append(line)
            i += 1
            continue
        elif in_table:
            flush_table()

        # Líneas vacías
        if not line:
            i += 1
            continue

        # Separadores horizontales
        if line in ("---", "***", "___"):
            story.append(Spacer(1, 0.2 * cm))
            story.append(
                HRFlowable(
                    width="100%",
                    thickness=0.8,
                    color=colors.HexColor("#e2e8f0"),
                    spaceAfter=8,
                    spaceBefore=8,
                )
            )
            i += 1
            continue

        # Título principal # (Portada / Banner)
        if line.startswith("# "):
            title_text = line[2:].strip()
            # Si hay líneas descriptivas a continuación
            subtitle_text = ""
            if i + 1 < n and lines[i + 1].strip().startswith("**"):
                subtitle_text = lines[i + 1].strip().strip("*")
                i += 1

            story.append(Spacer(1, 0.5 * cm))
            # Banner principal
            banner_data = [
                [Paragraph(inline_markdown_to_xml(title_text), styles["CoverTitle"])],
            ]
            if subtitle_text:
                banner_data.append([
                    Paragraph(
                        inline_markdown_to_xml(subtitle_text),
                        styles["CoverSubtitle"],
                    )
                ])

            banner = Table(
                banner_data,
                colWidths=[A4[0] - 4 * cm],
            )
            banner.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0f172a")),
                    ("TOPPADDING", (0, 0), (-1, -1), 14),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
                    ("LEFTPADDING", (0, 0), (-1, -1), 16),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 16),
                    ("BOX", (0, 0), (-1, -1), 1.5, colors.HexColor("#1e3a8a")),
                ])
            )
            story.append(banner)
            story.append(Spacer(1, 0.5 * cm))
            i += 1
            continue

        # Encabezado Nivel 2 ##
        if line.startswith("## "):
            h2_text = line[3:].strip()
            story.append(Spacer(1, 0.4 * cm))
            p = Paragraph(inline_markdown_to_xml(h2_text), styles["CustomH1"])
            story.append(KeepTogether([p, Spacer(1, 0.15 * cm)]))
            i += 1
            continue

        # Encabezado Nivel 3 ###
        if line.startswith("### "):
            h3_text = line[4:].strip()
            story.append(Spacer(1, 0.25 * cm))
            p = Paragraph(inline_markdown_to_xml(h3_text), styles["CustomH2"])
            story.append(KeepTogether([p, Spacer(1, 0.1 * cm)]))
            i += 1
            continue

        # Encabezado Nivel 4 ####
        if line.startswith("#### "):
            h4_text = line[5:].strip()
            story.append(Spacer(1, 0.2 * cm))
            p = Paragraph(inline_markdown_to_xml(h4_text), styles["CustomH3"])
            story.append(KeepTogether([p, Spacer(1, 0.1 * cm)]))
            i += 1
            continue

        # Blockquote >
        if line.startswith(">"):
            quote_text = line.lstrip(">").strip()
            p = Paragraph(inline_markdown_to_xml(quote_text), styles["CalloutText"])
            t = Table([[p]], colWidths=[A4[0] - 4 * cm])
            t.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
                    ("LINEBEFORE", (0, 0), (0, -1), 3.5, colors.HexColor("#3b82f6")),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ])
            )
            story.append(Spacer(1, 0.15 * cm))
            story.append(t)
            story.append(Spacer(1, 0.2 * cm))
            i += 1
            continue

        # Lista de viñetas -
        if line.startswith("- ") or line.startswith("* "):
            bullet_text = line[2:].strip()
            bullet_p = Paragraph(
                f"&bull; {inline_markdown_to_xml(bullet_text)}",
                styles["BulletItem"],
            )
            story.append(bullet_p)
            i += 1
            continue

        # Lista numerada (1. , 2. )
        num_match = re.match(r"^(\d+)\.\s+(.*)$", line)
        if num_match:
            num = num_match.group(1)
            num_text = num_match.group(2)
            num_p = Paragraph(
                f"<b>{num}.</b> {inline_markdown_to_xml(num_text)}",
                styles["BulletItem"],
            )
            story.append(num_p)
            i += 1
            continue

        # Párrafo estándar
        story.append(Paragraph(inline_markdown_to_xml(line), styles["CustomBody"]))
        i += 1

    if in_table:
        flush_table()

    return story


def build_pdf():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    md_path = os.path.join(base_dir, "docs", "manual_usuario.md")
    pdf_path = os.path.join(base_dir, "docs", "manual_usuario_zunin.pdf")

    if not os.path.exists(md_path):
        print(f"Error: No se encontró el archivo {md_path}")
        return False

    print(f"Leyendo documento Markdown: {md_path}")

    # Configuración del documento A4 con márgenes de 2cm
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2.2 * cm,
    )

    # Estilos tipográficos
    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="CoverTitle",
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#ffffff"),
            alignment=0,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CoverSubtitle",
            fontName="Helvetica",
            fontSize=10.5,
            leading=15,
            textColor=colors.HexColor("#93c5fd"),
            alignment=0,
            spaceBefore=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CustomH1",
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=17,
            textColor=colors.HexColor("#1e3a8a"),  # Azul institucional
            spaceBefore=10,
            spaceAfter=4,
            keepWithNext=True,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CustomH2",
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=14,
            textColor=colors.HexColor("#0f172a"),  # Pizarra oscura
            spaceBefore=8,
            spaceAfter=3,
            keepWithNext=True,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CustomH3",
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor("#334155"),
            spaceBefore=6,
            spaceAfter=2,
            keepWithNext=True,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CustomBody",
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#1e293b"),
            spaceBefore=2,
            spaceAfter=5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BulletItem",
            fontName="Helvetica",
            fontSize=8.8,
            leading=12.5,
            textColor=colors.HexColor("#1e293b"),
            leftIndent=14,
            spaceBefore=1,
            spaceAfter=2,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CalloutText",
            fontName="Helvetica-Oblique",
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#1e293b"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="TableHeader",
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=colors.white,
            alignment=0,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TableCell",
            fontName="Helvetica",
            fontSize=7.8,
            leading=10.5,
            textColor=colors.HexColor("#0f172a"),
            alignment=0,
        )
    )

    story = parse_markdown_to_flowables(md_path, styles)
    print(f"Total elementos flowable generados: {len(story)}")

    # Compilar PDF con dos pasadas para numeración total de páginas
    print(f"Generando archivo PDF: {pdf_path}...")
    doc.build(story, canvasmaker=NumberedCanvas)

    if os.path.exists(pdf_path):
        size_kb = os.path.getsize(pdf_path) / 1024
        print(f"PDF generado exitosamente ({size_kb:.1f} KB): {pdf_path}")
        return True
    else:
        print("Error: El archivo PDF no se generó.")
        return False


if __name__ == "__main__":
    success = build_pdf()
    exit(0 if success else 1)
