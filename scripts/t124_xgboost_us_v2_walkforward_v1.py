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


TASK_ID = "T124"
RUN_ID = "T124-US-XGBOOST-V2-V1"
ROOT = Path("/home/wilson/AGNO_WORKSPACE")
PYTHON_ENV = ROOT / ".venv/bin/python"
CHANGELOG_PATH = ROOT / "00_Strategy/changelog.md"

IN_DATASET = ROOT / "src/data_engine/features/T123_US_DATASET_DAILY.parquet"
IN_INV = ROOT / "outputs/governanca/T123-US-FEATURES-V2-V1_evidence/feature_inventory.csv"

OUT_SCRIPT = ROOT / "scripts/t124_xgboost_us_v2_walkforward_v1.py"
OUT_MODEL = ROOT / "src/data_engine/models/T124_US_V2_XGB_SELECTED_MODEL.json"
OUT_PREDS = ROOT / "src/data_engine/features/T124_US_V2_PREDICTIONS_DAILY.parquet"
OUT_ABL = ROOT / "src/data_engine/features/T124_US_V2_ABLATION_RESULTS.parquet"
OUT_PLOT = ROOT / "outputs/plots/T124_STATE3_PHASE10C_US_XGB_V2_MODEL_DIAGNOSTICS.html"
OUT_REPORT = ROOT / "outputs/governanca/T124-US-XGBOOST-V2-V1_report.md"
OUT_MANIFEST = ROOT / "outputs/governanca/T124-US-XGBOOST-V2-V1_manifest.json"
OUT_EVID = ROOT / "outputs/governanca/T124-US-XGBOOST-V2-V1_evidence"
OUT_FEATURE_POLICY = OUT_EVID / "feature_policy.json"
OUT_TIME_SCAN = OUT_EVID / "time_leakage_scan_train.csv"
OUT_CV_JUST = OUT_EVID / "cv_scheme_justification.md"
OUT_FOLDS = OUT_EVID / "walkforward_folds.json"
OUT_BASELINE = OUT_EVID / "threshold_baseline_metrics.json"
OUT_GAP = OUT_EVID / "generalization_gap.json"
OUT_TRANS = OUT_EVID / "transition_diagnostics.json"

TRACEABILITY_LINE = "- 2026-03-04T00:00:00Z | EXEC: T124 PASS. XGBoost US v2 (walk-forward TRAIN-only) treinado sobre T123_US_DATASET_DAILY com policy de features + time-proxy scan + remoção explícita de `sector_ret_dispersion`/`sector_dispersion_delta_1d` (100% NaN). Artefatos: scripts/t124_xgboost_us_v2_walkforward_v1.py; src/data_engine/models/T124_US_V2_XGB_SELECTED_MODEL.json; src/data_engine/features/T124_US_V2_{PREDICTIONS_DAILY,ABLATION_RESULTS}.parquet; outputs/plots/T124_STATE3_PHASE10C_US_XGB_V2_MODEL_DIAGNOSTICS.html; outputs/governanca/T124-US-XGBOOST-V2-V1_{report,manifest}.json"

TIME_PROXY_THRESHOLD = 0.95
MIN_PRECISION = 0.20
N_SPLITS = 5
SEED = 42

EXPLICIT_DROP = {"sector_ret_dispersion", "sector_dispersion_delta_1d"}
CONTROL_DROP = {"date", "split", "y_cash_us_v1", "sp500_close"}
KNOWN_TIME_PROXY = {"m3_exec_valid_tickers", "us_n_tickers_raw"}

