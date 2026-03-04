#!/home/wilson/AGNO_WORKSPACE/.venv/bin/python
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sklearn.impute import SimpleImputer
from sklearn.metrics import balanced_accuracy_score, log_loss, roc_auc_score
from sklearn.model_selection import TimeSeriesSplit
from xgboost import XGBClassifier


if not ("agno_env" in sys.prefix or ".venv" in sys.prefix):
    raise RuntimeError("FATAL: Not in agno_env/.venv")


TASK_ID = "T114"
RUN_ID = "T114-PHASE9C-ML-US-V1"
ROOT = Path("/home/wilson/AGNO_WORKSPACE")
PYTHON_ENV = ROOT / ".venv/bin/python"
CHANGELOG_PATH = ROOT / "00_Strategy/changelog.md"

IN_FEATURES = ROOT / "src/data_engine/features/T113_US_FEATURE_MATRIX_DAILY.parquet"
IN_DATASET = ROOT / "src/data_engine/features/T113_US_DATASET_DAILY.parquet"
IN_LABELS_T112 = ROOT / "src/data_engine/features/T112_US_LABELS_DAILY.parquet"
IN_LABELS_T113 = ROOT / "src/data_engine/features/T113_US_LABELS_DAILY.parquet"
IN_FEATURE_INV = ROOT / "outputs/governanca/T113-PHASE9B-US-FEATURES-V1_evidence/feature_inventory.csv"

OUT_SCRIPT = ROOT / "scripts/t114_ml_trigger_us_xgboost_ablation_v1.py"
OUT_PRED = ROOT / "src/data_engine/features/T114_US_ML_PREDICTIONS_DAILY.parquet"
OUT_CFG = ROOT / "src/data_engine/features/T114_US_ML_SELECTED_CONFIG.json"
OUT_HTML = ROOT / "outputs/plots/T114_STATE3_PHASE9C_US_ML_TRIGGER_DASHBOARD.html"
OUT_REPORT = ROOT / "outputs/governanca/T114-PHASE9C-ML-US-V1_report.md"
OUT_MANIFEST = ROOT / "outputs/governanca/T114-PHASE9C-ML-US-V1_manifest.json"
OUT_EVID_DIR = ROOT / "outputs/governanca/T114-PHASE9C-ML-US-V1_evidence"
OUT_PREFLIGHT = OUT_EVID_DIR / "input_preflight.json"
OUT_GUARD = OUT_EVID_DIR / "feature_guard.json"
OUT_ABL_PARQ = OUT_EVID_DIR / "ablation_results.parquet"
OUT_ABL_CSV = OUT_EVID_DIR / "ablation_results.csv"
OUT_DUAL_ACID = OUT_EVID_DIR / "dual_acid_metrics.json"
OUT_WF_CV = OUT_EVID_DIR / "walkforward_cv_summary.json"

RECORTE_START = pd.Timestamp("2018-07-02")
RECORTE_END = pd.Timestamp("2026-02-26")
TRAIN_END = pd.Timestamp("2022-12-30")
HOLDOUT_START = pd.Timestamp("2023-01-02")
EXPECTED_TOTAL = 1902
EXPECTED_TRAIN = 1115
EXPECTED_HOLDOUT = 787

THRESHOLDS = [0.40, 0.45, 0.50, 0.55, 0.60]
H_INS = [1, 2, 3]
H_OUTS = [1, 2, 3]

ACID_BR_START = pd.Timestamp("2024-11-01")
ACID_BR_END = pd.Timestamp("2025-11-30")
ACID_US_START = pd.Timestamp("2025-03-06")
ACID_US_END = pd.Timestamp("2025-05-09")

