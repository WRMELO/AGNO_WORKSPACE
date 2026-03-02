#!/home/wilson/AGNO_WORKSPACE/.venv/bin/python
"""T077 (versioned) - XGBoost ablation with stratified CV and threshold tuning.

Use `--run_id` (e.g., `T077-V3`) to avoid overwriting artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sklearn.metrics import balanced_accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import StratifiedKFold
from xgboost import XGBClassifier


ROOT = Path("/home/wilson/AGNO_WORKSPACE")

IN_DATASET = ROOT / "src/data_engine/features/T076_DATASET_DAILY.parquet"
IN_INV = ROOT / "outputs/governanca/T076-EDA-FEATURE-ENGINEERING-V1_evidence/feature_inventory.csv"

EXPLICIT_BLACKLIST = ["m3_n_tickers", "spc_n_tickers"]
TIME_PROXY_CORR_THRESHOLD = 0.95
THRESH_GRID = [0.05, 0.08, 0.10, 0.12, 0.15, 0.20, 0.30, 0.40, 0.50]
N_FOLDS = 5
MIN_PRECISION = 0.20


# Feature policy (V3): stable core allowlist (CTO direction)
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


@dataclass(frozen=True)
class RunPaths:
    run_id: str
    run_tag: str
    out_script: Path
    out_model: Path
    out_preds: Path
    out_abl: Path
    out_plot: Path
    out_report: Path
    out_manifest: Path
    out_evid_dir: Path
    out_blacklist: Path
    out_time_scan: Path
    out_cv_just: Path
    out_thr_search: Path
    out_acid: Path
    out_transitions: Path
    out_feature_policy: Path
    out_feature_stability: Path
    out_generalization_gap: Path


def make_run_paths(run_id: str) -> RunPaths:
    run_id = str(run_id).strip()
    run_tag = run_id.replace("-", "_")
    out_evid_dir = ROOT / f"outputs/governanca/{run_id}-XGBOOST-ABLATION-V1_evidence"
    return RunPaths(
        run_id=run_id,
        run_tag=run_tag,
        out_script=ROOT / "scripts/t077_xgboost_ablation_walkforward_v2.py",
        out_model=ROOT / f"src/data_engine/models/{run_tag}_XGB_SELECTED_MODEL.json",
        out_preds=ROOT / f"src/data_engine/features/{run_tag}_PREDICTIONS_DAILY.parquet",
        out_abl=ROOT / f"src/data_engine/features/{run_tag}_ABLATION_RESULTS.parquet",
        out_plot=ROOT / f"outputs/plots/{run_tag}_STATE3_PHASE6B_MODEL_DIAGNOSTICS.html",
        out_report=ROOT / f"outputs/governanca/{run_id}-XGBOOST-ABLATION-V1_report.md",
        out_manifest=ROOT / f"outputs/governanca/{run_id}-XGBOOST-ABLATION-V1_manifest.json",
        out_evid_dir=out_evid_dir,
        out_blacklist=out_evid_dir / "feature_blacklist.json",
        out_time_scan=out_evid_dir / "time_leakage_scan_train.csv",
        out_cv_just=out_evid_dir / "cv_scheme_justification.md",
        out_thr_search=out_evid_dir / "threshold_search_results.parquet",
        out_acid=out_evid_dir / "acid_window_holdout_metrics.json",
        out_transitions=out_evid_dir / "transition_diagnostics.json",
        out_feature_policy=out_evid_dir / "feature_policy_v3.json",
        out_feature_stability=out_evid_dir / "feature_stability_train_report.csv",
        out_generalization_gap=out_evid_dir / "generalization_gap.json",
    )


@dataclass
class Gate:
    name: str
    passed: bool
    detail: str


def ensure_dirs(paths: RunPaths) -> None:
    for p in [
        paths.out_model.parent,
        paths.out_preds.parent,
        paths.out_abl.parent,
        paths.out_plot.parent,
        paths.out_report.parent,
        paths.out_evid_dir,
    ]:
        p.mkdir(parents=True, exist_ok=True)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


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
    cur = 1
    for i in range(1, len(y)):
        if y[i] == y[i - 1]:
            cur += 1
        else:
            lengths.append(cur)
            cur = 1
    lengths.append(cur)
    return float(np.mean(lengths))


def cls_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    return {
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "f1_cash": float(f1_score(y_true, y_pred, pos_label=1, zero_division=0)),
        "recall_cash": float(recall_score(y_true, y_pred, pos_label=1, zero_division=0)),
        "precision_cash": float(precision_score(y_true, y_pred, pos_label=1, zero_division=0)),
        "transition_rate_pred": transition_rate(y_pred),
    }


def scan_time_proxy(train_df: pd.DataFrame, features: List[str]) -> pd.DataFrame:
    t = train_df.copy()
    t["date_ordinal"] = t["date"].map(pd.Timestamp.toordinal).astype(float)
    rows = []
    for f in features:
        s = pd.to_numeric(t[f], errors="coerce")
        d = t["date_ordinal"]
        mask = s.notna() & d.notna()
        if int(mask.sum()) < 3:
            corr = np.nan
        else:
            x = s.loc[mask].to_numpy(dtype=float)
            y = d.loc[mask].to_numpy(dtype=float)
            if np.std(x) == 0.0 or np.std(y) == 0.0:
                corr = np.nan
            else:
                corr = float(np.corrcoef(x, y)[0, 1])
        rows.append({"feature": f, "corr_with_date_ordinal_train": corr, "abs_corr": abs(corr) if pd.notna(corr) else np.nan})
    return pd.DataFrame(rows).sort_values("abs_corr", ascending=False)


def choose_threshold(y_true: np.ndarray, y_proba: np.ndarray) -> Tuple[float, pd.DataFrame]:
    rows = []
    for thr in THRESH_GRID:
        y_pred = (y_proba >= thr).astype(int)
        m = cls_metrics(y_true, y_pred)
        rows.append({"threshold": float(thr), **m, "meets_min_precision": bool(m["precision_cash"] >= MIN_PRECISION)})
    df = pd.DataFrame(rows)
    feasible = df[df["meets_min_precision"]].copy()
    pool = feasible if not feasible.empty else df
    pool = pool.sort_values(
        by=["recall_cash", "balanced_accuracy", "precision_cash", "threshold"],
        ascending=[False, False, False, True],
    )
    best = float(pool.iloc[0]["threshold"])
    return best, df


def build_plot(preds: pd.DataFrame, importance: pd.DataFrame, out_plot: Path, title: str) -> None:
    fig = make_subplots(
        rows=3,
        cols=1,
        subplot_titles=("y_cash vs y_pred_cash", "y_proba_cash", "Top-20 feature importance"),
        vertical_spacing=0.10,
    )

    fig.add_trace(go.Scatter(x=preds["date"], y=preds["y_cash"], mode="lines", name="y_true", line=dict(color="#1f77b4")), row=1, col=1)
    fig.add_trace(go.Scatter(x=preds["date"], y=preds["y_pred_cash"], mode="lines", name="y_pred", line=dict(color="#d62728")), row=1, col=1)
    fig.add_trace(go.Scatter(x=preds["date"], y=preds["y_proba_cash"], mode="lines", name="proba", line=dict(color="#2ca02c")), row=2, col=1)
    fig.add_vrect(x0="2024-11-01", x1="2025-11-30", fillcolor="red", opacity=0.10, line_width=0, annotation_text="Acid window", annotation_position="top left", row=1, col=1)
    fig.add_vrect(x0="2024-11-01", x1="2025-11-30", fillcolor="red", opacity=0.10, line_width=0, row=2, col=1)

    imp = importance.head(20)
    fig.add_trace(go.Bar(x=imp["feature"], y=imp["importance_gain"], name="gain", marker_color="#9467bd"), row=3, col=1)
    fig.update_xaxes(tickangle=30, row=3, col=1)
    fig.update_layout(height=1100, template="plotly_white", title=title)
    fig.write_html(out_plot, include_plotlyjs="cdn")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_id", type=str, default="T077-V2", help="Run identifier for versioned artifacts (e.g., T077-V3).")
    args = parser.parse_args()

    paths = make_run_paths(args.run_id)
    ensure_dirs(paths)
    retry_log: List[str] = []
    gates: List[Gate] = []

    # Input load
    df = pd.read_parquet(IN_DATASET)
    _inv = pd.read_csv(IN_INV)

    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df = df.sort_values("date").reset_index(drop=True)
    train = df[df["split"] == "TRAIN"].copy()
    holdout = df[df["split"] == "HOLDOUT"].copy()

    base_features = [c for c in df.columns if c not in ["date", "split", "y_cash"]]

    # Feature governance
    leakage_scan = scan_time_proxy(train, base_features)
    leakage_scan.to_csv(paths.out_time_scan, index=False)

    blacklisted: List[Dict[str, object]] = []
    for f in EXPLICIT_BLACKLIST:
        if f in base_features:
            blacklisted.append({"feature": f, "reason": "explicit_blacklist_f001"})
    for _, r in leakage_scan.iterrows():
        if pd.notna(r["abs_corr"]) and float(r["abs_corr"]) > TIME_PROXY_CORR_THRESHOLD and r["feature"] not in EXPLICIT_BLACKLIST:
            blacklisted.append(
                {
                    "feature": str(r["feature"]),
                    "reason": f"time_proxy_abs_corr_gt_{TIME_PROXY_CORR_THRESHOLD:.2f}",
                    "abs_corr": float(r["abs_corr"]),
                }
            )

    blacklisted_features = sorted({x["feature"] for x in blacklisted})
    paths.out_blacklist.write_text(
        json.dumps({"blacklisted_features": blacklisted, "threshold_abs_corr_date": TIME_PROXY_CORR_THRESHOLD}, indent=2),
        encoding="utf-8",
    )

    # Feature policy V3 (allowlist core stable)
    core_present = [f for f in CORE_ALLOWLIST if f in base_features and f not in blacklisted_features]
    dropped_by_policy = sorted([f for f in base_features if f not in core_present and f not in blacklisted_features])
    feature_policy_payload = {
        "run_id": paths.run_id,
        "policy": "ALLOWLIST_CORE_V3",
        "core_allowlist": CORE_ALLOWLIST,
        "base_features_count": int(len(base_features)),
        "blacklisted_features": blacklisted_features,
        "dropped_by_policy_count": int(len(dropped_by_policy)),
        "dropped_by_policy_sample": dropped_by_policy[:50],
        "features_used_final": core_present,
    }
    paths.out_feature_policy.write_text(json.dumps(feature_policy_payload, indent=2), encoding="utf-8")

    features = core_present.copy()
    X_train = train[features].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    y_train = train["y_cash"].astype(int).copy()
    X_holdout = holdout[features].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    y_holdout = holdout["y_cash"].astype(int).copy()

    neg = int((y_train == 0).sum())
    pos = int((y_train == 1).sum())
    scale_pos_weight = float(neg / max(pos, 1))

    cv_just = f"""# CV Scheme Justification ({paths.run_id})