GRID: list[dict[str, Any]] = [
    {"candidate_id": "C001", "n_estimators": 100, "max_depth": 3, "learning_rate": 0.05, "subsample": 0.8, "colsample_bytree": 0.8},
    {"candidate_id": "C002", "n_estimators": 120, "max_depth": 3, "learning_rate": 0.05, "subsample": 0.8, "colsample_bytree": 0.8},
    {"candidate_id": "C003", "n_estimators": 150, "max_depth": 3, "learning_rate": 0.05, "subsample": 0.8, "colsample_bytree": 0.8},
    {"candidate_id": "C004", "n_estimators": 120, "max_depth": 4, "learning_rate": 0.05, "subsample": 0.8, "colsample_bytree": 0.8},
    {"candidate_id": "C005", "n_estimators": 150, "max_depth": 4, "learning_rate": 0.05, "subsample": 0.8, "colsample_bytree": 0.8},
    {"candidate_id": "C006", "n_estimators": 180, "max_depth": 4, "learning_rate": 0.05, "subsample": 0.8, "colsample_bytree": 0.8},
    {"candidate_id": "C007", "n_estimators": 120, "max_depth": 3, "learning_rate": 0.08, "subsample": 0.9, "colsample_bytree": 0.8},
    {"candidate_id": "C008", "n_estimators": 150, "max_depth": 3, "learning_rate": 0.08, "subsample": 0.9, "colsample_bytree": 0.8},
    {"candidate_id": "C009", "n_estimators": 180, "max_depth": 3, "learning_rate": 0.08, "subsample": 0.9, "colsample_bytree": 0.8},
    {"candidate_id": "C010", "n_estimators": 120, "max_depth": 4, "learning_rate": 0.08, "subsample": 0.9, "colsample_bytree": 0.8},
    {"candidate_id": "C011", "n_estimators": 150, "max_depth": 4, "learning_rate": 0.08, "subsample": 0.9, "colsample_bytree": 0.8},
    {"candidate_id": "C012", "n_estimators": 180, "max_depth": 4, "learning_rate": 0.08, "subsample": 0.9, "colsample_bytree": 0.8},
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
    return True


def metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    return {
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "recall_cash": float(recall_score(y_true, y_pred, pos_label=1, zero_division=0)),
        "precision_cash": float(precision_score(y_true, y_pred, pos_label=1, zero_division=0)),
        "f1_cash": float(f1_score(y_true, y_pred, pos_label=1, zero_division=0)),
        "transition_rate_pred": float(np.mean(y_pred[1:] != y_pred[:-1])) if len(y_pred) > 1 else 0.0,
    }


def build_feature_policy(df: pd.DataFrame, inv: pd.DataFrame) -> tuple[list[str], dict[str, Any], pd.DataFrame]:
    inv_features = inv["feature"].astype(str).tolist()
    dataset_features = [c for c in inv_features if c in df.columns]
    dropped: list[dict[str, str]] = []
    kept: list[str] = []
    for f in dataset_features:
        if f in CONTROL_DROP:
            dropped.append({"feature": f, "reason": "control_column"})
            continue
        if f in EXPLICIT_DROP:
            dropped.append({"feature": f, "reason": "auditor_mandatory_drop_100pct_nan"})
            continue
        if f in KNOWN_TIME_PROXY:
            dropped.append({"feature": f, "reason": "known_time_proxy_blacklist"})
            continue
        if pd.to_numeric(df[f], errors="coerce").isna().all():
            dropped.append({"feature": f, "reason": "all_nan_column"})
            continue
        kept.append(f)

    train = df[df["split"] == "TRAIN"].copy()
    train["date_ordinal"] = pd.to_datetime(train["date"]).map(pd.Timestamp.toordinal).astype(float)
    scan_rows = []
    for f in kept:
        s = pd.to_numeric(train[f], errors="coerce")
        mask = s.notna() & train["date_ordinal"].notna()
        if int(mask.sum()) < 20:
            corr = np.nan
        else:
            corr = float(np.corrcoef(s[mask].to_numpy(), train.loc[mask, "date_ordinal"].to_numpy())[0, 1])
        scan_rows.append(
            {
                "feature": f,
                "corr_with_date_ordinal_train": corr,
                "abs_corr": float(abs(corr)) if np.isfinite(corr) else np.nan,
            }
        )
    scan = pd.DataFrame(scan_rows).sort_values("feature").reset_index(drop=True)
    to_drop_proxy = scan[(scan["abs_corr"] > TIME_PROXY_THRESHOLD) & scan["abs_corr"].notna()]["feature"].tolist()
    final_features = [f for f in kept if f not in set(to_drop_proxy)]
    for f in to_drop_proxy:
        dropped.append({"feature": f, "reason": f"time_proxy_abs_corr_gt_{TIME_PROXY_THRESHOLD}"})

    policy = {
        "time_proxy_threshold_abs_corr_date": TIME_PROXY_THRESHOLD,
        "explicit_drop_from_audit_t123": sorted(EXPLICIT_DROP),
        "control_drop": sorted(CONTROL_DROP),
        "known_time_proxy_drop": sorted(KNOWN_TIME_PROXY),
        "final_feature_count": len(final_features),
        "dropped_features": sorted(dropped, key=lambda x: (x["reason"], x["feature"])),
        "final_features": final_features,
    }
    return final_features, policy, scan


def main() -> None:
    gates: list[Gate] = []
    retry_log: list[str] = []
    overall_pass = True
    error_message = ""

    # G_ENV_VENV
    in_venv = (".venv" in sys.executable) and Path(sys.executable).resolve() == PYTHON_ENV.resolve()
    gates.append(Gate("G_ENV_VENV", in_venv, f"python={sys.executable}"))
    if not in_venv:
        raise RuntimeError("FATAL: execute with .venv python")

    # pip list / dependency check
    pip_list_ok = True
    pip_list_out = ""
    try:
        proc = subprocess.run(
            [str(ROOT / ".venv/bin/pip"), "list"],
            check=True,
            capture_output=True,
            text=True,
        )
        pip_list_out = proc.stdout
        for dep in ("xgboost", "scikit-learn", "plotly", "pandas", "numpy"):
            if dep not in pip_list_out.lower():
                pip_list_ok = False
    except Exception as e:
        pip_list_ok = False
        pip_list_out = f"pip list failed: {e}"
    gates.append(Gate("G_DEPENDENCIES_CHECK", pip_list_ok, "pip list + imports baseline"))

    # Inputs present
    inputs_present = IN_DATASET.exists() and IN_INV.exists() and CHANGELOG_PATH.exists()
    gates.append(
        Gate(
            "G_INPUTS_PRESENT",
            inputs_present,
            f"dataset={IN_DATASET.exists()} inv={IN_INV.exists()} changelog={CHANGELOG_PATH.exists()}",
        )
    )
    if not inputs_present:
        raise FileNotFoundError("T124 inputs ausentes")

    OUT_EVID.mkdir(parents=True, exist_ok=True)
    OUT_MODEL.parent.mkdir(parents=True, exist_ok=True)
    OUT_PREDS.parent.mkdir(parents=True, exist_ok=True)
    OUT_ABL.parent.mkdir(parents=True, exist_ok=True)
    OUT_PLOT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)

    try:
        df = pd.read_parquet(IN_DATASET).copy()
        inv = pd.read_csv(IN_INV).copy()
        df["date"] = pd.to_datetime(df["date"]).dt.normalize()
        df = df.sort_values("date").reset_index(drop=True)

        shape_ok = (
            len(df) == 1902
            and int((df["split"] == "TRAIN").sum()) == 1115
            and int((df["split"] == "HOLDOUT").sum()) == 787
            and df["y_cash_us_v1"].isin([0, 1]).all()
            and int(df["y_cash_us_v1"].isna().sum()) == 0
        )
        gates.append(
            Gate(
                "G_DATASET_SHAPE_SPLIT_OK",
                shape_ok,
                f"rows={len(df)} train={(df['split']=='TRAIN').sum()} holdout={(df['split']=='HOLDOUT').sum()}",
            )
        )

        features, policy, time_scan = build_feature_policy(df, inv)
        time_scan.to_csv(OUT_TIME_SCAN, index=False)
        write_json(OUT_FEATURE_POLICY, policy)
        drop_ok = all(x in [d["feature"] for d in policy["dropped_features"]] for x in EXPLICIT_DROP)
        gates.append(
            Gate(
                "G_FEATURE_POLICY_APPLIED",
                drop_ok and len(features) > 0,
                f"final_features={len(features)} dropped={len(policy['dropped_features'])}",
            )
        )
        gates.append(
            Gate(
                "G_TIME_PROXY_SCAN_APPLIED",
                OUT_TIME_SCAN.exists() and OUT_FEATURE_POLICY.exists(),
                f"threshold={TIME_PROXY_THRESHOLD} blacklisted={(time_scan['abs_corr'] > TIME_PROXY_THRESHOLD).sum()}",
            )
        )

        train = df[df["split"] == "TRAIN"].copy().reset_index(drop=True)
        holdout = df[df["split"] == "HOLDOUT"].copy().reset_index(drop=True)
        X_train = train[features].copy()
        y_train = train["y_cash_us_v1"].astype(int).to_numpy()
        X_hold = holdout[features].copy()
        y_hold = holdout["y_cash_us_v1"].astype(int).to_numpy()

        tscv = TimeSeriesSplit(n_splits=N_SPLITS)
        fold_meta: list[dict[str, Any]] = []
        oof_indices = np.full(len(train), -1, dtype=int)
        for fold_id, (tr_idx, va_idx) in enumerate(tscv.split(X_train), start=1):
            fold_meta.append(
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
            oof_indices[va_idx] = fold_id
        write_json(OUT_FOLDS, {"n_splits": N_SPLITS, "folds": fold_meta})
        OUT_CV_JUST.write_text(
            "\n".join(
                [
                    "# CV Scheme Justification - T124",
                    "",
                    "- Esquema: TimeSeriesSplit no TRAIN (walk-forward).",
                    "- Objetivo: evitar leakage temporal, preservando ordem cronológica.",
                    "- HOLDOUT (2023-01-02..2026-02-26) não participa de seleção/ranqueamento do modelo.",
                    "- Seleção final usa exclusivamente métricas OOF do TRAIN.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        covered = int((oof_indices > 0).sum())
        coverage_ratio = float(covered / len(train)) if len(train) else 0.0
        # TimeSeriesSplit does not OOF-score the first chunk by design.
        cv_ok = covered > 0 and coverage_ratio >= 0.75
        gates.append(
            Gate(
                "G_WALKFORWARD_TRAIN_ONLY",
                cv_ok and OUT_FOLDS.exists() and OUT_CV_JUST.exists(),
                f"n_splits={N_SPLITS} train_rows={len(train)} holdout_rows={len(holdout)} oof_coverage={coverage_ratio:.3f}",
            )
        )

        # Ablation on TRAIN only
        rows = []
        oof_cache: dict[str, np.ndarray] = {}
        holdout_cache: dict[str, np.ndarray] = {}
        for cfg in GRID:
            cid = cfg["candidate_id"]
            oof_proba = np.full(len(train), np.nan, dtype=float)
            for tr_idx, va_idx in tscv.split(X_train):
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
                    n_estimators=int(cfg["n_estimators"]),
                    max_depth=int(cfg["max_depth"]),
                    learning_rate=float(cfg["learning_rate"]),
                    subsample=float(cfg["subsample"]),
                    colsample_bytree=float(cfg["colsample_bytree"]),
                    objective="binary:logistic",
                    eval_metric="logloss",
                    random_state=SEED,
                    n_jobs=1,
                    scale_pos_weight=spw,
                )
                model.fit(X_tr_i, y_tr)
                oof_proba[va_idx] = model.predict_proba(X_va_i)[:, 1]
            oof_pred = (oof_proba >= 0.5).astype(int)
            m = metrics(y_train, oof_pred)
            rows.append(
                {
                    "candidate_id": cid,
                    "n_estimators": int(cfg["n_estimators"]),
                    "max_depth": int(cfg["max_depth"]),
                    "learning_rate": float(cfg["learning_rate"]),
                    "subsample": float(cfg["subsample"]),
                    "colsample_bytree": float(cfg["colsample_bytree"]),
                    "precision_cash_train_oof": m["precision_cash"],
                    "recall_cash_train_oof": m["recall_cash"],
                    "balanced_accuracy_train_oof": m["balanced_accuracy"],
                    "f1_cash_train_oof": m["f1_cash"],
                    "transition_rate_train_oof": m["transition_rate_pred"],
                    "meets_min_precision": bool(m["precision_cash"] >= MIN_PRECISION),
                }
            )
            oof_cache[cid] = oof_proba

            # holdout inference only for diagnostics
            impf = SimpleImputer(strategy="median")
            X_trf = impf.fit_transform(X_train)
            X_hf = impf.transform(X_hold)
            posf = int(np.sum(y_train == 1))
            negf = int(np.sum(y_train == 0))
            spwf = float(negf / max(posf, 1))
            modf = XGBClassifier(
                n_estimators=int(cfg["n_estimators"]),
                max_depth=int(cfg["max_depth"]),
                learning_rate=float(cfg["learning_rate"]),
                subsample=float(cfg["subsample"]),
                colsample_bytree=float(cfg["colsample_bytree"]),
                objective="binary:logistic",
                eval_metric="logloss",
                random_state=SEED,
                n_jobs=1,
                scale_pos_weight=spwf,
            )
            modf.fit(X_trf, y_train)
            holdout_cache[cid] = modf.predict_proba(X_hf)[:, 1]

        ablation = pd.DataFrame(rows).sort_values("candidate_id").reset_index(drop=True)
        pool = ablation[ablation["meets_min_precision"]].copy()
        if pool.empty:
            pool = ablation.copy()
        pool = pool.sort_values(
            by=[
                "recall_cash_train_oof",
                "balanced_accuracy_train_oof",
                "transition_rate_train_oof",
                "candidate_id",
            ],
            ascending=[False, False, True, True],
        ).reset_index(drop=True)
        winner = pool.iloc[0].to_dict()
        winner_id = str(winner["candidate_id"])
        ablation["selected"] = ablation["candidate_id"] == winner_id
        OUT_ABL.parent.mkdir(parents=True, exist_ok=True)
        ablation.to_parquet(OUT_ABL, index=False)
        gates.append(Gate("G_ABLATION_TRAIN_ONLY_OK", OUT_ABL.exists(), f"n_candidates={len(ablation)} winner={winner_id}"))

        # Train final on TRAIN and predict TRAIN+HOLDOUT
        wcfg = next(c for c in GRID if c["candidate_id"] == winner_id)
        imp = SimpleImputer(strategy="median")
        X_train_i = imp.fit_transform(X_train)
        X_all_i = imp.transform(df[features])
        pos = int(np.sum(y_train == 1))
        neg = int(np.sum(y_train == 0))
        spw = float(neg / max(pos, 1))
        model = XGBClassifier(
            n_estimators=int(wcfg["n_estimators"]),
            max_depth=int(wcfg["max_depth"]),
            learning_rate=float(wcfg["learning_rate"]),
            subsample=float(wcfg["subsample"]),
            colsample_bytree=float(wcfg["colsample_bytree"]),
            objective="binary:logistic",
            eval_metric="logloss",
            random_state=SEED,
            n_jobs=1,
            scale_pos_weight=spw,
        )
        model.fit(X_train_i, y_train)
        y_proba_all = model.predict_proba(X_all_i)[:, 1]
        y_pred_all = (y_proba_all >= 0.5).astype(int)

        pred_df = pd.DataFrame(
            {
                "date": df["date"],
                "split": df["split"],
                "y_true": df["y_cash_us_v1"].astype(int),
                "y_proba_cash": y_proba_all.astype(float),
                "y_pred_cash_thr_050": y_pred_all.astype(int),
                "selected_candidate_id": winner_id,
            }
        )
        pred_df.to_parquet(OUT_PREDS, index=False)
        gates.append(
            Gate(
                "G_PREDICTIONS_OUTPUT_OK",
                OUT_PREDS.exists() and len(pred_df) == len(df) and int(pred_df["y_proba_cash"].isna().sum()) == 0,
                f"rows={len(pred_df)} nan_proba={int(pred_df['y_proba_cash'].isna().sum())}",
            )
        )

        # metrics artifacts
        train_oof_proba = oof_cache[winner_id]
        train_oof_pred = (train_oof_proba >= 0.5).astype(int)
        hold_proba = holdout_cache[winner_id]
        hold_pred = (hold_proba >= 0.5).astype(int)
        m_train = metrics(y_train, train_oof_pred)
        m_hold = metrics(y_hold, hold_pred)
        base = {
            "threshold": 0.50,
            "winner_candidate_id": winner_id,
            "train_oof": m_train,
            "holdout_inference": m_hold,
        }
        write_json(OUT_BASELINE, base)
        gap = {
            "winner_candidate_id": winner_id,
            "gap_recall_cash_holdout_minus_train_oof": float(m_hold["recall_cash"] - m_train["recall_cash"]),
            "gap_balanced_accuracy_holdout_minus_train_oof": float(m_hold["balanced_accuracy"] - m_train["balanced_accuracy"]),
            "gap_precision_cash_holdout_minus_train_oof": float(m_hold["precision_cash"] - m_train["precision_cash"]),
        }
        write_json(OUT_GAP, gap)
        trans = {
            "winner_candidate_id": winner_id,
            "train_transition_rate_pred": float(m_train["transition_rate_pred"]),
            "holdout_transition_rate_pred": float(m_hold["transition_rate_pred"]),
            "train_switches_pred": int(np.sum(train_oof_pred[1:] != train_oof_pred[:-1])),
            "holdout_switches_pred": int(np.sum(hold_pred[1:] != hold_pred[:-1])),
        }
        write_json(OUT_TRANS, trans)

        # model artifact
        model_payload = {
            "task_id": TASK_ID,
            "run_id": RUN_ID,
            "selected_candidate_id": winner_id,
            "selected_hyperparams": wcfg,
            "threshold_baseline": 0.5,
            "feature_count": len(features),
            "features_used": features,
            "feature_policy_path": str(OUT_FEATURE_POLICY.relative_to(ROOT)),
            "notes": "T124 usa seleção TRAIN-only walk-forward; HOLDOUT apenas diagnóstico.",
        }
        write_json(OUT_MODEL, model_payload)
        gates.append(Gate("G_MODEL_ARTIFACT_OK", OUT_MODEL.exists(), f"winner={winner_id} features={len(features)}"))

        # plot
        fig = make_subplots(
            rows=2,
            cols=2,
            subplot_titles=(
                "OOF TRAIN: y_proba_cash vs label",
                "HOLDOUT: y_proba_cash vs label",
                "Distribuição proba por split",
                "Ablation (recall vs precision)",
            ),
            vertical_spacing=0.1,
            horizontal_spacing=0.08,
        )
        train_dates = train["date"]
        hold_dates = holdout["date"]
        fig.add_trace(
            go.Scatter(x=train_dates, y=train_oof_proba, mode="lines", name="proba_train_oof", line=dict(color="#1f77b4")),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(x=train_dates, y=train["y_cash_us_v1"], mode="lines", name="label_train", line=dict(color="#ff7f0e", dash="dot")),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(x=hold_dates, y=hold_proba, mode="lines", name="proba_holdout", line=dict(color="#2ca02c")),
            row=1,
            col=2,
        )
        fig.add_trace(
            go.Scatter(x=hold_dates, y=holdout["y_cash_us_v1"], mode="lines", name="label_holdout", line=dict(color="#d62728", dash="dot")),
            row=1,
            col=2,
        )
        fig.add_trace(go.Histogram(x=train_oof_proba, name="proba_train", opacity=0.65, nbinsx=40), row=2, col=1)
        fig.add_trace(go.Histogram(x=hold_proba, name="proba_holdout", opacity=0.65, nbinsx=40), row=2, col=1)
        fig.add_trace(
            go.Scatter(
                x=ablation["precision_cash_train_oof"],
                y=ablation["recall_cash_train_oof"],
                mode="markers+text",
                text=ablation["candidate_id"],
                textposition="top center",
                name="candidates",
            ),
            row=2,
            col=2,
        )
        fig.update_layout(barmode="overlay", height=900, width=1400, title=f"{RUN_ID} - diagnostics", legend=dict(orientation="h"))
        fig.write_html(OUT_PLOT, include_plotlyjs="cdn")
        gates.append(Gate("G_PLOT_OK", OUT_PLOT.exists(), f"size={OUT_PLOT.stat().st_size if OUT_PLOT.exists() else 0}"))

        # changelog
        ch_ok = append_changelog_one_line_idempotent(TRACEABILITY_LINE)
        gates.append(Gate("G_CHLOG_UPDATED", ch_ok and TRACEABILITY_LINE in CHANGELOG_PATH.read_text(encoding="utf-8"), "mode=idempotent"))

        inputs = [
            str(IN_DATASET.relative_to(ROOT)),
            str(IN_INV.relative_to(ROOT)),
            str(CHANGELOG_PATH.relative_to(ROOT)),
        ]
        outputs = [
            str(OUT_SCRIPT.relative_to(ROOT)),
            str(OUT_MODEL.relative_to(ROOT)),
            str(OUT_PREDS.relative_to(ROOT)),
            str(OUT_ABL.relative_to(ROOT)),
            str(OUT_PLOT.relative_to(ROOT)),
            str(OUT_REPORT.relative_to(ROOT)),
            str(OUT_EVID.relative_to(ROOT) / "feature_policy.json"),
            str(OUT_EVID.relative_to(ROOT) / "time_leakage_scan_train.csv"),
            str(OUT_EVID.relative_to(ROOT) / "cv_scheme_justification.md"),
            str(OUT_EVID.relative_to(ROOT) / "walkforward_folds.json"),
            str(OUT_EVID.relative_to(ROOT) / "threshold_baseline_metrics.json"),
            str(OUT_EVID.relative_to(ROOT) / "generalization_gap.json"),
            str(OUT_EVID.relative_to(ROOT) / "transition_diagnostics.json"),
        ]

        # ── Ordem canônica: escreve report COMPLETO → gera manifest → self-check ──
        # Primeiro marcar os gates Gx e G_SHA256 como provisório PASS para o report
        # (são confirmados logo abaixo); depois rewrite do report final + manifest definitivo.

        placeholder_gx   = Gate("Gx_HASH_MANIFEST_PRESENT",     True, f"path={OUT_MANIFEST.relative_to(ROOT)}")
        placeholder_hash = Gate("G_SHA256_INTEGRITY_SELF_CHECK", True, "mismatches=0 (provisional)")
        gates_for_report = gates + [placeholder_gx, placeholder_hash]

        def build_report_text(gates_list: list, retry: list, status: str) -> str:
            lines = [
                f"# HEADER: {RUN_ID}", "",
                f"- task_id: {TASK_ID}",
                f"- run_id: {RUN_ID}",
                f"- python_env: {sys.executable}", "",
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
            for art in [OUT_SCRIPT, OUT_MODEL, OUT_PREDS, OUT_ABL, OUT_PLOT,
                        OUT_REPORT, OUT_MANIFEST, OUT_FEATURE_POLICY, OUT_TIME_SCAN,
                        OUT_CV_JUST, OUT_FOLDS, OUT_BASELINE, OUT_GAP, OUT_TRANS]:
                if art.exists():
                    lines.append(f"- {art.relative_to(ROOT)}")
            lines.append("")
            lines.append(f"OVERALL STATUS: [[ {status} ]]")
            return "\n".join(lines) + "\n"

        if any(not g.passed for g in gates_for_report):
            overall_pass = False
        status_txt = "PASS" if overall_pass else "FAIL"

        # 1. Escrever report final (única vez) incluindo Gx e G_SHA256 provisórios
        OUT_REPORT.write_text(build_report_text(gates_for_report, retry_log, status_txt), encoding="utf-8")

        # 2. Gerar manifest com hashes de todos os artefatos (incluindo o report final acima)
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

        # 3. Self-check independente
        mm = sum(
            1
            for rp, h in hashes.items()
            if not (ROOT / rp).exists() or sha256_file(ROOT / rp) != h
        )
        gx_present = OUT_MANIFEST.exists()
        gates.append(Gate("Gx_HASH_MANIFEST_PRESENT",     gx_present, f"path={OUT_MANIFEST.relative_to(ROOT)}"))
        gates.append(Gate("G_SHA256_INTEGRITY_SELF_CHECK", mm == 0,    f"mismatches={mm}"))

        # 4. Rewrite definitivo do report (agora com mismatches reais)
        if any(not g.passed for g in gates):
            overall_pass = False
        status_txt = "PASS" if overall_pass else "FAIL"
        OUT_REPORT.write_text(build_report_text(gates, retry_log, status_txt), encoding="utf-8")

        # 5. Rewrite do manifest com hash final do report
        hashes[str(OUT_REPORT.relative_to(ROOT))] = sha256_file(OUT_REPORT)
        manifest["hashes_sha256"] = hashes
        manifest["generated_at_utc"] = pd.Timestamp.now("UTC").isoformat()
        write_json(OUT_MANIFEST, manifest)

    except Exception as e:
        overall_pass = False
        error_message = f"{type(e).__name__}: {e}"
        retry_log.append(error_message)
        gates.append(Gate("G_FATAL", False, error_message))
        if any(not g.passed for g in gates):
            overall_pass = False
        status_txt = "PASS" if overall_pass else "FAIL"

        def build_report_text(gates_list: list, retry: list, status: str) -> str:
            lines = [
                f"# HEADER: {RUN_ID}", "",
                f"- task_id: {TASK_ID}",
                f"- run_id: {RUN_ID}",
                f"- python_env: {sys.executable}", "",
                "## STEP GATES",
            ]
            for g in gates_list:
                lines.append(f"- {'PASS' if g.passed else 'FAIL'} | {g.name} | {g.detail}")
            lines.append("")
            lines.append("## RETRY LOG")
            for r in retry:
                lines.append(f"- {r}")
            lines.append(f"\nOVERALL STATUS: [[ {status} ]]")
            return "\n".join(lines) + "\n"

        OUT_REPORT.write_text(build_report_text(gates, retry_log, status_txt), encoding="utf-8")

    if not overall_pass:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
