"""
Builder de gráficas estáticas.

Genera imágenes PNG usando Matplotlib/Seaborn.
Implementa IReportBuilder.
"""
from __future__ import annotations

import logging
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from config.constants import (
    CHART_DPI,
    COL_CELL_NAME,
    COL_DATETIME,
    TOP_N_CHART,
)

matplotlib.use("Agg")  # Backend sin interfaz gráfica para generar PNG en hilos
logger = logging.getLogger(__name__)

plt.style.use("default")


def _alias_label(number: str, aliases: dict[str, str] | None) -> str:
    alias = (aliases or {}).get(number)
    return f"{number}\n({alias})" if alias else number


class TopCallsChartBuilder:
    """Genera gráfico de barras con los N números que más aparecen."""

    def build(
        self,
        df: pd.DataFrame,
        output_path: Path,
        column: str = "originador",
        title: str = "Top Llamadas",
        aliases: dict[str, str] | None = None,
        ascending: bool = False,
    ) -> None:
        if df is None or df.empty or column not in df.columns:
            return

        try:
            counts = df[column].astype(str).value_counts()
            counts = counts.sort_values(ascending=ascending).head(TOP_N_CHART)
        except Exception as exc:
            logger.error("Error calculando frecuencias '%s': %s", title, exc)
            return

        if counts.empty:
            return

        labels = [_alias_label(n, aliases) for n in counts.index]

        fig, ax = plt.subplots(figsize=(12, 7))
        try:
            sns.barplot(x=labels, y=counts.values, palette="tab10", ax=ax)
        except Exception:
            plt.close(fig)
            return

        ax.set_title(title, fontsize=14, fontweight="bold")
        ax.tick_params(axis="x", labelsize=9)
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(str(output_path), dpi=CHART_DPI, bbox_inches="tight")
        plt.close(fig)
        logger.debug("Gráfico guardado: %s", output_path)


class HourlyChartBuilder:
    """Genera gráfico de línea con actividad por hora del día (0-23)."""

    def build(self, df: pd.DataFrame, output_path: Path, **_: object) -> None:
        if df is None or df.empty or COL_DATETIME not in df.columns:
            return

        try:
            data = df.copy()
            if not pd.api.types.is_datetime64_any_dtype(data[COL_DATETIME]):
                data[COL_DATETIME] = pd.to_datetime(data[COL_DATETIME], errors="coerce")
            data.dropna(subset=[COL_DATETIME], inplace=True)
            if data.empty:
                return

            counts = (
                data[COL_DATETIME].dt.hour
                .value_counts()
                .sort_index()
                .reindex(range(24), fill_value=0)
            )
        except Exception as exc:
            logger.error("Error generando gráfico horario: %s", exc)
            return

        fig, ax = plt.subplots(figsize=(12, 6))
        sns.lineplot(x=counts.index, y=counts.values, marker="o", color="dodgerblue", ax=ax)
        ax.set_title("Frecuencia por Hora del Día", fontsize=14)
        ax.set_xticks(range(24))
        ax.grid(True, linestyle="--", alpha=0.6)
        plt.tight_layout()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(str(output_path), dpi=CHART_DPI)
        plt.close(fig)


class TopLocationChartBuilder:
    """
    Genera gráfico de barras: Top N números con su ubicación más frecuente.
    Útil para 'Desde dónde llaman' o 'Desde dónde se llamó'.
    """

    def build(
        self,
        df: pd.DataFrame,
        output_path: Path,
        number_col: str = "originador",
        title: str = "Top Ubicaciones",
        aliases: dict[str, str] | None = None,
    ) -> None:
        if df is None or df.empty or number_col not in df.columns:
            return

        try:
            counts = df[number_col].astype(str).value_counts().head(TOP_N_CHART)
            if counts.empty:
                return

            labels, values = [], []
            for number in counts.index:
                values.append(counts[number])
                location = self._extract_location(df, number, number_col)
                alias = (aliases or {}).get(number, "")
                label = f"{number}"
                if alias:
                    label += f"\n({alias})"
                label += f"\n📍 {location}"
                labels.append(label)

        except Exception as exc:
            logger.error("Error gráfico top ubicación: %s", exc)
            return

        fig, ax = plt.subplots(figsize=(12, 8))
        sns.barplot(x=labels, y=values, palette="viridis", ax=ax)
        ax.set_title(title, fontsize=14, fontweight="bold")
        ax.set_ylabel("Cantidad de Llamadas")
        ax.tick_params(axis="x", labelsize=8.5)
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(str(output_path), dpi=CHART_DPI, bbox_inches="tight")
        plt.close(fig)

    @staticmethod
    def _extract_location(df: pd.DataFrame, number: str, number_col: str) -> str:
        """Extrae la ubicación más frecuente para un número dado."""
        if COL_CELL_NAME not in df.columns:
            return "Desconocida"

        subset = df[df[number_col].astype(str) == number]
        modes = subset[COL_CELL_NAME].dropna().mode()
        if modes.empty:
            return "Desconocida"

        raw = str(modes.iloc[0]).upper()
        # "ANT.BARBOSA-2_R1" → "BARBOSA"
        if "." in raw:
            raw = raw.split(".")[1]
        raw = raw.split("-")[0].split("_")[0]
        return raw.strip() or "Desconocida"
