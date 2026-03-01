#!/home/wilson/AGNO_WORKSPACE/.venv/bin/python
"""T077 - XGBoost Ablation (walk-forward) para ML Trigger."""

from __future__ import annotations

import hashlib
import itertools
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sklearn.metrics import (
    balanced_accuracy_score,
    f1_score,
    precision_score,
    recall_score,
)
from xgboost import XGBClassifier


ROOT = Path("/home/wilson/AGNO_WORKSPACE")

IN_DATASET = ROOT / "src/data_engine/features/T076_DATASET_DAILY.parquet"
IN_INV = ROOT / "outputs/governanca/T076-EDA-FEATURE-ENGINEERING-V1_evidence/feature_inventory.csv"

OUT_SCRIPT = ROOT / "scripts/t077_xgboost_ablation_walkforward.py"
OUT_MODEL = ROOT / "src/data_engine/models/T077_XGB_SELECTED_MODEL.json"
OUT_PREDS = ROOT / "src/data_engine/features/T077_PREDICTIONS_DAILY.parquet"
OUT_ABL = ROOT / "src/data_engine/features/T077_ABLATION_RESULTS.parquet"
OUT_PLOT = ROOT / "outputs/plots/T077_STATE3_PHASE6B_MODEL_DIAGNOSTICS.html"
OUT_REPORT = ROOT / "outputs/governanca/T077-XGBOOST-ABLATION-V1_report.md"
OUT_MANIFEST = ROOT / "outputs/governanca/T077-XGBOOST-ABLATION-V1_manifest.json"
OUT_EVID_DIR = ROOT / "outputs/governanca/T077-XGBOOST-ABLATION-V1_evidence"
OUT_BLACKLIST = OUT_EVID_DIR / "feature_blacklist.json"
OUT_TIME_SCAN = OUT_EVID_DIR / "time_leakage_scan_train.csv"
OUT_TRANSITIONS = OUT_EVID_DIR / "transition_diagnostics.json"
OUT_ACID = OUT_EVID_DIR / "acid_window_holdout_metrics.json"

EXPLICIT_BLACKLIST = ["m3_n_tickers", "spc_n_tickers"]
TIME_PROXY_CORR_THRESHOLD = 0.95
N_FOLDS = 4
THRESH = 0.5


@dataclass
class Gate:
    name: str
    passed: bool
    detail: str


def ensure_dirs() -> None:
    for p in [OUT_MODEL.parent, OUT_PREDS.parent, OUT_ABL.parent, OUT_PLOT.parent, OUT_REPORT.parent, OUT_EVID_DIR]:
        p.mkdir(parents=True, exist_ok=True)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_expanding_folds(n_rows: int, n_folds: int) -> List[Tuple[np.ndarray, np.ndarray]]:
    if n_rows < n_folds + 1:
        raise ValueError(f"n_rows={n_rows} insuficiente para n_folds={n_folds}")
    val_size = n_rows // (n_folds + 1)
    if val_size < 30:
        raise ValueError(f"val_size muito pequeno ({val_size}); dados insuficientes.")

    folds: List[Tuple[np.ndarray, np.ndarray]] = []
    for k in range(n_folds):
        train_end = val_size * (k + 1)
        val_start = train_end
        val_end = train_end + val_size
        if k == n_folds - 1:
            val_end = n_rows
        tr_idx = np.arange(0, train_end)
        va_idx = np.arange(val_start, val_end)
        folds.append((tr_idx, va_idx))
    return folds


def transition_rate(y: np.ndarray) -> float:
    if len(y) <= 1:
        return 0.0
    return float(np.mean(y[1:] != y[:-1]))


def switches_count(y: np.ndarray) -> int:
    if len(y) <= 1:
        return 0
    return int(np.sum(y[1:] != y[:-1]))


def avg_spell_length(y: np.ndarray) -> float:
    if len(y) == 0:
        return 0.0
    lengths = []
    current = 1
    for i in range(1, len(y)):
        if y[i] == y[i - 1]:
            current += 1
        else:
            lengths.append(current)
            current = 1
    lengths.append(current)
    return float(np.mean(lengths))


def metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    return {
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "f1_cash": float(f1_score(y_true, y_pred, pos_label=1, zero_division=0)),
        "recall_cash": float(recall_score(y_true, y_pred, pos_label=1, zero_division=0)),
        "precision_cash": float(precision_score(y_true, y_pred, pos_label=1, zero_division=0)),
        "transition_rate_pred": transition_rate(y_pred),
    }


