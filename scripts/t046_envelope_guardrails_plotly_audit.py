#!/usr/bin/env python3
"""T046 - Envelope / Guardrails Plotly Audit (T039 baseline + T037 comparative)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


TASK_ID = "T046-ENVELOPE-PLOTLY-V1"
ROOT = Path("/home/wilson/AGNO_WORKSPACE")

INPUT_T039_CURVE = ROOT / "src/data_engine/portfolio/T039_PORTFOLIO_CURVE.parquet"
INPUT_T039_LEDGER = ROOT / "src/data_engine/portfolio/T039_PORTFOLIO_LEDGER.parquet"
INPUT_T037_CURVE = ROOT / "src/data_engine/portfolio/T037_PORTFOLIO_CURVE.parquet"
INPUT_T037_LEDGER = ROOT / "src/data_engine/portfolio/T037_PORTFOLIO_LEDGER.parquet"
INPUT_TASK_SPEC = (
    ROOT / "02_Knowledge_Bank/planning/task_specs/masterplan_v2/TASK_CEP_BUNDLE_CORE_V2_F2_003_ENVELOPE_PLOTLY_AUDIT.json"
)
INPUT_LEGACY_REPORT = ROOT / "02_Knowledge_Bank/outputs/masterplan_v2/f2_003/report.md"

OUTPUT_HTML = ROOT / "outputs/plots/T046_ENVELOPE_GUARDRAILS_AUDIT.html"
OUTPUT_REPORT = ROOT / "outputs/governanca/T046-ENVELOPE-PLOTLY-V1_report.md"
OUTPUT_MANIFEST = ROOT / "outputs/governanca/T046-ENVELOPE-PLOTLY-V1_manifest.json"
OUTPUT_EVIDENCE_DIR = ROOT / "outputs/governanca/T046-ENVELOPE-PLOTLY-V1_evidence"
OUTPUT_PLOT_INVENTORY = OUTPUT_EVIDENCE_DIR / "plot_inventory.json"
OUTPUT_SUMMARY = OUTPUT_EVIDENCE_DIR / "envelope_audit_summary.json"
SCRIPT_PATH = ROOT / "scripts/t046_envelope_guardrails_plotly_audit.py"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def find_true_intervals(mask: pd.Series, dates: pd.Series) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    intervals: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    start = None
    prev_date = None
    for is_true, dt in zip(mask.tolist(), dates.tolist()):
        if is_true and start is None:
            start = dt
        if not is_true and start is not None:
            intervals.append((start, prev_date if prev_date is not None else dt))
            start = None
        prev_date = dt
    if start is not None and prev_date is not None:
        intervals.append((start, prev_date))
    return intervals


def max_drawdown(equity: pd.Series) -> float:
    eq = pd.to_numeric(equity, errors="coerce").astype(float)
    if eq.empty:
        return float("nan")
    roll = eq.cummax()
    dd = eq / roll - 1.0
    return float(dd.min())


def compute_cagr(equity: pd.Series, annualization_days: int = 252) -> float:
    eq = pd.to_numeric(equity, errors="coerce").astype(float)
    eq = eq.dropna()
    if len(eq) < 2 or eq.iloc[0] <= 0:
        return float("nan")
    years = max((len(eq) - 1) / float(annualization_days), 1e-12)
    return float((eq.iloc[-1] / eq.iloc[0]) ** (1.0 / years) - 1.0)


def compute_sharpe(equity: pd.Series, annualization_days: int = 252) -> float:
    eq = pd.to_numeric(equity, errors="coerce").astype(float)
    if len(eq) < 3:
        return float("nan")
    r = eq.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    if r.empty:
        return float("nan")
    vol = float(r.std(ddof=0))
    if not np.isfinite(vol) or vol <= 0:
        return float("nan")
    return float(np.sqrt(float(annualization_days)) * float(r.mean()) / vol)


def daily_sell_reason_counts(ledger: pd.DataFrame, prefix: str) -> pd.DataFrame:
    df = ledger.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["reason"] = df["reason"].astype(str)
    sells = df[df["side"] == "SELL"].copy()
    if sells.empty:
        return pd.DataFrame(columns=["date"])
    pivot = (
        sells.pivot_table(index="date", columns="reason", values="ticker", aggfunc="size", fill_value=0)
        .sort_index()
        .reset_index()
    )
    pivot = pivot.rename(columns={c: f"{prefix}{c}" for c in pivot.columns if c != "date"})
    return pivot


def main() -> int:
    print(f"HEADER: {TASK_ID}")

    required_inputs = [
        INPUT_T039_CURVE,
        INPUT_T039_LEDGER,
        INPUT_T037_CURVE,
        INPUT_T037_LEDGER,
        INPUT_TASK_SPEC,
        INPUT_LEGACY_REPORT,
    ]
    missing = [str(p) for p in required_inputs if not p.exists()]
    if missing:
        print("STEP GATES:")
        print(f"- G1_PLOT_ARTIFACT_PRESENT: FAIL (missing inputs: {', '.join(missing)})")
        print("OVERALL STATUS: [[ FAIL ]]")
        return 1

    c39 = pd.read_parquet(INPUT_T039_CURVE).copy()
    l39 = pd.read_parquet(INPUT_T039_LEDGER).copy()
    c37 = pd.read_parquet(INPUT_T037_CURVE).copy()
    l37 = pd.read_parquet(INPUT_T037_LEDGER).copy()

    for df in [c39, c37]:
        df["date"] = pd.to_datetime(df["date"])
    for df in [l39, l37]:
        df["date"] = pd.to_datetime(df["date"])

    c39 = c39.sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)
    c37 = c37.sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)
    l39 = l39.sort_values(["date", "side", "ticker"]).reset_index(drop=True)
    l37 = l37.sort_values(["date", "side", "ticker"]).reset_index(drop=True)

    # Align on common dates to make overlays clean.
    dates = sorted(set(c39["date"]).intersection(set(c37["date"])))
    if not dates:
        raise RuntimeError("Sem interseção de datas entre T039 e T037.")
    c39a = c39[c39["date"].isin(dates)].copy().reset_index(drop=True)
    c37a = c37[c37["date"].isin(dates)].copy().reset_index(drop=True)

    # Derived series.
    eq39 = pd.to_numeric(c39a["equity_end"], errors="coerce").astype(float)
    eq37 = pd.to_numeric(c37a["equity_end"], errors="coerce").astype(float)
    dd39 = eq39 / eq39.cummax() - 1.0
    dd37 = eq37 / eq37.cummax() - 1.0

    exp39 = pd.to_numeric(c39a.get("exposure"), errors="coerce").fillna(0.0).astype(float)
    exp37 = pd.to_numeric(c37a.get("exposure"), errors="coerce").fillna(0.0).astype(float)

    regime39 = pd.to_numeric(c39a.get("regime_defensivo"), errors="coerce").fillna(0).astype(bool)
    slope39 = pd.to_numeric(c39a.get("slope_daily"), errors="coerce").astype(float)
    blocked39 = pd.to_numeric(c39a.get("n_blocked_reentry"), errors="coerce").fillna(0.0).astype(float)
    switches_final = int(pd.to_numeric(c39a.get("num_switches_cumsum"), errors="coerce").fillna(0).iloc[-1])

    # SELL reason daily counts.
    sell39 = daily_sell_reason_counts(l39, prefix="T039__")
    sell37 = daily_sell_reason_counts(l37, prefix="T037__")

    # Merge daily counts onto full date range (common dates).
    base = pd.DataFrame({"date": c39a["date"]})
    base = base.merge(sell39, on="date", how="left").merge(sell37, on="date", how="left")
    for col in base.columns:
        if col != "date":
            base[col] = pd.to_numeric(base[col], errors="coerce").fillna(0.0)

    # Evidence summary (must be NaN-free for key fields).
    summary = {
        "task_id": TASK_ID,
        "rows_common_dates": int(len(base)),
        "date_min": str(pd.to_datetime(base["date"].min()).date()),
        "date_max": str(pd.to_datetime(base["date"].max()).date()),
        "t039": {
            "equity_final": float(eq39.iloc[-1]),
            "cagr": float(compute_cagr(eq39)),
            "mdd": float(max_drawdown(eq39)),
            "sharpe": float(compute_sharpe(eq39)),
            "pct_regime_defensivo": float(regime39.mean()),
            "num_switches_final": int(switches_final),
            "n_blocked_reentry_sum": float(blocked39.sum()),
            "sell_reason_counts": l39[l39["side"] == "SELL"]["reason"].astype(str).value_counts().to_dict(),
        },
        "t037": {
            "equity_final": float(eq37.iloc[-1]),
            "cagr": float(compute_cagr(eq37)),
            "mdd": float(max_drawdown(eq37)),
            "sharpe": float(compute_sharpe(eq37)),
            "sell_reason_counts": l37[l37["side"] == "SELL"]["reason"].astype(str).value_counts().to_dict(),
        },
    }
    OUTPUT_EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    # Plot inventory: single html + trace names.
    plot_inventory = {
        "task_id": TASK_ID,
        "main_html": str(OUTPUT_HTML),
        "subplots": [
            {"row": 1, "title": "Equity overlay (T039 vs T037) + benchmarks"},
            {"row": 2, "title": "Drawdown overlay (T039 vs T037)"},
            {"row": 3, "title": "Exposure overlay (T039 vs T037) + regime shading"},
            {"row": 4, "title": "Regime (T039) + slope_daily (T039) + blocked reentry"},
            {"row": 5, "title": "SELL reasons daily counts (T039 and T037)"},
        ],
    }
    OUTPUT_PLOT_INVENTORY.write_text(json.dumps(plot_inventory, indent=2, sort_keys=True), encoding="utf-8")

    # Build Plotly figure.
    fig = make_subplots(
        rows=5,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.035,
        subplot_titles=[sp["title"] for sp in plot_inventory["subplots"]],
        specs=[[{"secondary_y": False}], [{"secondary_y": False}], [{"secondary_y": False}], [{"secondary_y": True}], [{"secondary_y": False}]],
    )

    # Row 1: equity overlay.
    fig.add_trace(go.Scatter(x=c39a["date"], y=eq39, mode="lines", name="T039 equity_end", line=dict(color="#d62728", width=2.2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=c37a["date"], y=eq37, mode="lines", name="T037 equity_end", line=dict(color="#2ca02c", width=2.2)), row=1, col=1)
    if "benchmark_ibov" in c39a.columns:
        fig.add_trace(go.Scatter(x=c39a["date"], y=c39a["benchmark_ibov"], mode="lines", name="Ibov (benchmark)", line=dict(color="#1f77b4", width=1.4, dash="dot")), row=1, col=1)
    if "cdi_credit" in c39a.columns:
        # cumulative CDI credit is not equity, but gives a cash accrual envelope reference.
        fig.add_trace(go.Scatter(x=c39a["date"], y=c39a["cdi_credit"].cumsum(), mode="lines", name="CDI credit (cum, T039)", line=dict(color="#7f7f7f", width=1.2, dash="dash")), row=1, col=1)

    # Row 2: drawdown overlay.
    fig.add_trace(go.Scatter(x=c39a["date"], y=dd39, mode="lines", name="T039 drawdown", line=dict(color="#d62728")), row=2, col=1)
    fig.add_trace(go.Scatter(x=c37a["date"], y=dd37, mode="lines", name="T037 drawdown", line=dict(color="#2ca02c")), row=2, col=1)

    # Row 3: exposure overlay.
    fig.add_trace(go.Scatter(x=c39a["date"], y=exp39, mode="lines", name="T039 exposure", line=dict(color="#d62728")), row=3, col=1)
    fig.add_trace(go.Scatter(x=c37a["date"], y=exp37, mode="lines", name="T037 exposure", line=dict(color="#2ca02c")), row=3, col=1)

    # Shade regime_defensivo on rows 1-4 for T039.
    for x0, x1 in find_true_intervals(regime39, c39a["date"]):
        for r in [1, 2, 3, 4]:
            fig.add_vrect(x0=x0, x1=x1, fillcolor="rgba(255,0,0,0.06)", line_width=0, row=r, col=1)

    # Row 4: regime + slope + blocked.
    fig.add_trace(
        go.Scatter(x=c39a["date"], y=regime39.astype(int), mode="lines", name="T039 regime_defensivo (0/1)", line=dict(color="#9467bd", width=1.4)),
        row=4,
        col=1,
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(x=c39a["date"], y=blocked39, mode="lines", name="T039 n_blocked_reentry", line=dict(color="#000000", width=1.2)),
        row=4,
        col=1,
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(x=c39a["date"], y=slope39, mode="lines", name="T039 slope_daily", line=dict(color="#ff7f0e", width=1.6)),
        row=4,
        col=1,
        secondary_y=True,
    )

    # Row 5: sell reasons daily counts.
    # Plot only columns that exist (dynamic set).
    reason_cols = [c for c in base.columns if c != "date"]
    # Keep top reasons by total to avoid clutter.
    totals = {c: float(base[c].sum()) for c in reason_cols}
    reason_cols_sorted = [c for c, _ in sorted(totals.items(), key=lambda kv: kv[1], reverse=True)]
    top_cols = reason_cols_sorted[:10]
    palette = [
        "#1f77b4",
        "#ff7f0e",
        "#2ca02c",
        "#d62728",
        "#9467bd",
        "#8c564b",
        "#e377c2",
        "#7f7f7f",
        "#bcbd22",
        "#17becf",
    ]
    for i, col in enumerate(top_cols):
        fig.add_trace(
            go.Bar(x=base["date"], y=base[col], name=f"SELL count {col}", marker_color=palette[i % len(palette)], opacity=0.55),
            row=5,
            col=1,
        )

    fig.update_layout(
        title="T046 - Envelope/Guardrails Plotly Audit (T039 baseline + T037 comparative)",
        template="plotly_white",
        hovermode="x unified",
        barmode="stack",
        height=1500,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    fig.update_yaxes(title_text="Equity", row=1, col=1)
    fig.update_yaxes(title_text="Drawdown", row=2, col=1, tickformat=".0%")
    fig.update_yaxes(title_text="Exposure", row=3, col=1, range=[0, 1])
    fig.update_yaxes(title_text="Regime/Blocked", row=4, col=1, secondary_y=False)
    fig.update_yaxes(title_text="Slope", row=4, col=1, secondary_y=True)
    fig.update_yaxes(title_text="SELL count/day", row=5, col=1)

    OUTPUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MANIFEST.parent.mkdir(parents=True, exist_ok=True)

    fig.write_html(OUTPUT_HTML, include_plotlyjs="cdn", full_html=True)

    # Report.
    report_lines = [
        f"# {TASK_ID} Report",
        "",
        "## 1) Inputs",
        "",
        f"- T039 Curve: `{INPUT_T039_CURVE}` ({len(c39)} linhas)",
        f"- T039 Ledger: `{INPUT_T039_LEDGER}` ({len(l39)} linhas)",
        f"- T037 Curve: `{INPUT_T037_CURVE}` ({len(c37)} linhas)",
        f"- T037 Ledger: `{INPUT_T037_LEDGER}` ({len(l37)} linhas)",
        "",
        "## 2) Summary (evidence JSON)",
        "",
        f"- `{OUTPUT_SUMMARY}`",
        "",
        "## 3) Key observations",
        "",
        f"- T039 dias em regime defensivo: {float(regime39.mean())*100.0:.2f}%",
        f"- T039 switches (cumsum final): {switches_final}",
        f"- T039 blocked reentry (sum): {float(blocked39.sum()):.0f}",
        "- Eventos de SELL são exibidos por `reason` (ledger) com barras diárias empilhadas (top-10 por contagem).",
        "",
        "## 4) Artifacts",
        "",
        f"- `{OUTPUT_HTML}`",
        f"- `{OUTPUT_PLOT_INVENTORY}`",
        f"- `{OUTPUT_SUMMARY}`",
        f"- `{OUTPUT_MANIFEST}`",
    ]
    OUTPUT_REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    outputs = [
        OUTPUT_HTML,
        OUTPUT_REPORT,
        OUTPUT_MANIFEST,
        OUTPUT_PLOT_INVENTORY,
        OUTPUT_SUMMARY,
        SCRIPT_PATH,
    ]

    manifest = {
        "task_id": TASK_ID,
        "inputs_consumed": [str(p) for p in required_inputs],
        "outputs_produced": [str(p) for p in outputs],
        "hashes_sha256": {
            **{str(p): sha256_file(p) for p in required_inputs},
            **{str(p): sha256_file(p) for p in outputs if p.exists()},
        },
    }
    OUTPUT_MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    # Gates.
    g1 = OUTPUT_HTML.exists()
    g2 = OUTPUT_PLOT_INVENTORY.exists() and OUTPUT_SUMMARY.exists() and OUTPUT_PLOT_INVENTORY.stat().st_size > 2 and OUTPUT_SUMMARY.stat().st_size > 2
    # Metrics: ensure key fields are finite.
    g3 = (
        np.isfinite(summary["t039"]["equity_final"])
        and np.isfinite(summary["t039"]["mdd"])
        and np.isfinite(summary["t037"]["equity_final"])
        and np.isfinite(summary["t037"]["mdd"])
    )
    gx = OUTPUT_MANIFEST.exists()

    print("STEP GATES:")
    print(f"- G1_PLOT_ARTIFACT_PRESENT: {'PASS' if g1 else 'FAIL'}")
    print(f"- G2_EVIDENCE_PRESENT: {'PASS' if g2 else 'FAIL'}")
    print(f"- G3_METRICS_NON_NAN: {'PASS' if g3 else 'FAIL'}")
    print(f"- Gx_HASH_MANIFEST_PRESENT: {'PASS' if gx else 'FAIL'}")

    print("RETRY LOG:")
    print("- none")

    print("ARTIFACT LINKS:")
    for p in [OUTPUT_HTML, OUTPUT_REPORT, OUTPUT_MANIFEST, OUTPUT_PLOT_INVENTORY, OUTPUT_SUMMARY, SCRIPT_PATH]:
        print(f"- {p}")

    overall = g1 and g2 and g3 and gx
    print(f"OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
