#!/usr/bin/env python3
"""T045 - Plotly accounting decomposition (P&L/Cost/Cash)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


TASK_ID = "T045-ACCOUNTING-PLOTLY-V1"
ROOT = Path("/home/wilson/AGNO_WORKSPACE")

INPUT_CURVE = ROOT / "src/data_engine/portfolio/T039_PORTFOLIO_CURVE.parquet"
INPUT_LEDGER = ROOT / "src/data_engine/portfolio/T039_PORTFOLIO_LEDGER.parquet"
INPUT_TASK_SPEC = (
    ROOT
    / "02_Knowledge_Bank/planning/task_specs/masterplan_v2/TASK_CEP_BUNDLE_CORE_V2_F1_002_ACCOUNTING_PLOTLY_DECOMPOSITION.json"
)
INPUT_LEGACY_REPORT = ROOT / "02_Knowledge_Bank/outputs/masterplan_v2/f1_002/report.md"

OUTPUT_HTML = ROOT / "outputs/plots/T045_STATE3_ACCOUNTING_DECOMPOSITION.html"
OUTPUT_REPORT = ROOT / "outputs/governanca/T045-ACCOUNTING-PLOTLY-V1_report.md"
OUTPUT_MANIFEST = ROOT / "outputs/governanca/T045-ACCOUNTING-PLOTLY-V1_manifest.json"
OUTPUT_EVIDENCE_DIR = ROOT / "outputs/governanca/T045-ACCOUNTING-PLOTLY-V1_evidence"
OUTPUT_DECOMP_SAMPLE = OUTPUT_EVIDENCE_DIR / "decomposition_sample.csv"
OUTPUT_VALID_SUMMARY = OUTPUT_EVIDENCE_DIR / "validations_summary.json"
OUTPUT_BUY_CADENCE = OUTPUT_EVIDENCE_DIR / "buy_cadence_check.csv"
SCRIPT_PATH = ROOT / "scripts/t045_plotly_accounting_decomposition.py"

ACCOUNTING_ABS_TOL = 1e-8
COST_ABS_TOL = 1e-9


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


def main() -> int:
    print(f"HEADER: {TASK_ID}")

    required_inputs = [INPUT_CURVE, INPUT_LEDGER, INPUT_TASK_SPEC, INPUT_LEGACY_REPORT]
    missing = [str(p) for p in required_inputs if not p.exists()]
    if missing:
        print("STEP GATES:")
        print(f"- G1_PLOT_ARTIFACT_PRESENT: FAIL (missing inputs: {', '.join(missing)})")
        print("OVERALL STATUS: [[ FAIL ]]")
        return 1

    curve = pd.read_parquet(INPUT_CURVE).copy()
    ledger = pd.read_parquet(INPUT_LEDGER).copy()
    curve["date"] = pd.to_datetime(curve["date"])
    ledger["date"] = pd.to_datetime(ledger["date"])
    curve = curve.sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)
    ledger = ledger.sort_values("date").drop_duplicates(keep="first").reset_index(drop=True)

    daily = pd.DataFrame({"date": curve["date"]})
    daily = daily.merge(curve, on="date", how="left", validate="one_to_one")

    trade_daily = (
        ledger.groupby(["date", "side"], as_index=False)
        .agg(
            notional=("notional", "sum"),
            net_notional=("net_notional", "sum"),
            cost_brl=("cost_brl", "sum"),
            n_trades=("ticker", "size"),
        )
        .sort_values(["date", "side"])
    )
    buy_daily = trade_daily[trade_daily["side"] == "BUY"][["date", "notional", "n_trades"]].rename(
        columns={"notional": "buy_notional", "n_trades": "buy_n_trades"}
    )
    sell_daily = trade_daily[trade_daily["side"] == "SELL"][["date", "notional", "n_trades"]].rename(
        columns={"notional": "sell_notional", "n_trades": "sell_n_trades"}
    )
    cost_daily = (
        ledger.groupby("date", as_index=False)
        .agg(daily_cost_brl=("cost_brl", "sum"))
        .sort_values("date")
    )

    daily = daily.merge(buy_daily, on="date", how="left")
    daily = daily.merge(sell_daily, on="date", how="left")
    daily = daily.merge(cost_daily, on="date", how="left")
    for col in ["buy_notional", "sell_notional", "daily_cost_brl", "buy_n_trades", "sell_n_trades"]:
        daily[col] = pd.to_numeric(daily[col], errors="coerce").fillna(0.0)

    daily["accounting_identity_rhs"] = pd.to_numeric(daily["cash_end"], errors="coerce") + pd.to_numeric(
        daily["positions_value_end"], errors="coerce"
    )
    daily["accounting_error_abs"] = (
        pd.to_numeric(daily["equity_end"], errors="coerce") - pd.to_numeric(daily["accounting_identity_rhs"], errors="coerce")
    ).abs()
    daily["accounting_error_rel"] = daily["accounting_error_abs"] / pd.to_numeric(daily["equity_end"], errors="coerce").replace(0, np.nan)
    daily["cum_cost_brl"] = daily["daily_cost_brl"].cumsum()
    daily["cum_cdi_credit"] = pd.to_numeric(daily["cdi_credit"], errors="coerce").fillna(0.0).cumsum()
    daily["turnover_daily_x"] = (
        (pd.to_numeric(daily["buy_notional"], errors="coerce") + pd.to_numeric(daily["sell_notional"], errors="coerce"))
        / pd.to_numeric(daily["equity_end"], errors="coerce").replace(0, np.nan)
    )

    OUTPUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MANIFEST.parent.mkdir(parents=True, exist_ok=True)

    buy_dates = (
        ledger[ledger["side"] == "BUY"][["date"]]
        .drop_duplicates()
        .sort_values("date")
        .reset_index(drop=True)
    )
    buy_dates["days_since_prev_buy"] = buy_dates["date"].diff().dt.days
    buy_dates.to_csv(OUTPUT_BUY_CADENCE, index=False)

    identity_max_abs = float(daily["accounting_error_abs"].max())
    identity_max_rel = float(daily["accounting_error_rel"].fillna(0.0).max())
    cost_total_ledger = float(pd.to_numeric(ledger["cost_brl"], errors="coerce").sum())
    cost_total_curve = float(daily["daily_cost_brl"].sum())
    cost_diff = float(abs(cost_total_ledger - cost_total_curve))
    min_cash_curve = float(pd.to_numeric(curve["cash_end"], errors="coerce").min())
    min_cash_ledger_before = float(pd.to_numeric(ledger["cash_before"], errors="coerce").min())
    min_cash_ledger_after = float(pd.to_numeric(ledger["cash_after"], errors="coerce").min())

    g3_accounting = identity_max_abs <= ACCOUNTING_ABS_TOL
    g4_costs = cost_diff <= COST_ABS_TOL
    cash_non_negative = min_cash_curve >= 0 and min_cash_ledger_before >= 0 and min_cash_ledger_after >= 0

    idx_sample = sorted(
        set(
            [0, len(daily) - 1, int(len(daily) / 2), daily["accounting_error_abs"].idxmax()]
            + list(range(0, len(daily), max(1, len(daily) // 10)))
        )
    )
    sample_cols = [
        "date",
        "equity_end",
        "cash_end",
        "positions_value_end",
        "accounting_identity_rhs",
        "accounting_error_abs",
        "accounting_error_rel",
        "daily_cost_brl",
        "cum_cost_brl",
        "cdi_daily",
        "cdi_credit",
        "cum_cdi_credit",
        "buy_notional",
        "sell_notional",
        "turnover_daily_x",
    ]
    daily.iloc[idx_sample][sample_cols].to_csv(OUTPUT_DECOMP_SAMPLE, index=False)

    validations = {
        "task_id": TASK_ID,
        "checks": {
            "accounting_identity_equity_equals_cash_plus_positions": {
                "pass": g3_accounting,
                "abs_tolerance": ACCOUNTING_ABS_TOL,
                "max_abs_error": identity_max_abs,
                "max_rel_error": identity_max_rel,
            },
            "costs_sum_consistency_ledger_vs_daily_series": {
                "pass": g4_costs,
                "abs_tolerance": COST_ABS_TOL,
                "ledger_cost_sum": cost_total_ledger,
                "daily_cost_sum": cost_total_curve,
                "abs_diff": cost_diff,
            },
            "cash_non_negative": {
                "pass": cash_non_negative,
                "min_cash_curve": min_cash_curve,
                "min_cash_ledger_before": min_cash_ledger_before,
                "min_cash_ledger_after": min_cash_ledger_after,
            },
        },
        "stats": {
            "n_curve_days": int(len(curve)),
            "n_ledger_rows": int(len(ledger)),
            "n_buy_days": int(len(buy_dates)),
            "buy_cadence_days_mean": float(pd.to_numeric(buy_dates["days_since_prev_buy"], errors="coerce").dropna().mean())
            if len(buy_dates) > 1
            else None,
            "buy_cadence_days_p95": float(pd.to_numeric(buy_dates["days_since_prev_buy"], errors="coerce").dropna().quantile(0.95))
            if len(buy_dates) > 1
            else None,
        },
    }
    OUTPUT_VALID_SUMMARY.write_text(json.dumps(validations, indent=2, sort_keys=True), encoding="utf-8")

    fig = make_subplots(
        rows=4,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        subplot_titles=[
            "Equity vs Cash vs Positions Value",
            "Custos: diário e cumulativo",
            "CDI no caixa: crédito diário e cumulativo",
            "Fluxo operacional: notional BUY/SELL e turnover diário",
        ],
    )

    fig.add_trace(go.Scatter(x=daily["date"], y=daily["equity_end"], mode="lines", name="equity_end", line=dict(color="#2ca02c", width=2.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=daily["date"], y=daily["cash_end"], mode="lines", name="cash_end", line=dict(color="#1f77b4")), row=1, col=1)
    fig.add_trace(
        go.Scatter(x=daily["date"], y=daily["positions_value_end"], mode="lines", name="positions_value_end", line=dict(color="#9467bd")),
        row=1,
        col=1,
    )

    fig.add_trace(go.Bar(x=daily["date"], y=daily["daily_cost_brl"], name="daily_cost_brl", marker_color="#d62728", opacity=0.5), row=2, col=1)
    fig.add_trace(go.Scatter(x=daily["date"], y=daily["cum_cost_brl"], mode="lines", name="cum_cost_brl", line=dict(color="#8c564b", width=2)), row=2, col=1)

    fig.add_trace(go.Bar(x=daily["date"], y=daily["cdi_credit"], name="cdi_credit_daily", marker_color="#17becf", opacity=0.5), row=3, col=1)
    fig.add_trace(go.Scatter(x=daily["date"], y=daily["cum_cdi_credit"], mode="lines", name="cum_cdi_credit", line=dict(color="#7f7f7f", width=2)), row=3, col=1)

    fig.add_trace(go.Bar(x=daily["date"], y=daily["buy_notional"], name="buy_notional", marker_color="#2ca02c", opacity=0.45), row=4, col=1)
    fig.add_trace(go.Bar(x=daily["date"], y=-daily["sell_notional"], name="sell_notional(-)", marker_color="#ff7f0e", opacity=0.45), row=4, col=1)
    fig.add_trace(
        go.Scatter(x=daily["date"], y=daily["turnover_daily_x"], mode="lines", name="turnover_daily_x", line=dict(color="#000000", width=1.5)),
        row=4,
        col=1,
    )

    regime = daily["regime_defensivo"].fillna(False).astype(bool)
    for x0, x1 in find_true_intervals(regime, daily["date"]):
        fig.add_vrect(x0=x0, x1=x1, fillcolor="rgba(255,0,0,0.06)", line_width=0)

    fig.update_layout(
        title="T045 STATE3 - Accounting Decomposition (P&L/Cost/Cash)",
        template="plotly_white",
        hovermode="x unified",
        barmode="relative",
        height=1200,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )

    fig.write_html(OUTPUT_HTML, include_plotlyjs="cdn", full_html=True)

    report_lines = [
        f"# {TASK_ID} Report",
        "",
        "## 1) Inputs",
        "",
        f"- Curve: `{INPUT_CURVE}` ({len(curve)} linhas)",
        f"- Ledger: `{INPUT_LEDGER}` ({len(ledger)} linhas)",
        "",
        "## 2) Validation summary",
        "",
        f"- Accounting identity (`equity_end = cash_end + positions_value_end`): {'PASS' if g3_accounting else 'FAIL'}",
        f"  - max_abs_error={identity_max_abs:.12f}, max_rel_error={identity_max_rel:.12f}",
        f"- Costs consistency (`sum(cost_brl)`): {'PASS' if g4_costs else 'FAIL'}",
        f"  - ledger_cost_sum={cost_total_ledger:.6f}, daily_cost_sum={cost_total_curve:.6f}, abs_diff={cost_diff:.12f}",
        f"- Cash non-negative: {'PASS' if cash_non_negative else 'FAIL'}",
        f"  - min_cash_curve={min_cash_curve:.6f}, min_cash_ledger_before={min_cash_ledger_before:.6f}, min_cash_ledger_after={min_cash_ledger_after:.6f}",
        "",
        "## 3) Observations",
        "",
        "- `cdi_credit` foi exibido e auditado exatamente como materializado no `T039_PORTFOLIO_CURVE.parquet` (sem reinterpretação).",
        "- Evidências de decomposição, validações e cadência de BUY foram exportadas em CSV/JSON.",
        "",
        "## 4) Artifacts",
        "",
        f"- `{OUTPUT_HTML}`",
        f"- `{OUTPUT_DECOMP_SAMPLE}`",
        f"- `{OUTPUT_VALID_SUMMARY}`",
        f"- `{OUTPUT_BUY_CADENCE}`",
        f"- `{OUTPUT_MANIFEST}`",
    ]
    OUTPUT_REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    manifest = {
        "task_id": TASK_ID,
        "inputs_consumed": [str(p) for p in required_inputs],
        "outputs_produced": [
            str(OUTPUT_HTML),
            str(OUTPUT_REPORT),
            str(OUTPUT_MANIFEST),
            str(OUTPUT_DECOMP_SAMPLE),
            str(OUTPUT_VALID_SUMMARY),
            str(OUTPUT_BUY_CADENCE),
            str(SCRIPT_PATH),
        ],
        "hashes_sha256": {
            **{str(p): sha256_file(p) for p in required_inputs},
            str(OUTPUT_HTML): sha256_file(OUTPUT_HTML),
            str(OUTPUT_REPORT): sha256_file(OUTPUT_REPORT),
            str(OUTPUT_DECOMP_SAMPLE): sha256_file(OUTPUT_DECOMP_SAMPLE),
            str(OUTPUT_VALID_SUMMARY): sha256_file(OUTPUT_VALID_SUMMARY),
            str(OUTPUT_BUY_CADENCE): sha256_file(OUTPUT_BUY_CADENCE),
            str(SCRIPT_PATH): sha256_file(SCRIPT_PATH),
        },
    }
    OUTPUT_MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    g1 = OUTPUT_HTML.exists()
    g2 = OUTPUT_DECOMP_SAMPLE.exists() and OUTPUT_VALID_SUMMARY.exists() and OUTPUT_BUY_CADENCE.exists()
    g3 = g3_accounting
    g4 = g4_costs
    gx = OUTPUT_MANIFEST.exists()

    print("STEP GATES:")
    print(f"- G1_PLOT_ARTIFACT_PRESENT: {'PASS' if g1 else 'FAIL'}")
    print(f"- G2_EVIDENCE_PRESENT: {'PASS' if g2 else 'FAIL'}")
    print(f"- G3_ACCOUNTING_IDENTITY: {'PASS' if g3 else 'FAIL'}")
    print(f"- G4_COSTS_AGREE: {'PASS' if g4 else 'FAIL'}")
    print(f"- Gx_HASH_MANIFEST_PRESENT: {'PASS' if gx else 'FAIL'}")

    print("RETRY LOG:")
    print("- none")

    print("ARTIFACT LINKS:")
    print(f"- {OUTPUT_HTML}")
    print(f"- {OUTPUT_REPORT}")
    print(f"- {OUTPUT_MANIFEST}")
    print(f"- {OUTPUT_DECOMP_SAMPLE}")
    print(f"- {OUTPUT_VALID_SUMMARY}")
    print(f"- {OUTPUT_BUY_CADENCE}")
    print(f"- {SCRIPT_PATH}")

    overall = g1 and g2 and g3 and g4 and gx
    print(f"OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