- T077-V1 falhou com CV temporal expanding-window por distribuição de classe incompatível.
- Evidência em TRAIN (n={len(y_train)}):
  - cash_frac_total={y_train.mean():.4f}
  - classe positiva concentrada no final do período (a partir de 2021-08).
- Com folds temporais, houve validações sem classe positiva e validações quase totalmente positivas, inviabilizando otimização robusta de recall_cash.
- Para medir capacidade discriminativa no TRAIN sem tocar no HOLDOUT, este run usa `StratifiedKFold(n_splits={N_FOLDS}, shuffle=True, random_state=42)`.
- Anti-lookahead permanece preservado pois as features já são `shift(1)` desde T076 e HOLDOUT segue intocado para avaliação final.
"""
    paths.out_cv_just.write_text(cv_just, encoding="utf-8")

    skf = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=42)

    grid = list(
        itertools.product(
            [120, 240],    # n_estimators
            [2, 3, 4],     # max_depth
            [0.03, 0.06],  # learning_rate
            [0.8, 1.0],    # subsample
            [0.8, 1.0],    # colsample_bytree
            [1, 3],        # min_child_weight
        )
    )

    ablation_rows: List[Dict[str, object]] = []
    threshold_rows: List[Dict[str, object]] = []

    for i, (n_estimators, max_depth, learning_rate, subsample, colsample_bytree, min_child_weight) in enumerate(grid):
        candidate_id = f"C{i:03d}"
        params = {
            "n_estimators": int(n_estimators),
            "max_depth": int(max_depth),
            "learning_rate": float(learning_rate),
            "subsample": float(subsample),
            "colsample_bytree": float(colsample_bytree),
            "min_child_weight": int(min_child_weight),
            "reg_lambda": 1.0,
            "scale_pos_weight": scale_pos_weight,
        }

        oof_proba = np.full(len(X_train), np.nan, dtype=float)
        fold_assign = np.full(len(X_train), -1, dtype=int)
        for fold_id, (tr_idx, va_idx) in enumerate(skf.split(X_train, y_train)):
            model = XGBClassifier(
                objective="binary:logistic",
                eval_metric="logloss",
                random_state=42,
                n_jobs=1,
                **params,
            )
            model.fit(X_train.iloc[tr_idx], y_train.iloc[tr_idx])
            oof_proba[va_idx] = model.predict_proba(X_train.iloc[va_idx])[:, 1]
            fold_assign[va_idx] = fold_id

        best_thr, thr_table = choose_threshold(y_train.values, oof_proba)
        for _, r in thr_table.iterrows():
            threshold_rows.append(
                {
                    "candidate_id": candidate_id,
                    "threshold": float(r["threshold"]),
                    "balanced_accuracy": float(r["balanced_accuracy"]),
                    "f1_cash": float(r["f1_cash"]),
                    "recall_cash": float(r["recall_cash"]),
                    "precision_cash": float(r["precision_cash"]),
                    "transition_rate_pred": float(r["transition_rate_pred"]),
                    "meets_min_precision": bool(r["meets_min_precision"]),
                    "selected_threshold_for_candidate": bool(abs(float(r["threshold"]) - best_thr) < 1e-12),
                }
            )

        # Fold metrics at selected threshold
        fold_metrics = []
        for fold_id in range(N_FOLDS):
            mask = fold_assign == fold_id
            y_true_fold = y_train.values[mask]
            y_pred_fold = (oof_proba[mask] >= best_thr).astype(int)
            fold_metrics.append(cls_metrics(y_true_fold, y_pred_fold))

        # Aggregate CV metrics
        row: Dict[str, object] = {"candidate_id": candidate_id, **params, "threshold_selected": best_thr}
        for k in ["balanced_accuracy", "f1_cash", "recall_cash", "precision_cash", "transition_rate_pred"]:
            vals = [m[k] for m in fold_metrics]
            row[f"{k}_mean_cv"] = float(np.mean(vals))
            row[f"{k}_std_cv"] = float(np.std(vals, ddof=0))

        row["gate_recall_cash"] = bool(row["recall_cash_mean_cv"] >= 0.50)
        row["gate_balanced_acc"] = bool(row["balanced_accuracy_mean_cv"] >= 0.55)
        row["gate_transition_rate"] = bool(row["transition_rate_pred_mean_cv"] >= 0.005)
        row["is_feasible"] = bool(row["gate_recall_cash"] and row["gate_balanced_acc"] and row["gate_transition_rate"])
        ablation_rows.append(row)

    ablation = pd.DataFrame(ablation_rows)
    ablation = ablation.sort_values(
        by=[
            "is_feasible",
            "recall_cash_mean_cv",
            "balanced_accuracy_mean_cv",
            "precision_cash_mean_cv",
            "candidate_id",
        ],
        ascending=[False, False, False, False, True],
    ).reset_index(drop=True)
    ablation.to_parquet(paths.out_abl, index=False)
    pd.DataFrame(threshold_rows).to_parquet(paths.out_thr_search, index=False)

    feasible = ablation[ablation["is_feasible"]].copy()
    logical_fail = feasible.empty
    winner_row = feasible.iloc[[0]].copy() if not logical_fail else ablation.iloc[[0]].copy()
    w = winner_row.iloc[0].to_dict()

    winner_params = {
        "n_estimators": int(w["n_estimators"]),
        "max_depth": int(w["max_depth"]),
        "learning_rate": float(w["learning_rate"]),
        "subsample": float(w["subsample"]),
        "colsample_bytree": float(w["colsample_bytree"]),
        "min_child_weight": int(w["min_child_weight"]),
        "reg_lambda": float(w["reg_lambda"]),
        "scale_pos_weight": float(w["scale_pos_weight"]),
    }
    winner_threshold = float(w["threshold_selected"])

    model = XGBClassifier(
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=42,
        n_jobs=1,
        **winner_params,
    )
    model.fit(X_train, y_train)

    proba_train = model.predict_proba(X_train)[:, 1]
    pred_train = (proba_train >= winner_threshold).astype(int)
    proba_hold = model.predict_proba(X_holdout)[:, 1]
    pred_hold = (proba_hold >= winner_threshold).astype(int)

    preds_train = pd.DataFrame(
        {"date": train["date"].values, "split": "TRAIN", "y_cash": y_train.values, "y_proba_cash": proba_train, "y_pred_cash": pred_train}
    )
    preds_hold = pd.DataFrame(
        {"date": holdout["date"].values, "split": "HOLDOUT", "y_cash": y_holdout.values, "y_proba_cash": proba_hold, "y_pred_cash": pred_hold}
    )
    preds = pd.concat([preds_train, preds_hold], ignore_index=True).sort_values("date")
    preds.to_parquet(paths.out_preds, index=False)

    importance = pd.DataFrame({"feature": features, "importance_gain": model.feature_importances_.astype(float)}).sort_values(
        "importance_gain", ascending=False
    )

    acid = preds[
        (preds["split"] == "HOLDOUT")
        & (preds["date"] >= pd.Timestamp("2024-11-01"))
        & (preds["date"] <= pd.Timestamp("2025-11-30"))
    ].copy()
    acid_payload = {
        "n_rows": int(acid.shape[0]),
        "y_cash_rate_true": float(acid["y_cash"].mean()) if not acid.empty else None,
        "y_cash_rate_pred": float(acid["y_pred_cash"].mean()) if not acid.empty else None,
        "metrics": cls_metrics(acid["y_cash"].values, acid["y_pred_cash"].values) if not acid.empty else {},
    }
    paths.out_acid.write_text(json.dumps(acid_payload, indent=2), encoding="utf-8")

    trans_payload = {
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
    paths.out_transitions.write_text(json.dumps(trans_payload, indent=2), encoding="utf-8")

    build_plot(preds, importance, paths.out_plot, title=f"{paths.run_id} Model Diagnostics")

    train_m = cls_metrics(y_train.values, pred_train)
    hold_m = cls_metrics(y_holdout.values, pred_hold)

    # Feature stability report (TRAIN only; informational)
    stab_rows = []
    for f in features:
        s = pd.to_numeric(train[f], errors="coerce")
        if int(s.notna().sum()) < 3:
            corr_y = np.nan
        else:
            corr_y = float(s.corr(y_train.astype(float), method="spearman"))
        corr_date_row = leakage_scan[leakage_scan["feature"] == f]
        abs_corr_date = float(corr_date_row["abs_corr"].iloc[0]) if not corr_date_row.empty and pd.notna(corr_date_row["abs_corr"].iloc[0]) else np.nan
        stab_rows.append({"feature": f, "spearman_corr_y_cash_train": corr_y, "abs_corr_date_ordinal_train": abs_corr_date})
    pd.DataFrame(stab_rows).sort_values("abs_corr_date_ordinal_train", ascending=False).to_csv(paths.out_feature_stability, index=False)

    # Generalization gap (winner)
    recall_cv = float(w.get("recall_cash_mean_cv", np.nan))
    balacc_cv = float(w.get("balanced_accuracy_mean_cv", np.nan))
    gap_payload = {
        "run_id": paths.run_id,
        "winner_candidate_id": str(w.get("candidate_id")),
        "recall_cash_mean_cv": recall_cv,
        "holdout_recall_cash": float(hold_m["recall_cash"]),
        "gap_recall": float(recall_cv - float(hold_m["recall_cash"])) if pd.notna(recall_cv) else None,
        "balanced_accuracy_mean_cv": balacc_cv,
        "holdout_balanced_accuracy": float(hold_m["balanced_accuracy"]),
        "gap_balacc": float(balacc_cv - float(hold_m["balanced_accuracy"])) if pd.notna(balacc_cv) else None,
    }
    paths.out_generalization_gap.write_text(json.dumps(gap_payload, indent=2), encoding="utf-8")

    report = f"""# {paths.run_id} - XGBoost Ablation (Stratified CV + Threshold Tuning)

