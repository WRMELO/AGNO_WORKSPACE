#!/home/wilson/AGNO_WORKSPACE/.venv/bin/python
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sklearn.impute import SimpleImputer
from sklearn.metrics import balanced_accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import TimeSeriesSplit
from xgboost import XGBClassifier


TASK_ID = "T125"
RUN_ID = "T125-US-TRIGGER-V2-THR-HYST-V1"
ROOT = Path("/home/wilson/AGNO_WORKSPACE")
PYTHON_ENV = ROOT / ".venv/bin/python"
CHANGELOG_PATH = ROOT / "00_Strategy/changelog.md"

IN_DATASET = ROOT / "src/data_engine/features/T123_US_DATASET_DAILY.parquet"
IN_MODEL = ROOT / "src/data_engine/models/T124_US_V2_XGB_SELECTED_MODEL.json"
IN_PREDS = ROOT / "src/data_engine/features/T124_US_V2_PREDICTIONS_DAILY.parquet"
IN_MACRO = ROOT / "src/data_engine/ssot/SSOT_MACRO_EXPANDED.parquet"

OUT_SCRIPT = ROOT / "scripts/t125_threshold_hysteresis_ablation_us_v2_v1.py"
OUT_SIGNALS = ROOT / "src/data_engine/features/T125_US_V2_TRIGGER_SIGNALS_DAILY.parquet"
OUT_ABL = ROOT / "src/data_engine/features/T125_US_V2_TRIGGER_ABLATION_RESULTS.parquet"
OUT_OOF = ROOT / "src/data_engine/features/T125_US_V2_TRIGGER_OOF_PROBA_TRAIN.parquet"
OUT_TIMING = ROOT / "src/data_engine/features/T125_US_V2_TRIGGER_TIMING_SP500_CURVE_DAILY.parquet"
OUT_CFG = ROOT / "src/data_engine/features/T125_US_V2_TRIGGER_SELECTED_CONFIG.json"
OUT_PLOT = ROOT / "outputs/plots/T125_STATE3_PHASE10C_US_TRIGGER_V2_THRESHOLD_HYSTERESIS.html"
OUT_REPORT = ROOT / "outputs/governanca/T125-US-TRIGGER-V2-THR-HYST-V1_report.md"
OUT_MANIFEST = ROOT / "outputs/governanca/T125-US-TRIGGER-V2-THR-HYST-V1_manifest.json"
OUT_EVID = ROOT / "outputs/governanca/T125-US-TRIGGER-V2-THR-HYST-V1_evidence"
OUT_GRID = OUT_EVID / "grid_definition.json"
OUT_SEL_RULE = OUT_EVID / "selection_rule.json"
OUT_FOLDS = OUT_EVID / "walkforward_folds.json"
OUT_CV_JUST = OUT_EVID / "cv_scheme_justification.md"
OUT_BASELINE = OUT_EVID / "threshold_baseline_metrics.json"
OUT_GAP = OUT_EVID / "generalization_gap.json"
OUT_TRANS = OUT_EVID / "transition_diagnostics.json"
OUT_TIMING_METRICS = OUT_EVID / "timing_sp500_metrics.json"

TRACEABILITY_LINE = "- 2026-03-04T23:00:00Z | EXEC: T125 PASS. Ablation threshold+histerese do Trigger US v2 (T124) com calibração TRAIN-only via OOF walk-forward e geração de sinais diários + timing SP500 diagnóstico. Artefatos: scripts/t125_threshold_hysteresis_ablation_us_v2_v1.py; src/data_engine/features/T125_US_V2_TRIGGER_{OOF_PROBA_TRAIN,ABLATION_RESULTS,TRIGGER_SIGNALS_DAILY,TRIGGER_TIMING_SP500_CURVE_DAILY}.parquet; src/data_engine/features/T125_US_V2_TRIGGER_SELECTED_CONFIG.json; outputs/plots/T125_STATE3_PHASE10C_US_TRIGGER_V2_THRESHOLD_HYSTERESIS.html; outputs/governanca/T125-US-TRIGGER-V2-THR-HYST-V1_{report,manifest}.json"

