#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
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


TASK_ID = "T067-AGGRESSIVE-ALLOCATION-ABLATION-V1"
BASE_CAPITAL = 100000.0
ROOT = Path("/home/wilson/AGNO_WORKSPACE")

SCRIPT_BASE = ROOT / "scripts/t063_market_slope_reentry_ablation.py"
SCRIPT_STYLE_REF = ROOT / "scripts/t064_plotly_phase3d_comparative.py"

INPUT_CANONICAL = ROOT / "src/data_engine/ssot/SSOT_CANONICAL_BASE.parquet"
INPUT_MACRO = ROOT / "src/data_engine/ssot/SSOT_MACRO.parquet"
INPUT_BLACKLIST = ROOT / "src/data_engine/ssot/SSOT_QUALITY_BLACKLIST_A001.json"
INPUT_SCORES = ROOT / "src/data_engine/features/T037_M3_SCORES_DAILY.parquet"

INPUT_T044_CURVE = ROOT / "src/data_engine/portfolio/T044_PORTFOLIO_CURVE_GUARDRAILS.parquet"
INPUT_T063_CURVE = ROOT / "src/data_engine/portfolio/T063_PORTFOLIO_CURVE_REENTRY_FIX_V2.parquet"
INPUT_T037_CURVE = ROOT / "src/data_engine/portfolio/T037_PORTFOLIO_CURVE.parquet"
INPUT_T044_SUMMARY = ROOT / "src/data_engine/portfolio/T044_BASELINE_SUMMARY.json"
INPUT_T063_SUMMARY = ROOT / "src/data_engine/portfolio/T063_BASELINE_SUMMARY_REENTRY_FIX_V2.json"
INPUT_T037_SUMMARY = ROOT / "src/data_engine/portfolio/T037_BASELINE_SUMMARY.json"

OUT_ABLATION = ROOT / "src/data_engine/portfolio/T067_AGGRESSIVE_ABLATION_RESULTS.parquet"
OUT_SELECTED_CFG = ROOT / "src/data_engine/portfolio/T067_AGGRESSIVE_SELECTED_CONFIG.json"
OUT_CURVE = ROOT / "src/data_engine/portfolio/T067_PORTFOLIO_CURVE_AGGRESSIVE.parquet"
OUT_LEDGER = ROOT / "src/data_engine/portfolio/T067_PORTFOLIO_LEDGER_AGGRESSIVE.parquet"
OUT_SUMMARY = ROOT / "src/data_engine/portfolio/T067_BASELINE_SUMMARY_AGGRESSIVE.json"

OUT_HTML = ROOT / "outputs/plots/T067_STATE3_PHASE4A_COMPARATIVE.html"
OUT_REPORT = ROOT / "outputs/governanca/T067-AGGRESSIVE-ALLOCATION-ABLATION-V1_report.md"
OUT_MANIFEST = ROOT / "outputs/governanca/T067-AGGRESSIVE-ALLOCATION-ABLATION-V1_manifest.json"
OUT_EVIDENCE_DIR = ROOT / "outputs/governanca/T067-AGGRESSIVE-ALLOCATION-ABLATION-V1_evidence"
OUT_CANDIDATE_SET = OUT_EVIDENCE_DIR / "candidate_set.json"
OUT_SELECTION_RULE = OUT_EVIDENCE_DIR / "selection_rule.json"
OUT_FEASIBILITY = OUT_EVIDENCE_DIR / "feasibility_snapshot.json"
OUT_METRICS_SNAPSHOT = OUT_EVIDENCE_DIR / "metrics_snapshot.json"
OUT_PLOT_INVENTORY = OUT_EVIDENCE_DIR / "plot_inventory.json"

CHANGELOG_PATH = ROOT / "00_Strategy/changelog.md"
TRACEABILITY_LINE = (
    "- 2026-03-01T12:40:00Z | STRATEGY: T067-AGGRESSIVE-ALLOCATION-ABLATION-V1 EXEC. "
    "Artefatos: outputs/plots/T067_STATE3_PHASE4A_COMPARATIVE.html; "
    "outputs/governanca/T067-AGGRESSIVE-ALLOCATION-ABLATION-V1_report.md; "
    "outputs/governanca/T067-AGGRESSIVE-ALLOCATION-ABLATION-V1_manifest.json; "
    "src/data_engine/portfolio/T067_AGGRESSIVE_SELECTED_CONFIG.json"
)


BUY_TURNOVER_CAP_GRID: list[float | None] = [None, 0.50, 0.30, 0.20, 0.10]
CADENCE_DAYS_GRID: list[int] = [5, 10, 15, 20, 25]