TRACEABILITY_LINE = "- 2026-03-04T00:00:00Z | EXEC: T114 ML trigger US (XGBoost walk-forward + ablação threshold/histerese) com feature-guard (27 features T113; exclui sp500_close) e dual acid window (BR+US). Artefatos: scripts/t114_ml_trigger_us_xgboost_ablation_v1.py; src/data_engine/features/T114_US_ML_{PREDICTIONS_DAILY,SELECTED_CONFIG}.(parquet|json); outputs/plots/T114_STATE3_PHASE9C_US_ML_TRIGGER_DASHBOARD.html; outputs/governanca/T114-PHASE9C-ML-US-V1_{report,manifest}.md"


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


def append_changelog_one_line_idempotent(line: str) -> bool:
    existing = CHANGELOG_PATH.read_text(encoding="utf-8") if CHANGELOG_PATH.exists() else ""
    if line in existing:
        return True
    text = existing
    if text and not text.endswith("\n"):
        text += "\n"
    text += line.rstrip("\n") + "\n"
    CHANGELOG_PATH.write_text(text, encoding="utf-8")
    return line in CHANGELOG_PATH.read_text(encoding="utf-8")


def count_switches(state_cash: pd.Series) -> int:
    return int((state_cash.astype(int).diff().abs() == 1).sum())


def compute_mdd(equity: pd.Series) -> float:
    eq = pd.to_numeric(equity, errors="coerce").to_numpy(dtype=float)
    if len(eq) == 0:
        return 0.0
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    return float(np.min(dd))


def compute_sharpe(daily_ret: pd.Series) -> float:
    r = pd.to_numeric(daily_ret, errors="coerce").fillna(0.0).to_numpy(dtype=float)
    std = float(np.std(r, ddof=1)) if len(r) > 1 else 0.0
    if std <= 0:
        return 0.0
    return float((np.mean(r) / std) * np.sqrt(252.0))


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


def evaluate_subset(df: pd.DataFrame) -> dict[str, float]:
    if len(df) == 0:
        return {
            "rows": 0,
            "cash_frac": 0.0,
            "switches": 0,
            "precision_cash": 0.0,
            "recall_cash": 0.0,
            "equity_end": 100000.0,
            "mdd": 0.0,
            "sharpe": 0.0,
        }
    y = df["y_cash_us_v1"].astype(int)
    s = df["state_cash"].astype(int)
    tp = int(((s == 1) & (y == 1)).sum())
    fp = int(((s == 1) & (y == 0)).sum())
    fn = int(((s == 0) & (y == 1)).sum())
    precision = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
    recall = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0

    ret = pd.to_numeric(df["strategy_ret"], errors="coerce").fillna(0.0)
    equity = 100000.0 * (1.0 + ret).cumprod()
    return {
        "rows": int(len(df)),
        "cash_frac": float(s.mean()),
        "switches": int(count_switches(s)),
        "precision_cash": precision,
        "recall_cash": recall,
        "equity_end": float(equity.iloc[-1]),
        "mdd": compute_mdd(equity),
        "sharpe": compute_sharpe(ret),
    }