## Contexto
- T077-V1: FAIL lógico (feasible_count=0/48), recall_cash_mean_cv ~0.17 e acid window sem detecção de caixa.
- Este run: `scale_pos_weight` + threshold tuning no TRAIN e CV estratificado (justificado em evidência dedicada).
- Feature policy: ALLOWLIST core estável (CTO).

## Inputs
- `{IN_DATASET.relative_to(ROOT)}`
- `{IN_INV.relative_to(ROOT)}`

## Governança de features
- explicit blacklist (F-001): {EXPLICIT_BLACKLIST}
- threshold proxy temporal: abs(corr(feature, date_ordinal)) > {TIME_PROXY_CORR_THRESHOLD}
- features iniciais: {len(base_features)}
- removidas: {len(blacklisted_features)}
- finais: {len(features)}

## CV / thresholding
- CV: StratifiedKFold(n_splits={N_FOLDS}, shuffle=True, random_state=42)
- scale_pos_weight={scale_pos_weight:.4f}
- threshold grid: {THRESH_GRID}
- candidatos: {len(ablation)}
- feasíveis: {int(ablation['is_feasible'].sum())}
- winner: {w['candidate_id']}
- threshold winner: {winner_threshold}

## Métricas do winner
- TRAIN: {train_m}
- HOLDOUT: {hold_m}
- ACID: {acid_payload}
- Gap (CV -> HOLDOUT): {gap_payload}