REGIME_FIXED = {
    "market_slope_window": 30,
    "in_hyst_days": 4,
    "out_hyst_days": 4,
}
THRESHOLDS = {
    "MDD_total_min": -0.30,
}

SELECTION_ORDER = [
    "excess_return_2023plus_vs_t044 DESC",
    "CAGR DESC",
    "Sharpe DESC",
    "turnover_total ASC",
    "candidate_id ASC",
]


def _load_base_module():
    spec = importlib.util.spec_from_file_location("t063_base_module", SCRIPT_BASE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Nao foi possivel carregar script base: {SCRIPT_BASE}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _json_safe(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, tuple):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, (np.floating, float)):
        v = float(obj)
        return v if np.isfinite(v) else None
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if pd.isna(obj):
        return None
    return obj


def write_json_strict(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_safe(payload), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def parse_json_strict(path: Path) -> Any:
    txt = path.read_text(encoding="utf-8")
    return json.loads(
        txt, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(f"invalid constant: {x}"))
    )


def update_changelog_one_line(line: str) -> bool:
    CHANGELOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    before = CHANGELOG_PATH.read_text(encoding="utf-8") if CHANGELOG_PATH.exists() else ""
    before_size = len(before.encode("utf-8"))
    text = before
    if text and not text.endswith("\n"):
        text += "\n"
    text += line.rstrip("\n") + "\n"
    CHANGELOG_PATH.write_text(text, encoding="utf-8")
    after_size = len(text.encode("utf-8"))
    delta = after_size - before_size
    expected = len((line.rstrip("\n") + "\n").encode("utf-8"))
    return delta == expected and text.endswith(line.rstrip("\n") + "\n")


