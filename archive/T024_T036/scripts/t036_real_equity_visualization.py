from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import yfinance as yf


if not ("agno_env" in sys.prefix or ".venv" in sys.prefix):
    raise RuntimeError("FATAL: Not in agno_env!")


START_DATE = pd.Timestamp("2018-07-02")
BASE_CAPITAL = 100_000.0
BVSP_TICKER = "^BVSP"
SP500_TICKER = "^GSPC"

CURVE_FILE = Path("src/data_engine/portfolio/SSOT_PORTFOLIO_CURVE_CLONE.parquet")
CANONICAL_FILE = Path("src/data_engine/ssot/SSOT_CANONICAL_BASE.parquet")
OUTPUT_HTML = Path("src/verification_plots/T036_Real_Equity_Comparison.html")


def download_index_close(ticker: str, start: str) -> pd.DataFrame:
    end_fetch = (date.today() + timedelta(days=1)).isoformat()
    raw = yf.download(ticker, start=start, end=end_fetch, auto_adjust=True, progress=False)
    if raw.empty:
        raise RuntimeError(f"Falha ao baixar {ticker} via yfinance.")
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [
            "_".join([str(x) for x in tup if str(x) not in {"", "None"}]).strip("_")
            for tup in raw.columns.to_flat_index()
        ]
    raw = raw.reset_index()
    date_col = "Date" if "Date" in raw.columns else "date"
    close_candidates = [c for c in raw.columns if str(c).startswith("Close")]
    if not close_candidates:
        raise RuntimeError(f"Coluna de fechamento não encontrada para {ticker}.")
    close_col = close_candidates[0]
    out = raw[[date_col, close_col]].copy()
    out.columns = ["date", "close"]
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.normalize()
    out = out.dropna(subset=["date", "close"]).sort_values("date")
    return out