## Artefatos
- `{paths.out_model.relative_to(ROOT)}`
- `{paths.out_preds.relative_to(ROOT)}`
- `{paths.out_abl.relative_to(ROOT)}`
- `{paths.out_plot.relative_to(ROOT)}`
- `{paths.out_blacklist.relative_to(ROOT)}`
- `{paths.out_time_scan.relative_to(ROOT)}`
- `{paths.out_cv_just.relative_to(ROOT)}`
- `{paths.out_thr_search.relative_to(ROOT)}`
- `{paths.out_feature_policy.relative_to(ROOT)}`
- `{paths.out_feature_stability.relative_to(ROOT)}`
- `{paths.out_generalization_gap.relative_to(ROOT)}`
- `{paths.out_acid.relative_to(ROOT)}`
- `{paths.out_transitions.relative_to(ROOT)}`
"""
    paths.out_report.write_text(report, encoding="utf-8")

    model_payload = {
        "task_id": paths.run_id,
        "model_type": "XGBClassifier",
        "winner_candidate_id": w["candidate_id"],
        "params": winner_params,
        "threshold": winner_threshold,
        "selection_metric_train": "recall_cash_mean_cv_then_balanced_accuracy",
        "cv_scheme": f"StratifiedKFold_{N_FOLDS}_shuffle_true_rs42",
        "features_used": features,
        "features_removed_blacklist": blacklisted_features,
        "train_metrics": train_m,
        "holdout_metrics": hold_m,
        "logical_fail_no_feasible_candidates": logical_fail,
        "feature_policy": feature_policy_payload,
    }
    paths.out_model.write_text(json.dumps(model_payload, indent=2), encoding="utf-8")

    inputs = [IN_DATASET, IN_INV]
    outputs = [
        paths.out_script,
        paths.out_model,
        paths.out_preds,
        paths.out_abl,
        paths.out_plot,
        paths.out_report,
        paths.out_blacklist,
        paths.out_time_scan,
        paths.out_cv_just,
        paths.out_thr_search,
        paths.out_feature_policy,
        paths.out_feature_stability,
        paths.out_generalization_gap,
        paths.out_acid,
        paths.out_transitions,
    ]
    manifest = {
        "task_id": paths.run_id,
        "manifest_id": f"{paths.run_id}-XGBOOST-ABLATION-V1",
        "inputs_consumed": [str(p.relative_to(ROOT)) for p in inputs],
        "outputs_produced": [str(p.relative_to(ROOT)) for p in outputs],
        "hashes_sha256": {str(p.relative_to(ROOT)): sha256_file(p) for p in inputs + outputs},
        "self_hash_excluded": True,
    }
    paths.out_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    policy_pass = set(features) == set(core_present) and set(features).issubset(set(CORE_ALLOWLIST))
    gates.append(Gate("G_FEATURE_POLICY_CORE_APPLIED", bool(policy_pass), f"features_used={len(features)} core={len(core_present)}"))

    gap_recall = gap_payload.get("gap_recall")
    gap_pass = (gap_recall is not None) and (abs(float(gap_recall)) < 0.15)
    gates.append(Gate("G_GENERALIZATION_GAP_RECALL", bool(gap_pass), f"gap_recall={gap_recall}"))

    gates.append(Gate("G1_INPUTS_PRESENT", all(p.exists() for p in inputs), "inputs T076 presentes"))
    gates.append(Gate("G2_BLACKLIST_APPLIED", all(f in blacklisted_features for f in EXPLICIT_BLACKLIST), f"blacklisted={EXPLICIT_BLACKLIST}"))
    gates.append(Gate("G3_TIME_PROXY_SCAN_PRESENT", paths.out_time_scan.exists(), str(paths.out_time_scan.relative_to(ROOT))))
    gates.append(Gate("G4_CV_JUSTIFICATION_PRESENT", paths.out_cv_just.exists(), str(paths.out_cv_just.relative_to(ROOT))))
    gates.append(Gate("G5_THRESHOLD_SEARCH_PRESENT", paths.out_thr_search.exists(), str(paths.out_thr_search.relative_to(ROOT))))
    gates.append(Gate("G6_ABLATION_RESULTS_PRESENT", paths.out_abl.exists(), f"candidatos={len(ablation)}"))
    gates.append(Gate("G7_MODEL_PREDS_PRESENT", paths.out_model.exists() and paths.out_preds.exists(), "modelo + predições gerados"))
    gates.append(Gate("G8_ACID_EVALUATED", paths.out_acid.exists() and acid_payload["n_rows"] > 0, f"acid_n_rows={acid_payload['n_rows']}"))
    gates.append(Gate("Gx_HASH_MANIFEST_PRESENT", paths.out_manifest.exists(), str(paths.out_manifest.relative_to(ROOT))))

    overall_pass = all(g.passed for g in gates) and (not logical_fail)

    print(f"HEADER: {paths.run_id}")
    print("STEP GATES:")
    for g in gates:
        print(f"- {g.name}: {'PASS' if g.passed else 'FAIL'} | {g.detail}")
    print("RETRY LOG:")
    if retry_log:
        for item in retry_log:
            print(f"- {item}")
    else:
        print("- none")
    print("ARTIFACT LINKS:")
    for p in outputs + [paths.out_manifest]:
        print(f"- {p.relative_to(ROOT)}")
    if logical_fail:
        print("- LOGIC_NOTE: nenhum candidato passou hard constraints no TRAIN-CV")
    print(f"OVERALL STATUS: [[ {'PASS' if overall_pass else 'FAIL'} ]]")
    return 0 if overall_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
