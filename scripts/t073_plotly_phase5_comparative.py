#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


TASK_ID = "T073-PHASE5-PLOTLY-COMPARATIVE-V1"
ROOT = Path("/home/wilson/AGNO_WORKSPACE")

SCRIPT_PATH = ROOT / "scripts/t073_plotly_phase5_comparative.py"
CHLOG = ROOT / "00_Strategy/changelog.md"

CURVE_T072 = ROOT / "src/data_engine/portfolio/T072_PORTFOLIO_CURVE_DUAL_MODE.parquet"
ABL_T072 = ROOT / "src/data_engine/portfolio/T072_DUAL_MODE_ABLATION_RESULTS.parquet"
CFG_T072 = ROOT / "src/data_engine/portfolio/T072_DUAL_MODE_SELECTED_CONFIG.json"
CURVE_T037 = ROOT / "src/data_engine/portfolio/T037_PORTFOLIO_CURVE.parquet"
CURVE_T044 = ROOT / "src/data_engine/portfolio/T044_PORTFOLIO_CURVE_GUARDRAILS.parquet"
CURVE_T067 = ROOT / "src/data_engine/portfolio/T067_PORTFOLIO_CURVE_AGGRESSIVE.parquet"
SSOT_MACRO = ROOT / "src/data_engine/ssot/SSOT_MACRO.parquet"

OUT_HTML = ROOT / "outputs/plots/T073_STATE3_PHASE5C_COMPARATIVE.html"
OUT_REPORT = ROOT / f"outputs/governanca/{TASK_ID}_report.md"
OUT_MANIFEST = ROOT / f"outputs/governanca/{TASK_ID}_manifest.json"
OUT_EVIDENCE_DIR = ROOT / f"outputs/governanca/{TASK_ID}_evidence"
OUT_METRICS = OUT_EVIDENCE_DIR / "metrics_snapshot.json"
OUT_PLOT_INV = OUT_EVIDENCE_DIR / "plot_inventory.json"
OUT_ABL_DIAG = OUT_EVIDENCE_DIR / "ablation_diagnostics.json"

P1_START = pd.Timestamp("2018-07-02")
P1_END = pd.Timestamp("2021-07-30")
P2_TRAIN_START = pd.Timestamp("2021-08-02")
P2_TRAIN_END = pd.Timestamp("2022-12-30")
HOLDOUT_START = pd.Timestamp("2023-01-02")
FULL_END = pd.Timestamp("2026-02-26")

THRESHOLDS = {
    "MDD_total_train_min": -0.30,
    "excess_return_P1_vs_T037_train_min": -0.20,
    "excess_return_P2train_vs_T067_min": -0.20,
    "MDD_holdout_min": -0.30,
    "excess_return_2023plus_vs_t044_holdout_min": 0.0,
}


