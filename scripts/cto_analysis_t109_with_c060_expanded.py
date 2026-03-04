#!/home/wilson/AGNO_WORKSPACE/.venv/bin/python
"""CTO exploratory dashboard: T109 comparative + C060 Expanded trace.

Adds the C060 Expanded (BR+BDR+US, N=10) curve to the T109 Phase 8
comparative dashboard. All original traces are preserved.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

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

OUT_HTML = ROOT / "outputs/plots/CTO_T109_PHASE8E_WITH_C060_EXPANDED.html"

ACID_START = pd.Timestamp("2024-11-01")
ACID_END = pd.Timestamp("2025-11-30")

COLOR_PHASE8 = "#1f77b4"
COLOR_C060 = "#2ca02c"
COLOR_C060_EXP = "#9b59b6"
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


def split_metrics(curve: pd.DataFrame) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for key, sub in [
        ("train", curve[curve["split"] == "TRAIN"]),
        ("holdout", curve[curve["split"] == "HOLDOUT"]),
        ("acid", curve[(curve["split"] == "HOLDOUT") & (curve["date"] >= ACID_START) & (curve["date"] <= ACID_END)]),
    ]:
        if len(sub) < 2:
            out[key] = {"equity_final": np.nan, "cagr": np.nan, "mdd": np.nan, "sharpe": np.nan, "switches": np.nan}
            continue
        m = metrics(sub["equity_end_norm"])
        m["switches"] = float((sub["state_cash"].diff().abs() == 1).sum()) if "state_cash" in sub.columns else 0.0
        out[key] = m
    return out


def main() -> int:
    print("=" * 70)
    print("CTO DASHBOARD: T109 + C060 Expanded")
    print("=" * 70)

    w = pd.read_parquet(IN_T108_CURVE_ML).copy()
    b = pd.read_parquet(IN_T108_CURVE_BASE).copy()
    c = pd.read_parquet(IN_C060_CURVE).copy()
    e = pd.read_parquet(IN_C060_EXPANDED).copy()
    for df in [w, b, c, e]:
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
        subplot_titles=("Equity (base R$100k)", "Drawdown", "Switches Cumulativos", "State Cash (0=Mercado, 1=Caixa)"),
    )

    fig.add_trace(go.Scatter(x=w["date"], y=w["equity_end_norm"], name="Phase8 Winner+ML (N=15)", line=dict(color=COLOR_PHASE8, width=2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=c["date"], y=c["equity_end_norm"], name="C060 Original (BR, N=10)", line=dict(color=COLOR_C060, width=2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=e["date"], y=e["equity_end_norm"], name="C060 Expanded (BR+BDR, N=10)", line=dict(color=COLOR_C060_EXP, width=2.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=cdi["date"], y=cdi["equity_end_norm"], name="CDI", line=dict(color=COLOR_CDI, width=1.5, dash="dot")), row=1, col=1)
    fig.add_trace(go.Scatter(x=ibov["date"], y=ibov["equity_end_norm"], name="Ibov", line=dict(color=COLOR_IBOV, width=1.5, dash="dash")), row=1, col=1)

    fig.add_trace(go.Scatter(x=w["date"], y=drawdown(w["equity_end_norm"]), name="DD Phase8", line=dict(color=COLOR_PHASE8, width=1.5)), row=2, col=1)
    fig.add_trace(go.Scatter(x=c["date"], y=drawdown(c["equity_end_norm"]), name="DD C060", line=dict(color=COLOR_C060, width=1.5)), row=2, col=1)
    fig.add_trace(go.Scatter(x=e["date"], y=drawdown(e["equity_end_norm"]), name="DD C060 Expanded", line=dict(color=COLOR_C060_EXP, width=2)), row=2, col=1)
    fig.add_trace(go.Scatter(x=cdi["date"], y=drawdown(cdi["equity_end_norm"]), name="DD CDI", line=dict(color=COLOR_CDI, width=1, dash="dot")), row=2, col=1)
    fig.add_trace(go.Scatter(x=ibov["date"], y=drawdown(ibov["equity_end_norm"]), name="DD Ibov", line=dict(color=COLOR_IBOV, width=1, dash="dash")), row=2, col=1)

    fig.add_trace(go.Scatter(x=w["date"], y=w["switches_cumsum"], name="Switches Phase8", line=dict(color=COLOR_PHASE8, width=1.5)), row=3, col=1)
    fig.add_trace(go.Scatter(x=c["date"], y=c["switches_cumsum"], name="Switches C060", line=dict(color=COLOR_C060, width=1.5)), row=3, col=1)
    fig.add_trace(go.Scatter(x=e["date"], y=e["switches_cumsum"], name="Switches C060 Exp", line=dict(color=COLOR_C060_EXP, width=2)), row=3, col=1)

    fig.add_trace(go.Scatter(x=w["date"], y=w["state_cash"], name="State Phase8", line=dict(color=COLOR_PHASE8, width=1.5)), row=4, col=1)
    fig.add_trace(go.Scatter(x=c["date"], y=c["state_cash"], name="State C060", line=dict(color=COLOR_C060, width=1.5)), row=4, col=1)
    fig.add_trace(go.Scatter(x=e["date"], y=e["state_cash"], name="State C060 Exp", line=dict(color=COLOR_C060_EXP, width=2)), row=4, col=1)

    for r in [1, 2, 3, 4]:
        fig.add_vrect(x0=ACID_START, x1=ACID_END, fillcolor="orange", opacity=0.12, line_width=0, row=r, col=1)

    fig.update_layout(
        height=1550,
        title="CTO Analysis - C060 Expanded vs Phase 8 Winner vs C060 Original vs CDI vs Ibov",
        template="plotly_white",
        legend={"orientation": "h", "y": 1.02, "x": 0.0},
    )
    fig.update_yaxes(title_text="R$", row=1, col=1)
    fig.update_yaxes(title_text="Drawdown", tickformat=".1%", row=2, col=1)
    fig.update_yaxes(title_text="# Switches", row=3, col=1)
    fig.update_yaxes(title_text="State", row=4, col=1)

    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(OUT_HTML), include_plotlyjs="cdn")
    print(f"Dashboard saved: {OUT_HTML}")

    print("\n" + "=" * 70)
    print("METRICS COMPARISON (HOLDOUT)")
    print("=" * 70)

    curves = {
        "C060 Original (BR, N=10)": c,
        "C060 Expanded (BR+BDR, N=10)": e,
        "Phase8 Winner+ML (N=15)": w,
        "CDI": cdi,
        "Ibov": ibov,
    }

    header = f"{'Curve':<35} {'Equity':>12} {'CAGR':>8} {'MDD':>8} {'Sharpe':>8} {'Switches':>9}"
    print(header)
    print("-" * len(header))

    for label, df in curves.items():
        holdout = df[df["split"] == "HOLDOUT"].copy()
        if len(holdout) < 2:
            print(f"{label:<35} {'N/A':>12}")
            continue
        m = metrics(holdout["equity_end_norm"])
        sw = float((holdout["state_cash"].diff().abs() == 1).sum()) if "state_cash" in holdout.columns else 0.0
        print(f"{label:<35} {m['equity_final']:>12,.2f} {m['cagr']*100:>7.2f}% {m['mdd']*100:>7.2f}% {m['sharpe']:>8.3f} {sw:>9.0f}")

    print("\n" + "=" * 70)
    print("METRICS COMPARISON (ACID WINDOW)")
    print("=" * 70)

    print(header)
    print("-" * len(header))

    for label, df in curves.items():
        acid = df[(df["split"] == "HOLDOUT") & (df["date"] >= ACID_START) & (df["date"] <= ACID_END)].copy()
        if len(acid) < 2:
            print(f"{label:<35} {'N/A':>12}")
            continue
        m = metrics(acid["equity_end_norm"])
        sw = float((acid["state_cash"].diff().abs() == 1).sum()) if "state_cash" in acid.columns else 0.0
        print(f"{label:<35} {m['equity_final']:>12,.2f} {m['cagr']*100:>7.2f}% {m['mdd']*100:>7.2f}% {m['sharpe']:>8.3f} {sw:>9.0f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
