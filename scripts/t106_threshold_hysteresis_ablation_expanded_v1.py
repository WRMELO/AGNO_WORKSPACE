#!/home/wilson/AGNO_WORKSPACE/.venv/bin/python
from __future__ import annotations

import hashlib
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from xgboost import XGBClassifier


if not ("agno_env" in sys.prefix or ".venv" in sys.prefix):
    raise RuntimeError("FATAL: Not in agno_env/.venv")


TASK_ID = "T106"
RUN_ID = "T106-ML-TRIGGER-TUNING-EXPANDED-V1"
ROOT = Path("/home/wilson/AGNO_WORKSPACE")
BASE_CAPITAL = 100000.0

PYTHON_ENV = ROOT / ".venv/bin/python"
CHANGELOG_PATH = ROOT / "00_Strategy/changelog.md"
TRACEABILITY_LINE = (
    "- 2026-03-03T21:48:01Z | EXEC: T106 PASS/FAIL. Artefatos: "
    "scripts/t106_threshold_hysteresis_ablation_expanded_v1.py; "
    "src/data_engine/portfolio/T106_ML_TRIGGER_EXPANDED_SELECTED_CONFIG.json; "
    "src/data_engine/portfolio/T106_ML_TRIGGER_EXPANDED_ABLATION_RESULTS.parquet; "
    "outputs/governanca/T106-ML-TRIGGER-TUNING-EXPANDED-V1_manifest.json"
)

INPUT_T072_CURVE = ROOT / "src/data_engine/portfolio/T072_PORTFOLIO_CURVE_DUAL_MODE.parquet"
INPUT_T072_CONFIG = ROOT / "src/data_engine/portfolio/T072_DUAL_MODE_SELECTED_CONFIG.json"
INPUT_T105_PREDS = ROOT / "src/data_engine/features/T105_V1_PREDICTIONS.parquet"
INPUT_T104_DATASET = ROOT / "src/data_engine/features/T104_DATASET_DAILY.parquet"
INPUT_T105_VARIANT = ROOT / "outputs/governanca/T105-V1-XGBOOST-RETRAIN-EXPANDED-V1_evidence/variant_comparison.json"
INPUT_C060_CURVE = ROOT / "outputs/governanca/T079-PHASE6-PLOTLY-COMPARATIVE-V1_evidence/c060_curve_snapshot.parquet"

OUT_SCRIPT = ROOT / "scripts/t106_threshold_hysteresis_ablation_expanded_v1.py"
OUT_SELECTED_CFG = ROOT / "src/data_engine/portfolio/T106_ML_TRIGGER_EXPANDED_SELECTED_CONFIG.json"
OUT_ABLATION = ROOT / "src/data_engine/portfolio/T106_ML_TRIGGER_EXPANDED_ABLATION_RESULTS.parquet"
OUT_CURVE = ROOT / "src/data_engine/portfolio/T106_PORTFOLIO_CURVE_ML_TRIGGER_EXPANDED.parquet"
OUT_SUMMARY = ROOT / "src/data_engine/portfolio/T106_BASELINE_SUMMARY_ML_TRIGGER_EXPANDED.json"
OUT_PLOT = ROOT / "outputs/plots/T106_STATE3_PHASE8C_ML_TUNING_COMPARATIVE.html"
OUT_REPORT = ROOT / "outputs/governanca/T106-ML-TRIGGER-TUNING-EXPANDED-V1_report.md"
OUT_MANIFEST = ROOT / "outputs/governanca/T106-ML-TRIGGER-TUNING-EXPANDED-V1_manifest.json"
OUT_EVIDENCE_DIR = ROOT / "outputs/governanca/T106-ML-TRIGGER-TUNING-EXPANDED-V1_evidence"
OUT_SELECTION_RULE = OUT_EVIDENCE_DIR / "selection_rule.json"
OUT_CANDIDATE_SET = OUT_EVIDENCE_DIR / "candidate_set.json"
OUT_METRICS_SNAPSHOT = OUT_EVIDENCE_DIR / "metrics_snapshot.json"
OUT_ACID_WINDOW = OUT_EVIDENCE_DIR / "acid_window_definition.json"
OUT_JOIN_COVERAGE = OUT_EVIDENCE_DIR / "join_coverage.json"
OUT_VARIANT_FIN = OUT_EVIDENCE_DIR / "variant_comparison_financial.json"

THR_GRID = [0.05, 0.08, 0.10, 0.12, 0.15, 0.20, 0.25]
H_IN_GRID = [1, 2, 3]
H_OUT_GRID = [2, 3, 4, 5]
MAX_SWITCHES_TRAIN = 40
MDD_MIN_TRAIN = -0.30