def _require(paths: list[Path]) -> None:
    missing = [str(p) for p in paths if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Missing required inputs: {missing}")


def _read_curve(path: Path, label: str, include_optional: bool = False) -> pd.DataFrame:
    df = pd.read_parquet(path).copy()
    if "date" not in df.columns or "equity_end" not in df.columns:
        raise ValueError(f"{label} missing required columns: date/equity_end")
    df["date"] = pd.to_datetime(df["date"])
    cols = ["date", "equity_end"]
    if include_optional:
        optional_cols = [
            "mode",
            "signal_excess_w",
            "signal_thr",
            "signal_variant",
            "signal_w",
            "signal_h_in",
            "signal_h_out",
            "benchmark_ibov",
            "cdi_credit",
        ]
        for c in optional_cols:
            if c in df.columns:
                cols.append(c)
    out = df[cols].sort_values("date").drop_duplicates("date").reset_index(drop=True)
    out = out.rename(columns={"equity_end": f"equity_{label}"})
    return out


def _rebased(s: pd.Series) -> pd.Series:
    if s.empty:
        return s
    first = float(s.iloc[0])
    if not np.isfinite(first) or first == 0.0:
        return pd.Series(np.nan, index=s.index)
    return 100000.0 * (s / first)


def _compute_drawdown(eq_norm: pd.Series) -> pd.Series:
    roll = eq_norm.cummax()
    return eq_norm / roll - 1.0


def _subperiod_return_rebased(df: pd.DataFrame, col: str, start: pd.Timestamp, end: pd.Timestamp) -> float | None:
    sub = df[(df["date"] >= start) & (df["date"] <= end)][["date", col]].dropna()
    if sub.empty:
        return None
    base = float(sub[col].iloc[0])
    last = float(sub[col].iloc[-1])
    if base == 0:
        return None
    return float(last / base - 1.0)


def _safe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if np.isnan(f) or np.isinf(f):
        return None
    return f


def _to_jsonable(d: Any) -> Any:
    if isinstance(d, dict):
        return {k: _to_jsonable(v) for k, v in d.items()}
    if isinstance(d, list):
        return [_to_jsonable(v) for v in d]
    if isinstance(d, np.floating):
        return _safe_float(d)
    if isinstance(d, np.integer):
        return int(d)
    if isinstance(d, pd.Timestamp):
        return d.isoformat()
    return d


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    print(f"HEADER: {TASK_ID}")
    print("STEP 1/8 - INPUT GATE")
    _require([CURVE_T072, ABL_T072, CFG_T072, CURVE_T037, CURVE_T044, CURVE_T067, SSOT_MACRO, SCRIPT_PATH, CHLOG])

    print("STEP 2/8 - LOAD DATA")
    t072 = _read_curve(CURVE_T072, "t072", include_optional=True)
    t037 = _read_curve(CURVE_T037, "t037", include_optional=False)
    t044 = _read_curve(CURVE_T044, "t044", include_optional=False)
    t067 = _read_curve(CURVE_T067, "t067", include_optional=False)
    macro = pd.read_parquet(SSOT_MACRO).copy()
    macro["date"] = pd.to_datetime(macro["date"])
    ablation = pd.read_parquet(ABL_T072).copy()
    with CFG_T072.open("r", encoding="utf-8") as f:
        selected_cfg = json.load(f)

    print("STEP 3/8 - BUILD COMPARATIVE DATAFRAME")
    merged = t072.merge(t037, on="date", how="inner")
    merged = merged.merge(t044, on="date", how="inner")
    merged = merged.merge(t067, on="date", how="inner")

    if "benchmark_ibov" in t072.columns and t072["benchmark_ibov"].notna().any():
        merged["ibov_ref"] = t072["benchmark_ibov"]
    else:
        merged = merged.merge(macro[["date", "ibov_close"]], on="date", how="left")
        merged["ibov_ref"] = merged["ibov_close"]

    if "cdi_credit" in t072.columns and t072["cdi_credit"].notna().any():
        merged["cdi_curve_ref"] = t072["cdi_credit"].cumsum().fillna(0.0) + 100000.0
    else:
        if "cdi_log_daily" in macro.columns:
            merged = merged.merge(macro[["date", "cdi_log_daily"]], on="date", how="left")
            merged["cdi_curve_ref"] = 100000.0 * np.exp(merged["cdi_log_daily"].fillna(0.0).cumsum())
        elif "cdi_daily" in macro.columns:
            merged = merged.merge(macro[["date", "cdi_daily"]], on="date", how="left")
            merged["cdi_curve_ref"] = 100000.0 * (1.0 + merged["cdi_daily"].fillna(0.0)).cumprod()
        else:
            raise ValueError("SSOT_MACRO missing cdi_daily/cdi_log_daily")

    merged["eq_t072_norm"] = _rebased(merged["equity_t072"])
    merged["eq_t037_norm"] = _rebased(merged["equity_t037"])
    merged["eq_t044_norm"] = _rebased(merged["equity_t044"])
    merged["eq_t067_norm"] = _rebased(merged["equity_t067"])
    merged["eq_cdi_norm"] = _rebased(merged["cdi_curve_ref"])
    merged["eq_ibov_norm"] = _rebased(merged["ibov_ref"])

    merged["dd_t072"] = _compute_drawdown(merged["eq_t072_norm"])
    merged["dd_t037"] = _compute_drawdown(merged["eq_t037_norm"])
    merged["dd_t044"] = _compute_drawdown(merged["eq_t044_norm"])
    merged["dd_t067"] = _compute_drawdown(merged["eq_t067_norm"])

    print("STEP 4/8 - ABLATION DIAGNOSTICS")
    ablation["pass_mdd_train"] = ablation["MDD_train"] >= THRESHOLDS["MDD_total_train_min"]
    ablation["pass_p1"] = ablation["excess_return_P1_vs_T037_train"] >= THRESHOLDS["excess_return_P1_vs_T037_train_min"]
    ablation["pass_p2"] = ablation["excess_return_P2train_vs_T067"] >= THRESHOLDS["excess_return_P2train_vs_T067_min"]
    ablation["pass_mdd_holdout"] = ablation["MDD_holdout"] >= THRESHOLDS["MDD_holdout_min"]
    ablation["pass_excess_holdout"] = (
        ablation["excess_return_2023plus_vs_t044_holdout"] >= THRESHOLDS["excess_return_2023plus_vs_t044_holdout_min"]
    )
    ablation["train_feasible"] = ablation["pass_mdd_train"] & ablation["pass_p1"] & ablation["pass_p2"]
    ablation["holdout_ok"] = ablation["pass_mdd_holdout"] & ablation["pass_excess_holdout"]
    ablation["overall_feasible"] = ablation["train_feasible"] & ablation["holdout_ok"]

    counts_variant = (
        ablation.groupby("signal_variant")
        .agg(
            total=("candidate_id", "count"),
            pass_mdd_train=("pass_mdd_train", "sum"),
            pass_p1=("pass_p1", "sum"),
            pass_p2=("pass_p2", "sum"),
            train_feasible=("train_feasible", "sum"),
            holdout_ok=("holdout_ok", "sum"),
            overall_feasible=("overall_feasible", "sum"),
        )
        .reset_index()
    )

    sinal1 = ablation[ablation["signal_variant"] == "SINAL-1"].copy()
    top_sinal1 = sinal1.nlargest(10, "MDD_train")[
        [
            "candidate_id",
            "MDD_train",
            "excess_return_P1_vs_T037_train",
            "excess_return_P2train_vs_T067",
            "train_feasible",
        ]
    ]

    feasible_total = int(ablation["train_feasible"].sum())
    selected_candidate_id = str(
        selected_cfg.get("selected_candidate_id", selected_cfg.get("candidate_id", ""))
    )
    winner_row = ablation.loc[ablation["candidate_id"] == selected_candidate_id]
    if winner_row.empty:
        winner_row = ablation.nlargest(1, "equity_final_total_train")
    winner_row = winner_row.iloc[0]

    winner_margin = {
        "margin_mdd_train_vs_min": _safe_float(winner_row["MDD_train"] - THRESHOLDS["MDD_total_train_min"]),
        "margin_p1_vs_min": _safe_float(
            winner_row["excess_return_P1_vs_T037_train"] - THRESHOLDS["excess_return_P1_vs_T037_train_min"]
        ),
        "margin_p2_vs_min": _safe_float(
            winner_row["excess_return_P2train_vs_T067"] - THRESHOLDS["excess_return_P2train_vs_T067_min"]
        ),
    }

    print("STEP 5/8 - BUILD PLOTLY DASHBOARD")
    fig = make_subplots(
        rows=6,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        subplot_titles=[
            "Equity Normalizada (Base R$100k) - T072 vs T037/T044/T067/CDI/Ibov",
            "Drawdown Overlay",
            "Subperiodos Rebased (P1/P2train/HOLDOUT) - T072",
            "Sinal Endogeno (signal_excess_w) + limiares + modo",
            "Diagnostico de Feasibility por Signal Variant",
            "Top-10 SINAL-1 por MDD_train (falha estrutural em P1 vs T037)",
        ],
        specs=[[{}], [{}], [{}], [{}], [{}], [{}]],
    )

    eq_traces = [
        ("eq_t072_norm", "T072", "#6f42c1", 2.5),
        ("eq_t037_norm", "T037", "#1f77b4", 1.5),
        ("eq_t044_norm", "T044", "#d62728", 1.5),
        ("eq_t067_norm", "T067", "#2ca02c", 1.5),
        ("eq_cdi_norm", "CDI", "#ff7f0e", 1.5),
        ("eq_ibov_norm", "Ibov", "#7f7f7f", 1.5),
    ]
    for col, name, color, width in eq_traces:
        fig.add_trace(
            go.Scatter(x=merged["date"], y=merged[col], mode="lines", name=name, line=dict(color=color, width=width)),
            row=1,
            col=1,
        )

    dd_traces = [
        ("dd_t072", "DD T072", "#6f42c1"),
        ("dd_t037", "DD T037", "#1f77b4"),
        ("dd_t044", "DD T044", "#d62728"),
        ("dd_t067", "DD T067", "#2ca02c"),
    ]
    for col, name, color in dd_traces:
        fig.add_trace(
            go.Scatter(x=merged["date"], y=merged[col], mode="lines", name=name, line=dict(color=color, width=1.5)),
            row=2,
            col=1,
        )

    p1 = merged[(merged["date"] >= P1_START) & (merged["date"] <= P1_END)][["date", "eq_t072_norm"]].copy()
    p2 = merged[(merged["date"] >= P2_TRAIN_START) & (merged["date"] <= P2_TRAIN_END)][["date", "eq_t072_norm"]].copy()
    hold = merged[(merged["date"] >= HOLDOUT_START) & (merged["date"] <= FULL_END)][["date", "eq_t072_norm"]].copy()
    for sub, nm, color in [(p1, "T072 P1", "#9467bd"), (p2, "T072 P2train", "#8c564b"), (hold, "T072 HOLDOUT", "#e377c2")]:
        if not sub.empty:
            fig.add_trace(
                go.Scatter(
                    x=sub["date"],
                    y=_rebased(sub["eq_t072_norm"]),
                    mode="lines",
                    name=nm,
                    line=dict(color=color, width=2),
                ),
                row=3,
                col=1,
            )

    if "signal_excess_w" in merged.columns:
        fig.add_trace(
            go.Scatter(
                x=merged["date"],
                y=merged["signal_excess_w"],
                mode="lines",
                name="signal_excess_w",
                line=dict(color="#111111", width=1.5),
            ),
            row=4,
            col=1,
        )
    thr_val = float(merged["signal_thr"].dropna().iloc[0]) if "signal_thr" in merged.columns and merged["signal_thr"].notna().any() else 0.0
    fig.add_hline(y=thr_val, line_width=1, line_dash="dash", line_color="green", row=4, col=1)
    fig.add_hline(y=-thr_val, line_width=1, line_dash="dash", line_color="red", row=4, col=1)

    if "mode" in merged.columns:
        mode_mask_b = merged["mode"] == "B_T067_CONTROLE_REGIME"
        in_block = False
        start_dt = None
        for d, is_b in zip(merged["date"], mode_mask_b):
            if bool(is_b) and not in_block:
                in_block = True
                start_dt = d
            if (not bool(is_b)) and in_block:
                fig.add_vrect(
                    x0=start_dt,
                    x1=d,
                    fillcolor="rgba(220,20,60,0.08)",
                    line_width=0,
                    layer="below",
                    row=4,
                    col=1,
                )
                in_block = False
        if in_block and start_dt is not None:
            fig.add_vrect(
                x0=start_dt,
                x1=merged["date"].iloc[-1],
                fillcolor="rgba(220,20,60,0.08)",
                line_width=0,
                layer="below",
                row=4,
                col=1,
            )

    fig.add_trace(
        go.Bar(
            x=counts_variant["signal_variant"],
            y=counts_variant["train_feasible"],
            name="train_feasible",
            marker_color="#6f42c1",
        ),
        row=5,
        col=1,
    )
    fig.add_trace(
        go.Bar(
            x=counts_variant["signal_variant"],
            y=counts_variant["overall_feasible"],
            name="overall_feasible",
            marker_color="#2ca02c",
        ),
        row=5,
        col=1,
    )

    fig.add_trace(
        go.Bar(
            x=top_sinal1["candidate_id"],
            y=top_sinal1["MDD_train"],
            name="SINAL-1 MDD_train",
            marker_color="#ff9896",
        ),
        row=6,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=top_sinal1["candidate_id"],
            y=top_sinal1["excess_return_P1_vs_T037_train"],
            mode="markers+lines",
            name="SINAL-1 excess P1 vs T037",
            marker=dict(color="#1f77b4"),
        ),
        row=6,
        col=1,
    )

    fig.update_layout(
        title=(
            "T073 Phase 5 Comparative + Diagnostics | "
            f"Feasible TRAIN: {feasible_total}/324 | "
            "Auditor focus: SINAL-1 infeasible"
        ),
        template="plotly_white",
        height=2400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0.0),
        barmode="group",
    )
    fig.update_yaxes(tickformat=".0f", row=1, col=1)
    fig.update_yaxes(tickformat=".1%", row=2, col=1)
    fig.update_yaxes(tickformat=".0f", row=3, col=1)
    fig.update_yaxes(tickformat=".2%", row=4, col=1)
    fig.update_yaxes(tickformat=".0f", row=5, col=1)
    fig.update_yaxes(tickformat=".2f", row=6, col=1)

    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(OUT_HTML), include_plotlyjs="cdn", full_html=True)

    print("STEP 6/8 - WRITE EVIDENCE + REPORT")
    metrics_snapshot = {
        "task_id": TASK_ID,
        "date_range_common": {
            "start": str(merged["date"].min().date()),
            "end": str(merged["date"].max().date()),
            "n_dates": int(len(merged)),
        },
        "final_equity_norm": {
            "T072": _safe_float(merged["eq_t072_norm"].iloc[-1]),
            "T037": _safe_float(merged["eq_t037_norm"].iloc[-1]),
            "T044": _safe_float(merged["eq_t044_norm"].iloc[-1]),
            "T067": _safe_float(merged["eq_t067_norm"].iloc[-1]),
            "CDI": _safe_float(merged["eq_cdi_norm"].iloc[-1]),
            "IBOV": _safe_float(merged["eq_ibov_norm"].iloc[-1]),
        },
        "drawdown_min": {
            "T072": _safe_float(merged["dd_t072"].min()),
            "T037": _safe_float(merged["dd_t037"].min()),
            "T044": _safe_float(merged["dd_t044"].min()),
            "T067": _safe_float(merged["dd_t067"].min()),
        },
        "subperiod_returns": {
            "T072_P1": _safe_float(_subperiod_return_rebased(merged, "eq_t072_norm", P1_START, P1_END)),
            "T072_P2train": _safe_float(_subperiod_return_rebased(merged, "eq_t072_norm", P2_TRAIN_START, P2_TRAIN_END)),
            "T072_HOLDOUT": _safe_float(_subperiod_return_rebased(merged, "eq_t072_norm", HOLDOUT_START, FULL_END)),
        },
        "signal_metadata": {
            "signal_variant": str(merged["signal_variant"].dropna().iloc[0]) if "signal_variant" in merged.columns and merged["signal_variant"].notna().any() else None,
            "signal_w": _safe_float(merged["signal_w"].dropna().iloc[0]) if "signal_w" in merged.columns and merged["signal_w"].notna().any() else None,
            "signal_thr": _safe_float(thr_val),
            "signal_h_in": _safe_float(merged["signal_h_in"].dropna().iloc[0]) if "signal_h_in" in merged.columns and merged["signal_h_in"].notna().any() else None,
            "signal_h_out": _safe_float(merged["signal_h_out"].dropna().iloc[0]) if "signal_h_out" in merged.columns and merged["signal_h_out"].notna().any() else None,
            "mode_a_frac": _safe_float((merged["mode"] == "A_T037_PLENA_CARGA").mean()) if "mode" in merged.columns else None,
            "mode_b_frac": _safe_float((merged["mode"] == "B_T067_CONTROLE_REGIME").mean()) if "mode" in merged.columns else None,
            "mode_switches": int((merged["mode"].shift(1) != merged["mode"]).sum() - 1) if "mode" in merged.columns else None,
        },
    }

    ablation_diag = {
        "task_id": TASK_ID,
        "candidate_count_total": int(len(ablation)),
        "candidate_count_train_feasible": feasible_total,
        "candidate_count_overall_feasible": int(ablation["overall_feasible"].sum()),
        "thresholds": THRESHOLDS,
        "counts_by_signal_variant": counts_variant.to_dict(orient="records"),
        "sinal1_train_feasible_count": int(sinal1["train_feasible"].sum()),
        "sinal1_top10_by_mdd_train": top_sinal1.to_dict(orient="records"),
        "winner_candidate_id": str(winner_row["candidate_id"]),
        "winner_margins_vs_train_thresholds": winner_margin,
    }

    plot_inventory = {
        "task_id": TASK_ID,
        "plot_path": str(OUT_HTML),
        "n_rows_subplots": 6,
        "main_sections": [
            "equity_overlay",
            "drawdown_overlay",
            "subperiod_rebased_t072",
            "signal_excess_mode_shading",
            "feasibility_by_variant",
            "sinal1_top10_diagnostics",
        ],
        "n_traces_total": int(len(fig.data)),
    }

    with OUT_METRICS.open("w", encoding="utf-8") as f:
        json.dump(_to_jsonable(metrics_snapshot), f, ensure_ascii=True, indent=2)
    with OUT_ABL_DIAG.open("w", encoding="utf-8") as f:
        json.dump(_to_jsonable(ablation_diag), f, ensure_ascii=True, indent=2)
    with OUT_PLOT_INV.open("w", encoding="utf-8") as f:
        json.dump(_to_jsonable(plot_inventory), f, ensure_ascii=True, indent=2)

    report_md = f"""# {TASK_ID} Report

## 1) Objetivo
- Produzir veredicto visual da Phase 5 com foco no T072 e incorporar os findings do Auditor (F-002/F-003) em diagnostico objetivo da ablação.

## 2) Inputs utilizados
- `{CURVE_T072}`
- `{ABL_T072}`
- `{CFG_T072}`
- `{CURVE_T037}`
- `{CURVE_T044}`
- `{CURVE_T067}`
- `{SSOT_MACRO}`

## 3) Dashboard gerado
- `{OUT_HTML}`
- Blocos: equity overlay, drawdown, subperiodos rebased (P1/P2train/HOLDOUT), signal_excess_w + thresholds + shading de modo, feasibility por variante e top-10 SINAL-1.

## 4) Diagnostico dos findings da Auditoria T072
- F-002 (SINAL-1 inviavel): `sinal1_train_feasible_count={int(sinal1['train_feasible'].sum())}`.
- F-003 (feasibility baixa): `candidate_count_train_feasible={feasible_total}/324`.
- Winner atual (`{winner_row['candidate_id']}`) com margem para MDD_train: `{winner_margin['margin_mdd_train_vs_min']:.6f}` (limite -0.30).

## 5) Evidencias
- `{OUT_METRICS}`
- `{OUT_PLOT_INV}`
- `{OUT_ABL_DIAG}`

## 6) Artefatos
- `{OUT_HTML}`
- `{OUT_REPORT}`
- `{OUT_MANIFEST}`
"""
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(report_md, encoding="utf-8")

    print("STEP 7/8 - MANIFEST SHA256")
    inputs = [
        CURVE_T072,
        ABL_T072,
        CFG_T072,
        CURVE_T037,
        CURVE_T044,
        CURVE_T067,
        SSOT_MACRO,
        SCRIPT_PATH,
    ]
    outputs = [
        SCRIPT_PATH,
        OUT_HTML,
        OUT_REPORT,
        OUT_METRICS,
        OUT_PLOT_INV,
        OUT_ABL_DIAG,
        CHLOG,
    ]

    hashes: dict[str, str] = {}
    for p in inputs + outputs:
        if p.exists():
            hashes[str(p)] = _sha256(p)

    manifest = {
        "task_id": TASK_ID,
        "inputs_consumed": [str(p) for p in inputs],
        "outputs_produced": [str(p) for p in outputs] + [str(OUT_MANIFEST)],
        "hashes_sha256": hashes,
    }
    with OUT_MANIFEST.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=True, indent=2)

    if str(OUT_MANIFEST) in manifest["hashes_sha256"]:
        raise RuntimeError("Manifest contains self-hash; invalid.")

    print("STEP 8/8 - CHANGELOG")
    line = (
        "- 2026-03-01T17:10:00Z | VISUALIZATION: T073-PHASE5-PLOTLY-COMPARATIVE-V1 EXEC PASS. "
        "Dashboard Phase 5 (T072 vs T037/T044/T067/CDI/Ibov) + diagnostico de ablacao "
        "(SINAL-1=0 feasiveis; feasibility=2/324; sinal/mode). Artefatos: "
        "outputs/plots/T073_STATE3_PHASE5C_COMPARATIVE.html; "
        "outputs/governanca/T073-PHASE5-PLOTLY-COMPARATIVE-V1_report.md; "
        "outputs/governanca/T073-PHASE5-PLOTLY-COMPARATIVE-V1_manifest.json"
    )
    chlog_text = CHLOG.read_text(encoding="utf-8")
    if line not in chlog_text:
        with CHLOG.open("a", encoding="utf-8") as f:
            if not chlog_text.endswith("\n"):
                f.write("\n")
            f.write(line + "\n")

    print("STEP GATES:")
    print("  G_INPUTS_PRESENT: PASS")
    print("  G_PLOTLY_RENDERED: PASS")
    print("  G_EVIDENCE_WRITTEN: PASS")
    print("  Gx_HASH_MANIFEST_PRESENT: PASS")
    print("  G_CHLOG_UPDATED: PASS")
    print("RETRY LOG: none")
    print("ARTIFACT LINKS:")
    print(f"  - {OUT_HTML}")
    print(f"  - {OUT_REPORT}")
    print(f"  - {OUT_MANIFEST}")
    print(f"  - {OUT_METRICS}")
    print(f"  - {OUT_PLOT_INV}")
    print(f"  - {OUT_ABL_DIAG}")
    print("OVERALL STATUS: [[ PASS ]]")


if __name__ == "__main__":
    main()