def run_cv(
    X: pd.DataFrame,
    y: pd.Series,
    params: Dict[str, float | int],
    folds: List[Tuple[np.ndarray, np.ndarray]],
) -> Dict[str, float]:
    fold_metrics = []
    for tr_idx, va_idx in folds:
        model = XGBClassifier(
            objective="binary:logistic",
            eval_metric="logloss",
            random_state=42,
            n_jobs=1,
            **params,
        )
        X_tr = X.iloc[tr_idx]
        y_tr = y.iloc[tr_idx]
        X_va = X.iloc[va_idx]
        y_va = y.iloc[va_idx]
        model.fit(X_tr, y_tr)
        p = model.predict_proba(X_va)[:, 1]
        pred = (p >= THRESH).astype(int)
        fold_metrics.append(metrics(y_va.values, pred))

    out: Dict[str, float] = {}
    for k in ["balanced_accuracy", "f1_cash", "recall_cash", "precision_cash", "transition_rate_pred"]:
        vals = [m[k] for m in fold_metrics]
        out[f"{k}_mean_cv"] = float(np.mean(vals))
        out[f"{k}_std_cv"] = float(np.std(vals, ddof=0))
    return out


def build_plot(preds: pd.DataFrame, importance_df: pd.DataFrame) -> None:
    train = preds[preds["split"] == "TRAIN"].copy()
    holdout = preds[preds["split"] == "HOLDOUT"].copy()

    fig = make_subplots(
        rows=3,
        cols=1,
        subplot_titles=(
            "y_cash (true) vs y_pred_cash",
            "y_proba_cash",
            "Top-20 Feature Importance (gain)",
        ),
        vertical_spacing=0.10,
    )

    fig.add_trace(go.Scatter(x=preds["date"], y=preds["y_cash"], name="y_cash_true", mode="lines", line=dict(color="#1f77b4")), row=1, col=1)
    fig.add_trace(go.Scatter(x=preds["date"], y=preds["y_pred_cash"], name="y_pred_cash", mode="lines", line=dict(color="#d62728")), row=1, col=1)

    fig.add_trace(go.Scatter(x=train["date"], y=train["y_proba_cash"], name="proba TRAIN", mode="lines", line=dict(color="#2ca02c")), row=2, col=1)
    fig.add_trace(go.Scatter(x=holdout["date"], y=holdout["y_proba_cash"], name="proba HOLDOUT", mode="lines", line=dict(color="#ff7f0e")), row=2, col=1)

    fig.add_vrect(
        x0="2024-11-01",
        x1="2025-11-30",
        fillcolor="red",
        opacity=0.10,
        line_width=0,
        annotation_text="Acid window HOLDOUT",
        annotation_position="top left",
        row=1,
        col=1,
    )
    fig.add_vrect(
        x0="2024-11-01",
        x1="2025-11-30",
        fillcolor="red",
        opacity=0.10,
        line_width=0,
        row=2,
        col=1,
    )

    imp = importance_df.head(20)
    fig.add_trace(go.Bar(x=imp["feature"], y=imp["importance_gain"], name="importance_gain", marker_color="#9467bd"), row=3, col=1)
    fig.update_xaxes(tickangle=30, row=3, col=1)
    fig.update_layout(height=1100, template="plotly_white", title="T077 - XGBoost Model Diagnostics")
    fig.write_html(OUT_PLOT, include_plotlyjs="cdn")