def normalize_to_base(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce").astype(float)
    return BASE_CAPITAL * (s / float(s.iloc[0]))


def compute_drawdown(equity_norm: pd.Series) -> pd.Series:
    s = pd.to_numeric(equity_norm, errors="coerce").astype(float)
    return s / s.cummax() - 1.0


def benchmark_metrics(series: pd.Series) -> dict[str, float]:
    s = pd.to_numeric(series, errors="coerce").astype(float)
    r = s.pct_change().fillna(0.0)
    years = max((len(s) - 1) / 252.0, 1.0 / 252.0)
    cagr = float((s.iloc[-1] / s.iloc[0]) ** (1.0 / years) - 1.0)
    mdd = float((s / s.cummax() - 1.0).min())
    vol = float(r.std(ddof=0))
    sharpe = float((r.mean() / vol) * np.sqrt(252.0)) if vol > 0 else np.nan
    return {"equity_final": float(s.iloc[-1]), "cagr": cagr, "mdd": mdd, "sharpe": sharpe}


def participation_metrics_safe(curve: pd.DataFrame) -> dict[str, float]:
    c = curve.copy()
    exposure = pd.to_numeric(c.get("exposure", pd.Series(np.nan, index=c.index)), errors="coerce")
    equity = pd.to_numeric(c.get("equity_end", pd.Series(np.nan, index=c.index)), errors="coerce")
    cash = pd.to_numeric(c.get("cash_end", pd.Series(np.nan, index=c.index)), errors="coerce")
    cash_weight = (cash / equity.replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan)
    regime = pd.to_numeric(c.get("regime_defensivo", pd.Series(np.nan, index=c.index)), errors="coerce")
    return {
        "time_in_market_frac": float((exposure > 0).mean()) if len(exposure) else np.nan,
        "avg_exposure": float(exposure.mean()) if len(exposure.dropna()) else np.nan,
        "days_cash_ge_090_frac": float((cash_weight >= 0.90).mean()) if len(cash_weight) else np.nan,
        "days_defensive_frac": float(regime.fillna(0).astype(bool).mean()) if len(regime) else np.nan,
    }


def find_true_intervals(mask: pd.Series, dates: pd.Series) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    intervals: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    start = None
    prev = None
    for m, dt in zip(mask.tolist(), dates.tolist()):
        if m and start is None:
            start = dt
        if not m and start is not None:
            intervals.append((start, prev if prev is not None else dt))
            start = None
        prev = dt
    if start is not None and prev is not None:
        intervals.append((start, prev))
    return intervals


def subperiod_return(curve: pd.DataFrame, start_date: str) -> float:
    c = curve.copy()
    c["date"] = pd.to_datetime(c["date"], errors="coerce").dt.normalize()
    c = c.sort_values("date").reset_index(drop=True)
    sub = c[c["date"] >= pd.Timestamp(start_date)].copy()
    if len(sub) < 2:
        return float("nan")
    eq = pd.to_numeric(sub["equity_end"], errors="coerce").astype(float)
    if not np.isfinite(eq.iloc[0]) or eq.iloc[0] <= 0:
        return float("nan")
    return float(eq.iloc[-1] / eq.iloc[0] - 1.0)


def get_metric(d: dict[str, Any], keys: list[str]) -> float | None:
    for key in keys:
        v = d.get(key)
        if v is None:
            continue
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        if np.isfinite(fv):
            return fv
    return None


def main() -> int:
    print(f"HEADER: {TASK_ID}")
    gates: dict[str, str] = {}
    retry_log: list[str] = []

    required_inputs = [
        INPUT_CANONICAL,
        INPUT_MACRO,
        INPUT_BLACKLIST,
        INPUT_SCORES,
        INPUT_T044_CURVE,
        INPUT_T063_CURVE,
        INPUT_T037_CURVE,
        INPUT_T044_SUMMARY,
        INPUT_T063_SUMMARY,
        INPUT_T037_SUMMARY,
        SCRIPT_BASE,
        SCRIPT_STYLE_REF,
    ]
    missing = [str(p) for p in required_inputs if not p.exists()]
    if missing:
        gates["G0_INPUTS_PRESENT"] = "FAIL"
        print("STEP GATES:")
        for k, v in gates.items():
            print(f"- {k}: {v} (missing: {', '.join(missing)})")
        print("RETRY LOG:")
        print("- none")
        print("ARTIFACT LINKS:")
        print(f"- {OUT_REPORT}")
        print("OVERALL STATUS: [[ FAIL ]]")
        return 1

    OUT_ABLATION.parent.mkdir(parents=True, exist_ok=True)
    OUT_EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)

    base = _load_base_module()
    engine = base.prepare_engine_data()
    t044_curve = pd.read_parquet(INPUT_T044_CURVE).copy()
    t063_curve = pd.read_parquet(INPUT_T063_CURVE).copy()
    t037_curve = pd.read_parquet(INPUT_T037_CURVE).copy()
    macro = pd.read_parquet(INPUT_MACRO).copy()
    t044_summary = parse_json_strict(INPUT_T044_SUMMARY)
    t063_summary = parse_json_strict(INPUT_T063_SUMMARY)
    t037_summary = parse_json_strict(INPUT_T037_SUMMARY)

    gates["G0_INPUTS_PRESENT"] = "PASS"

    t044_ret_2023plus = subperiod_return(t044_curve, "2023-01-01")
    if not np.isfinite(t044_ret_2023plus):
        gates["G1_T044_REF_2023_RETURN"] = "FAIL"
        print("STEP GATES:")
        for k, v in gates.items():
            print(f"- {k}: {v}")
        print("RETRY LOG:")
        print("- none")
        print("ARTIFACT LINKS:")
        print(f"- {OUT_REPORT}")
        print("OVERALL STATUS: [[ FAIL ]]")
        return 1
    gates["G1_T044_REF_2023_RETURN"] = "PASS"

    candidates: list[dict[str, Any]] = []
    for cadence in CADENCE_DAYS_GRID:
        for cap in BUY_TURNOVER_CAP_GRID:
            cap_tag = "NONE" if cap is None else f"{cap:.2f}".replace(".", "p")
            candidates.append(
                {
                    "candidate_id": f"CAD{cadence:02d}_CAP{cap_tag}",
                    "cadence_days": int(cadence),
                    "buy_turnover_cap_ratio": None if cap is None else float(cap),
                    "market_slope_window": int(REGIME_FIXED["market_slope_window"]),
                    "in_hyst_days": int(REGIME_FIXED["in_hyst_days"]),
                    "out_hyst_days": int(REGIME_FIXED["out_hyst_days"]),
                }
            )
    write_json_strict(
        OUT_CANDIDATE_SET,
        {
            "task_id": TASK_ID,
            "grid": {
                "buy_turnover_cap_ratio": BUY_TURNOVER_CAP_GRID,
                "cadence_days": CADENCE_DAYS_GRID,
            },
            "candidate_count": len(candidates),
            "candidates": candidates,
        },
    )

    rows: list[dict[str, Any]] = []
    feasible_rows: list[dict[str, Any]] = []
    best: dict[str, Any] | None = None
    best_key: tuple[Any, ...] | None = None

    for cand in candidates:
        ledger, curve, extra = base.run_candidate(
            engine=engine,
            slope_window=int(cand["market_slope_window"]),
            in_hyst=int(cand["in_hyst_days"]),
            out_hyst=int(cand["out_hyst_days"]),
            cadence_days=int(cand["cadence_days"]),
            buy_turnover_cap_ratio=cand["buy_turnover_cap_ratio"],
        )
        m = base.compute_metrics(curve["equity_end"])
        p = base.participation_metrics(curve)
        t_total = base.turnover_total(ledger, curve)
        t_reentry = base.subperiod_time_in_market(
            curve, base.REENTRY_SUBPERIOD_START, base.REENTRY_SUBPERIOD_END
        )
        eq_final = float(pd.to_numeric(curve["equity_end"], errors="coerce").astype(float).iloc[-1])
        ret_2023plus = subperiod_return(curve, "2023-01-01")
        excess_vs_t044 = float(ret_2023plus - t044_ret_2023plus) if np.isfinite(ret_2023plus) else float("nan")

        row = {
            "candidate_id": cand["candidate_id"],
            "cadence_days": int(cand["cadence_days"]),
            "buy_turnover_cap_ratio": cand["buy_turnover_cap_ratio"],
            "market_slope_window": int(cand["market_slope_window"]),
            "in_hyst_days": int(cand["in_hyst_days"]),
            "out_hyst_days": int(cand["out_hyst_days"]),
            "equity_final": eq_final,
            "CAGR": float(m["cagr"]),
            "MDD": float(m["mdd"]),
            "Sharpe": float(m["sharpe"]),
            "turnover_total": float(t_total),
            "time_in_market_frac": float(p["time_in_market_frac"]),
            "avg_exposure": float(p["avg_exposure"]),
            "days_cash_ge_090_frac": float(p["days_cash_ge_090_frac"]),
            "days_defensive_frac": float(p["days_defensive_frac"]),
            "reentry_subperiod_time_in_market": float(t_reentry),
            "num_switches": int(extra.get("num_switches", 0)),
            "return_2023plus": float(ret_2023plus),
            "t044_return_2023plus_ref": float(t044_ret_2023plus),
            "excess_return_2023plus_vs_t044": float(excess_vs_t044),
        }
        rows.append(row)

        feasible = np.isfinite(row["MDD"]) and row["MDD"] >= THRESHOLDS["MDD_total_min"]
        if feasible:
            feasible_rows.append(row)
            key = (
                -row["excess_return_2023plus_vs_t044"],
                -row["CAGR"],
                -row["Sharpe"],
                row["turnover_total"],
                row["candidate_id"],
            )
            if best_key is None or key < best_key:
                best_key = key
                best = {"cfg": cand, "row": row, "curve": curve, "ledger": ledger}

    ablation_df = pd.DataFrame(rows).sort_values(
        ["excess_return_2023plus_vs_t044", "CAGR", "Sharpe", "turnover_total"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)
    ablation_df.to_parquet(OUT_ABLATION, index=False)
    gates["G2_ABLATION_RESULTS_PRESENT"] = "PASS"

    write_json_strict(
        OUT_FEASIBILITY,
        {
            "task_id": TASK_ID,
            "thresholds": THRESHOLDS,
            "selection_order": SELECTION_ORDER,
            "total_candidates": int(len(candidates)),
            "feasible_count": int(len(feasible_rows)),
            "feasible_candidate_ids": [r["candidate_id"] for r in feasible_rows],
            "t044_return_2023plus_ref": float(t044_ret_2023plus),
        },
    )

    if best is None:
        gates["G3_FEASIBLE_NONEMPTY"] = "FAIL"
        OUT_REPORT.write_text(
            "\n".join(
                [
                    f"# {TASK_ID} Report",
                    "",
                    "## Resultado",
                    f"- feasible_count: 0 / {len(candidates)}",
                    "- Nenhum candidato atingiu o hard constraint MDD >= -0.30.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
    else:
        gates["G3_FEASIBLE_NONEMPTY"] = "PASS"
        cfg = best["cfg"]
        row = best["row"]
        win_curve = best["curve"].copy()
        win_ledger = best["ledger"].copy()

        write_json_strict(
            OUT_SELECTED_CFG,
            {
                "task_id": TASK_ID,
                "selected_candidate_id": cfg["candidate_id"],
                "cadence_days": int(cfg["cadence_days"]),
                "buy_turnover_cap_ratio": cfg["buy_turnover_cap_ratio"],
                "market_mu_window": int(base.MU_WINDOW),
                "market_slope_window": int(cfg["market_slope_window"]),
                "in_hyst_days": int(cfg["in_hyst_days"]),
                "out_hyst_days": int(cfg["out_hyst_days"]),
                "thresholds": THRESHOLDS,
                "selection_order": SELECTION_ORDER,
            },
        )
        win_curve.to_parquet(OUT_CURVE, index=False)
        win_ledger.to_parquet(OUT_LEDGER, index=False)
        write_json_strict(
            OUT_SUMMARY,
            {
                "task_id": TASK_ID,
                "selected_candidate_id": cfg["candidate_id"],
                "equity_final": float(row["equity_final"]),
                "cagr": float(row["CAGR"]),
                "mdd": float(row["MDD"]),
                "sharpe": float(row["Sharpe"]),
                "turnover_total": float(row["turnover_total"]),
                "time_in_market_frac": float(row["time_in_market_frac"]),
                "avg_exposure": float(row["avg_exposure"]),
                "days_cash_ge_090_frac": float(row["days_cash_ge_090_frac"]),
                "days_defensive_frac": float(row["days_defensive_frac"]),
                "reentry_subperiod_time_in_market": float(row["reentry_subperiod_time_in_market"]),
                "num_switches": int(row["num_switches"]),
                "return_2023plus": float(row["return_2023plus"]),
                "t044_return_2023plus_ref": float(row["t044_return_2023plus_ref"]),
                "excess_return_2023plus_vs_t044": float(row["excess_return_2023plus_vs_t044"]),
            },
        )
        write_json_strict(
            OUT_SELECTION_RULE,
            {
                "task_id": TASK_ID,
                "constraints": THRESHOLDS,
                "selection_order": SELECTION_ORDER,
                "selected_candidate_id": cfg["candidate_id"],
            },
        )
        gates["G4_WINNER_ARTIFACTS_PRESENT"] = "PASS"

        for df in [win_curve, t044_curve, t063_curve, t037_curve, macro]:
            df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
        common_dates = (
            set(win_curve["date"].dropna())
            & set(t044_curve["date"].dropna())
            & set(t063_curve["date"].dropna())
            & set(t037_curve["date"].dropna())
            & set(macro["date"].dropna())
        )
        common_dates = sorted(pd.to_datetime(list(common_dates)))
        if len(common_dates) < 30:
            gates["G5_PLOTLY_PRESENT"] = "FAIL"
            gates["G6_TRACE_SIGNATURE"] = "FAIL"
            raise RuntimeError("intersecao de datas insuficiente para plotly")

        def align_curve(df: pd.DataFrame) -> pd.DataFrame:
            out = df[df["date"].isin(common_dates)].copy().sort_values("date").reset_index(drop=True)
            out["equity_norm"] = normalize_to_base(out["equity_end"])
            return out

        wina = align_curve(win_curve)
        t044a = align_curve(t044_curve)
        t063a = align_curve(t063_curve)
        t037a = align_curve(t037_curve)
        macroa = macro[macro["date"].isin(common_dates)].copy().sort_values("date").reset_index(drop=True)

        cdi_source = "cdi_log_daily"
        if "cdi_log_daily" in macroa.columns:
            cdi_log = pd.to_numeric(macroa["cdi_log_daily"], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
            cdi_growth = np.exp(np.cumsum(cdi_log.to_numpy(dtype=float)))
        elif "cdi_daily" in macroa.columns:
            cdi_source = "cdi_daily"
            cdi_daily = pd.to_numeric(macroa["cdi_daily"], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
            cdi_growth = (1.0 + cdi_daily.to_numpy(dtype=float)).cumprod()
        elif "cdi_rate_daily" in macroa.columns:
            cdi_source = "cdi_rate_daily"
            cdi_daily = pd.to_numeric(macroa["cdi_rate_daily"], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
            cdi_growth = (1.0 + cdi_daily.to_numpy(dtype=float)).cumprod()
        else:
            raise RuntimeError("macro sem cdi_log_daily/cdi_daily/cdi_rate_daily")
        cdi_rebased = BASE_CAPITAL * (cdi_growth / float(cdi_growth[0]))

        if "ibov_close" not in macroa.columns:
            raise RuntimeError("macro sem ibov_close")
        ibov_close = pd.to_numeric(macroa["ibov_close"], errors="coerce").ffill().bfill().astype(float)
        ibov_rebased = normalize_to_base(ibov_close)

        dd67 = compute_drawdown(wina["equity_norm"])
        dd44 = compute_drawdown(t044a["equity_norm"])
        dd63 = compute_drawdown(t063a["equity_norm"])
        dd37 = compute_drawdown(t037a["equity_norm"])

        fig = make_subplots(
            rows=3,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            row_heights=[0.55, 0.25, 0.20],
            specs=[[{"type": "xy"}], [{"type": "xy"}], [{"type": "table"}]],
            subplot_titles=[
                "Equity Normalizada (Base R$100k): T067 vs T044 vs T063 vs T037 + CDI + IBOV",
                "Drawdown Overlay: T067 vs T044 vs T063 vs T037",
                "Tabela de Metricas",
            ],
        )

        fig.add_trace(go.Scatter(x=wina["date"], y=wina["equity_norm"], mode="lines", name="T067 Aggressive Winner", line=dict(color="#2ca02c", width=2.8)), row=1, col=1)
        fig.add_trace(go.Scatter(x=t044a["date"], y=t044a["equity_norm"], mode="lines", name="T044 Winner Phase2", line=dict(color="#d62728", dash="dash", width=2.0)), row=1, col=1)
        fig.add_trace(go.Scatter(x=t063a["date"], y=t063a["equity_norm"], mode="lines", name="T063 Reentry Fix", line=dict(color="#9467bd", dash="dot", width=1.9)), row=1, col=1)
        fig.add_trace(go.Scatter(x=t037a["date"], y=t037a["equity_norm"], mode="lines", name="T037 Baseline", line=dict(color="#1f77b4", dash="dot", width=1.9)), row=1, col=1)
        fig.add_trace(go.Scatter(x=wina["date"], y=cdi_rebased, mode="lines", name="CDI Acumulado", line=dict(color="#7f7f7f", width=1.7)), row=1, col=1)
        fig.add_trace(go.Scatter(x=wina["date"], y=ibov_rebased, mode="lines", name="Ibovespa ^BVSP", line=dict(color="#111111", width=1.7)), row=1, col=1)

        fig.add_trace(go.Scatter(x=wina["date"], y=dd67, mode="lines", name="DD T067", line=dict(color="#2ca02c", width=1.9)), row=2, col=1)
        fig.add_trace(go.Scatter(x=t044a["date"], y=dd44, mode="lines", name="DD T044", line=dict(color="#d62728", dash="dash", width=1.6)), row=2, col=1)
        fig.add_trace(go.Scatter(x=t063a["date"], y=dd63, mode="lines", name="DD T063", line=dict(color="#9467bd", dash="dot", width=1.6)), row=2, col=1)
        fig.add_trace(go.Scatter(x=t037a["date"], y=dd37, mode="lines", name="DD T037", line=dict(color="#1f77b4", dash="dot", width=1.6)), row=2, col=1)

        for df, color in [(wina, "rgba(44, 160, 44, 0.08)"), (t044a, "rgba(214, 39, 40, 0.06)")]:
            regime = pd.to_numeric(df.get("regime_defensivo", 0), errors="coerce").fillna(0).astype(bool)
            for x0, x1 in find_true_intervals(regime, df["date"]):
                fig.add_vrect(x0=x0, x1=x1, fillcolor=color, line_width=0, layer="below", row=1, col=1)
                fig.add_vrect(x0=x0, x1=x1, fillcolor=color, line_width=0, layer="below", row=2, col=1)

        pm67 = participation_metrics_safe(wina)
        pm44 = participation_metrics_safe(t044a)
        pm63 = participation_metrics_safe(t063a)
        pm37 = participation_metrics_safe(t037a)

        bm_cdi = benchmark_metrics(pd.Series(cdi_rebased))
        bm_ibov = benchmark_metrics(pd.Series(ibov_rebased))
        m44 = t044_summary.get("metrics_total", {})
        m63 = t063_summary
        m37 = t037_summary

        table_rows = ["T067", "T044", "T063", "T037", "CDI", "IBOV"]
        table_equity = [
            float(row["equity_final"]),
            get_metric(m44, ["equity_final"]),
            get_metric(m63, ["equity_final"]),
            get_metric(m37, ["equity_final"]),
            bm_cdi["equity_final"],
            bm_ibov["equity_final"],
        ]
        table_cagr = [
            float(row["CAGR"]),
            get_metric(m44, ["CAGR", "cagr"]),
            get_metric(m63, ["cagr", "CAGR"]),
            get_metric(m37, ["cagr", "CAGR"]),
            bm_cdi["cagr"],
            bm_ibov["cagr"],
        ]
        table_mdd = [
            float(row["MDD"]),
            get_metric(m44, ["MDD", "mdd"]),
            get_metric(m63, ["mdd", "MDD"]),
            get_metric(m37, ["mdd", "MDD"]),
            bm_cdi["mdd"],
            bm_ibov["mdd"],
        ]
        table_sharpe = [
            float(row["Sharpe"]),
            get_metric(m44, ["sharpe"]),
            get_metric(m63, ["sharpe"]),
            get_metric(m37, ["sharpe"]),
            bm_cdi["sharpe"],
            bm_ibov["sharpe"],
        ]
        table_turnover = [
            float(row["turnover_total"]),
            get_metric(m44, ["turnover_total"]),
            get_metric(m63, ["turnover_total"]),
            get_metric(m37, ["turnover_total"]),
            None,
            None,
        ]
        table_tim = [
            float(row["time_in_market_frac"]),
            pm44["time_in_market_frac"],
            pm63["time_in_market_frac"],
            pm37["time_in_market_frac"],
            None,
            None,
        ]

        fig.add_trace(
            go.Table(
                header=dict(
                    values=[
                        "Serie",
                        "Equity Final",
                        "CAGR",
                        "MDD",
                        "Sharpe",
                        "Turnover",
                        "Time In Market",
                    ],
                    fill_color="#f0f0f0",
                ),
                cells=dict(
                    values=[
                        table_rows,
                        [f"{v:,.2f}" if v is not None else "-" for v in table_equity],
                        [f"{v:.2%}" if v is not None else "-" for v in table_cagr],
                        [f"{v:.2%}" if v is not None else "-" for v in table_mdd],
                        [f"{v:.2f}" if v is not None else "-" for v in table_sharpe],
                        [f"{v:.2f}" if v is not None else "-" for v in table_turnover],
                        [f"{v:.2%}" if v is not None else "-" for v in table_tim],
                    ],
                    fill_color="white",
                ),
                name="Tabela de Metricas",
            ),
            row=3,
            col=1,
        )

        fig.update_layout(
            title="STATE 3 Phase 4A - Comparative (T067 Aggressive vs T044/T063/T037)",
            template="plotly_white",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0),
            height=1020,
        )
        fig.update_yaxes(title_text="Patrimonio (R$)", row=1, col=1)
        fig.update_yaxes(title_text="Drawdown", tickformat=".0%", row=2, col=1)
        fig.update_xaxes(title_text="Data", row=2, col=1)
        fig.write_html(str(OUT_HTML), include_plotlyjs="cdn", full_html=True)

        win_ret_2023 = subperiod_return(wina, "2023-01-01")
        t044_ret_2023 = subperiod_return(t044a, "2023-01-01")
        metrics_snapshot = {
            "task_id": TASK_ID,
            "date_range_common": {
                "start": str(common_dates[0].date()),
                "end": str(common_dates[-1].date()),
                "n_dates": len(common_dates),
            },
            "cdi_source_used": cdi_source,
            "selection_winner": {
                "candidate_id": cfg["candidate_id"],
                "cadence_days": cfg["cadence_days"],
                "buy_turnover_cap_ratio": cfg["buy_turnover_cap_ratio"],
                "return_2023plus": float(win_ret_2023),
                "t044_return_2023plus_ref": float(t044_ret_2023),
                "excess_return_2023plus_vs_t044": float(win_ret_2023 - t044_ret_2023),
            },
            "final_equity_norm": {
                "T067": float(wina["equity_norm"].iloc[-1]),
                "T044": float(t044a["equity_norm"].iloc[-1]),
                "T063": float(t063a["equity_norm"].iloc[-1]),
                "T037": float(t037a["equity_norm"].iloc[-1]),
                "CDI": float(cdi_rebased[-1]),
                "IBOV": float(ibov_rebased.iloc[-1]),
            },
        }
        write_json_strict(OUT_METRICS_SNAPSHOT, metrics_snapshot)

        plot_inventory = {
            "task_id": TASK_ID,
            "output_html": str(OUT_HTML),
            "expected_equity_traces": 6,
            "expected_drawdown_traces": 4,
            "expected_table_traces": 1,
            "total_traces": len(fig.data),
            "trace_names": [trace.name for trace in fig.data],
        }
        write_json_strict(OUT_PLOT_INVENTORY, plot_inventory)

        report_lines = [
            f"# {TASK_ID} Report",
            "",
            "## 1) Objetivo",
            "- Superar o trecho CDI-bloqueado da T044 (recorte 2023+) com alocacao agressiva controlada por MDD.",
            "",
            "## 2) Grid testado",
            f"- BUY_TURNOVER_CAP_GRID={BUY_TURNOVER_CAP_GRID}",
            f"- CADENCE_DAYS_GRID={CADENCE_DAYS_GRID} (pregoes)",
            f"- regime_fixado: slope_window={REGIME_FIXED['market_slope_window']}, in_hyst={REGIME_FIXED['in_hyst_days']}, out_hyst={REGIME_FIXED['out_hyst_days']}",
            "",
            "## 3) Constraints e selecao",
            f"- hard_constraint: MDD >= {THRESHOLDS['MDD_total_min']}",
            f"- selection_order: {SELECTION_ORDER}",
            f"- selected_candidate_id: {cfg['candidate_id']}",
            "",
            "## 4) Winner metrics (total)",
            f"- equity_final: {row['equity_final']:.2f}",
            f"- CAGR: {row['CAGR']:.6f}",
            f"- MDD: {row['MDD']:.6f}",
            f"- Sharpe: {row['Sharpe']:.6f}",
            f"- turnover_total: {row['turnover_total']:.6f}",
            f"- time_in_market_frac: {row['time_in_market_frac']:.6f}",
            f"- avg_exposure: {row['avg_exposure']:.6f}",
            "",
            "## 5) Comparacao explicita 2023+ (T067 vs T044)",
            f"- T067 return_2023plus: {row['return_2023plus']:.6f}",
            f"- T044 return_2023plus_ref: {row['t044_return_2023plus_ref']:.6f}",
            f"- excess_return_2023plus_vs_t044: {row['excess_return_2023plus_vs_t044']:.6f}",
            "",
            "## 6) Artefatos",
            f"- `{OUT_ABLATION}`",
            f"- `{OUT_SELECTED_CFG}`",
            f"- `{OUT_CURVE}`",
            f"- `{OUT_LEDGER}`",
            f"- `{OUT_SUMMARY}`",
            f"- `{OUT_HTML}`",
            f"- `{OUT_METRICS_SNAPSHOT}`",
            f"- `{OUT_PLOT_INVENTORY}`",
            f"- `{OUT_REPORT}`",
            f"- `{OUT_MANIFEST}`",
        ]
        OUT_REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

        gates["G5_PLOTLY_PRESENT"] = "PASS" if OUT_HTML.exists() else "FAIL"
        gates["G6_TRACE_SIGNATURE"] = "PASS" if len(fig.data) == 11 else "FAIL"

    ch_ok = update_changelog_one_line(TRACEABILITY_LINE)
    gates["G_CHLOG_UPDATED"] = "PASS" if ch_ok else "FAIL"

    script_path = Path(__file__).resolve()
    inputs_for_manifest = required_inputs + [script_path]
    outputs_for_manifest = [
        OUT_ABLATION,
        OUT_SELECTED_CFG,
        OUT_CURVE,
        OUT_LEDGER,
        OUT_SUMMARY,
        OUT_HTML,
        OUT_REPORT,
        OUT_CANDIDATE_SET,
        OUT_SELECTION_RULE,
        OUT_FEASIBILITY,
        OUT_METRICS_SNAPSHOT,
        OUT_PLOT_INVENTORY,
        OUT_MANIFEST,
        CHANGELOG_PATH,
    ]
    hash_targets = [p for p in inputs_for_manifest + outputs_for_manifest if p.exists() and p != OUT_MANIFEST]
    write_json_strict(
        OUT_MANIFEST,
        {
            "task_id": TASK_ID,
            "inputs_consumed": [str(p) for p in inputs_for_manifest],
            "outputs_produced": [str(p) for p in outputs_for_manifest],
            "hashes_sha256": {str(p): sha256_file(p) for p in hash_targets},
        },
    )
    gates["Gx_HASH_MANIFEST_PRESENT"] = "PASS" if OUT_MANIFEST.exists() else "FAIL"

    print("STEP GATES:")
    for k, v in gates.items():
        print(f"- {k}: {v}")
    print("RETRY LOG:")
    if retry_log:
        for r in retry_log:
            print(f"- {r}")
    else:
        print("- none")
    print("ARTIFACT LINKS:")
    print(f"- {OUT_ABLATION}")
    if OUT_SELECTED_CFG.exists():
        print(f"- {OUT_SELECTED_CFG}")
    if OUT_CURVE.exists():
        print(f"- {OUT_CURVE}")
    if OUT_LEDGER.exists():
        print(f"- {OUT_LEDGER}")
    if OUT_SUMMARY.exists():
        print(f"- {OUT_SUMMARY}")
    if OUT_HTML.exists():
        print(f"- {OUT_HTML}")
    print(f"- {OUT_REPORT}")
    print(f"- {OUT_CANDIDATE_SET}")
    print(f"- {OUT_SELECTION_RULE}")
    print(f"- {OUT_FEASIBILITY}")
    if OUT_METRICS_SNAPSHOT.exists():
        print(f"- {OUT_METRICS_SNAPSHOT}")
    if OUT_PLOT_INVENTORY.exists():
        print(f"- {OUT_PLOT_INVENTORY}")
    print(f"- {OUT_MANIFEST}")
    print(f"- {CHANGELOG_PATH}")

    overall_pass = all(v == "PASS" for v in gates.values())
    print(f"OVERALL STATUS: [[ {'PASS' if overall_pass else 'FAIL'} ]]")
    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
