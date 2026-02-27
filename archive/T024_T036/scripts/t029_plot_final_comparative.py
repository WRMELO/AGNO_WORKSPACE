from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import yfinance as yf


if not ("agno_env" in sys.prefix or ".venv" in sys.prefix):
    raise RuntimeError("FATAL: Not in agno_env!")


PORTFOLIO_CURVE_FILE = Path("src/data_engine/portfolio/SSOT_PORTFOLIO_CURVE.parquet")
CANONICAL_FILE = Path("src/data_engine/ssot/SSOT_CANONICAL_BASE.parquet")
OUTPUT_HTML = Path("src/verification_plots/T029_Final_Comparative.html")
START_DATE = pd.Timestamp("2018-07-02")
SP500_TICKER = "^GSPC"


def normalize_base_1(series: pd.Series) -> pd.Series:
    base = float(series.iloc[0])
    if base == 0:
        raise RuntimeError("Valor base zero; não é possível normalizar.")
    return series / base


def add_trace(fig: go.Figure, x: pd.Series, y: pd.Series, name: str, color: str, dash: str, width: float) -> None:
    ret_pct = (y - 1.0) * 100.0
    custom = pd.DataFrame({"ret_pct": ret_pct}).to_numpy()
    fig.add_trace(
        go.Scatter(
            x=x,
            y=y,
            mode="lines",
            name=name,
            line=dict(color=color, dash=dash, width=width),
            customdata=custom,
            hovertemplate=(
                "Data: %{x|%Y-%m-%d}<br>"
                "Base 1: %{y:.4f}<br>"
                "Ret. Acum.: %{customdata[0]:.2f}%<extra></extra>"
            ),
        )
    )


def main() -> None:
    for path in [PORTFOLIO_CURVE_FILE, CANONICAL_FILE]:
        if not path.exists():
            raise RuntimeError(f"Arquivo ausente: {path}")

    curve = pd.read_parquet(PORTFOLIO_CURVE_FILE)
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    curve = curve.dropna(subset=["date"]).sort_values("date")
    curve = curve[curve["date"] >= START_DATE].copy()
    if curve.empty:
        raise RuntimeError("Sem dados de carteira para a data inicial solicitada.")

    # Pre-load solicitado do canônico.
    canonical = pd.read_parquet(CANONICAL_FILE, columns=["ticker", "date"])
    canonical["date"] = pd.to_datetime(canonical["date"], errors="coerce").dt.normalize()
    canonical = canonical.dropna(subset=["date"]).sort_values(["date", "ticker"])

    if "cdi_daily" in curve.columns:
        cdi_base = curve[["date", "cdi_daily"]].dropna().sort_values("date").copy()
        cdi_base["cdi_wealth"] = (1.0 + cdi_base["cdi_daily"].astype(float)).cumprod()
        cdi_series = cdi_base[["date", "cdi_wealth"]]
    else:
        raise RuntimeError("Coluna cdi_daily não encontrada em SSOT_PORTFOLIO_CURVE.parquet.")

    ibov_series = curve[["date", "ibov_close"]].dropna().sort_values("date")
    portfolio_series = curve[["date", "equity_end"]].dropna().sort_values("date")

    end_fetch = (date.today() + timedelta(days=1)).isoformat()
    sp500_raw = yf.download(
        SP500_TICKER,
        start="2018-01-01",
        end=end_fetch,
        auto_adjust=True,
        progress=False,
    )
    if sp500_raw.empty:
        raise RuntimeError("Falha ao baixar dados do S&P 500 via yfinance.")
    if isinstance(sp500_raw.columns, pd.MultiIndex):
        sp500_raw.columns = [
            "_".join([str(x) for x in tup if str(x) not in {"", "None"}]).strip("_")
            for tup in sp500_raw.columns.to_flat_index()
        ]
    sp500_raw = sp500_raw.reset_index()
    date_col = "Date" if "Date" in sp500_raw.columns else "date"
    close_candidates = [c for c in sp500_raw.columns if str(c).startswith("Close")]
    if not close_candidates:
        raise RuntimeError("Coluna de fechamento do ^GSPC não encontrada no download do yfinance.")
    close_col = close_candidates[0]
    sp500_raw["date"] = pd.to_datetime(sp500_raw[date_col], errors="coerce").dt.normalize()
    sp500_series = sp500_raw[["date", close_col]].rename(columns={close_col: "sp500_close"}).dropna().sort_values("date")
    sp500_series = sp500_series[sp500_series["date"] >= START_DATE]

    merged = portfolio_series.merge(cdi_series, on="date", how="inner")
    merged = merged.merge(ibov_series, on="date", how="inner")
    merged = merged.merge(sp500_series, on="date", how="inner")
    merged = merged[merged["date"] >= START_DATE].sort_values("date").reset_index(drop=True)
    if merged.empty:
        raise RuntimeError("Sem interseção de datas entre as quatro séries para plot.")

    merged["normalized_portfolio"] = normalize_base_1(merged["equity_end"])
    merged["normalized_cdi"] = normalize_base_1(merged["cdi_wealth"])
    merged["normalized_ibov"] = normalize_base_1(merged["ibov_close"])
    merged["normalized_sp500"] = normalize_base_1(merged["sp500_close"])

    fig = go.Figure()
    add_trace(fig, merged["date"], merged["normalized_portfolio"], "AGNO Strategy", "green", "solid", 3.0)
    add_trace(fig, merged["date"], merged["normalized_ibov"], "Ibovespa", "#1f77b4", "dot", 2.0)
    add_trace(fig, merged["date"], merged["normalized_cdi"], "CDI", "gray", "dash", 2.0)
    add_trace(fig, merged["date"], merged["normalized_sp500"], "S&P 500 USD (^GSPC)", "orange", "solid", 2.0)

    fig.update_layout(
        title="AGNO Portfolio vs Benchmarks (Base 1.0 = Jul/2018)",
        xaxis_title="Date",
        yaxis_title="Accumulated Wealth (Base 1.0)",
        template="plotly_white",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )

    OUTPUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(OUTPUT_HTML), include_plotlyjs="cdn")

    print("TASK T029 - PORTFOLIO VISUALIZATION CORRECTED")
    print(f"SP500_SOURCE: Yahoo Finance ({SP500_TICKER})")
    print(f"ROWS_PLOTTED: {len(merged)}")
    print(f"OUTPUT: {OUTPUT_HTML}")
    print("OVERALL STATUS: [[ PASS ]]")


if __name__ == "__main__":
    main()