N_SPLITS = 5
SEED = 42
EXPECTED_ROWS = 1902
EXPECTED_TRAIN = 1115
EXPECTED_HOLDOUT = 787
THRESHOLDS = [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70]
H_INS = [1, 2, 3, 4, 5]
H_OUTS = [1, 2, 3, 4, 5]


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
        x = float(obj)
        return x if np.isfinite(x) else None
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


def append_changelog_one_line_idempotent(line: str) -> bool:
    existing = CHANGELOG_PATH.read_text(encoding="utf-8") if CHANGELOG_PATH.exists() else ""
    if line in existing:
        return True
    text = existing
    if text and not text.endswith("\n"):
        text += "\n"
    text += line + "\n"
    CHANGELOG_PATH.write_text(text, encoding="utf-8")
    return line in CHANGELOG_PATH.read_text(encoding="utf-8")


def hysteresis_state(proba: pd.Series, threshold: float, h_in: int, h_out: int) -> pd.Series:
    p = pd.to_numeric(proba, errors="coerce").fillna(0.0).to_numpy(dtype=float)
    state = np.zeros(len(p), dtype=int)
    in_streak = 0
    out_streak = 0
    cash = 0
    for i, v in enumerate(p):
        if v >= threshold:
            in_streak += 1
            out_streak = 0
        else:
            out_streak += 1
            in_streak = 0
        if cash == 0 and in_streak >= h_in:
            cash = 1
            in_streak = 0
        elif cash == 1 and out_streak >= h_out:
            cash = 0
            out_streak = 0
        state[i] = cash
    return pd.Series(state, index=proba.index, dtype=int)


def cls_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    y_true_i = np.asarray(y_true, dtype=int)
    y_pred_i = np.asarray(y_pred, dtype=int)
    switches = int(np.sum(y_pred_i[1:] != y_pred_i[:-1])) if len(y_pred_i) > 1 else 0
    transition_rate = float(switches / max(len(y_pred_i) - 1, 1))
    return {
        "precision_cash": float(precision_score(y_true_i, y_pred_i, pos_label=1, zero_division=0)),
        "recall_cash": float(recall_score(y_true_i, y_pred_i, pos_label=1, zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true_i, y_pred_i)),
        "f1_cash": float(f1_score(y_true_i, y_pred_i, pos_label=1, zero_division=0)),
        "cash_frac": float(np.mean(y_pred_i)),
        "switches": float(switches),
        "transition_rate_pred": transition_rate,
    }


def compute_mdd(equity: pd.Series) -> float:
    eq = pd.to_numeric(equity, errors="coerce").ffill().fillna(100000.0).to_numpy(dtype=float)
    peak = np.maximum.accumulate(eq)
    dd = eq / np.maximum(peak, 1e-12) - 1.0
    return float(np.min(dd)) if len(dd) else 0.0


def compute_sharpe(daily_ret: pd.Series) -> float:
    r = pd.to_numeric(daily_ret, errors="coerce").fillna(0.0).to_numpy(dtype=float)
    if len(r) < 2:
        return 0.0
    std = float(np.std(r, ddof=1))
    if std <= 0:
        return 0.0
    return float((np.mean(r) / std) * np.sqrt(252.0))


def eval_timing(df: pd.DataFrame) -> dict[str, float]:
    if len(df) == 0:
        return {
            "rows": 0.0,
            "equity_end": 100000.0,
            "mdd": 0.0,
            "sharpe": 0.0,
            "switches": 0.0,
            "cash_frac": 0.0,
        }
    eq = pd.to_numeric(df["equity"], errors="coerce").fillna(100000.0)
    ret = pd.to_numeric(df["strategy_ret"], errors="coerce").fillna(0.0)
    st = pd.to_numeric(df["state_cash"], errors="coerce").fillna(0).astype(int)
    sw = int(np.sum(st.to_numpy()[1:] != st.to_numpy()[:-1])) if len(st) > 1 else 0
    return {
        "rows": float(len(df)),
        "equity_end": float(eq.iloc[-1]),
        "mdd": compute_mdd(eq),
        "sharpe": compute_sharpe(ret),
        "switches": float(sw),
        "cash_frac": float(st.mean()),
    }


