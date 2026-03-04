#!/home/wilson/AGNO_WORKSPACE/.venv/bin/python
"""CTO exploratory dashboard: ALL 6 variants comparative.

Traces:
  1. Phase8 Winner+ML (N=15, thr=0.05)
  2. C060 Original (BR, N=10, thr=0.25)
  3. CDI
  4. Ibov
  5. C060 Expanded (BR+BDR, N=10, thr=0.25)
  6. N15 Expanded thr=0.25 (BR+BDR, N=15, thr=0.25)  [NEW]
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

if not ("agno_env" in sys.prefix or ".venv" in sys.prefix):
    raise RuntimeError("FATAL: Not in agno_env/.venv")

ROOT = Path("/home/wilson/AGNO_WORKSPACE")
BASE_CAPITAL = 100000.0

IN_T108_CURVE_ML = ROOT / "src/data_engine/portfolio/T108_PORTFOLIO_CURVE_DUAL_MODE_EXPANDED_ML_TRIGGER_WINNER.parquet"
IN_T108_CURVE_BASE = ROOT / "src/data_engine/portfolio/T108_PORTFOLIO_CURVE_DUAL_MODE_EXPANDED_WINNER.parquet"
IN_C060_CURVE = ROOT / "outputs/governanca/T079-PHASE6-PLOTLY-COMPARATIVE-V1_evidence/c060_curve_snapshot.parquet"
IN_C060_EXPANDED = ROOT / "src/data_engine/portfolio/CTO_C060_EXPANDED_UNIVERSE_CURVE.parquet"
IN_N15_C060_THR = ROOT / "src/data_engine/portfolio/CTO_WINNER_C060_THRESHOLD_CURVE.parquet"

OUT_HTML = ROOT / "outputs/plots/CTO_T109_PHASE8E_WITH_ALL_VARIANTS.html"

ACID_START = pd.Timestamp("2024-11-01")
ACID_END = pd.Timestamp("2025-11-30")
HOLDOUT_START = pd.Timestamp("2023-01-02")

COLOR_PHASE8 = "#1f77b4"
COLOR_C060 = "#2ca02c"
COLOR_C060_EXP = "#9b59b6"
COLOR_N15_C060 = "#DAA520"
COLOR_CDI = "#7f7f7f"
COLOR_IBOV = "#ff7f0e"


def drawdown(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce").astype(float)
    return s / s.cummax() - 1.0


def metrics(equity: pd.Series) -> dict[str, float]:
    s = pd.to_numeric(equity, errors="coerce").astype(float)
    r = s.pct_change().fillna(0.0)
    years = max((len(s) - 1) / 252.0, 1.0 / 252.0)
    cagr = float((s.iloc[-1] / s.iloc[0]) ** (1.0 / years) - 1.0)
    mdd = float(drawdown(s).min())
    vol = float(r.std(ddof=0))
    sharpe = float((r.mean() / vol) * np.sqrt(252.0)) if vol > 0 else np.nan
    return {"equity_final": float(s.iloc[-1]), "cagr": cagr, "mdd": mdd, "sharpe": sharpe}


def compute_time_in_cash(sub: pd.DataFrame) -> float:
    if "state_cash" not in sub.columns:
        return 0.0
    total = float(len(sub))
    if total == 0:
        return 0.0
    return float(sub["state_cash"].sum()) / total


def print_table(title: str, curves: dict[str, pd.DataFrame], filter_fn) -> None:
    print(f"\n{'=' * 110}")
    print(title)
    print("=" * 110)
    header = f"{'Curve':<40} {'Equity':>12} {'CAGR':>8} {'MDD':>8} {'Sharpe':>8} {'Switches':>9} {'Cash%':>7}"
    print(header)
    print("-" * len(header))
    for label, df in curves.items():
        sub = filter_fn(df)
        if len(sub) < 2:
            print(f"{label:<40} {'N/A':>12}")
            continue
        m = metrics(sub["equity_end_norm"])
        sw = float((sub["state_cash"].diff().abs() == 1).sum()) if "state_cash" in sub.columns else 0.0
        cash_pct = compute_time_in_cash(sub)
        print(f"{label:<40} {m['equity_final']:>12,.2f} {m['cagr']*100:>7.2f}% {m['mdd']*100:>7.2f}% {m['sharpe']:>8.3f} {sw:>9.0f} {cash_pct*100:>6.1f}%")


def main() -> int:
    print("=" * 110)
    print("CTO DASHBOARD: ALL 6 VARIANTS COMPARATIVE")
    print("=" * 110)

    w = pd.read_parquet(IN_T108_CURVE_ML).copy()
    b = pd.read_parquet(IN_T108_CURVE_BASE).copy()
    c = pd.read_parquet(IN_C060_CURVE).copy()
    e = pd.read_parquet(IN_C060_EXPANDED).copy()
    n = pd.read_parquet(IN_N15_C060_THR).copy()
    for df in [w, b, c, e, n]:
        df["date"] = pd.to_datetime(df["date"])
        df["split"] = df["split"].astype(str)

    cdi = pd.DataFrame({"date": b["date"], "split": b["split"]})
    cdi["equity_end_norm"] = BASE_CAPITAL * (1.0 + pd.to_numeric(b["cdi_daily"], errors="coerce").fillna(0.0)).cumprod()
    cdi.loc[cdi.index[0], "equity_end_norm"] = BASE_CAPITAL
    cdi["drawdown"] = drawdown(cdi["equity_end_norm"])
    cdi["state_cash"] = 0
    cdi["switches_cumsum"] = 0

    ibov = pd.DataFrame({"date": b["date"], "split": b["split"]})
    ibov["equity_end_norm"] = pd.to_numeric(b["benchmark_ibov"], errors="coerce").astype(float)
    ibov["drawdown"] = drawdown(ibov["equity_end_norm"])
    ibov["state_cash"] = 0
    ibov["switches_cumsum"] = 0

    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        subplot_titles=(
            "Equity (base R$100k)",
            "Drawdown",
            "Switches Cumulativos",
            "State Cash (0=Mercado, 1=Caixa)",
        ),
    )

    traces_equity = [
        (w, "Phase8 Winner+ML (N=15, thr=0.05)", COLOR_PHASE8, 2, None),
        (c, "C060 Original (BR, N=10, thr=0.25)", COLOR_C060, 2, None),
        (e, "C060 Expanded (BR+BDR, N=10, thr=0.25)", COLOR_C060_EXP, 2, None),
        (n, "N15 Expanded (BR+BDR, N=15, thr=0.25)", COLOR_N15_C060, 2.5, None),
        (cdi, "CDI", COLOR_CDI, 1.5, "dot"),
        (ibov, "Ibov", COLOR_IBOV, 1.5, "dash"),
    ]

    for df, name, color, width, dash in traces_equity:
        line_kwargs = dict(color=color, width=width)
        if dash:
            line_kwargs["dash"] = dash
        fig.add_trace(go.Scatter(x=df["date"], y=df["equity_end_norm"], name=name, line=line_kwargs), row=1, col=1)

    for df, name, color, width, dash in traces_equity:
        line_kwargs = dict(color=color, width=max(width - 0.5, 1))
        if dash:
            line_kwargs["dash"] = dash
        fig.add_trace(go.Scatter(x=df["date"], y=drawdown(df["equity_end_norm"]), name=f"DD {name}", line=line_kwargs, showlegend=False), row=2, col=1)

    strategy_traces = [
        (w, "Switches Phase8", COLOR_PHASE8, 1.5),
        (c, "Switches C060", COLOR_C060, 1.5),
        (e, "Switches C060 Exp", COLOR_C060_EXP, 1.5),
        (n, "Switches N15 C060", COLOR_N15_C060, 2),
    ]
    for df, name, color, width in strategy_traces:
        fig.add_trace(go.Scatter(x=df["date"], y=df["switches_cumsum"], name=name, line=dict(color=color, width=width), showlegend=False), row=3, col=1)

    for df, name, color, width in strategy_traces:
        fig.add_trace(go.Scatter(x=df["date"], y=df["state_cash"], name=f"State {name}", line=dict(color=color, width=width), showlegend=False), row=4, col=1)

    for r in [1, 2, 3, 4]:
        fig.add_vrect(x0=ACID_START, x1=ACID_END, fillcolor="orange", opacity=0.12, line_width=0, row=r, col=1)

    fig.update_layout(
        height=1600,
        title="CTO Analysis — All 6 Variants: Phase8 vs C060 vs C060-Expanded vs N15-Expanded vs CDI vs Ibov",
        template="plotly_white",
        legend={"orientation": "h", "y": 1.02, "x": 0.0},
    )
    fig.update_yaxes(title_text="R$", row=1, col=1)
    fig.update_yaxes(title_text="Drawdown", tickformat=".1%", row=2, col=1)
    fig.update_yaxes(title_text="# Switches", row=3, col=1)
    fig.update_yaxes(title_text="State", row=4, col=1)

    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(OUT_HTML), include_plotlyjs="cdn")
    print(f"\nDashboard saved: {OUT_HTML}")

    curves = {
        "Phase8 Winner+ML (N=15, thr=0.05)": w,
        "C060 Original (BR, N=10, thr=0.25)": c,
        "C060 Expanded (BR+BDR, N=10, thr=0.25)": e,
        "N15 Expanded (BR+BDR, N=15, thr=0.25)": n,
        "CDI": cdi,
        "Ibov": ibov,
    }

    print_table(
        "METRICS — HOLDOUT (2023-01-02 → 2026-02-26)",
        curves,
        lambda df: df[df["split"] == "HOLDOUT"].copy(),
    )

    print_table(
        "METRICS — ACID WINDOW (2024-11-01 → 2025-11-30)",
        curves,
        lambda df: df[(df["split"] == "HOLDOUT") & (df["date"] >= ACID_START) & (df["date"] <= ACID_END)].copy(),
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