def render_report(
    gates: list[Gate],
    retry_log: list[str],
    overall: bool,
    winner: dict[str, Any],
    dual_acid: dict[str, Any],
) -> str:
    lines = [
        f"# HEADER: {TASK_ID}",
        "",
        "## STEP GATES",
    ]
    for g in gates:
        lines.append(f"- {g.name}: {'PASS' if g.passed else 'FAIL'} | {g.detail}")
    lines.extend(
        [
            "",
            "## RESUMO",
            f"- winner: thr={winner.get('threshold')} h_in={winner.get('h_in')} h_out={winner.get('h_out')}",
            (
                f"- holdout: mdd={winner.get('mdd_holdout'):.4f} sharpe={winner.get('sharpe_holdout'):.4f} "
                f"cash_frac={winner.get('cash_frac_holdout'):.4f}"
            ),
            f"- dual_acid: acid_br_rows={dual_acid['acid_br']['rows']} | acid_us_rows={dual_acid['acid_us']['rows']}",
            "",
            "## RETRY LOG",
            "- none" if not retry_log else "",
        ]
    )
    if retry_log:
        for r in retry_log:
            lines.append(f"- {r}")
    lines.extend(
        [
            "",
            "## ARTIFACT LINKS",
            f"- {OUT_PRED.relative_to(ROOT)}",
            f"- {OUT_CFG.relative_to(ROOT)}",
            f"- {OUT_HTML.relative_to(ROOT)}",
            f"- {OUT_REPORT.relative_to(ROOT)}",
            f"- {OUT_MANIFEST.relative_to(ROOT)}",
            f"- {OUT_PREFLIGHT.relative_to(ROOT)}",
            f"- {OUT_GUARD.relative_to(ROOT)}",
            f"- {OUT_ABL_PARQ.relative_to(ROOT)}",
            f"- {OUT_ABL_CSV.relative_to(ROOT)}",
            f"- {OUT_DUAL_ACID.relative_to(ROOT)}",
            f"- {OUT_WF_CV.relative_to(ROOT)}",
            "",
            f"## OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    gates: list[Gate] = []
    retry_log: list[str] = []
    winner: dict[str, Any] = {}
    dual_acid_payload: dict[str, Any] = {"acid_br": {"rows": 0}, "acid_us": {"rows": 0}}

    try:
        for p in [
            OUT_PRED,
            OUT_CFG,
            OUT_HTML,
            OUT_REPORT,
            OUT_MANIFEST,
            OUT_PREFLIGHT,
            OUT_GUARD,
            OUT_ABL_PARQ,
            OUT_ABL_CSV,
            OUT_DUAL_ACID,
            OUT_WF_CV,
        ]:
            p.parent.mkdir(parents=True, exist_ok=True)

        env_ok = PYTHON_ENV.exists() and (".venv" in sys.prefix or "agno_env" in sys.prefix)
        gates.append(Gate("G_ENV_VENV", env_ok, f"python={sys.executable}"))
        if not env_ok:
            raise RuntimeError("python env check failed")

        labels_path = IN_LABELS_T113 if IN_LABELS_T113.exists() else IN_LABELS_T112
        inputs_ok = all([IN_FEATURES.exists(), IN_DATASET.exists(), labels_path.exists(), IN_FEATURE_INV.exists()])
        gates.append(
            Gate(
                "G0_INPUTS_EXIST",
                inputs_ok,
                (
                    f"features={IN_FEATURES.exists()} dataset={IN_DATASET.exists()} "
                    f"labels={labels_path.exists()} inv={IN_FEATURE_INV.exists()}"
                ),
            )
        )
        if not inputs_ok:
            raise RuntimeError("required inputs missing")

        fm = pd.read_parquet(IN_FEATURES).copy()
        ds = pd.read_parquet(IN_DATASET).copy()
        lb = pd.read_parquet(labels_path).copy()
        inv = pd.read_csv(IN_FEATURE_INV)

        fm["date"] = pd.to_datetime(fm["date"]).dt.normalize()
        ds["date"] = pd.to_datetime(ds["date"]).dt.normalize()
        lb["date"] = pd.to_datetime(lb["date"]).dt.normalize()

        fm = fm[(fm["date"] >= RECORTE_START) & (fm["date"] <= RECORTE_END)].sort_values("date").reset_index(drop=True)
        ds = ds[(ds["date"] >= RECORTE_START) & (ds["date"] <= RECORTE_END)].sort_values("date").reset_index(drop=True)
        lb = lb[(lb["date"] >= RECORTE_START) & (lb["date"] <= RECORTE_END)].sort_values("date").reset_index(drop=True)
        total_ok = len(fm) == EXPECTED_TOTAL and len(ds) == EXPECTED_TOTAL and len(lb) == EXPECTED_TOTAL
        train_rows = int((fm["date"] <= TRAIN_END).sum())
        holdout_rows = int((fm["date"] >= HOLDOUT_START).sum())
        split_ok = train_rows == EXPECTED_TRAIN and holdout_rows == EXPECTED_HOLDOUT
        gates.append(
            Gate(
                "G1_SCOPE_AND_SPLIT_OK",
                total_ok and split_ok,
                f"fm={len(fm)} ds={len(ds)} lb={len(lb)} train={train_rows} holdout={holdout_rows}",
            )
        )
        if not (total_ok and split_ok):
            raise RuntimeError("scope/split mismatch")

        feature_list = inv["feature"].dropna().astype(str).drop_duplicates().tolist()
        fm_feature_cols = [c for c in fm.columns if c != "date"]
        forbidden = {"sp500_close", "y_cash_us_v1", "variant_id_selected", "fwd_window_selected", "drawdown_threshold_selected"}
        missing_in_fm = sorted(set(feature_list) - set(fm_feature_cols))
        extra_in_fm = sorted(set(fm_feature_cols) - set(feature_list))
        forbidden_found = sorted(set(feature_list) & forbidden)
        guard_ok = (
            len(feature_list) == 27
            and len(missing_in_fm) == 0
            and len(extra_in_fm) == 0
            and len(forbidden_found) == 0
            and "sp500_close" not in feature_list
        )
        guard_payload = {
            "feature_count_expected": 27,
            "feature_count_inventory": len(feature_list),
            "feature_count_feature_matrix": len(fm_feature_cols),
            "feature_list": feature_list,
            "missing_in_feature_matrix": missing_in_fm,
            "extra_in_feature_matrix": extra_in_fm,
            "forbidden_columns_found": forbidden_found,
            "checks_passed": guard_ok,
        }
        write_json(OUT_GUARD, guard_payload)
        gates.append(Gate("G_FEATURE_GUARD", guard_ok, f"missing={len(missing_in_fm)} extra={len(extra_in_fm)}"))
        if not guard_ok:
            raise RuntimeError("feature guard failed")

        base = fm[["date"] + feature_list].merge(lb[["date", "y_cash_us_v1"]], on="date", how="inner")
        base = base.merge(ds[["date", "sp500_close"]], on="date", how="inner")
        join_ok = len(base) == EXPECTED_TOTAL
        label_ok = not base["y_cash_us_v1"].isna().any() and set(base["y_cash_us_v1"].astype(int).unique()).issubset({0, 1})
        gates.append(Gate("G2_JOIN_LABEL_OK", join_ok and label_ok, f"rows={len(base)} label_unique={sorted(base['y_cash_us_v1'].astype(int).unique().tolist())}"))
        if not (join_ok and label_ok):
            raise RuntimeError("join/label contract failed")

        base["split"] = np.where(base["date"] <= TRAIN_END, "TRAIN", "HOLDOUT")
        base["sp500_ret_1d"] = pd.to_numeric(base["sp500_close"], errors="coerce").pct_change().fillna(0.0)
        train_mask = base["split"] == "TRAIN"
        hold_mask = base["split"] == "HOLDOUT"

        X = base[feature_list].copy()
        y = base["y_cash_us_v1"].astype(int).copy()

        tscv = TimeSeriesSplit(n_splits=5)
        train_idx = np.where(train_mask.values)[0]
        X_train = X.iloc[train_idx]
        y_train = y.iloc[train_idx]
        oof = np.full(len(X_train), np.nan, dtype=float)
        fold_stats: list[dict[str, Any]] = []

        for fold_id, (tr_i, va_i) in enumerate(tscv.split(X_train), start=1):
            x_tr = X_train.iloc[tr_i]
            y_tr = y_train.iloc[tr_i]
            x_va = X_train.iloc[va_i]
            y_va = y_train.iloc[va_i]

            imp = SimpleImputer(strategy="median")
            x_tr_imp = imp.fit_transform(x_tr)
            x_va_imp = imp.transform(x_va)

            model = XGBClassifier(
                n_estimators=300,
                max_depth=4,
                learning_rate=0.03,
                subsample=0.9,
                colsample_bytree=0.9,
                objective="binary:logistic",
                eval_metric="logloss",
                random_state=42,
            )
            model.fit(x_tr_imp, y_tr)
            p_va = model.predict_proba(x_va_imp)[:, 1]
            oof[va_i] = p_va

            y_va_np = y_va.to_numpy(dtype=int)
            y_hat = (p_va >= 0.5).astype(int)
            fold_stats.append(
                {
                    "fold": fold_id,
                    "train_rows": int(len(tr_i)),
                    "valid_rows": int(len(va_i)),
                    "logloss": float(log_loss(y_va_np, p_va, labels=[0, 1])),
                    "auc": float(roc_auc_score(y_va_np, p_va)) if len(np.unique(y_va_np)) > 1 else 0.5,
                    "balacc": float(balanced_accuracy_score(y_va_np, y_hat)),
                }
            )

        imp_full = SimpleImputer(strategy="median")
        X_train_imp = imp_full.fit_transform(X_train)
        X_hold_imp = imp_full.transform(X.loc[hold_mask])
        X_train_all_imp = imp_full.transform(X_train)

        model_final = XGBClassifier(
            n_estimators=300,
            max_depth=4,
            learning_rate=0.03,
            subsample=0.9,
            colsample_bytree=0.9,
            objective="binary:logistic",
            eval_metric="logloss",
            random_state=42,
        )
        model_final.fit(X_train_imp, y_train)
        hold_proba = model_final.predict_proba(X_hold_imp)[:, 1]
        train_fallback = model_final.predict_proba(X_train_all_imp)[:, 1]
        oof = np.where(np.isnan(oof), train_fallback, oof)

        proba_all = np.zeros(len(base), dtype=float)
        proba_all[train_idx] = oof
        proba_all[np.where(hold_mask.values)[0]] = hold_proba
        base["proba"] = proba_all

        wf_summary = {
            "n_splits": 5,
            "folds": fold_stats,
            "mean_logloss": float(np.mean([f["logloss"] for f in fold_stats])),
            "mean_auc": float(np.mean([f["auc"] for f in fold_stats])),
            "mean_balacc": float(np.mean([f["balacc"] for f in fold_stats])),
            "oof_missing_after_fill": int(np.isnan(oof).sum()),
        }
        write_json(OUT_WF_CV, wf_summary)
        gates.append(Gate("G3_WALKFORWARD_OOF_READY", wf_summary["oof_missing_after_fill"] == 0, f"folds={len(fold_stats)}"))

        rows = []
        for thr in THRESHOLDS:
            for h_in in H_INS:
                for h_out in H_OUTS:
                    state_cash = hysteresis_state(base["proba"], thr, h_in, h_out)
                    work = base.copy()
                    work["state_cash"] = state_cash.astype(int)
                    work["state_market"] = 1 - work["state_cash"]
                    work["strategy_ret"] = np.where(work["state_cash"] == 1, 0.0, work["sp500_ret_1d"])

                    tr_eval = evaluate_subset(work.loc[train_mask].copy())
                    ho_eval = evaluate_subset(work.loc[hold_mask].copy())
                    feasible = 0.05 <= tr_eval["cash_frac"] <= 0.80

                    rows.append(
                        {
                            "threshold": float(thr),
                            "h_in": int(h_in),
                            "h_out": int(h_out),
                            "feasible_train": bool(feasible),
                            "cash_frac_train": tr_eval["cash_frac"],
                            "switches_train": tr_eval["switches"],
                            "precision_train": tr_eval["precision_cash"],
                            "recall_train": tr_eval["recall_cash"],
                            "equity_train": tr_eval["equity_end"],
                            "mdd_train": tr_eval["mdd"],
                            "sharpe_train": tr_eval["sharpe"],
                            "cash_frac_holdout": ho_eval["cash_frac"],
                            "switches_holdout": ho_eval["switches"],
                            "precision_holdout": ho_eval["precision_cash"],
                            "recall_holdout": ho_eval["recall_cash"],
                            "equity_holdout": ho_eval["equity_end"],
                            "mdd_holdout": ho_eval["mdd"],
                            "sharpe_holdout": ho_eval["sharpe"],
                        }
                    )

        abl = pd.DataFrame(rows)
        gates.append(Gate("G4_ABLATION_GRID_OK", len(abl) == len(THRESHOLDS) * len(H_INS) * len(H_OUTS), f"rows={len(abl)}"))
        if len(abl) == 0:
            raise RuntimeError("ablation empty")

        abl = abl.sort_values(
            by=["feasible_train", "mdd_train", "sharpe_train", "recall_train", "switches_train", "threshold", "h_in", "h_out"],
            ascending=[False, False, False, False, True, True, True, True],
        ).reset_index(drop=True)
        abl["rank"] = np.arange(1, len(abl) + 1)
        win = abl.iloc[0].to_dict()
        winner = {k: (float(v) if isinstance(v, np.floating) else int(v) if isinstance(v, np.integer) else v) for k, v in win.items()}

        base["state_cash"] = hysteresis_state(base["proba"], winner["threshold"], winner["h_in"], winner["h_out"]).astype(int)
        base["state_market"] = 1 - base["state_cash"]
        base["strategy_ret"] = np.where(base["state_cash"] == 1, 0.0, base["sp500_ret_1d"])
        base["equity"] = 100000.0 * (1.0 + base["strategy_ret"]).cumprod()
        base["chosen_threshold"] = float(winner["threshold"])
        base["chosen_h_in"] = int(winner["h_in"])
        base["chosen_h_out"] = int(winner["h_out"])

        hold_eval = evaluate_subset(base.loc[hold_mask].copy())
        winner["mdd_holdout"] = hold_eval["mdd"]
        winner["sharpe_holdout"] = hold_eval["sharpe"]
        winner["cash_frac_holdout"] = hold_eval["cash_frac"]

        # Architect criterion explicit in JSON (keep as requested)
        mdd_target_ok = float(winner["mdd_holdout"]) < -0.10
        gates.append(Gate("G5_HOLDOUT_MDD_TARGET", mdd_target_ok, f"mdd_holdout={winner['mdd_holdout']:.4f} target=<-0.10"))
        if not mdd_target_ok:
            raise RuntimeError("holdout mdd target failed")

        acid_br_mask = (base["date"] >= ACID_BR_START) & (base["date"] <= ACID_BR_END)
        acid_us_mask = (base["date"] >= ACID_US_START) & (base["date"] <= ACID_US_END)
        acid_br = evaluate_subset(base.loc[acid_br_mask].copy())
        acid_us = evaluate_subset(base.loc[acid_us_mask].copy())
        dual_acid_payload = {
            "acid_br": {"start": ACID_BR_START, "end": ACID_BR_END, **acid_br},
            "acid_us": {"start": ACID_US_START, "end": ACID_US_END, **acid_us},
        }
        write_json(OUT_DUAL_ACID, dual_acid_payload)
        gates.append(
            Gate(
                "G6_DUAL_ACID_METRICS_READY",
                acid_br["rows"] > 0 and acid_us["rows"] > 0,
                f"acid_br_rows={acid_br['rows']} acid_us_rows={acid_us['rows']}",
            )
        )

        preflight = {
            "inputs": {
                "features": str(IN_FEATURES.relative_to(ROOT)),
                "dataset": str(IN_DATASET.relative_to(ROOT)),
                "labels": str(labels_path.relative_to(ROOT)),
                "feature_inventory": str(IN_FEATURE_INV.relative_to(ROOT)),
            },
            "rows": {
                "features": len(fm),
                "dataset": len(ds),
                "labels": len(lb),
                "base_joined": len(base),
                "train": int(train_mask.sum()),
                "holdout": int(hold_mask.sum()),
            },
            "date_range": {"start": base["date"].min(), "end": base["date"].max()},
        }
        write_json(OUT_PREFLIGHT, preflight)

        pred_cols = [
            "date",
            "split",
            "y_cash_us_v1",
            "proba",
            "state_cash",
            "state_market",
            "chosen_threshold",
            "chosen_h_in",
            "chosen_h_out",
            "sp500_close",
            "sp500_ret_1d",
            "strategy_ret",
            "equity",
        ]
        base[pred_cols].to_parquet(OUT_PRED, index=False)
        abl.to_parquet(OUT_ABL_PARQ, index=False)
        abl.to_csv(OUT_ABL_CSV, index=False)
        write_json(OUT_CFG, {"task_id": TASK_ID, "run_id": RUN_ID, "winner": winner, "selection_policy": "TRAIN_ONLY"})
        gates.append(
            Gate(
                "G7_OUTPUT_ARTIFACTS_WRITTEN",
                OUT_PRED.exists() and OUT_CFG.exists() and OUT_ABL_PARQ.exists() and OUT_ABL_CSV.exists(),
                f"pred={OUT_PRED.exists()} cfg={OUT_CFG.exists()} abl={OUT_ABL_PARQ.exists()}",
            )
        )

        fig = make_subplots(
            rows=3,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.06,
            specs=[[{"type": "xy"}], [{"type": "xy"}], [{"type": "table"}]],
            subplot_titles=("Equity + Cash Shading", "Drawdown", "Winner + Dual Acid Summary"),
        )
        fig.add_trace(go.Scatter(x=base["date"], y=base["equity"], name="equity"), row=1, col=1)
        dd = base["equity"] / base["equity"].cummax() - 1.0
        fig.add_trace(go.Scatter(x=base["date"], y=dd, name="drawdown"), row=2, col=1)
        fig.add_hline(y=-0.10, line_dash="dash", line_color="red", row=2, col=1)

        arr = base["state_cash"].to_numpy(dtype=int)
        start = None
        for i, v in enumerate(arr):
            if v == 1 and start is None:
                start = i
            if v == 0 and start is not None:
                fig.add_vrect(
                    x0=base["date"].iloc[start],
                    x1=base["date"].iloc[i - 1],
                    fillcolor="orange",
                    opacity=0.15,
                    line_width=0,
                    row=1,
                    col=1,
                )
                start = None
        if start is not None:
            fig.add_vrect(
                x0=base["date"].iloc[start],
                x1=base["date"].iloc[-1],
                fillcolor="orange",
                opacity=0.15,
                line_width=0,
                row=1,
                col=1,
            )

        table_rows = [
            ["threshold", "h_in", "h_out", "mdd_holdout", "sharpe_holdout", "acid_br_mdd", "acid_us_mdd"],
            [
                str(winner["threshold"]),
                str(winner["h_in"]),
                str(winner["h_out"]),
                f"{winner['mdd_holdout']:.4f}",
                f"{winner['sharpe_holdout']:.4f}",
                f"{dual_acid_payload['acid_br']['mdd']:.4f}",
                f"{dual_acid_payload['acid_us']['mdd']:.4f}",
            ],
        ]
        fig.add_trace(go.Table(header={"values": table_rows[0]}, cells={"values": [table_rows[1]]}), row=3, col=1)
        fig.update_layout(height=1250, template="plotly_white", title="T114 - US ML Trigger (XGBoost + Dual Acid)")
        fig.write_html(str(OUT_HTML), include_plotlyjs="cdn")
        gates.append(Gate("G8_DASHBOARD_READY", OUT_HTML.exists(), f"path={OUT_HTML}"))

        ch_ok = append_changelog_one_line_idempotent(TRACEABILITY_LINE)
        gates.append(Gate("G_CHLOG_UPDATED", ch_ok, f"path={CHANGELOG_PATH}"))

        OUT_REPORT.write_text(
            render_report(gates, retry_log, all(g.passed for g in gates), winner, dual_acid_payload),
            encoding="utf-8",
        )

        outputs_hash = [
            OUT_SCRIPT,
            OUT_PRED,
            OUT_CFG,
            OUT_HTML,
            OUT_REPORT,
            OUT_PREFLIGHT,
            OUT_GUARD,
            OUT_ABL_PARQ,
            OUT_ABL_CSV,
            OUT_DUAL_ACID,
            OUT_WF_CV,
            CHANGELOG_PATH,
        ]
        manifest = {
            "task_id": TASK_ID,
            "run_id": RUN_ID,
            "manifest_policy": "no_self_hash",
            "inputs_consumed": [
                str(IN_FEATURES.relative_to(ROOT)),
                str(IN_DATASET.relative_to(ROOT)),
                str(labels_path.relative_to(ROOT)),
                str(IN_FEATURE_INV.relative_to(ROOT)),
            ],
            "outputs_produced": [
                str(OUT_SCRIPT.relative_to(ROOT)),
                str(OUT_PRED.relative_to(ROOT)),
                str(OUT_CFG.relative_to(ROOT)),
                str(OUT_HTML.relative_to(ROOT)),
                str(OUT_REPORT.relative_to(ROOT)),
                str(OUT_MANIFEST.relative_to(ROOT)),
                str(OUT_PREFLIGHT.relative_to(ROOT)),
                str(OUT_GUARD.relative_to(ROOT)),
                str(OUT_ABL_PARQ.relative_to(ROOT)),
                str(OUT_ABL_CSV.relative_to(ROOT)),
                str(OUT_DUAL_ACID.relative_to(ROOT)),
                str(OUT_WF_CV.relative_to(ROOT)),
            ],
            "hashes_sha256": {str(p.relative_to(ROOT)): sha256_file(p) for p in outputs_hash},
        }
        write_json(OUT_MANIFEST, manifest)
        gates.append(Gate("Gx_HASH_MANIFEST_PRESENT", OUT_MANIFEST.exists(), f"path={OUT_MANIFEST}"))

        mismatches = []
        for rel, exp in manifest["hashes_sha256"].items():
            got = sha256_file(ROOT / rel)
            if got != exp:
                mismatches.append(rel)
        hash_ok = len(mismatches) == 0
        gates.append(Gate("G_SHA256_INTEGRITY_SELF_CHECK", hash_ok, f"mismatches={len(mismatches)}"))

        overall = all(g.passed for g in gates)
        OUT_REPORT.write_text(render_report(gates, retry_log, overall, winner, dual_acid_payload), encoding="utf-8")
        manifest["hashes_sha256"] = {str(p.relative_to(ROOT)): sha256_file(p) for p in outputs_hash}
        write_json(OUT_MANIFEST, manifest)

        print(f"HEADER: {TASK_ID}")
        print("STEP GATES:")
        for g in gates:
            print(f"- {g.name}: {'PASS' if g.passed else 'FAIL'} | {g.detail}")
        print("RETRY LOG:")
        print("- none" if not retry_log else "\n".join(f"- {r}" for r in retry_log))
        print("ARTIFACT LINKS:")
        print(f"- {OUT_PRED}")
        print(f"- {OUT_CFG}")
        print(f"- {OUT_HTML}")
        print(f"- {OUT_REPORT}")
        print(f"- {OUT_MANIFEST}")
        print(f"- {OUT_PREFLIGHT}")
        print(f"- {OUT_GUARD}")
        print(f"- {OUT_ABL_PARQ}")
        print(f"- {OUT_ABL_CSV}")
        print(f"- {OUT_DUAL_ACID}")
        print(f"- {OUT_WF_CV}")
        print(f"OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]")
        return 0 if overall else 2
    except Exception as exc:
        retry_log.append(f"FATAL: {type(exc).__name__}: {exc}")
        gates.append(Gate("G_FATAL", False, f"{type(exc).__name__}: {exc}"))
        OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
        OUT_REPORT.write_text(render_report(gates, retry_log, False, winner, dual_acid_payload), encoding="utf-8")
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