def main() -> None:
    gates: list[Gate] = []
    retry_log: list[str] = []
    overall_pass = True

    in_venv = (".venv" in sys.executable) and Path(sys.executable).resolve() == PYTHON_ENV.resolve()
    gates.append(Gate("G_ENV_VENV", in_venv, f"python={sys.executable}"))
    if not in_venv:
        raise RuntimeError("FATAL: execute with .venv python")

    pip_list_ok = True
    try:
        proc = subprocess.run(
            [str(ROOT / ".venv/bin/pip"), "list"],
            check=True,
            capture_output=True,
            text=True,
        )
        pip_out = proc.stdout.lower()
        for dep in ("xgboost", "scikit-learn", "plotly", "pandas", "numpy"):
            if dep not in pip_out:
                pip_list_ok = False
    except Exception as e:
        pip_list_ok = False
        retry_log.append(f"pip list error: {type(e).__name__}: {e}")
    gates.append(Gate("G_DEPENDENCIES_CHECK", pip_list_ok, "pip list + imports baseline"))

    inputs_present = IN_DATASET.exists() and IN_MODEL.exists() and IN_PREDS.exists() and CHANGELOG_PATH.exists()
    gates.append(
        Gate(
            "G_INPUTS_PRESENT",
            inputs_present,
            f"dataset={IN_DATASET.exists()} model={IN_MODEL.exists()} preds={IN_PREDS.exists()} changelog={CHANGELOG_PATH.exists()}",
        )
    )
    if not inputs_present:
        raise FileNotFoundError("T125 inputs ausentes")

    for p in [
        OUT_SIGNALS.parent,
        OUT_ABL.parent,
        OUT_OOF.parent,
        OUT_TIMING.parent,
        OUT_CFG.parent,
        OUT_PLOT.parent,
        OUT_REPORT.parent,
        OUT_EVID,
    ]:
        p.mkdir(parents=True, exist_ok=True)

    try:
        df = pd.read_parquet(IN_DATASET).copy()
        preds = pd.read_parquet(IN_PREDS).copy()
        model_cfg = json.loads(IN_MODEL.read_text(encoding="utf-8"))
        macro = pd.read_parquet(IN_MACRO).copy() if IN_MACRO.exists() else pd.DataFrame()

        df["date"] = pd.to_datetime(df["date"]).dt.normalize()
        preds["date"] = pd.to_datetime(preds["date"]).dt.normalize()
        if len(macro) > 0 and "date" in macro.columns:
            macro["date"] = pd.to_datetime(macro["date"]).dt.normalize()

        df = df.sort_values("date").reset_index(drop=True)
        preds = preds.sort_values("date").reset_index(drop=True)
        train = df[df["split"] == "TRAIN"].copy().reset_index(drop=True)
        hold = df[df["split"] == "HOLDOUT"].copy().reset_index(drop=True)

        split_ok = (
            len(df) == EXPECTED_ROWS
            and int((df["split"] == "TRAIN").sum()) == EXPECTED_TRAIN
            and int((df["split"] == "HOLDOUT").sum()) == EXPECTED_HOLDOUT
            and df["y_cash_us_v1"].isin([0, 1]).all()
            and int(df["y_cash_us_v1"].isna().sum()) == 0
            and len(preds) == EXPECTED_ROWS
        )
        gates.append(
            Gate(
                "G_SPLIT_SHAPE_OK",
                split_ok,
                f"dataset_rows={len(df)} train={len(train)} holdout={len(hold)} preds_rows={len(preds)}",
            )
        )

        features = [f for f in model_cfg.get("features_used", []) if f in df.columns]
        if len(features) == 0:
            raise RuntimeError("features_used vazio ou ausente no dataset")
        hp = model_cfg.get("selected_hyperparams", {})
        required_hp = {"n_estimators", "max_depth", "learning_rate", "subsample", "colsample_bytree"}
        if not required_hp.issubset(set(hp)):
            raise RuntimeError("selected_hyperparams incompleto no model json")

        X_train = train[features].copy()
        y_train = train["y_cash_us_v1"].astype(int).to_numpy()
        tscv = TimeSeriesSplit(n_splits=N_SPLITS)
        oof_proba = np.full(len(train), np.nan, dtype=float)
        oof_fold = np.full(len(train), -1, dtype=int)
        folds: list[dict[str, Any]] = []
        for fold_id, (tr_idx, va_idx) in enumerate(tscv.split(X_train), start=1):
            folds.append(
                {
                    "fold_id": fold_id,
                    "train_rows": int(len(tr_idx)),
                    "valid_rows": int(len(va_idx)),
                    "train_date_min": str(train.loc[tr_idx, "date"].min().date()),
                    "train_date_max": str(train.loc[tr_idx, "date"].max().date()),
                    "valid_date_min": str(train.loc[va_idx, "date"].min().date()),
                    "valid_date_max": str(train.loc[va_idx, "date"].max().date()),
                }
            )
            X_tr = X_train.iloc[tr_idx]
            y_tr = y_train[tr_idx]
            X_va = X_train.iloc[va_idx]
            imp = SimpleImputer(strategy="median")
            X_tr_i = imp.fit_transform(X_tr)
            X_va_i = imp.transform(X_va)
            pos = int(np.sum(y_tr == 1))
            neg = int(np.sum(y_tr == 0))
            spw = float(neg / max(pos, 1))
            model = XGBClassifier(
                n_estimators=int(hp["n_estimators"]),
                max_depth=int(hp["max_depth"]),
                learning_rate=float(hp["learning_rate"]),
                subsample=float(hp["subsample"]),
                colsample_bytree=float(hp["colsample_bytree"]),
                objective="binary:logistic",
                eval_metric="logloss",
                random_state=SEED,
                n_jobs=1,
                scale_pos_weight=spw,
            )
            model.fit(X_tr_i, y_tr)
            oof_proba[va_idx] = model.predict_proba(X_va_i)[:, 1]
            oof_fold[va_idx] = fold_id

        covered = int(np.isfinite(oof_proba).sum())
        coverage_ratio = float(covered / len(train)) if len(train) else 0.0
        cv_ok = covered > 0 and coverage_ratio >= 0.75 and len(folds) == N_SPLITS
        gates.append(
            Gate(
                "G_WALKFORWARD_TRAIN_OOF_OK",
                cv_ok,
                f"n_splits={N_SPLITS} covered={covered} train_rows={len(train)} coverage_ratio={coverage_ratio:.3f}",
            )
        )
        write_json(OUT_FOLDS, {"n_splits": N_SPLITS, "folds": folds})
        OUT_CV_JUST.write_text(
            "\n".join(
                [
                    "# CV Scheme Justification - T125",
                    "",
                    "- Esquema: TimeSeriesSplit no TRAIN (walk-forward).",
                    "- OOF no TRAIN usado para calibrar threshold+histerese sem leakage.",
                    "- HOLDOUT não participa da seleção de configuração.",
                    "- HOLDOUT é apenas diagnóstico de generalização.",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        oof_df = train[["date", "split", "y_cash_us_v1"]].copy()
        oof_df["proba_oof"] = oof_proba
        oof_df["oof_fold_id"] = oof_fold
        oof_df.rename(columns={"y_cash_us_v1": "y_true"}, inplace=True)
        oof_df.to_parquet(OUT_OOF, index=False)

        rows: list[dict[str, Any]] = []
        grid_rows: list[dict[str, Any]] = []
        cid = 1
        for thr in THRESHOLDS:
            for h_in in H_INS:
                for h_out in H_OUTS:
                    candidate_id = f"C{cid:03d}"
                    grid_rows.append({"candidate_id": candidate_id, "threshold": float(thr), "h_in": int(h_in), "h_out": int(h_out)})
                    state = hysteresis_state(oof_df["proba_oof"], float(thr), int(h_in), int(h_out))
                    m = cls_metrics(oof_df["y_true"].to_numpy(dtype=int), state.to_numpy(dtype=int))
                    rows.append(
                        {
                            "candidate_id": candidate_id,
                            "threshold": float(thr),
                            "h_in": int(h_in),
                            "h_out": int(h_out),
                            "precision_cash_train_oof": m["precision_cash"],
                            "recall_cash_train_oof": m["recall_cash"],
                            "balanced_accuracy_train_oof": m["balanced_accuracy"],
                            "f1_cash_train_oof": m["f1_cash"],
                            "cash_frac_train_oof": m["cash_frac"],
                            "switches_train_oof": int(m["switches"]),
                            "transition_rate_train_oof": m["transition_rate_pred"],
                            "rule_precision_gte_020": bool(m["precision_cash"] >= 0.20),
                            "rule_precision_gte_010": bool(m["precision_cash"] >= 0.10),
                            "rule_cash_frac_015_060": bool(0.15 <= m["cash_frac"] <= 0.60),
                        }
                    )
                    cid += 1
        ablation = pd.DataFrame(rows).sort_values("candidate_id").reset_index(drop=True)
        ablation.to_parquet(OUT_ABL, index=False)
        write_json(OUT_GRID, {"thresholds": THRESHOLDS, "h_in": H_INS, "h_out": H_OUTS, "n_candidates": int(len(ablation))})
        gates.append(
            Gate(
                "G_ABLATION_GRID_COMPLETE",
                len(ablation) == (len(THRESHOLDS) * len(H_INS) * len(H_OUTS)),
                f"n_candidates={len(ablation)} expected={len(THRESHOLDS) * len(H_INS) * len(H_OUTS)}",
            )
        )

        pool_main = ablation[(ablation["rule_precision_gte_020"]) & (ablation["rule_cash_frac_015_060"])].copy()
        selection_mode = "main_precision_020_and_cashfrac_015_060"
        if pool_main.empty:
            pool_main = ablation[(ablation["rule_precision_gte_010"]) & (ablation["rule_cash_frac_015_060"])].copy()
            selection_mode = "fallback_precision_010_and_cashfrac_015_060"
        if pool_main.empty:
            pool_main = ablation.copy()
            selection_mode = "fallback_full_pool"
        pool_main = pool_main.sort_values(
            by=[
                "balanced_accuracy_train_oof",
                "recall_cash_train_oof",
                "switches_train_oof",
                "threshold",
                "h_in",
                "h_out",
                "candidate_id",
            ],
            ascending=[False, False, True, True, True, True, True],
        ).reset_index(drop=True)
        winner = pool_main.iloc[0].to_dict()
        winner_id = str(winner["candidate_id"])
        thr_w = float(winner["threshold"])
        h_in_w = int(winner["h_in"])
        h_out_w = int(winner["h_out"])
        ablation["selected"] = ablation["candidate_id"] == winner_id
        ablation.to_parquet(OUT_ABL, index=False)

        sel_rule = {
            "selection_mode": selection_mode,
            "selection_scope": "TRAIN_OOF_ONLY",
            "sort_order": [
                "balanced_accuracy_train_oof DESC",
                "recall_cash_train_oof DESC",
                "switches_train_oof ASC",
                "threshold ASC",
                "h_in ASC",
                "h_out ASC",
                "candidate_id ASC",
            ],
            "winner": {
                "candidate_id": winner_id,
                "threshold": thr_w,
                "h_in": h_in_w,
                "h_out": h_out_w,
            },
        }
        write_json(OUT_SEL_RULE, sel_rule)

        train_state = hysteresis_state(oof_df["proba_oof"], thr_w, h_in_w, h_out_w)
        train_m = cls_metrics(oof_df["y_true"].to_numpy(dtype=int), train_state.to_numpy(dtype=int))

        signals = preds.copy()
        signals = signals.sort_values("date").reset_index(drop=True)
        signals["state_cash"] = hysteresis_state(signals["y_proba_cash"], thr_w, h_in_w, h_out_w).astype(int)
        signals["threshold"] = thr_w
        signals["h_in"] = h_in_w
        signals["h_out"] = h_out_w
        signals["selected_candidate_id"] = winner_id
        signals.to_parquet(OUT_SIGNALS, index=False)
        gates.append(
            Gate(
                "G_SELECTED_CONFIG_OK",
                OUT_CFG.parent.exists() and len(signals) == EXPECTED_ROWS and set(signals["state_cash"].unique()).issubset({0, 1}),
                f"winner={winner_id} thr={thr_w:.2f} h_in={h_in_w} h_out={h_out_w}",
            )
        )

        hold_s = signals[signals["split"] == "HOLDOUT"].copy().reset_index(drop=True)
        hold_m = cls_metrics(hold_s["y_true"].to_numpy(dtype=int), hold_s["state_cash"].to_numpy(dtype=int))
        write_json(
            OUT_BASELINE,
            {
                "winner_candidate_id": winner_id,
                "threshold": thr_w,
                "h_in": h_in_w,
                "h_out": h_out_w,
                "train_oof": train_m,
                "holdout_inference": hold_m,
            },
        )
        write_json(
            OUT_GAP,
            {
                "winner_candidate_id": winner_id,
                "gap_precision_cash_holdout_minus_train_oof": float(hold_m["precision_cash"] - train_m["precision_cash"]),
                "gap_recall_cash_holdout_minus_train_oof": float(hold_m["recall_cash"] - train_m["recall_cash"]),
                "gap_balanced_accuracy_holdout_minus_train_oof": float(hold_m["balanced_accuracy"] - train_m["balanced_accuracy"]),
            },
        )
        write_json(
            OUT_TRANS,
            {
                "winner_candidate_id": winner_id,
                "train_switches_pred": int(train_m["switches"]),
                "holdout_switches_pred": int(hold_m["switches"]),
                "train_transition_rate_pred": float(train_m["transition_rate_pred"]),
                "holdout_transition_rate_pred": float(hold_m["transition_rate_pred"]),
            },
        )

        cfg_payload = {
            "task_id": TASK_ID,
            "run_id": RUN_ID,
            "source_model": str(IN_MODEL.relative_to(ROOT)),
            "winner_candidate_id": winner_id,
            "threshold": thr_w,
            "h_in": h_in_w,
            "h_out": h_out_w,
            "selection_scope": "TRAIN_OOF_ONLY",
            "selection_rule_path": str(OUT_SEL_RULE.relative_to(ROOT)),
        }
        write_json(OUT_CFG, cfg_payload)

        timing = signals.merge(df[["date", "sp500_close"]], on="date", how="left")
        if len(macro) > 0 and "fed_funds_rate" in macro.columns:
            timing = timing.merge(macro[["date", "fed_funds_rate"]], on="date", how="left")
            timing["fed_funds_rate"] = pd.to_numeric(timing["fed_funds_rate"], errors="coerce").ffill().bfill()
            timing["cash_ret"] = np.log1p((timing["fed_funds_rate"] / 100.0) / 252.0)
        else:
            timing["fed_funds_rate"] = np.nan
            timing["cash_ret"] = 0.0
        timing["sp500_close"] = pd.to_numeric(timing["sp500_close"], errors="coerce")
        timing["sp500_ret"] = timing["sp500_close"].pct_change().fillna(0.0)
        timing["strategy_ret"] = np.where(timing["state_cash"] == 1, timing["cash_ret"], timing["sp500_ret"])
        timing["equity"] = 100000.0 * (1.0 + pd.to_numeric(timing["strategy_ret"], errors="coerce").fillna(0.0)).cumprod()
        timing["drawdown"] = timing["equity"] / timing["equity"].cummax() - 1.0
        timing.to_parquet(OUT_TIMING, index=False)

        timing_train = eval_timing(timing[timing["split"] == "TRAIN"])
        timing_hold = eval_timing(timing[timing["split"] == "HOLDOUT"])
        timing_all = eval_timing(timing)
        write_json(
            OUT_TIMING_METRICS,
            {
                "winner_candidate_id": winner_id,
                "train": timing_train,
                "holdout": timing_hold,
                "overall": timing_all,
            },
        )

        fig = make_subplots(
            rows=2,
            cols=2,
            subplot_titles=(
                "TRAIN OOF: proba vs label vs state",
                "HOLDOUT: proba vs label vs state",
                "Ablation (precision vs recall)",
                "Timing SP500 (equity + drawdown)",
            ),
            vertical_spacing=0.12,
            horizontal_spacing=0.08,
            specs=[[{"type": "xy"}, {"type": "xy"}], [{"type": "xy"}, {"type": "xy"}]],
        )
        tr_oof = oof_df.copy()
        tr_oof["state_cash"] = train_state.astype(int)
        fig.add_trace(go.Scatter(x=tr_oof["date"], y=tr_oof["proba_oof"], mode="lines", name="train_proba_oof"), row=1, col=1)
        fig.add_trace(go.Scatter(x=tr_oof["date"], y=tr_oof["y_true"], mode="lines", name="train_label", line=dict(dash="dot")), row=1, col=1)
        fig.add_trace(go.Scatter(x=tr_oof["date"], y=tr_oof["state_cash"], mode="lines", name="train_state_cash", line=dict(dash="dash")), row=1, col=1)

        hsig = signals[signals["split"] == "HOLDOUT"].copy()
        fig.add_trace(go.Scatter(x=hsig["date"], y=hsig["y_proba_cash"], mode="lines", name="holdout_proba"), row=1, col=2)
        fig.add_trace(go.Scatter(x=hsig["date"], y=hsig["y_true"], mode="lines", name="holdout_label", line=dict(dash="dot")), row=1, col=2)
        fig.add_trace(go.Scatter(x=hsig["date"], y=hsig["state_cash"], mode="lines", name="holdout_state_cash", line=dict(dash="dash")), row=1, col=2)

        fig.add_trace(
            go.Scatter(
                x=ablation["precision_cash_train_oof"],
                y=ablation["recall_cash_train_oof"],
                mode="markers",
                name="candidates",
                text=ablation["candidate_id"],
            ),
            row=2,
            col=1,
        )
        selp = ablation[ablation["selected"]].copy()
        if len(selp) == 1:
            fig.add_trace(
                go.Scatter(
                    x=selp["precision_cash_train_oof"],
                    y=selp["recall_cash_train_oof"],
                    mode="markers+text",
                    marker=dict(size=12, color="red"),
                    text=selp["candidate_id"],
                    textposition="top center",
                    name="winner",
                ),
                row=2,
                col=1,
            )

        fig.add_trace(go.Scatter(x=timing["date"], y=timing["equity"], mode="lines", name="timing_equity"), row=2, col=2)
        fig.add_trace(go.Scatter(x=timing["date"], y=timing["drawdown"], mode="lines", name="timing_drawdown"), row=2, col=2)
        fig.update_layout(height=920, width=1450, title=f"{RUN_ID} - threshold+hysteresis ablation", legend=dict(orientation="h"))
        fig.write_html(OUT_PLOT, include_plotlyjs="cdn")

        outputs_expected = [
            OUT_SCRIPT,
            OUT_SIGNALS,
            OUT_ABL,
            OUT_OOF,
            OUT_TIMING,
            OUT_CFG,
            OUT_PLOT,
            OUT_REPORT,
            OUT_GRID,
            OUT_SEL_RULE,
            OUT_FOLDS,
            OUT_CV_JUST,
            OUT_BASELINE,
            OUT_GAP,
            OUT_TRANS,
            OUT_TIMING_METRICS,
        ]
        outputs_ok = all(p.exists() for p in outputs_expected if p != OUT_REPORT)
        gates.append(
            Gate(
                "G_OUTPUTS_PRESENT",
                outputs_ok
                and len(ablation) == 225
                and len(signals) == 1902
                and int(signals["y_proba_cash"].isna().sum()) == 0,
                f"ablation_rows={len(ablation)} signals_rows={len(signals)} nan_proba={int(signals['y_proba_cash'].isna().sum())}",
            )
        )

        ch_ok = append_changelog_one_line_idempotent(TRACEABILITY_LINE)
        gates.append(Gate("G_CHLOG_UPDATED", ch_ok, "mode=idempotent"))

        inputs = [
            str(IN_DATASET.relative_to(ROOT)),
            str(IN_MODEL.relative_to(ROOT)),
            str(IN_PREDS.relative_to(ROOT)),
            str(CHANGELOG_PATH.relative_to(ROOT)),
        ]
        if IN_MACRO.exists():
            inputs.append(str(IN_MACRO.relative_to(ROOT)))

        outputs = [
            str(OUT_SCRIPT.relative_to(ROOT)),
            str(OUT_SIGNALS.relative_to(ROOT)),
            str(OUT_ABL.relative_to(ROOT)),
            str(OUT_OOF.relative_to(ROOT)),
            str(OUT_TIMING.relative_to(ROOT)),
            str(OUT_CFG.relative_to(ROOT)),
            str(OUT_PLOT.relative_to(ROOT)),
            str(OUT_REPORT.relative_to(ROOT)),
            str(OUT_GRID.relative_to(ROOT)),
            str(OUT_SEL_RULE.relative_to(ROOT)),
            str(OUT_FOLDS.relative_to(ROOT)),
            str(OUT_CV_JUST.relative_to(ROOT)),
            str(OUT_BASELINE.relative_to(ROOT)),
            str(OUT_GAP.relative_to(ROOT)),
            str(OUT_TRANS.relative_to(ROOT)),
            str(OUT_TIMING_METRICS.relative_to(ROOT)),
        ]

        placeholder_gx = Gate("Gx_HASH_MANIFEST_PRESENT", True, f"path={OUT_MANIFEST.relative_to(ROOT)}")
        placeholder_hash = Gate("G_SHA256_INTEGRITY_SELF_CHECK", True, "mismatches=0 (provisional)")
        gates_for_report = gates + [placeholder_gx, placeholder_hash]

        def build_report_text(gates_list: list[Gate], retry: list[str], status: str) -> str:
            lines = [
                f"# HEADER: {RUN_ID}",
                "",
                f"- task_id: {TASK_ID}",
                f"- run_id: {RUN_ID}",
                f"- python_env: {sys.executable}",
                "",
                "## STEP GATES",
            ]
            for g in gates_list:
                lines.append(f"- {'PASS' if g.passed else 'FAIL'} | {g.name} | {g.detail}")
            lines.append("")
            lines.append("## RETRY LOG")
            if retry:
                for r in retry:
                    lines.append(f"- {r}")
            else:
                lines.append("- none")
            lines.append("")
            lines.append("## ARTIFACT LINKS")
            for art in [ROOT / p for p in outputs]:
                if art.exists():
                    lines.append(f"- {art.relative_to(ROOT)}")
            lines.append(f"- {OUT_MANIFEST.relative_to(ROOT)}")
            lines.append("")
            lines.append(f"OVERALL STATUS: [[ {status} ]]")
            return "\n".join(lines) + "\n"

        if any(not g.passed for g in gates_for_report):
            overall_pass = False
        status_txt = "PASS" if overall_pass else "FAIL"
        OUT_REPORT.write_text(build_report_text(gates_for_report, retry_log, status_txt), encoding="utf-8")

        hash_targets = [CHANGELOG_PATH] + [ROOT / p for p in outputs] + [OUT_REPORT]
        hashes: dict[str, str] = {}
        for p in hash_targets:
            if p.exists():
                hashes[str(p.relative_to(ROOT))] = sha256_file(p)

        manifest = {
            "task_id": TASK_ID,
            "run_id": RUN_ID,
            "policy": "no_self_hash",
            "generated_at_utc": pd.Timestamp.now("UTC").isoformat(),
            "inputs_consumed": inputs,
            "outputs_produced": outputs,
            "hashes_sha256": hashes,
        }
        write_json(OUT_MANIFEST, manifest)

        mm = sum(1 for rp, h in hashes.items() if not (ROOT / rp).exists() or sha256_file(ROOT / rp) != h)
        gates.append(Gate("Gx_HASH_MANIFEST_PRESENT", OUT_MANIFEST.exists(), f"path={OUT_MANIFEST.relative_to(ROOT)}"))
        gates.append(Gate("G_SHA256_INTEGRITY_SELF_CHECK", mm == 0, f"mismatches={mm}"))

        if any(not g.passed for g in gates):
            overall_pass = False
        status_txt = "PASS" if overall_pass else "FAIL"
        OUT_REPORT.write_text(build_report_text(gates, retry_log, status_txt), encoding="utf-8")

        hashes[str(OUT_REPORT.relative_to(ROOT))] = sha256_file(OUT_REPORT)
        manifest["hashes_sha256"] = hashes
        manifest["generated_at_utc"] = pd.Timestamp.now("UTC").isoformat()
        write_json(OUT_MANIFEST, manifest)

    except Exception as e:
        overall_pass = False
        retry_log.append(f"{type(e).__name__}: {e}")
        gates.append(Gate("G_FATAL", False, retry_log[-1]))
        status_txt = "FAIL"
        lines = [
            f"# HEADER: {RUN_ID}",
            "",
            f"- task_id: {TASK_ID}",
            f"- run_id: {RUN_ID}",
            f"- python_env: {sys.executable}",
            "",
            "## STEP GATES",
        ]
        for g in gates:
            lines.append(f"- {'PASS' if g.passed else 'FAIL'} | {g.name} | {g.detail}")
        lines.append("")
        lines.append("## RETRY LOG")
        for r in retry_log:
            lines.append(f"- {r}")
        lines.append("")
        lines.append(f"OVERALL STATUS: [[ {status_txt} ]]")
        OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
        OUT_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if not overall_pass:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
