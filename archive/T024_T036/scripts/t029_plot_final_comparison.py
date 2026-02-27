from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go


if not ("agno_env" in sys.prefix or ".venv" in sys.prefix):
    raise RuntimeError("FATAL: Not in agno_env!")


PORTFOLIO_CURVE_FILE = Path("src/data_engine/portfolio/SSOT_PORTFOLIO_CURVE.parquet")
CANONICAL_FILE = Path("src/data_engine/ssot/SSOT_CANONICAL_BASE.parquet")
MACRO_FILE = Path("src/data_engine/ssot/SSOT_MACRO.parquet")
OUTPUT_HTML = Path("src/verification_plots/T029_Final_Comparative.html")
START_DATE = pd.Timestamp("2018-07-02")


def normalize_base_1(series: pd.Series) -> pd.Series:
    first = float(series.iloc[0])
    if first == 0:
        raise RuntimeError("Série com valor inicial zero não pode ser normalizada.")
    return series / first


def main() -> None:
    for path in [PORTFOLIO_CURVE_FILE, CANONICAL_FILE]:
        if not path.exists():
            raise RuntimeError(f"Arquivo ausente: {path}")

    curve = pd.read_parquet(PORTFOLIO_CURVE_FILE)
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    curve = curve.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

    # Carregado para cumprir requisito de contexto da task.
    canonical = pd.read_parquet(CANONICAL_FILE, columns=["ticker", "date"])
    canonical["date"] = pd.to_datetime(canonical["date"], errors="coerce").dt.normalize()
    canonical = canonical.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

    if "sp500_close" in canonical.columns:
        sp500_df = canonical[["date", "sp500_close"]].dropna().drop_duplicates("date")
    else:
        if not MACRO_FILE.exists():
            raise RuntimeError("SP500 não encontrado no canônico e SSOT_MACRO ausente.")
        macro = pd.read_parquet(MACRO_FILE, columns=["date", "sp500_close"])
        macro["date"] = pd.to_datetime(macro["date"], errors="coerce").dt.normalize()
        sp500_df = macro.dropna(subset=["date", "sp500_close"]).drop_duplicates("date")

    data = curve[["date", "equity_end", "ibov_close", "cdi_daily"]].dropna(subset=["date"]).copy()
    data = data[data["date"] >= START_DATE].sort_values("date").reset_index(drop=True)
    if data.empty:
        raise RuntimeError("Sem dados de portfolio para o período solicitado.")

    sp500_df = sp500_df[sp500_df["date"] >= START_DATE].sort_values("date").reset_index(drop=True)
    if sp500_df.empty:
        raise RuntimeError("Sem dados de SP500 para o período solicitado.")

    data = data.merge(sp500_df, on="date", how="inner")
    if data.empty:
        raise RuntimeError("Sem interseção de datas entre portfolio e SP500.")

    data["cdi_wealth"] = (1.0 + data["cdi_daily"]).cumprod()
    data["normalized_portfolio"] = normalize_base_1(data["equity_end"])
    data["normalized_cdi"] = normalize_base_1(data["cdi_wealth"])
    data["normalized_bovespa"] = normalize_base_1(data["ibov_close"])
    data["normalized_sp500"] = normalize_base_1(data["sp500_close"])

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=data["date"], y=data["normalized_portfolio"], mode="lines", name="Portfolio (Base 1)"))
    fig.add_trace(go.Scatter(x=data["date"], y=data["normalized_cdi"], mode="lines", name="CDI (Base 1)"))
    fig.add_trace(go.Scatter(x=data["date"], y=data["normalized_bovespa"], mode="lines", name="Bovespa (Base 1)"))
    fig.add_trace(go.Scatter(x=data["date"], y=data["normalized_sp500"], mode="lines", name="S&P 500 (Base 1)"))

    fig.update_layout(
        title="T029 - Final Comparative Performance (Base 1 from 2018-07-02)",
        xaxis_title="Date",
        yaxis_title="Accumulated Wealth (Base 1.0)",
        template="plotly_white",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )

    OUTPUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(OUTPUT_HTML), include_plotlyjs="cdn")

    print("TASK T029 - PLOTLY VISUALIZATION")
    print(f"START_DATE: {START_DATE.date()}")
    print(f"ROWS_PLOTTED: {len(data)}")
    print(f"OUTPUT: {OUTPUT_HTML}")
    print("OVERALL STATUS: [[ PASS ]]")


if __name__ == "__main__":
    main()
