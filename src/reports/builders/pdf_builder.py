"""
Builder de informe PDF forense.

Genera un PDF profesional con tablas, gráficas embebidas y mapas estáticos
usando ReportLab Platypus para layout programático.
"""
from __future__ import annotations

import logging
from datetime import datetime
from functools import partial
from pathlib import Path
from xml.sax.saxutils import escape

from typing import Callable, Optional

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, cm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.flowables import HRFlowable

from config.constants import (
    CALL_TYPE_INCOMING,
    CALL_TYPE_OUTGOING,
    COL_CALL_TYPE,
    COL_DATETIME,
    COL_LATITUDE,
    COL_LONGITUDE,
    COL_ORIGINATOR,
    COL_RECEIVER,
    PDF_ACCENT_COLOR_HEX,
    PDF_BRAND_COLOR_HEX,
    PDF_MAP_DIR_NAME,
    TOP_N_CALLS,
)
from config.settings import settings
from core.models import PdfExportConfig, ReportConfig, RouteMapMode

logger = logging.getLogger(__name__)

# ── Medidas de página ────────────────────────────────────────────────────────
_PAGE_W, _PAGE_H = letter  # 612 x 792 puntos
_MARGIN_TOP = 60
_MARGIN_BOTTOM = 50
_MARGIN_LEFT = 50
_MARGIN_RIGHT = 50
_CONTENT_W = _PAGE_W - _MARGIN_LEFT - _MARGIN_RIGHT  # ~512 pts = ~7.1 in


# ══════════════════════════════════════════════════════════════════════════════
# Estilos
# ══════════════════════════════════════════════════════════════════════════════

class _Sty:
    """Colores y estilos centralizados para el PDF corporativo."""

    ALT_ROW = colors.HexColor("#f8f9fa")
    BORDER = colors.HexColor("#dee2e6")
    LIGHT_GRAY = colors.HexColor("#6c757d")
    KPI_BG = colors.HexColor("#e8f4fd")
    BRAND = colors.HexColor(PDF_BRAND_COLOR_HEX)
    HEADER_BG = colors.HexColor("#f8f9fa")
    HEADER_TXT = colors.HexColor("#6c757d")

    @classmethod
    def styles(cls, primary_color: str, secondary_color: str) -> dict[str, ParagraphStyle]:
        base = getSampleStyleSheet()
        brand = colors.HexColor(primary_color)
        accent = colors.HexColor(secondary_color)

        return {
            "title": ParagraphStyle(
                "PTitle", parent=base["Title"],
                fontSize=20, fontName="Helvetica-Bold",
                textColor=brand, spaceAfter=4, alignment=TA_CENTER,
            ),
            "subtitle": ParagraphStyle(
                "PSub", parent=base["Normal"],
                fontSize=11, textColor=cls.LIGHT_GRAY,
                alignment=TA_CENTER, spaceAfter=16,
            ),
            "h2": ParagraphStyle(
                "PH2", parent=base["Heading2"],
                fontSize=14, fontName="Helvetica-Bold",
                textColor=brand, spaceBefore=18, spaceAfter=8,
            ),
            "h3": ParagraphStyle(
                "PH3", parent=base["Heading3"],
                fontSize=11, fontName="Helvetica-Bold",
                textColor=brand, spaceBefore=10, spaceAfter=4,
            ),
            "body": ParagraphStyle(
                "PBody", parent=base["Normal"],
                fontSize=9, fontName="Helvetica", leading=12,
            ),
            "cell": ParagraphStyle(
                "PCell", parent=base["Normal"],
                fontSize=8, fontName="Helvetica", leading=10,
            ),
            "cell_bold": ParagraphStyle(
                "PCellB", parent=base["Normal"],
                fontSize=8, fontName="Helvetica-Bold", leading=10,
            ),
            "cell_header": ParagraphStyle(
                "PCellH", parent=base["Normal"],
                fontSize=8, fontName="Helvetica-Bold", leading=10,
                textColor=colors.HexColor("#343a40"),
            ),
            "link": ParagraphStyle(
                "PLink", parent=base["Normal"],
                fontSize=7, fontName="Helvetica",
                textColor=accent, leading=9,
            ),
            "footer": ParagraphStyle(
                "PFoot", parent=base["Normal"],
                fontSize=7, textColor=colors.gray, alignment=TA_CENTER,
            ),
            "note": ParagraphStyle(
                "PNote", parent=base["Normal"],
                fontSize=8, fontName="Helvetica-Oblique",
                textColor=cls.LIGHT_GRAY, spaceBefore=6, spaceAfter=6,
                leftIndent=10,
            ),
            "kpi_value": ParagraphStyle(
                "PKpi", parent=base["Normal"],
                fontSize=16, fontName="Helvetica-Bold",
                textColor=brand, alignment=TA_CENTER,
            ),
            "kpi_label": ParagraphStyle(
                "PKpiL", parent=base["Normal"],
                fontSize=8, textColor=cls.LIGHT_GRAY,
                alignment=TA_CENTER,
            ),
        }