ACID_START = pd.Timestamp("2024-11-01")
ACID_END = pd.Timestamp("2025-11-30")

CORE_ALLOWLIST = [
    "equity_mom_63d",
    "equity_dd_252d",
    "equity_vol_63d",
    "equity_vol_21d",
    "equity_ret_21d",
    "signal_excess_w",
    "n_positions",
    "sp500_vol_21d",
    "spc_xbar_special_frac",
    "equity_vs_cdi_21d",
    "equity_ret_5d",
    "ibov_ret_21d",
    "ibov_minus_cdi_21d",
    "m3_frac_top_decile",
]


@dataclass
class Gate:
    name: str
    passed: bool
    detail: str


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
    if isinstance(obj, pd.Timestamp):
        return obj.strftime("%Y-%m-%d")
    if pd.isna(obj):
        return None
    return obj


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_safe(payload), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


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


def apply_hysteresis(prob: pd.Series, thr: float, h_in: int, h_out: int) -> pd.Series:
    vals = pd.to_numeric(prob, errors="coerce").fillna(0.0).astype(float).values
    state = False
    in_count = 0
    out_count = 0
    out: list[int] = []
    for p in vals:
        if p >= thr:
            in_count += 1
            out_count = 0
        else:
            out_count += 1
            in_count = 0
        if not state and in_count >= h_in:
            state = True
        elif state and out_count >= h_out:
            state = False
        out.append(1 if state else 0)
    return pd.Series(out, index=prob.index, dtype="int64")


def calc_switches(state_cash: pd.Series) -> int:
    s = pd.to_numeric(state_cash, errors="coerce").fillna(0).astype(int)
    return int((s.diff().abs() == 1).sum())


def build_overlay_curve(df: pd.DataFrame, state_cash: pd.Series, curve_name: str) -> pd.DataFrame:
    out = df[["date", "split", "ret_t072", "ret_cdi"]].copy()
    out["state_cash"] = pd.to_numeric(state_cash, errors="coerce").fillna(0).astype(int)
    out["ret_strategy"] = np.where(out["state_cash"] == 1, out["ret_cdi"], out["ret_t072"])
    out["equity_end_norm"] = BASE_CAPITAL * (1.0 + out["ret_strategy"]).cumprod()
    out.loc[out.index[0], "equity_end_norm"] = BASE_CAPITAL
    out["drawdown"] = drawdown(out["equity_end_norm"])
    out["switches_cumsum"] = (out["state_cash"].diff().abs() == 1).fillna(False).astype(int).cumsum()
    out["curve_name"] = curve_name
    return out


def split_metrics(curve: pd.DataFrame) -> dict[str, dict[str, float]]:
    train = curve[curve["split"] == "TRAIN"].copy()
    hold = curve[curve["split"] == "HOLDOUT"].copy()
    acid = curve[(curve["date"] >= ACID_START) & (curve["date"] <= ACID_END) & (curve["split"] == "HOLDOUT")].copy()
    out: dict[str, dict[str, float]] = {}
    for k, sub in [("train", train), ("holdout", hold), ("acid", acid)]:
        if len(sub) < 2:
            out[k] = {"equity_final": np.nan, "cagr": np.nan, "mdd": np.nan, "sharpe": np.nan, "switches": np.nan, "time_in_cash_frac": np.nan}
            continue
        m = metrics(sub["equity_end_norm"])
        m["switches"] = float(calc_switches(sub["state_cash"]))
        m["time_in_cash_frac"] = float(sub["state_cash"].mean())
        out[k] = m
    return out


def append_changelog_one_line(line: str) -> bool:
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


def pick_c060_curve() -> pd.DataFrame | None:
    if not INPUT_C060_CURVE.exists():
        return None
    c060 = pd.read_parquet(INPUT_C060_CURVE).copy()
    if "date" not in c060.columns:
        return None
    c060["date"] = pd.to_datetime(c060["date"])
    if "equity_end_norm" in c060.columns:
        eq = pd.to_numeric(c060["equity_end_norm"], errors="coerce")
    elif "equity_end" in c060.columns:
        eq = pd.to_numeric(c060["equity_end"], errors="coerce")
    else:
        return None
    c060 = c060[["date"]].copy()
    c060["equity_end_norm"] = eq
    c060 = c060.dropna().sort_values("date")
    c060["drawdown"] = drawdown(c060["equity_end_norm"])
    return c060