def main() -> None:
    for path in [CURVE_FILE, CANONICAL_FILE]:
        if not path.exists():
            raise RuntimeError(f"Arquivo ausente: {path}")

    canonical = pd.read_parquet(CANONICAL_FILE)
    print("CANONICAL_COLUMNS:", list(canonical.columns))

    curve = pd.read_parquet(CURVE_FILE)
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    curve = curve.dropna(subset=["date", "equity_end"]).sort_values("date")
    curve = curve[curve["date"] >= START_DATE].copy()
    if curve.empty:
        raise RuntimeError("Sem dados da curva clone a partir da data inicial.")

    source_cdi = "NONE"
    source_ibov = "NONE"
    source_sp500 = "Yahoo"

    # CDI aliases no canônico
    cdi_aliases = ["cdi_daily", "CDI", "cdi", "taxa_cdi", "cdi_ret_t", "cdi_diario"]
    cdi_col = next((c for c in cdi_aliases if c in canonical.columns), None)
    if cdi_col is not None and {"date", cdi_col}.issubset(canonical.columns):
        cdi_df = canonical[["date", cdi_col]].copy()
        cdi_df["date"] = pd.to_datetime(cdi_df["date"], errors="coerce").dt.normalize()
        cdi_df = cdi_df.dropna(subset=["date", cdi_col]).sort_values("date")
        cdi_df = cdi_df.rename(columns={cdi_col: "cdi_daily"})
        source_cdi = f"Canonical:{cdi_col}"
    elif "cdi_daily" in curve.columns:
        cdi_df = curve[["date", "cdi_daily"]].dropna().sort_values("date").copy()
        source_cdi = "Curve:cdi_daily"
    else:
        raise RuntimeError("CDI não encontrado nem no canônico nem na curva clone.")

    # Ibovespa aliases no canônico
    # Caso não exista, fallback para Yahoo ^BVSP.
    ibov_aliases = ["ibov_close", "close_ibov", "ibov", "^BVSP_close", "close_bvsp"]
    ibov_df: pd.DataFrame
    ibov_col = next((c for c in ibov_aliases if c in canonical.columns), None)
    if ibov_col is not None and {"date", ibov_col}.issubset(canonical.columns):
        ibov_df = canonical[["date", ibov_col]].copy()
        ibov_df["date"] = pd.to_datetime(ibov_df["date"], errors="coerce").dt.normalize()
        ibov_df = ibov_df.dropna(subset=["date", ibov_col]).sort_values("date")
        ibov_df = ibov_df.rename(columns={ibov_col: "ibov_close"})
        source_ibov = f"Canonical:{ibov_col}"
    elif {"ticker", "date", "close_operational"}.issubset(canonical.columns):
        tmp = canonical[canonical["ticker"].astype(str).str.upper().eq("^BVSP")].copy()
        if not tmp.empty:
            tmp["date"] = pd.to_datetime(tmp["date"], errors="coerce").dt.normalize()
            ibov_df = tmp[["date", "close_operational"]].dropna().sort_values("date")
            ibov_df = ibov_df.rename(columns={"close_operational": "ibov_close"})
            source_ibov = "Canonical:ticker_^BVSP"
        else:
            ibov_y = download_index_close(BVSP_TICKER, "2018-01-01")
            ibov_df = ibov_y.rename(columns={"close": "ibov_close"})
            source_ibov = "Yahoo:^BVSP"
    else:
        ibov_y = download_index_close(BVSP_TICKER, "2018-01-01")
        ibov_df = ibov_y.rename(columns={"close": "ibov_close"})
        source_ibov = "Yahoo:^BVSP"

    sp500_df = download_index_close(SP500_TICKER, "2018-01-01").rename(columns={"close": "sp500_close"})

    # Base de datas da curva clone
    base = curve[["date", "equity_end"]].copy().sort_values("date")

    # Merge e alinhamento
    merged = base.merge(cdi_df[["date", "cdi_daily"]], on="date", how="left")
    merged = merged.merge(ibov_df[["date", "ibov_close"]], on="date", how="left")
    merged = merged.merge(sp500_df[["date", "sp500_close"]], on="date", how="left")
    merged = merged.sort_values("date").reset_index(drop=True)

    merged["cdi_daily"] = merged["cdi_daily"].ffill().fillna(0.0)
    merged["ibov_close"] = merged["ibov_close"].ffill()
    merged["sp500_close"] = merged["sp500_close"].ffill()
    merged = merged.dropna(subset=["ibov_close", "sp500_close"]).copy()
    merged = merged[merged["date"] >= START_DATE].copy()
    if merged.empty:
        raise RuntimeError("Sem datas úteis após alinhamento dos benchmarks.")

    # Normalização para base 100k
    merged["portfolio_equity"] = BASE_CAPITAL * (merged["equity_end"].astype(float) / float(merged["equity_end"].iloc[0]))
    cdi_growth = (1.0 + merged["cdi_daily"].astype(float)).cumprod()
    merged["cdi_equity"] = BASE_CAPITAL * (cdi_growth / float(cdi_growth.iloc[0]))
    merged["ibov_equity"] = BASE_CAPITAL * (merged["ibov_close"].astype(float) / float(merged["ibov_close"].iloc[0]))
    merged["sp500_equity"] = BASE_CAPITAL * (merged["sp500_close"].astype(float) / float(merged["sp500_close"].iloc[0]))

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=merged["date"],
            y=merged["portfolio_equity"],
            mode="lines",
            name="T035 Clone Portfolio",
            line=dict(color="green", width=3),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=merged["date"],
            y=merged["cdi_equity"],
            mode="lines",
            name="CDI Acumulado",
            line=dict(color="gray", width=2, dash="dash"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=merged["date"],
            y=merged["ibov_equity"],
            mode="lines",
            name="Ibovespa (^BVSP)",
            line=dict(color="#1f77b4", width=2, dash="dot"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=merged["date"],
            y=merged["sp500_equity"],
            mode="lines",
            name="S&P 500 USD (^GSPC)",
            line=dict(color="orange", width=2),
        )
    )

    fig.update_layout(
        title="T036 - Real Equity Comparison (Base 100k)",
        xaxis_title="Data",
        yaxis_title="Patrimônio Total (R$)",
        template="plotly_white",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )

    OUTPUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(OUTPUT_HTML), include_plotlyjs="cdn")

    print("TASK T036 - REAL EQUITY VISUALIZATION ROBUST")
    print(f"ROWS_PLOTTED: {len(merged)}")
    print(f"START_DATE_USED: {merged['date'].iloc[0].date()}")
    print(f"START_PORTFOLIO: {merged['portfolio_equity'].iloc[0]:.2f}")
    print(f"START_CDI: {merged['cdi_equity'].iloc[0]:.2f}")
    print(f"START_IBOV: {merged['ibov_equity'].iloc[0]:.2f}")
    print(f"START_SP500: {merged['sp500_equity'].iloc[0]:.2f}")
    print(f"FINAL_PORTFOLIO: {merged['portfolio_equity'].iloc[-1]:.2f}")
    print(f"FINAL_CDI: {merged['cdi_equity'].iloc[-1]:.2f}")
    print(f"FINAL_IBOV: {merged['ibov_equity'].iloc[-1]:.2f}")
    print(f"FINAL_SP500: {merged['sp500_equity'].iloc[-1]:.2f}")
    print(f"Fonte de Dados Usada: CDI={source_cdi} | IBOV={source_ibov} | SP500={source_sp500}")
    print(f"OUTPUT: {OUTPUT_HTML}")
    print("OVERALL STATUS: [[ PASS ]]")


if __name__ == "__main__":
    main()