def main() -> int:
    ensure_dirs()
    retry_log: List[str] = []
    gates: List[Gate] = []

    df = pd.read_parquet(IN_DATASET)
    _inv = pd.read_csv(IN_INV)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df = df.sort_values("date").reset_index(drop=True)

    base_features = [c for c in df.columns if c not in ["date", "split", "y_cash"]]
    train = df[df["split"] == "TRAIN"].copy()
    holdout = df[df["split"] == "HOLDOUT"].copy()

    # Feature governance
    blacklisted = []
    for f in EXPLICIT_BLACKLIST:
        if f in base_features:
            blacklisted.append({"feature": f, "reason": "explicit_blacklist_f001"})

    train_ord = train.copy()
    train_ord["date_ordinal"] = train_ord["date"].map(pd.Timestamp.toordinal).astype(float)
    leakage_scan_rows = []
    for f in base_features:
        s = pd.to_numeric(train_ord[f], errors="coerce")
        dord = pd.to_numeric(train_ord["date_ordinal"], errors="coerce")
        mask = s.notna() & dord.notna()
        if int(mask.sum()) < 3:
            corr = np.nan
        else:
            x = s.loc[mask].to_numpy(dtype=float)
            y = dord.loc[mask].to_numpy(dtype=float)
            # Se a feature é constante, correlação não é definida; tratamos como NaN.
            if np.std(x) == 0.0 or np.std(y) == 0.0:
                corr = np.nan
            else:
                corr = float(np.corrcoef(x, y)[0, 1])
        leakage_scan_rows.append({"feature": f, "corr_with_date_ordinal_train": corr, "abs_corr": abs(corr) if pd.notna(corr) else np.nan})
    leakage_scan = pd.DataFrame(leakage_scan_rows).sort_values("abs_corr", ascending=False)
    leakage_scan.to_csv(OUT_TIME_SCAN, index=False)

    for _, row in leakage_scan.iterrows():
        if pd.notna(row["abs_corr"]) and row["abs_corr"] > TIME_PROXY_CORR_THRESHOLD and row["feature"] not in EXPLICIT_BLACKLIST:
            blacklisted.append({"feature": row["feature"], "reason": f"time_proxy_abs_corr_gt_{TIME_PROXY_CORR_THRESHOLD:.2f}", "abs_corr": float(row['abs_corr'])})

    blacklisted_features = sorted({x["feature"] for x in blacklisted})
    OUT_BLACKLIST.write_text(json.dumps({"blacklisted_features": blacklisted, "threshold_abs_corr_date": TIME_PROXY_CORR_THRESHOLD}, indent=2), encoding="utf-8")

    features = [f for f in base_features if f not in blacklisted_features]
    X_train = train[features].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    y_train = train["y_cash"].astype(int).copy()
    X_holdout = holdout[features].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    y_holdout = holdout["y_cash"].astype(int).copy()

    folds = build_expanding_folds(len(train), N_FOLDS)

    grid = list(
        itertools.product(
            [120, 240],    # n_estimators
            [2, 3, 4],     # max_depth
            [0.03, 0.06],  # learning_rate
            [0.8],         # subsample
            [0.8, 1.0],    # colsample_bytree
            [1, 3],        # min_child_weight
        )
    )

    rows = []
    for i, (n_estimators, max_depth, learning_rate, subsample, colsample_bytree, min_child_weight) in enumerate(grid):
        params = {
            "n_estimators": int(n_estimators),
            "max_depth": int(max_depth),
            "learning_rate": float(learning_rate),
            "subsample": float(subsample),
            "colsample_bytree": float(colsample_bytree),
            "min_child_weight": int(min_child_weight),
            "reg_lambda": 1.0,
        }
        cvm = run_cv(X_train, y_train, params, folds)
        row = {"candidate_id": f"C{i:03d}", **params, **cvm}
        row["gate_transition_rate"] = row["transition_rate_pred_mean_cv"] >= 0.01
        row["gate_recall_cash"] = row["recall_cash_mean_cv"] >= 0.60
        row["gate_balanced_acc"] = row["balanced_accuracy_mean_cv"] >= 0.55
        row["is_feasible"] = bool(row["gate_transition_rate"] and row["gate_recall_cash"] and row["gate_balanced_acc"])
        rows.append(row)

    ablation = pd.DataFrame(rows)
    ablation = ablation.sort_values(
        by=[
            "is_feasible",
            "balanced_accuracy_mean_cv",
            "recall_cash_mean_cv",
            "f1_cash_mean_cv",
            "n_estimators",
            "candidate_id",
        ],
        ascending=[False, False, False, False, True, True],
    ).reset_index(drop=True)
    ablation.to_parquet(OUT_ABL, index=False)

    feasible = ablation[ablation["is_feasible"]].copy()
    if feasible.empty:
        winner_row = ablation.iloc[[0]].copy()
        logical_fail = True
    else:
        winner_row = feasible.iloc[[0]].copy()
        logical_fail = False
    w = winner_row.iloc[0].to_dict()

    winner_params = {
        "n_estimators": int(w["n_estimators"]),
        "max_depth": int(w["max_depth"]),
        "learning_rate": float(w["learning_rate"]),
        "subsample": float(w["subsample"]),
        "colsample_bytree": float(w["colsample_bytree"]),
        "min_child_weight": int(w["min_child_weight"]),
        "reg_lambda": float(w["reg_lambda"]),
    }

    model = XGBClassifier(
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=42,
        n_jobs=1,
        **winner_params,
    )
    model.fit(X_train, y_train)

    proba_train = model.predict_proba(X_train)[:, 1]
    pred_train = (proba_train >= THRESH).astype(int)
    proba_hold = model.predict_proba(X_holdout)[:, 1]
    pred_hold = (proba_hold >= THRESH).astype(int)

    preds_train = pd.DataFrame(
        {
            "date": train["date"].values,
            "split": "TRAIN",
            "y_cash": y_train.values,
            "y_proba_cash": proba_train,
            "y_pred_cash": pred_train,
        }
    )
    preds_hold = pd.DataFrame(
        {
            "date": holdout["date"].values,
            "split": "HOLDOUT",
            "y_cash": y_holdout.values,
            "y_proba_cash": proba_hold,
            "y_pred_cash": pred_hold,
        }
    )
    preds = pd.concat([preds_train, preds_hold], ignore_index=True).sort_values("date")
    preds.to_parquet(OUT_PREDS, index=False)

    # Importance
    importance_df = pd.DataFrame({"feature": features, "importance_gain": model.feature_importances_.astype(float)})
    importance_df = importance_df.sort_values("importance_gain", ascending=False).reset_index(drop=True)

    # Acid window
    acid = preds[(preds["split"] == "HOLDOUT") & (preds["date"] >= pd.Timestamp("2024-11-01")) & (preds["date"] <= pd.Timestamp("2025-11-30"))].copy()
    acid_metrics = metrics(acid["y_cash"].values, acid["y_pred_cash"].values) if not acid.empty else {}
    acid_payload = {
        "n_rows": int(acid.shape[0]),
        "y_cash_rate_true": float(acid["y_cash"].mean()) if not acid.empty else None,
        "y_cash_rate_pred": float(acid["y_pred_cash"].mean()) if not acid.empty else None,
        "metrics": acid_metrics,
    }
    OUT_ACID.write_text(json.dumps(acid_payload, indent=2), encoding="utf-8")

    # Transition diagnostics
    trans = {
        "train": {
            "true_switches": switches_count(y_train.values),
            "pred_switches": switches_count(pred_train),
            "true_avg_spell": avg_spell_length(y_train.values),
            "pred_avg_spell": avg_spell_length(pred_train),
        },
        "holdout": {
            "true_switches": switches_count(y_holdout.values),
            "pred_switches": switches_count(pred_hold),
            "true_avg_spell": avg_spell_length(y_holdout.values),
            "pred_avg_spell": avg_spell_length(pred_hold),
        },
    }
    OUT_TRANSITIONS.write_text(json.dumps(trans, indent=2), encoding="utf-8")

    # Plot
    build_plot(preds, importance_df)

    # Report
    train_m = metrics(y_train.values, pred_train)
    hold_m = metrics(y_holdout.values, pred_hold)
    report = f"""# T077 - XGBoost Ablation (Walk-forward)

## Objetivo
Treinar e selecionar classificador binário (y_cash) com CV temporal no TRAIN, sem usar HOLDOUT para tuning.

## Inputs
- `{IN_DATASET.relative_to(ROOT)}`
- `{IN_INV.relative_to(ROOT)}`

## Governança de Features
- Explicit blacklist (F-001): {EXPLICIT_BLACKLIST}
- Time proxy gate: abs(corr(feature, date_ordinal)) > {TIME_PROXY_CORR_THRESHOLD}
- Features iniciais: {len(base_features)}
- Features removidas: {len(blacklisted_features)}
- Features finais para modelagem: {len(features)}

## CV temporal (TRAIN)
- folds: {N_FOLDS} (expanding window)
- threshold classificação: {THRESH}
- candidatos avaliados: {len(ablation)}
- candidatos feasíveis: {int(ablation['is_feasible'].sum())}
- vencedor: {w['candidate_id']}

## Métricas modelo vencedor
- TRAIN balanced_accuracy: {train_m['balanced_accuracy']:.4f}
- TRAIN recall_cash: {train_m['recall_cash']:.4f}
- TRAIN precision_cash: {train_m['precision_cash']:.4f}
- HOLDOUT balanced_accuracy: {hold_m['balanced_accuracy']:.4f}
- HOLDOUT recall_cash: {hold_m['recall_cash']:.4f}
- HOLDOUT precision_cash: {hold_m['precision_cash']:.4f}

## Teste ácido (HOLDOUT nov/2024-nov/2025)
- n_rows: {acid_payload['n_rows']}
- y_cash_rate_true: {acid_payload['y_cash_rate_true']}
- y_cash_rate_pred: {acid_payload['y_cash_rate_pred']}
- metrics: {acid_payload['metrics']}

## Artefatos
- `{OUT_MODEL.relative_to(ROOT)}`
- `{OUT_PREDS.relative_to(ROOT)}`
- `{OUT_ABL.relative_to(ROOT)}`
- `{OUT_PLOT.relative_to(ROOT)}`
- `{OUT_BLACKLIST.relative_to(ROOT)}`
- `{OUT_TIME_SCAN.relative_to(ROOT)}`
- `{OUT_TRANSITIONS.relative_to(ROOT)}`
- `{OUT_ACID.relative_to(ROOT)}`
"""
    OUT_REPORT.write_text(report, encoding="utf-8")

    model_payload = {
        "task_id": "T077",
        "model_type": "XGBClassifier",
        "winner_candidate_id": w["candidate_id"],
        "params": winner_params,
        "threshold": THRESH,
        "selection_metric_train": "balanced_accuracy_mean_cv",
        "cv_scheme": f"expanding_window_{N_FOLDS}_folds",
        "features_used": features,
        "features_removed_blacklist": blacklisted_features,
        "train_metrics": train_m,
        "holdout_metrics": hold_m,
        "logical_fail_no_feasible_candidates": logical_fail,
    }
    OUT_MODEL.write_text(json.dumps(model_payload, indent=2), encoding="utf-8")

    # Manifest
    inputs = [IN_DATASET, IN_INV]
    outputs = [
        OUT_SCRIPT,
        OUT_MODEL,
        OUT_PREDS,
        OUT_ABL,
        OUT_PLOT,
        OUT_REPORT,
        OUT_BLACKLIST,
        OUT_TIME_SCAN,
        OUT_TRANSITIONS,
        OUT_ACID,
    ]
    hashes = {str(p.relative_to(ROOT)): sha256_file(p) for p in inputs + outputs}
    manifest = {
        "task_id": "T077",
        "manifest_id": "T077-XGBOOST-ABLATION-V1",
        "inputs_consumed": [str(p.relative_to(ROOT)) for p in inputs],
        "outputs_produced": [str(p.relative_to(ROOT)) for p in outputs],
        "hashes_sha256": hashes,
        "self_hash_excluded": True,
    }
    OUT_MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Gates
    gates.append(Gate("G1_INPUTS_PRESENT", all(p.exists() for p in inputs), "inputs T076 presentes"))
    gates.append(Gate("G2_BLACKLIST_APPLIED", all(f in blacklisted_features for f in EXPLICIT_BLACKLIST), f"blacklisted={EXPLICIT_BLACKLIST}"))
    gates.append(Gate("G3_TIME_PROXY_SCAN_PRESENT", OUT_TIME_SCAN.exists(), str(OUT_TIME_SCAN.relative_to(ROOT))))
    gates.append(Gate("G4_ABLATION_RESULTS_PRESENT", OUT_ABL.exists(), f"candidatos={len(ablation)}"))
    gates.append(Gate("G5_MODEL_AND_PREDS_PRESENT", OUT_MODEL.exists() and OUT_PREDS.exists(), "modelo + predições gerados"))
    gates.append(Gate("G6_ACID_WINDOW_EVALUATED", OUT_ACID.exists() and acid_payload["n_rows"] > 0, f"acid_n_rows={acid_payload['n_rows']}"))
    gates.append(Gate("Gx_HASH_MANIFEST_PRESENT", OUT_MANIFEST.exists(), str(OUT_MANIFEST.relative_to(ROOT))))

    overall_pass = all(g.passed for g in gates) and (not logical_fail)

    print("HEADER: T077")
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
    for p in outputs + [OUT_MANIFEST]:
        print(f"- {p.relative_to(ROOT)}")
    if logical_fail:
        print("- LOGIC_NOTE: nenhum candidato passou hard constraints; top-1 foi materializado para diagnóstico")
    print(f"OVERALL STATUS: [[ {'PASS' if overall_pass else 'FAIL'} ]]")
    return 0 if overall_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