def make_core_predictions(t104: pd.DataFrame, core_params: dict[str, Any], core_threshold: float) -> pd.DataFrame:
    use_cols = [c for c in CORE_ALLOWLIST if c in t104.columns]
    train = t104[t104["split"] == "TRAIN"].copy()
    hold = t104[t104["split"] == "HOLDOUT"].copy()
    x_train = train[use_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    y_train = train["y_cash"].astype(int)
    x_hold = hold[use_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)

    params = {
        "n_estimators": int(core_params["n_estimators"]),
        "max_depth": int(core_params["max_depth"]),
        "learning_rate": float(core_params["learning_rate"]),
        "subsample": float(core_params["subsample"]),
        "colsample_bytree": float(core_params["colsample_bytree"]),
        "min_child_weight": int(core_params["min_child_weight"]),
        "reg_lambda": float(core_params["reg_lambda"]),
        "scale_pos_weight": float(core_params["scale_pos_weight"]),
    }
    model = XGBClassifier(objective="binary:logistic", eval_metric="logloss", random_state=42, n_jobs=1, **params)
    model.fit(x_train, y_train)
    p_train = model.predict_proba(x_train)[:, 1]
    p_hold = model.predict_proba(x_hold)[:, 1]
    yhat_train = (p_train >= core_threshold).astype(int)
    yhat_hold = (p_hold >= core_threshold).astype(int)
    preds = pd.concat(
        [
            pd.DataFrame({"date": train["date"], "split": "TRAIN", "y_cash": y_train.values, "y_proba_cash": p_train, "y_pred_cash": yhat_train}),
            pd.DataFrame({"date": hold["date"], "split": "HOLDOUT", "y_cash": hold["y_cash"].astype(int).values, "y_proba_cash": p_hold, "y_pred_cash": yhat_hold}),
        ],
        ignore_index=True,
    ).sort_values("date")
    return preds


def run_variant_ablation(variant: str, merged: pd.DataFrame, baseline_train_equity: float) -> tuple[pd.DataFrame, dict[str, Any], pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    candidate_id = 0
    curves_by_id: dict[str, pd.DataFrame] = {}
    for thr in THR_GRID:
        for h_in in H_IN_GRID:
            for h_out in H_OUT_GRID:
                candidate_id += 1
                cid = f"{variant}_C{candidate_id:03d}"
                state = apply_hysteresis(merged["y_proba_cash"], thr=thr, h_in=h_in, h_out=h_out)
                curve = build_overlay_curve(merged, state, cid)
                sm = split_metrics(curve)
                eq_train = float(sm["train"]["equity_final"])
                mdd_train = float(sm["train"]["mdd"])
                sw_train = int(sm["train"]["switches"])
                feasible = (eq_train >= baseline_train_equity) and (mdd_train >= MDD_MIN_TRAIN) and (sw_train <= MAX_SWITCHES_TRAIN)
                rows.append(
                    {
                        "variant": variant,
                        "candidate_id": cid,
                        "thr": float(thr),
                        "h_in": int(h_in),
                        "h_out": int(h_out),
                        "feasible": bool(feasible),
                        "equity_final_train": eq_train,
                        "cagr_train": float(sm["train"]["cagr"]),
                        "mdd_train": mdd_train,
                        "sharpe_train": float(sm["train"]["sharpe"]),
                        "switches_train": sw_train,
                        "time_in_cash_frac_train": float(sm["train"]["time_in_cash_frac"]),
                        "equity_final_holdout": float(sm["holdout"]["equity_final"]),
                        "cagr_holdout": float(sm["holdout"]["cagr"]),
                        "mdd_holdout": float(sm["holdout"]["mdd"]),
                        "sharpe_holdout": float(sm["holdout"]["sharpe"]),
                        "switches_holdout": int(sm["holdout"]["switches"]),
                        "time_in_cash_frac_holdout": float(sm["holdout"]["time_in_cash_frac"]),
                        "equity_final_acid": float(sm["acid"]["equity_final"]),
                        "cagr_acid": float(sm["acid"]["cagr"]),
                        "mdd_acid": float(sm["acid"]["mdd"]),
                        "sharpe_acid": float(sm["acid"]["sharpe"]),
                        "switches_acid": int(sm["acid"]["switches"]),
                        "time_in_cash_frac_acid": float(sm["acid"]["time_in_cash_frac"]),
                        "excess_vs_t072_train": eq_train - baseline_train_equity,
                    }
                )
                curves_by_id[cid] = curve
    cdf = pd.DataFrame(rows)
    feasible = cdf[cdf["feasible"]].copy()
    if feasible.empty:
        winner = cdf.sort_values(
            by=["equity_final_train", "sharpe_train", "switches_train", "candidate_id"],
            ascending=[False, False, True, True],
        ).iloc[0].to_dict()
    else:
        winner = feasible.sort_values(
            by=["equity_final_train", "sharpe_train", "switches_train", "candidate_id"],
            ascending=[False, False, True, True],
        ).iloc[0].to_dict()
    return cdf, winner, curves_by_id[str(winner["candidate_id"])]


def main() -> int:
    gates: list[Gate] = []
    retry_log: list[str] = []
    try:
        for p in [OUT_SCRIPT, OUT_SELECTED_CFG, OUT_ABLATION, OUT_CURVE, OUT_SUMMARY, OUT_PLOT, OUT_REPORT, OUT_MANIFEST]:
            p.parent.mkdir(parents=True, exist_ok=True)
        OUT_EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

        gate_env = PYTHON_ENV.exists() and (".venv" in sys.prefix or "agno_env" in sys.prefix)
        gates.append(Gate("G_ENV_VENV", gate_env, f"python={sys.executable}"))

        inputs_ok = all(
            p.exists()
            for p in [INPUT_T072_CURVE, INPUT_T072_CONFIG, INPUT_T105_PREDS, INPUT_T104_DATASET, INPUT_T105_VARIANT]
        )
        gates.append(
            Gate(
                "G_INPUTS_PRESENT",
                inputs_ok,
                (
                    f"t072_curve={INPUT_T072_CURVE.exists()} t072_cfg={INPUT_T072_CONFIG.exists()} "
                    f"t105_preds={INPUT_T105_PREDS.exists()} t104_dataset={INPUT_T104_DATASET.exists()} "
                    f"variant_cmp={INPUT_T105_VARIANT.exists()}"
                ),
            )
        )
        if not inputs_ok:
            raise FileNotFoundError("Inputs obrigatorios ausentes.")

        t072 = pd.read_parquet(INPUT_T072_CURVE).copy()
        t072_cfg = json.loads(INPUT_T072_CONFIG.read_text(encoding="utf-8"))
        pred_ext = pd.read_parquet(INPUT_T105_PREDS).copy()
        t104 = pd.read_parquet(INPUT_T104_DATASET).copy()
        variant_cmp = json.loads(INPUT_T105_VARIANT.read_text(encoding="utf-8"))
        core_cfg = variant_cmp["CORE"]

        t072["date"] = pd.to_datetime(t072["date"])
        pred_ext["date"] = pd.to_datetime(pred_ext["date"])
        t104["date"] = pd.to_datetime(t104["date"])

        t072["ret_t072"] = pd.to_numeric(t072["equity_end"], errors="coerce").pct_change().fillna(0.0)
        if "cdi_daily" in t072.columns:
            t072["ret_cdi"] = pd.to_numeric(t072["cdi_daily"], errors="coerce").fillna(0.0)
        elif "cdi_credit" in t072.columns:
            eq = pd.to_numeric(t072["equity_end"], errors="coerce").replace(0.0, np.nan)
            t072["ret_cdi"] = (pd.to_numeric(t072["cdi_credit"], errors="coerce") / eq).fillna(0.0)
        else:
            raise ValueError("Sem cdi_daily/cdi_credit para retorno CDI.")

        req_cols = {"date", "split", "y_cash", "y_proba_cash", "y_pred_cash"}
        ext_schema_ok = req_cols.issubset(set(pred_ext.columns))
        gates.append(Gate("G_EXT_PRED_SCHEMA_OK", ext_schema_ok, f"cols={sorted(list(pred_ext.columns))}"))
        if not ext_schema_ok:
            raise ValueError("Schema T105 preds invalido.")

        pred_core = make_core_predictions(
            t104=t104,
            core_params=core_cfg["winner_params"],
            core_threshold=float(core_cfg["winner_threshold"]),
        )
        core_schema_ok = req_cols.issubset(set(pred_core.columns))
        gates.append(Gate("G_CORE_PRED_RETRAINED", core_schema_ok, "CORE predictions generated from T104 retrain"))
        if not core_schema_ok:
            raise ValueError("Falha ao gerar predições CORE.")

        merged_ext = t072.merge(
            pred_ext[["date", "split", "y_cash", "y_proba_cash", "y_pred_cash"]],
            on="date",
            how="inner",
            validate="one_to_one",
        ).sort_values("date")
        merged_core = t072.merge(
            pred_core[["date", "split", "y_cash", "y_proba_cash", "y_pred_cash"]],
            on="date",
            how="inner",
            validate="one_to_one",
        ).sort_values("date")
        merged_ext = merged_ext.reset_index(drop=True)
        merged_core = merged_core.reset_index(drop=True)

        split_counts = merged_ext["split"].value_counts().to_dict()
        coverage_payload = {
            "rows_merged_ext": int(len(merged_ext)),
            "rows_merged_core": int(len(merged_core)),
            "rows_t072": int(len(t072)),
            "rows_t105_preds": int(len(pred_ext)),
            "rows_core_preds": int(len(pred_core)),
            "split_counts_ext": split_counts,
            "min_date": merged_ext["date"].min(),
            "max_date": merged_ext["date"].max(),
        }
        write_json(OUT_JOIN_COVERAGE, coverage_payload)
        join_ok = (
            len(merged_ext) == 1902
            and len(merged_core) == 1902
            and split_counts.get("TRAIN", 0) == 1115
            and split_counts.get("HOLDOUT", 0) == 787
        )
        gates.append(Gate("G_JOIN_COVERAGE_OK", join_ok, f"split={split_counts} rows_ext={len(merged_ext)} rows_core={len(merged_core)}"))
        if not join_ok:
            raise ValueError("Cobertura inesperada no merge.")

        acid_mask = (merged_ext["date"] >= ACID_START) & (merged_ext["date"] <= ACID_END)
        acid_holdout_ok = bool((merged_ext.loc[acid_mask, "split"] == "HOLDOUT").all())
        gates.append(Gate("G_ACID_WINDOW_HOLDOUT_OK", acid_holdout_ok, f"acid_rows={int(acid_mask.sum())}"))

        baseline = merged_ext[["date", "split", "ret_t072"]].copy()
        baseline["state_cash"] = 0
        baseline["ret_strategy"] = baseline["ret_t072"]
        baseline["equity_end_norm"] = BASE_CAPITAL * (1.0 + baseline["ret_strategy"]).cumprod()
        baseline.loc[baseline.index[0], "equity_end_norm"] = BASE_CAPITAL
        baseline["drawdown"] = drawdown(baseline["equity_end_norm"])
        baseline["switches_cumsum"] = 0
        baseline["curve_name"] = "T072_BASELINE"
        baseline_split = split_metrics(baseline)
        baseline_train_equity = float(baseline_split["train"]["equity_final"])

        abl_ext, win_ext, curve_ext = run_variant_ablation("CORE_PLUS_MACRO_EXPANDED_FX", merged_ext, baseline_train_equity)
        abl_core, win_core, curve_core = run_variant_ablation("CORE", merged_core, baseline_train_equity)
        ablation = pd.concat([abl_ext, abl_core], ignore_index=True)
        ablation.to_parquet(OUT_ABLATION, index=False)

        feasible_global = ablation[ablation["feasible"]].copy()
        if feasible_global.empty:
            global_win = ablation.sort_values(
                by=["equity_final_train", "sharpe_train", "switches_train", "candidate_id"],
                ascending=[False, False, True, True],
            ).iloc[0].to_dict()
        else:
            global_win = feasible_global.sort_values(
                by=["equity_final_train", "sharpe_train", "switches_train", "candidate_id"],
                ascending=[False, False, True, True],
            ).iloc[0].to_dict()

        global_curve = curve_ext if str(global_win["variant"]) == "CORE_PLUS_MACRO_EXPANDED_FX" else curve_core
        global_curve.to_parquet(OUT_CURVE, index=False)

        variant_financial = {
            "CORE_PLUS_MACRO_EXPANDED_FX": {
                "winner_candidate_id": str(win_ext["candidate_id"]),
                "winner_params": {"thr": float(win_ext["thr"]), "h_in": int(win_ext["h_in"]), "h_out": int(win_ext["h_out"])},
                "metrics": split_metrics(curve_ext),
                "feasible_count": int(abl_ext["feasible"].sum()),
                "total_candidates": int(len(abl_ext)),
            },
            "CORE": {
                "winner_candidate_id": str(win_core["candidate_id"]),
                "winner_params": {"thr": float(win_core["thr"]), "h_in": int(win_core["h_in"]), "h_out": int(win_core["h_out"])},
                "metrics": split_metrics(curve_core),
                "feasible_count": int(abl_core["feasible"].sum()),
                "total_candidates": int(len(abl_core)),
            },
            "GLOBAL_WINNER": {
                "variant": str(global_win["variant"]),
                "candidate_id": str(global_win["candidate_id"]),
                "params": {"thr": float(global_win["thr"]), "h_in": int(global_win["h_in"]), "h_out": int(global_win["h_out"])},
                "metrics": split_metrics(global_curve),
            },
        }
        write_json(OUT_VARIANT_FIN, variant_financial)

        selected_cfg = {
            "task_id": TASK_ID,
            "run_id": RUN_ID,
            "selection_mode": "TRAIN_ONLY",
            "winner_variant": str(global_win["variant"]),
            "winner_candidate_id": str(global_win["candidate_id"]),
            "winner_params": {"thr": float(global_win["thr"]), "h_in": int(global_win["h_in"]), "h_out": int(global_win["h_out"])},
            "thresholds": {"MDD_train_min": MDD_MIN_TRAIN, "max_switches_train": MAX_SWITCHES_TRAIN, "equity_train_vs_t072_min": 0.0},
            "grids": {"thr_grid": THR_GRID, "h_in_grid": H_IN_GRID, "h_out_grid": H_OUT_GRID},
            "variants": ["CORE_PLUS_MACRO_EXPANDED_FX", "CORE"],
            "walk_forward": t072_cfg.get("walk_forward", {}),
        }
        write_json(OUT_SELECTED_CFG, selected_cfg)
        write_json(
            OUT_SUMMARY,
            {
                "task_id": TASK_ID,
                "run_id": RUN_ID,
                "baseline_t072": baseline_split,
                "variant_comparison_financial": variant_financial,
                "global_winner": selected_cfg["winner_candidate_id"],
            },
        )
        write_json(
            OUT_SELECTION_RULE,
            {
                "selection_mode": "TRAIN_ONLY",
                "order": [
                    "equity_final_train DESC",
                    "sharpe_train DESC",
                    "switches_train ASC",
                    "candidate_id ASC",
                ],
                "feasibility": {
                    "equity_final_train_gte_t072_train": True,
                    "mdd_train_min": MDD_MIN_TRAIN,
                    "max_switches_train": MAX_SWITCHES_TRAIN,
                },
            },
        )
        write_json(
            OUT_CANDIDATE_SET,
            {
                "task_id": TASK_ID,
                "run_id": RUN_ID,
                "variants": {
                    "CORE_PLUS_MACRO_EXPANDED_FX": {"n_candidates_total": int(len(abl_ext)), "n_candidates_feasible": int(abl_ext["feasible"].sum())},
                    "CORE": {"n_candidates_total": int(len(abl_core)), "n_candidates_feasible": int(abl_core["feasible"].sum())},
                },
            },
        )
        write_json(
            OUT_METRICS_SNAPSHOT,
            {
                "baseline_t072": baseline_split,
                "winner_core_plus_fx": variant_financial["CORE_PLUS_MACRO_EXPANDED_FX"]["metrics"],
                "winner_core": variant_financial["CORE"]["metrics"],
                "winner_global": variant_financial["GLOBAL_WINNER"],
            },
        )
        write_json(
            OUT_ACID_WINDOW,
            {"definition": "HOLDOUT only", "acid_start": ACID_START, "acid_end": ACID_END, "n_rows": int(acid_mask.sum())},
        )

        c060 = pick_c060_curve()
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08, subplot_titles=("Equity (base 100k)", "Drawdown"))
        fig.add_trace(go.Scatter(x=baseline["date"], y=baseline["equity_end_norm"], name="T072 baseline"), row=1, col=1)
        fig.add_trace(go.Scatter(x=curve_ext["date"], y=curve_ext["equity_end_norm"], name=f"CORE+FX winner {win_ext['candidate_id']}"), row=1, col=1)
        fig.add_trace(go.Scatter(x=curve_core["date"], y=curve_core["equity_end_norm"], name=f"CORE winner {win_core['candidate_id']}"), row=1, col=1)
        fig.add_trace(go.Scatter(x=global_curve["date"], y=global_curve["equity_end_norm"], name=f"GLOBAL winner {global_win['candidate_id']}"), row=1, col=1)
        if c060 is not None:
            fig.add_trace(go.Scatter(x=c060["date"], y=c060["equity_end_norm"], name="C060"), row=1, col=1)

        fig.add_trace(go.Scatter(x=baseline["date"], y=baseline["drawdown"], name="DD T072", line={"dash": "dot"}), row=2, col=1)
        fig.add_trace(go.Scatter(x=curve_ext["date"], y=curve_ext["drawdown"], name="DD CORE+FX", line={"dash": "dot"}), row=2, col=1)
        fig.add_trace(go.Scatter(x=curve_core["date"], y=curve_core["drawdown"], name="DD CORE", line={"dash": "dot"}), row=2, col=1)
        fig.add_trace(go.Scatter(x=global_curve["date"], y=global_curve["drawdown"], name="DD GLOBAL", line={"dash": "dot"}), row=2, col=1)
        if c060 is not None and "drawdown" in c060.columns:
            fig.add_trace(go.Scatter(x=c060["date"], y=c060["drawdown"], name="DD C060", line={"dash": "dot"}), row=2, col=1)

        fig.add_vrect(x0=ACID_START, x1=ACID_END, fillcolor="orange", opacity=0.12, line_width=0, annotation_text="Acid window")
        fig.update_layout(height=900, title=f"{TASK_ID} - ML tuning comparativo (CORE vs CORE+FX)")
        fig.write_html(str(OUT_PLOT), include_plotlyjs="cdn")

        artifacts_ok = all(
            p.exists()
            for p in [
                OUT_SELECTED_CFG,
                OUT_ABLATION,
                OUT_CURVE,
                OUT_SUMMARY,
                OUT_PLOT,
                OUT_SELECTION_RULE,
                OUT_CANDIDATE_SET,
                OUT_METRICS_SNAPSHOT,
                OUT_ACID_WINDOW,
                OUT_JOIN_COVERAGE,
                OUT_VARIANT_FIN,
            ]
        )
        gates.append(Gate("G_ARTIFACTS_WRITTEN", artifacts_ok, "core+evidence artifacts created"))

        # Only output files that are materialized before manifest creation.
        outputs_for_hash = [
            OUT_SCRIPT,
            OUT_SELECTED_CFG,
            OUT_ABLATION,
            OUT_CURVE,
            OUT_SUMMARY,
            OUT_PLOT,
            OUT_SELECTION_RULE,
            OUT_CANDIDATE_SET,
            OUT_METRICS_SNAPSHOT,
            OUT_ACID_WINDOW,
            OUT_JOIN_COVERAGE,
            OUT_VARIANT_FIN,
            OUT_REPORT,
            CHANGELOG_PATH,
        ]
        manifest_payload = {
            "task_id": TASK_ID,
            "run_id": RUN_ID,
            "inputs_consumed": [
                str(INPUT_T072_CURVE.relative_to(ROOT)),
                str(INPUT_T072_CONFIG.relative_to(ROOT)),
                str(INPUT_T105_PREDS.relative_to(ROOT)),
                str(INPUT_T104_DATASET.relative_to(ROOT)),
                str(INPUT_T105_VARIANT.relative_to(ROOT)),
            ],
            "outputs_produced": [str(p.relative_to(ROOT)) for p in outputs_for_hash] + [str(OUT_MANIFEST.relative_to(ROOT))],
            "hashes_sha256": {},
            "manifest_policy": "no_self_hash",
        }

        chlog_ok = append_changelog_one_line(TRACEABILITY_LINE)
        gates.append(Gate("G_CHLOG_UPDATED", chlog_ok, f"path={CHANGELOG_PATH}"))

        # Report before manifest hash map is frozen.
        report_lines = [f"# HEADER: {TASK_ID}", "", "## STEP GATES"]
        for g in gates:
            report_lines.append(f"- {g.name}: {'PASS' if g.passed else 'FAIL'} | {g.detail}")
        report_lines.extend(["", "## RETRY LOG", "- none" if not retry_log else ""])
        if retry_log:
            for r in retry_log:
                report_lines.append(f"- {r}")
        report_lines.extend(
            [
                "",
                "## ARTIFACT LINKS",
                f"- {OUT_SELECTED_CFG.relative_to(ROOT)}",
                f"- {OUT_ABLATION.relative_to(ROOT)}",
                f"- {OUT_CURVE.relative_to(ROOT)}",
                f"- {OUT_SUMMARY.relative_to(ROOT)}",
                f"- {OUT_PLOT.relative_to(ROOT)}",
                f"- {OUT_VARIANT_FIN.relative_to(ROOT)}",
                f"- {OUT_MANIFEST.relative_to(ROOT)}",
            ]
        )
        OUT_REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

        # Refresh hash map after report/changelog writes.
        manifest_payload["hashes_sha256"] = {str(p.relative_to(ROOT)): sha256_file(p) for p in outputs_for_hash}
        write_json(OUT_MANIFEST, manifest_payload)
        gates.append(Gate("Gx_HASH_MANIFEST_PRESENT", OUT_MANIFEST.exists(), f"path={OUT_MANIFEST.relative_to(ROOT)}"))
        mismatches = 0
        for rel, expected in manifest_payload["hashes_sha256"].items():
            got = sha256_file(ROOT / rel)
            if got != expected:
                mismatches += 1
        gates.append(Gate("G_SHA256_INTEGRITY_SELF_CHECK", mismatches == 0, f"mismatches={mismatches}"))

        overall_pass = all(g.passed for g in gates)

        # Rewrite report with final gates and status.
        report_lines = [f"# HEADER: {TASK_ID}", "", "## STEP GATES"]
        for g in gates:
            report_lines.append(f"- {g.name}: {'PASS' if g.passed else 'FAIL'} | {g.detail}")
        report_lines.extend(["", "## RETRY LOG", "- none" if not retry_log else ""])
        if retry_log:
            for r in retry_log:
                report_lines.append(f"- {r}")
        report_lines.extend(
            [
                "",
                "## EXECUTIVE SUMMARY",
                f"- winner_global_variant: {global_win['variant']}",
                f"- winner_global_candidate_id: {global_win['candidate_id']}",
                f"- winner_global_params: thr={global_win['thr']}, h_in={int(global_win['h_in'])}, h_out={int(global_win['h_out'])}",
                f"- winner_core_candidate_id: {win_core['candidate_id']}",
                f"- winner_core_plus_fx_candidate_id: {win_ext['candidate_id']}",
                "",
                "## ARTIFACT LINKS",
                f"- {OUT_SELECTED_CFG.relative_to(ROOT)}",
                f"- {OUT_ABLATION.relative_to(ROOT)}",
                f"- {OUT_CURVE.relative_to(ROOT)}",
                f"- {OUT_SUMMARY.relative_to(ROOT)}",
                f"- {OUT_PLOT.relative_to(ROOT)}",
                f"- {OUT_SELECTION_RULE.relative_to(ROOT)}",
                f"- {OUT_CANDIDATE_SET.relative_to(ROOT)}",
                f"- {OUT_METRICS_SNAPSHOT.relative_to(ROOT)}",
                f"- {OUT_ACID_WINDOW.relative_to(ROOT)}",
                f"- {OUT_JOIN_COVERAGE.relative_to(ROOT)}",
                f"- {OUT_VARIANT_FIN.relative_to(ROOT)}",
                f"- {OUT_REPORT.relative_to(ROOT)}",
                f"- {OUT_MANIFEST.relative_to(ROOT)}",
                "",
                f"## OVERALL STATUS: [[ {'PASS' if overall_pass else 'FAIL'} ]]",
                "",
            ]
        )
        OUT_REPORT.write_text("\n".join(report_lines), encoding="utf-8")

        print(f"HEADER: {TASK_ID}")
        print("STEP GATES:")
        for g in gates:
            print(f"- {g.name}: {'PASS' if g.passed else 'FAIL'} | {g.detail}")
        print("RETRY LOG:")
        if retry_log:
            for r in retry_log:
                print(f"- {r}")
        else:
            print("- none")
        print("ARTIFACT LINKS:")
        print(f"- {OUT_SELECTED_CFG}")
        print(f"- {OUT_ABLATION}")
        print(f"- {OUT_CURVE}")
        print(f"- {OUT_SUMMARY}")
        print(f"- {OUT_PLOT}")
        print(f"- {OUT_VARIANT_FIN}")
        print(f"- {OUT_MANIFEST}")
        print(f"OVERALL STATUS: [[ {'PASS' if overall_pass else 'FAIL'} ]]")
        return 0 if overall_pass else 2

    except Exception as exc:
        retry_log.append(f"FATAL: {type(exc).__name__}: {exc}")
        gates.append(Gate("G_FATAL", False, f"{type(exc).__name__}: {exc}"))
        report_lines = [f"# HEADER: {TASK_ID}", "", "## STEP GATES"]
        for g in gates:
            report_lines.append(f"- {g.name}: {'PASS' if g.passed else 'FAIL'} | {g.detail}")
        report_lines.extend(["", "## RETRY LOG"])
        for r in retry_log:
            report_lines.append(f"- {r}")
        report_lines.extend(["", "## ARTIFACT LINKS", f"- {OUT_REPORT}", "", "## OVERALL STATUS: [[ FAIL ]]", ""])
        OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
        OUT_REPORT.write_text("\n".join(report_lines), encoding="utf-8")
        print(f"HEADER: {TASK_ID}")
        print("STEP GATES:")
        for g in gates:
            print(f"- {g.name}: {'PASS' if g.passed else 'FAIL'} | {g.detail}")
        print("RETRY LOG:")
        for r in retry_log:
            print(f"- {r}")
        print("ARTIFACT LINKS:")
        print(f"- {OUT_REPORT}")
        print("OVERALL STATUS: [[ FAIL ]]")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