def _table_base_style() -> list:
    """Comandos base de estilo para tablas de datos."""
    return [
        ("BACKGROUND", (0, 0), (-1, 0), _Sty.HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#343a40")), # Forced dark text for visibility
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 7.5),
        ("TOPPADDING", (0, 1), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 3),
        ("ALIGN", (0, 1), (-1, -1), "LEFT"),
        ("GRID", (0, 0), (-1, -1), 0.5, _Sty.BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]


def _alt_rows(num_data_rows: int) -> list:
    """Comandos de filas alternadas (excluye header en fila 0)."""
    cmds = []
    for i in range(1, num_data_rows + 1):
        if i % 2 == 0:
            cmds.append(("BACKGROUND", (0, i), (-1, i), _Sty.ALT_ROW))
    return cmds


def _coords_paragraph(
    lat: object, lon: object, sty: ParagraphStyle, sty_link: ParagraphStyle,
) -> Paragraph:
    """Crea celda de coordenadas con link a Google Maps si tiene datos."""
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (TypeError, ValueError):
        return Paragraph("N/A", sty)
    if pd.isna(lat_f) or pd.isna(lon_f):
        return Paragraph("N/A", sty)

    coords = f"{lat_f:.5f}, {lon_f:.5f}"
    url = f"https://www.google.com/maps?q={lat_f},{lon_f}"
    return Paragraph(
        f'<a href="{url}" color="{PDF_ACCENT_COLOR_HEX}">{coords}</a>',
        sty_link,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Builder principal
# ══════════════════════════════════════════════════════════════════════════════

class PdfReportBuilder:
    """Construye un informe PDF forense profesional con ReportLab."""

    def __init__(self, config: ReportConfig = None) -> None:
        self.config = config
        if config:
            self._s = _Sty.styles(config.primary_color, config.secondary_color)
        else:
            self._s = _Sty.styles(PDF_BRAND_COLOR_HEX, PDF_ACCENT_COLOR_HEX)

    def build(
        self,
        df: pd.DataFrame,
        output_path: Path,
        report_config: ReportConfig,
        pdf_config: PdfExportConfig,
        base_dir: Path,
        geocoding_service=None,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> Path:
        self.config = report_config
        self._s = _Sty.styles(report_config.primary_color, report_config.secondary_color)
        """Genera el PDF completo.

        Args:
            df: DataFrame procesado completo (llamadas + datos internet).
            output_path: Ruta para el PDF de salida.
            report_config: Configuración del informe.
            pdf_config: Configuración específica de PDF.
            base_dir: Directorio base del informe (contiene graphics/, etc.).
            geocoding_service: Servicio de geocodificación para departamento/municipio.

        Returns:
            Ruta al PDF generado.
        """
        self._geo = geocoding_service
        self._progress = progress_callback

        def _emit(pct: int, text: str) -> None:
            if self._progress:
                self._progress(pct, text)

        # Separar llamadas y datos
        _emit(55, "Construyendo PDF: preparando datos...")
        mask_data = df[COL_CALL_TYPE].astype(str).str.upper().str.contains("DATO")
        df_calls = df[~mask_data].copy()
        df_data = df[mask_data].copy()

        # Determinar logo
        logo_path: Path | None = None
        if report_config.include_letterhead:
            if report_config.logo_type == "custom" and report_config.custom_logo_path:
                custom_path = Path(report_config.custom_logo_path)
                if custom_path.exists():
                    logo_path = custom_path
            elif settings.logo_path.exists():
                logo_path = settings.logo_path

        # Construir documento
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=letter,
            topMargin=_MARGIN_TOP,
            bottomMargin=_MARGIN_BOTTOM,
            leftMargin=_MARGIN_LEFT,
            rightMargin=_MARGIN_RIGHT,
            title=f"Informe - {report_config.report_name}",
            author="Coyprot Analysis",
        )

        story: list = []
        _emit(58, "Construyendo PDF: portada...")
        story.extend(self._cover(report_config, df_calls, df_data, logo_path))
        story.append(PageBreak())

        if report_config.pdf_draft and len(report_config.pdf_draft) > 0:
            _emit(60, "Construyendo PDF: Procesando bloques personalizados...")
            for i, block in enumerate(report_config.pdf_draft):
                _emit(60 + min(25, int(i / len(report_config.pdf_draft) * 25)), f"Construyendo bloque: {block.get('title', 'Bloque')}...")
                story.extend(self._render_block(block, df_calls, df_data, base_dir, report_config))
        else:
            # Fallback legacy builder if no blocks
            _emit(60, "Construyendo PDF: resumen...")
            story.extend(self._summary(df_calls, report_config))
            story.append(PageBreak())
            _emit(62, "Construyendo PDF: gráficos...")
            story.extend(self._charts(base_dir / "graphics"))
            _emit(65, "Construyendo PDF: tablas entrantes...")
            story.extend(self._call_tables(df_calls, report_config, "entrante"))
            _emit(75, "Construyendo PDF: tablas salientes...")
            story.extend(self._call_tables(df_calls, report_config, "saliente"))
            _emit(85, "Construyendo PDF: mapas...")
            story.extend(self._maps_section(base_dir, pdf_config))

        story.extend(self._notes(report_config, pdf_config))

        _emit(88, "Construyendo PDF: renderizando documento...")

        footer_fn = partial(self._draw_header_footer, logo_path=logo_path, primary_color=report_config.primary_color)
        doc.build(story, onFirstPage=footer_fn, onLaterPages=footer_fn)
        logger.info("PDF generado: %s", output_path)
        return output_path

    # ── Portada ──────────────────────────────────────────────────────────────

    def _cover(
        self,
        config: ReportConfig,
        df_calls: pd.DataFrame,
        df_data: pd.DataFrame,
        logo_path: Path | None,
    ) -> list:
        elems: list = []

        # Espacio superior
        elems.append(Spacer(1, 40))

        # Logo
        if logo_path and logo_path.exists():
            try:
                img = Image(str(logo_path), width=2.2 * inch, height=0.8 * inch)
                img.hAlign = "CENTER"
                elems.append(img)
                elems.append(Spacer(1, 16))
            except Exception:
                pass

        elems.append(Paragraph("INFORME DE ANALISIS DE LLAMADAS", self._s["title"]))
        elems.append(Paragraph(escape(config.report_name), self._s["subtitle"]))
        elems.append(Spacer(1, 8))
        elems.append(HRFlowable(
            width="80%", thickness=1.5, color=colors.HexColor(config.primary_color),
            spaceAfter=20, hAlign="CENTER",
        ))

        # Metadatos del caso
        meta = config.case_metadata.to_dict()
        if any(v.strip() for v in meta.values()):
            rows = [
                [Paragraph(f"<b>{escape(k)}</b>", self._s["cell_bold"]),
                 Paragraph(escape(v) if v.strip() else "—", self._s["cell"])]
                for k, v in meta.items()
            ]
            t = Table(rows, colWidths=[1.8 * inch, 3.5 * inch])
            t.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, _Sty.BORDER),
                ("BACKGROUND", (0, 0), (0, -1), _Sty.ALT_ROW),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ]))
            t.hAlign = "CENTER"
            elems.append(t)
            elems.append(Spacer(1, 20))

        # Fecha de generación
        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        elems.append(Paragraph(
            f"Fecha de generacion: <b>{now}</b>", self._s["body"],
        ))
        elems.append(Spacer(1, 6))

        # Resumen rápido
        total_calls = len(df_calls)
        total_data = len(df_data)
        elems.append(Paragraph(
            f"Registros de llamadas: <b>{total_calls:,}</b> | "
            f"Registros de datos internet: <b>{total_data:,}</b>",
            self._s["body"],
        ))
        elems.append(Spacer(1, 30))

        # Nota de integridad
        elems.append(Paragraph(
            "La integridad de este documento puede verificarse con el archivo "
            "<b>.sha256</b> generado junto al PDF.",
            self._s["note"],
        ))

        return elems

    # ── Resumen / KPIs ───────────────────────────────────────────────────────

    def _summary(self, df_calls: pd.DataFrame, config: ReportConfig) -> list:
        elems: list = []
        elems.append(Paragraph("Resumen General", self._s["h2"]))

        # Calcular estadísticas
        unique_nums: set[str] = set()
        for col in (COL_ORIGINATOR, COL_RECEIVER):
            if col in df_calls.columns:
                unique_nums.update(df_calls[col].dropna().astype(str).unique())

        total = len(df_calls)
        n_in = len(df_calls[df_calls[COL_CALL_TYPE] == CALL_TYPE_INCOMING])
        n_out = len(df_calls[df_calls[COL_CALL_TYPE] == CALL_TYPE_OUTGOING])
        avg = round(total / len(unique_nums), 2) if unique_nums else 0

        # KPI cards como tabla
        kpi_data = [
            ("Total Llamadas", f"{total:,}"),
            ("Entrantes", f"{n_in:,}"),
            ("Salientes", f"{n_out:,}"),
            ("Numeros Unicos", f"{len(unique_nums):,}"),
            ("Promedio/Numero", f"{avg}"),
        ]
        header = [Paragraph(f"<b>{k}</b>", self._s["kpi_label"]) for k, _ in kpi_data]
        values = [Paragraph(v, self._s["kpi_value"]) for _, v in kpi_data]

        kpi_table = Table(
            [header, values],
            colWidths=[_CONTENT_W / len(kpi_data)] * len(kpi_data),
        )
        kpi_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), _Sty.KPI_BG),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("BOX", (0, 0), (-1, -1), 1, _Sty.BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, _Sty.BORDER),
            ("ROUNDEDCORNERS", [6, 6, 6, 6]),
        ]))
        elems.append(kpi_table)
        elems.append(Spacer(1, 16))

        # Top Entrantes
        df_in = df_calls[df_calls[COL_CALL_TYPE] == CALL_TYPE_INCOMING]
        top_in = self._top_n_list(df_in, COL_ORIGINATOR, config)
        if top_in:
            elems.append(Paragraph("Top Numeros Entrantes", self._s["h3"]))
            elems.append(self._small_ranking_table(top_in))
            elems.append(Spacer(1, 10))

        # Top Salientes
        df_out = df_calls[df_calls[COL_CALL_TYPE] == CALL_TYPE_OUTGOING]
        top_out = self._top_n_list(df_out, COL_RECEIVER, config)
        if top_out:
            elems.append(Paragraph("Top Numeros Salientes", self._s["h3"]))
            elems.append(self._small_ranking_table(top_out))

        return elems

    def _top_n_list(
        self, df: pd.DataFrame, col: str, config: ReportConfig, n: int = TOP_N_CALLS,
    ) -> list[tuple[str, int]]:
        if df.empty or col not in df.columns:
            return []
        result = []
        for num, count in df[col].value_counts().head(n).items():
            display = config.display_name(str(num))
            result.append((display, int(count)))
        return result

    def _small_ranking_table(self, items: list[tuple[str, int]]) -> Table:
        header = [
            Paragraph("<b>#</b>", self._s["cell_header"]),
            Paragraph("<b>Numero / Alias</b>", self._s["cell_header"]),
            Paragraph("<b>Frecuencia</b>", self._s["cell_header"]),
        ]
        rows = [header]
        for i, (name, freq) in enumerate(items, 1):
            rows.append([
                Paragraph(str(i), self._s["cell"]),
                Paragraph(escape(name), self._s["cell"]),
                Paragraph(f"{freq:,}", self._s["cell"]),
            ])
        t = Table(rows, colWidths=[0.4 * inch, 3.5 * inch, 1.0 * inch])
        cmds = _table_base_style() + _alt_rows(len(items))
        t.setStyle(TableStyle(cmds))
        return t

    # ── Gráficos ─────────────────────────────────────────────────────────────

    def _charts(self, graphics_dir: Path) -> list:
        elems: list = []
        chart_files = [
            ("top_llamadas_recibidas.png", "Top Llamadas Recibidas"),
            ("top_ubicacion_recibidas.png", "Top Origen y Ubicacion"),
            ("top_llamadas_realizadas.png", "Top Llamadas Realizadas"),
            ("top_ubicacion_realizadas.png", "Top Destino y Ubicacion"),
            ("grafico_horario_llamadas.png", "Distribucion Horaria de Llamadas"),
        ]

        found = False
        for filename, title in chart_files:
            path = graphics_dir / filename
            if not path.exists():
                continue
            if not found:
                elems.append(Paragraph("Graficos Estadisticos", self._s["h2"]))
                found = True
            elems.append(Paragraph(title, self._s["h3"]))
            try:
                img = Image(str(path), width=6.2 * inch, height=3.2 * inch)
                img.hAlign = "CENTER"
                elems.append(img)
                elems.append(Spacer(1, 8))
            except Exception:
                logger.warning("No se pudo embeber chart: %s", filename)

        if found:
            elems.append(PageBreak())
        return elems

    # ── Tablas detalladas de llamadas ─────────────────────────────────────────

    def _call_tables(
        self,
        df_calls: pd.DataFrame,
        config: ReportConfig,
        call_type: str,
    ) -> list:
        elems: list = []

        if call_type == "entrante":
            mask = df_calls[COL_CALL_TYPE] == CALL_TYPE_INCOMING
            number_col = COL_ORIGINATOR
            section_title = "Detalle Llamadas Entrantes"
        else:
            mask = df_calls[COL_CALL_TYPE] == CALL_TYPE_OUTGOING
            number_col = COL_RECEIVER
            section_title = "Detalle Llamadas Salientes"

        df_type = df_calls[mask].copy()
        if df_type.empty:
            return elems

        elems.append(Paragraph(section_title, self._s["h2"]))

        has_coords = (
            COL_LATITUDE in df_type.columns
            and df_type[COL_LATITUDE].notna().any()
        )

        # Agrupar por número
        grouped = df_type.groupby(number_col, sort=False)
        for number, group in sorted(grouped, key=lambda x: -len(x[1])):
            display = config.display_name(str(number))
            elems.append(Paragraph(
                f"{escape(display)} ({len(group):,} registros)", self._s["h3"],
            ))

            header = [
                Paragraph("<b>#</b>", self._s["cell_header"]),
                Paragraph("<b>Fecha/Hora</b>", self._s["cell_header"]),
                Paragraph("<b>Dur.(s)</b>", self._s["cell_header"]),
                Paragraph("<b>Departamento</b>", self._s["cell_header"]),
                Paragraph("<b>Municipio</b>", self._s["cell_header"]),
                Paragraph("<b>Coordenadas</b>", self._s["cell_header"]),
            ]

            col_widths = [
                0.35 * inch,  # #
                1.25 * inch,  # Fecha/Hora
                0.55 * inch,  # Duracion
                1.15 * inch,  # Departamento
                1.05 * inch,  # Municipio
                1.75 * inch,  # Coordenadas
            ]

            rows = [header]
            for seq, row in enumerate(
                group.sort_values(COL_DATETIME).itertuples(index=False), 1
            ):
                dt = getattr(row, COL_DATETIME, None)
                dt_str = ""
                if dt is not None and pd.notna(dt):
                    try:
                        dt_str = dt.strftime("%Y-%m-%d %H:%M")
                    except Exception:
                        dt_str = str(dt)

                dur = getattr(row, "duracion", 0)
                try:
                    dur = int(dur)
                except (TypeError, ValueError):
                    dur = 0

                lat = getattr(row, COL_LATITUDE, None) if has_coords else None
                lon = getattr(row, COL_LONGITUDE, None) if has_coords else None

                depto = "—"
                muni = "—"
                if has_coords and self._geo:
                    try:
                        lat_f = float(lat)
                        lon_f = float(lon)
                        if pd.notna(lat_f) and pd.notna(lon_f):
                            depto, muni = self._geo.get_location(lat_f, lon_f)
                    except (TypeError, ValueError):
                        pass

                rows.append([
                    Paragraph(str(seq), self._s["cell"]),
                    Paragraph(dt_str, self._s["cell"]),
                    Paragraph(str(dur), self._s["cell"]),
                    Paragraph(escape(depto), self._s["cell"]),
                    Paragraph(escape(muni), self._s["cell"]),
                    _coords_paragraph(lat, lon, self._s["cell"], self._s["link"]),
                ])

            num_data = len(rows) - 1
            cmds = _table_base_style() + _alt_rows(num_data)

            t = Table(rows, colWidths=col_widths, repeatRows=1)
            t.setStyle(TableStyle(cmds))
            elems.append(t)
            elems.append(Spacer(1, 12))

        elems.append(PageBreak())
        return elems

    # ── Sección de mapas ─────────────────────────────────────────────────────

    def _maps_section(self, base_dir: Path, pdf_config: PdfExportConfig) -> list:
        elems: list = []
        maps_dir = base_dir / PDF_MAP_DIR_NAME

        if not maps_dir.exists():
            return elems

        # Mapa de ubicaciones
        loc_map = maps_dir / "mapa_ubicaciones.png"
        if loc_map.exists() and pdf_config.include_location_maps:
            elems.append(Paragraph("Mapa de Ubicaciones de Llamadas", self._s["h2"]))
            try:
                img = Image(str(loc_map), width=6.5 * inch, height=4.3 * inch)
                img.hAlign = "CENTER"
                elems.append(img)
                elems.append(Spacer(1, 8))
                elems.append(Paragraph(
                    "Marcadores azules: llamadas entrantes. "
                    "Marcadores verdes: llamadas salientes.",
                    self._s["note"],
                ))
                elems.append(PageBreak())
            except Exception:
                logger.warning("No se pudo embeber mapa de ubicaciones.")

        # Mapas de recorrido
        if not pdf_config.include_route_maps:
            return elems

        if pdf_config.route_map_mode == RouteMapMode.CONSOLIDATED:
            consolidated = maps_dir / "ruta_consolidada.png"
            if consolidated.exists():
                elems.append(Paragraph("Recorrido Consolidado de Datos", self._s["h2"]))
                try:
                    img = Image(str(consolidated), width=6.5 * inch, height=4.3 * inch)
                    img.hAlign = "CENTER"
                    elems.append(img)
                    elems.append(Spacer(1, 8))
                    elems.append(Paragraph(
                        "Ruta consolidada de todos los registros de datos de "
                        "internet, diferenciada por colores segun el dia.",
                        self._s["note"],
                    ))
                except Exception:
                    logger.warning("No se pudo embeber ruta consolidada.")
        else:
            # Mapas diarios
            import re
            daily_maps = sorted(
                maps_dir.glob("ruta_*.png"),
                key=lambda p: p.stem,
            )
            # Excluir la consolidada si existe
            daily_maps = [p for p in daily_maps if p.stem != "ruta_consolidada"]

            if daily_maps:
                elems.append(Paragraph(
                    "Recorrido Detallado por Dia", self._s["h2"],
                ))
                for map_path in daily_maps:
                    # Extraer fecha del nombre: ruta_2024-01-15.png
                    date_part = map_path.stem.replace("ruta_", "")
                    try:
                        dt = pd.Timestamp(date_part)
                        _MESES = (
                            "", "enero", "febrero", "marzo", "abril", "mayo",
                            "junio", "julio", "agosto", "septiembre",
                            "octubre", "noviembre", "diciembre",
                        )
                        label = f"{dt.day} de {_MESES[dt.month]} de {dt.year}"
                    except Exception:
                        label = date_part

                    elems.append(Paragraph(label, self._s["h3"]))
                    try:
                        img = Image(
                            str(map_path), width=6.5 * inch, height=4.0 * inch,
                        )
                        img.hAlign = "CENTER"
                        elems.append(img)
                        elems.append(Spacer(1, 6))
                    except Exception:
                        logger.warning("No se pudo embeber: %s", map_path.name)

        return elems

    # ── Notas finales ────────────────────────────────────────────────────────

    def _notes(self, config: ReportConfig, pdf_config: PdfExportConfig) -> list:
        elems: list = []
        elems.append(Spacer(1, 20))
        elems.append(HRFlowable(
            width="100%", thickness=1, color=_Sty.BORDER,
            spaceAfter=12, spaceBefore=12,
        ))

        # Nota de informe interactivo
        if pdf_config.ftp_url:
            elems.append(Paragraph(
                f"El informe interactivo completo esta disponible en: "
                f'<a href="{escape(pdf_config.ftp_url)}" '
                f'color="{PDF_ACCENT_COLOR_HEX}">'
                f"{escape(pdf_config.ftp_url)}</a>",
                self._s["body"],
            ))
            elems.append(Spacer(1, 8))

        # Adjuntos
        if config.pdf_attachments:
            valid = [a for a in config.pdf_attachments if a.is_valid]
            if valid:
                elems.append(Paragraph("Documentos Adjuntos", self._s["h3"]))
                header = [
                    Paragraph("<b>Categoria</b>", self._s["cell_header"]),
                    Paragraph("<b>Archivo</b>", self._s["cell_header"]),
                ]
                rows = [header]
                for att in valid:
                    rows.append([
                        Paragraph(escape(att.category), self._s["cell"]),
                        Paragraph(escape(att.filename), self._s["cell"]),
                    ])
                t = Table(rows, colWidths=[1.5 * inch, 4.0 * inch])
                cmds = _table_base_style() + _alt_rows(len(valid))
                t.setStyle(TableStyle(cmds))
                elems.append(t)
                elems.append(Spacer(1, 10))

        # Nota de integridad final
        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        elems.append(Paragraph(
            f"Documento generado el {now}. "
            "Verifique la integridad con el archivo SHA-256 adjunto.",
            self._s["note"],
        ))

        return elems

    # ── Header / Footer ──────────────────────────────────────────────────────

    @staticmethod
    def _draw_header_footer(
        canvas, doc, logo_path: Path | None = None, primary_color: str = PDF_BRAND_COLOR_HEX
    ) -> None:
        """Dibuja header con logo opcional y footer con número de página."""
        canvas.saveState()

        # Header: línea superior sutil
        canvas.setStrokeColor(colors.HexColor(primary_color))
        canvas.setLineWidth(1.5)
        y_top = doc.height + doc.topMargin - 10
        canvas.line(doc.leftMargin, y_top, _PAGE_W - doc.rightMargin, y_top)

        # Logo pequeño en header (excepto página 1 que ya tiene uno grande)
        if logo_path and logo_path.exists() and doc.page > 1:
            try:
                canvas.drawImage(
                    str(logo_path),
                    doc.leftMargin, y_top + 2,
                    width=60, height=22,
                    preserveAspectRatio=True, mask="auto",
                )
            except Exception:
                pass

        # Footer
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.gray)
        canvas.drawCentredString(
            _PAGE_W / 2, doc.bottomMargin - 20,
            f"Pagina {doc.page}",
        )
        canvas.setStrokeColor(colors.HexColor("#dee2e6"))
        canvas.setLineWidth(0.5)
        canvas.line(
            doc.leftMargin, doc.bottomMargin - 8,
            _PAGE_W - doc.rightMargin, doc.bottomMargin - 8,
        )

        canvas.restoreState()

    def _render_block(self, block: dict, df_calls: pd.DataFrame, df_data: pd.DataFrame, base_dir: Path, config: ReportConfig) -> list:
        elems = []
        btype = block.get('type')
        title = block.get('title')

        if title:
            elems.append(Paragraph(escape(title), self._s["h2"]))

        if btype == 'TEXT':
            content = block.get('content', '')
            for line in content.split('\n'):
                if line.strip():
                    elems.append(Paragraph(escape(line), self._s["body"]))
            elems.append(Spacer(1, 12))

        elif btype == 'MAP':
            # To render an actual map we would use Plotly Kaleido again based on filters
            # For this MVP phase, we will display an informative text that the dynamic map is queued,
            # Or render the existing maps if conditions are met. True dynamic kaleido is complex for the PDF engine inline.
            # We'll render a placeholder or existing map based on type.
            elems.append(Paragraph("<i>[Generación dinámica de mapa solicitada. Incluyendo mapa de ubicaciones general por defecto.]</i>", self._s["note"]))
            loc_map = base_dir / PDF_MAP_DIR_NAME / "mapa_ubicaciones.png"
            if loc_map.exists():
                try:
                    img = Image(str(loc_map), width=6.5 * inch, height=4.3 * inch)
                    img.hAlign = "CENTER"
                    elems.append(img)
                    elems.append(Spacer(1, 8))
                except Exception:
                    pass
            elems.append(PageBreak())

        elif btype == 'TABLE':
            t_type = block.get('table_type')
            filters = block.get('filters', {})
            if t_type == 'FREQUENCIES':
                # Similar to existing summary frequencies
                top_n = min(100, int(filters.get('top_n', 10)))
                # Render incoming
                if not df_calls.empty and COL_CALL_TYPE in df_calls.columns:
                    df_in = df_calls[df_calls[COL_CALL_TYPE].str.lower() == CALL_TYPE_INCOMING.lower()]
                    df_out = df_calls[df_calls[COL_CALL_TYPE].str.lower() == CALL_TYPE_OUTGOING.lower()]

                    elems.append(Paragraph(f"Top {top_n} Frecuencias Entrantes", self._s["h3"]))
                    if not df_in.empty and COL_ORIGINATOR in df_in.columns:
                        top_in = df_in[COL_ORIGINATOR].value_counts().head(top_n)
                        rows = [[Paragraph("<b>Número (Alias)</b>", self._s["cell_header"]), Paragraph("<b>Frecuencia</b>", self._s["cell_header"])]]
                        for num, count in top_in.items():
                            disp = config.display_name(num)
                            rows.append([Paragraph(escape(disp), self._s["cell"]), Paragraph(str(count), self._s["cell"])])
                        if len(rows) > 1:
                            t = Table(rows, colWidths=[4 * inch, 1.5 * inch])
                            t.setStyle(TableStyle(_table_base_style() + _alt_rows(len(rows)-1)))
                            elems.append(t)
                            elems.append(Spacer(1, 12))

                    elems.append(Paragraph(f"Top {top_n} Frecuencias Salientes", self._s["h3"]))
                    if not df_out.empty and COL_RECEIVER in df_out.columns:
                        top_out = df_out[COL_RECEIVER].value_counts().head(top_n)
                        rows = [[Paragraph("<b>Número (Alias)</b>", self._s["cell_header"]), Paragraph("<b>Frecuencia</b>", self._s["cell_header"])]]
                        for num, count in top_out.items():
                            disp = config.display_name(num)
                            rows.append([Paragraph(escape(disp), self._s["cell"]), Paragraph(str(count), self._s["cell"])])
                        if len(rows) > 1:
                            t = Table(rows, colWidths=[4 * inch, 1.5 * inch])
                            t.setStyle(TableStyle(_table_base_style() + _alt_rows(len(rows)-1)))
                            elems.append(t)
                            elems.append(Spacer(1, 12))

            elif t_type == 'RAW_LOGS':
                # Render filtered table
                spec_num = str(filters.get('specific_number', '')).strip()
                df_filtered = df_calls.copy()
                if spec_num and not df_filtered.empty:
                    mask = (df_filtered[COL_ORIGINATOR].astype(str).str.contains(spec_num, na=False)) | \
                           (df_filtered[COL_RECEIVER].astype(str).str.contains(spec_num, na=False))
                    df_filtered = df_filtered[mask]

                if df_filtered.empty:
                    elems.append(Paragraph("No hay registros para este filtro.", self._s["note"]))
                else:
                    elems.append(Paragraph(f"Registros Detallados (Total: {len(df_filtered)})", self._s["h3"]))
                    header = [
                        Paragraph("<b>Fecha/Hora</b>", self._s["cell_header"]),
                        Paragraph("<b>Tipo</b>", self._s["cell_header"]),
                        Paragraph("<b>Originador</b>", self._s["cell_header"]),
                        Paragraph("<b>Receptor</b>", self._s["cell_header"]),
                        Paragraph("<b>Dur.(s)</b>", self._s["cell_header"]),
                    ]
                    rows = [header]

                    df_sorted = df_filtered.sort_values(COL_DATETIME) if COL_DATETIME in df_filtered.columns else df_filtered

                    for row in df_sorted.head(500).itertuples(index=False): # Limit 500 per block max
                        dt = getattr(row, COL_DATETIME, None)
                        dt_str = dt.strftime("%Y-%m-%d %H:%M") if pd.notna(dt) else str(dt)
                        call_type = getattr(row, COL_CALL_TYPE, "")
                        orig = config.display_name(getattr(row, COL_ORIGINATOR, ""))
                        rec = config.display_name(getattr(row, COL_RECEIVER, ""))
                        dur = getattr(row, "duracion", 0)

                        rows.append([
                            Paragraph(escape(dt_str), self._s["cell"]),
                            Paragraph(escape(str(call_type)), self._s["cell"]),
                            Paragraph(escape(str(orig)), self._s["cell"]),
                            Paragraph(escape(str(rec)), self._s["cell"]),
                            Paragraph(str(dur), self._s["cell"])
                        ])

                    t = Table(rows, colWidths=[1.3 * inch, 0.9 * inch, 1.5 * inch, 1.5 * inch, 0.5 * inch])
                    t.setStyle(TableStyle(_table_base_style() + _alt_rows(len(rows)-1)))
                    elems.append(t)
                    if len(df_filtered) > 500:
                        elems.append(Paragraph("<i>(Se muestran solo los primeros 500 registros)</i>", self._s["note"]))
                    elems.append(PageBreak())

        return elems
