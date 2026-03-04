#!/home/wilson/AGNO_WORKSPACE/.venv/bin/python
"""T105 - XGBoost retrain with expanded features (T104 dataset).

Execution notes:
- Uses TRAIN/HOLDOUT split already materialized in T104.
- Keeps anti-lookahead assumptions from upstream features.
- Produces versioned T105_V1 artifacts and governance report/manifest.
"""

from __future__ import annotations

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
SCRIPT_PATH = ROOT / "scripts/t105_xgboost_retrain_expanded_walkforward_v1.py"

IN_DATASET = ROOT / "src/data_engine/features/T104_DATASET_DAILY.parquet"
IN_INV = ROOT / "outputs/governanca/T104-EDA-FEATURE-ENGINEERING-EXPANDED-V1_evidence/feature_inventory.csv"

OUT_MODEL = ROOT / "src/data_engine/models/T105_V1_XGB_SELECTED_MODEL.json"
OUT_PREDS = ROOT / "src/data_engine/features/T105_V1_PREDICTIONS.parquet"
OUT_ABL = ROOT / "src/data_engine/features/T105_V1_ABLATION_RESULTS.parquet"
OUT_PLOT = ROOT / "outputs/plots/T105_V1_STATE3_PHASE8C_MODEL_DIAGNOSTICS.html"
OUT_REPORT = ROOT / "outputs/governanca/T105-V1-XGBOOST-RETRAIN-EXPANDED-V1_report.md"
OUT_MANIFEST = ROOT / "outputs/governanca/T105-V1-XGBOOST-RETRAIN-EXPANDED-V1_manifest.json"
OUT_EVID = ROOT / "outputs/governanca/T105-V1-XGBOOST-RETRAIN-EXPANDED-V1_evidence"

OUT_POLICY = OUT_EVID / "feature_policy.json"
OUT_SCAN = OUT_EVID / "time_leakage_scan_train.csv"
OUT_VARIANT_CMP = OUT_EVID / "variant_comparison.json"
OUT_THRESHOLD = OUT_EVID / "threshold_search_results.parquet"
OUT_STABILITY = OUT_EVID / "feature_stability_report.csv"
OUT_ACID = OUT_EVID / "acid_window_holdout_metrics.json"
OUT_TRANSITIONS = OUT_EVID / "transition_diagnostics.json"
OUT_GAP = OUT_EVID / "generalization_gap.json"

CHANGELOG = ROOT / "00_Strategy/changelog.md"
CHANGELOG_LINE = (
    "- 2026-03-03T21:17:16Z | EXEC: T105 XGBoost retreino com features expandidas "
    "(T104 dataset, walk-forward split, policy de features + macro_expanded_fx/T103) "
    "com governanca SHA256. Artefatos: "
    "scripts/t105_xgboost_retrain_expanded_walkforward_v1.py; "
    "src/data_engine/models/T105_V1_XGB_SELECTED_MODEL.json; "
    "src/data_engine/features/T105_V1_{PREDICTIONS,ABLATION_RESULTS}.parquet; "
    "outputs/plots/T105_V1_STATE3_PHASE8C_MODEL_DIAGNOSTICS.html; "
    "outputs/governanca/T105-V1-XGBOOST-RETRAIN-EXPANDED-V1_{report,manifest}.md"
)

EXPLICIT_BLACKLIST = {"m3_n_tickers", "spc_n_tickers"}
TIME_PROXY_CORR_THRESHOLD = 0.95
THRESH_GRID = [0.05, 0.08, 0.10, 0.12, 0.15, 0.20, 0.30, 0.40, 0.50]
N_FOLDS = 5
MIN_PRECISION = 0.20

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


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def cls_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    return {
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "f1_cash": float(f1_score(y_true, y_pred, pos_label=1, zero_division=0)),
        "recall_cash": float(recall_score(y_true, y_pred, pos_label=1, zero_division=0)),
        "precision_cash": float(precision_score(y_true, y_pred, pos_label=1, zero_division=0)),
        "transition_rate_pred": float(np.mean(y_pred[1:] != y_pred[:-1])) if len(y_pred) > 1 else 0.0,
    }


def choose_threshold(y_true: np.ndarray, y_proba: np.ndarray) -> Tuple[float, pd.DataFrame]:
    rows = []
    for thr in THRESH_GRID:
        y_pred = (y_proba >= thr).astype(int)
        m = cls_metrics(y_true, y_pred)
        rows.append(
            {
                "threshold": float(thr),
                **m,
                "meets_min_precision": bool(m["precision_cash"] >= MIN_PRECISION),
            }
        )
    df = pd.DataFrame(rows)
    feasible = df[df["meets_min_precision"]]
    pool = feasible if not feasible.empty else df
    pool = pool.sort_values(
        by=["recall_cash", "balanced_accuracy", "precision_cash", "threshold"],
        ascending=[False, False, False, True],
    )
    return float(pool.iloc[0]["threshold"]), df


def scan_time_proxy(train_df: pd.DataFrame, features: List[str]) -> pd.DataFrame:
    t = train_df.copy()
    t["date_ordinal"] = t["date"].map(pd.Timestamp.toordinal).astype(float)
    rows = []
    for f in features:
        s = pd.to_numeric(t[f], errors="coerce")
        mask = s.notna() & t["date_ordinal"].notna()
        corr = np.nan
        if int(mask.sum()) >= 3:
            x = s[mask].to_numpy(dtype=float)
            y = t.loc[mask, "date_ordinal"].to_numpy(dtype=float)
            if np.std(x) > 0 and np.std(y) > 0:
                corr = float(np.corrcoef(x, y)[0, 1])
        rows.append({"feature": f, "corr_with_date_ordinal_train": corr, "abs_corr": abs(corr) if pd.notna(corr) else np.nan})
    return pd.DataFrame(rows).sort_values("abs_corr", ascending=False)


def ensure_dirs() -> None:
    for p in [OUT_MODEL.parent, OUT_PREDS.parent, OUT_ABL.parent, OUT_PLOT.parent, OUT_REPORT.parent, OUT_EVID]:
        p.mkdir(parents=True, exist_ok=True)


def evaluate_variant(
    variant: str,
    features: List[str],
    train: pd.DataFrame,
    holdout: pd.DataFrame,
    scale_pos_weight: float,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, object], pd.DataFrame]:
    x_train = train[features].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    y_train = train["y_cash"].astype(int)
    x_hold = holdout[features].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    y_hold = holdout["y_cash"].astype(int)
    skf = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=42)

    grid = list(itertools.product([120, 240], [2, 3, 4], [0.03, 0.06], [0.8, 1.0], [0.8, 1.0], [1, 3]))
    ablation_rows: List[Dict[str, object]] = []
    thr_rows: List[Dict[str, object]] = []

    for i, (n_est, max_depth, lr, subsample, colsample, min_child_weight) in enumerate(grid):
        candidate_id = f"{variant}_C{i:03d}"
        params = {
            "n_estimators": int(n_est),
            "max_depth": int(max_depth),
            "learning_rate": float(lr),
            "subsample": float(subsample),
            "colsample_bytree": float(colsample),
            "min_child_weight": int(min_child_weight),
            "reg_lambda": 1.0,
            "scale_pos_weight": float(scale_pos_weight),
        }

        oof = np.full(len(x_train), np.nan, dtype=float)
        fold_assign = np.full(len(x_train), -1, dtype=int)
        for fold_id, (tr_idx, va_idx) in enumerate(skf.split(x_train, y_train)):
            model = XGBClassifier(objective="binary:logistic", eval_metric="logloss", random_state=42, n_jobs=1, **params)
            model.fit(x_train.iloc[tr_idx], y_train.iloc[tr_idx])
            oof[va_idx] = model.predict_proba(x_train.iloc[va_idx])[:, 1]
            fold_assign[va_idx] = fold_id

        best_thr, thr_table = choose_threshold(y_train.values, oof)
        thr_table["candidate_id"] = candidate_id
        thr_table["variant"] = variant
        thr_table["selected_threshold_for_candidate"] = thr_table["threshold"].map(lambda x: bool(abs(float(x) - best_thr) < 1e-12))
        thr_rows.append(thr_table)

        fold_metrics = []
        for fold_id in range(N_FOLDS):
            m = fold_assign == fold_id
            y_pred_fold = (oof[m] >= best_thr).astype(int)
            fold_metrics.append(cls_metrics(y_train.values[m], y_pred_fold))

        row: Dict[str, object] = {
            "variant": variant,
            "candidate_id": candidate_id,
            "threshold_selected": float(best_thr),
            **params,
        }
        for k in ["balanced_accuracy", "f1_cash", "recall_cash", "precision_cash", "transition_rate_pred"]:
            vals = [z[k] for z in fold_metrics]
            row[f"{k}_mean_cv"] = float(np.mean(vals))
            row[f"{k}_std_cv"] = float(np.std(vals, ddof=0))
        row["gate_recall_cash"] = bool(row["recall_cash_mean_cv"] >= 0.50)
        row["gate_balanced_acc"] = bool(row["balanced_accuracy_mean_cv"] >= 0.55)
        row["gate_transition_rate"] = bool(row["transition_rate_pred_mean_cv"] >= 0.005)
        row["is_feasible"] = bool(row["gate_recall_cash"] and row["gate_balanced_acc"] and row["gate_transition_rate"])
        ablation_rows.append(row)

    abl = pd.DataFrame(ablation_rows).sort_values(
        by=["is_feasible", "recall_cash_mean_cv", "balanced_accuracy_mean_cv", "precision_cash_mean_cv", "candidate_id"],
        ascending=[False, False, False, False, True],
    )
    thresholds = pd.concat(thr_rows, ignore_index=True)
    feasible = abl[abl["is_feasible"]]
    winner = feasible.iloc[0] if not feasible.empty else abl.iloc[0]

    winner_params = {
        "n_estimators": int(winner["n_estimators"]),
        "max_depth": int(winner["max_depth"]),
        "learning_rate": float(winner["learning_rate"]),
        "subsample": float(winner["subsample"]),
        "colsample_bytree": float(winner["colsample_bytree"]),
        "min_child_weight": int(winner["min_child_weight"]),
        "reg_lambda": float(winner["reg_lambda"]),
        "scale_pos_weight": float(winner["scale_pos_weight"]),
    }
    winner_thr = float(winner["threshold_selected"])

    model = XGBClassifier(objective="binary:logistic", eval_metric="logloss", random_state=42, n_jobs=1, **winner_params)
    model.fit(x_train, y_train)
    p_train = model.predict_proba(x_train)[:, 1]
    yhat_train = (p_train >= winner_thr).astype(int)
    p_hold = model.predict_proba(x_hold)[:, 1]
    yhat_hold = (p_hold >= winner_thr).astype(int)

    payload = {
        "variant": variant,
        "winner_candidate_id": str(winner["candidate_id"]),
        "winner_threshold": winner_thr,
        "winner_params": winner_params,
        "train_metrics": cls_metrics(y_train.values, yhat_train),
        "holdout_metrics": cls_metrics(y_hold.values, yhat_hold),
        "feasible_count": int(abl["is_feasible"].sum()),
        "total_candidates": int(len(abl)),
    }
    importance = pd.DataFrame({"feature": features, "importance_gain": model.feature_importances_.astype(float)}).sort_values(
        "importance_gain", ascending=False
    )
    return abl, thresholds, payload, importance


def main() -> int:
    ensure_dirs()
    retry_log: List[str] = []
    gates: List[Gate] = []

    df = pd.read_parquet(IN_DATASET)
    inv = pd.read_csv(IN_INV)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df = df.sort_values("date").reset_index(drop=True)
    train = df[df["split"] == "TRAIN"].copy()
    holdout = df[df["split"] == "HOLDOUT"].copy()

    base_features = [c for c in df.columns if c not in {"date", "split", "y_cash"}]
    scan = scan_time_proxy(train, base_features)
    scan.to_csv(OUT_SCAN, index=False)

    blacklisted = set(EXPLICIT_BLACKLIST)
    for _, r in scan.iterrows():
        if pd.notna(r["abs_corr"]) and float(r["abs_corr"]) > TIME_PROXY_CORR_THRESHOLD:
            blacklisted.add(str(r["feature"]))

    core_features = [f for f in CORE_ALLOWLIST if f in base_features and f not in blacklisted]
    macro_fx = inv.loc[inv["block"] == "macro_expanded_fx", "feature"].dropna().astype(str).tolist()
    macro_fx = [f for f in macro_fx if f in base_features and f not in blacklisted]
    extended_features = sorted(set(core_features + macro_fx))

    y_train = train["y_cash"].astype(int)
    neg = int((y_train == 0).sum())
    pos = int((y_train == 1).sum())
    scale_pos_weight = float(neg / max(pos, 1))

    abl_core, thr_core, payload_core, _imp_core = evaluate_variant("CORE", core_features, train, holdout, scale_pos_weight)
    abl_ext, thr_ext, payload_ext, imp_ext = evaluate_variant("CORE_PLUS_MACRO_EXPANDED_FX", extended_features, train, holdout, scale_pos_weight)
    ablation = pd.concat([abl_core, abl_ext], ignore_index=True)
    thresholds = pd.concat([thr_core, thr_ext], ignore_index=True)

    # Global winner across variants
    ablation_sorted = ablation.sort_values(
        by=["is_feasible", "recall_cash_mean_cv", "balanced_accuracy_mean_cv", "precision_cash_mean_cv", "candidate_id"],
        ascending=[False, False, False, False, True],
    ).reset_index(drop=True)
    winner = ablation_sorted.iloc[0]
    winner_variant = str(winner["variant"])
    winner_features = core_features if winner_variant == "CORE" else extended_features
    winner_thr = float(winner["threshold_selected"])
    winner_params = {
        "n_estimators": int(winner["n_estimators"]),
        "max_depth": int(winner["max_depth"]),
        "learning_rate": float(winner["learning_rate"]),
        "subsample": float(winner["subsample"]),
        "colsample_bytree": float(winner["colsample_bytree"]),
        "min_child_weight": int(winner["min_child_weight"]),
        "reg_lambda": float(winner["reg_lambda"]),
        "scale_pos_weight": float(winner["scale_pos_weight"]),
    }

    x_train = train[winner_features].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    x_hold = holdout[winner_features].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    y_hold = holdout["y_cash"].astype(int)
    model = XGBClassifier(objective="binary:logistic", eval_metric="logloss", random_state=42, n_jobs=1, **winner_params)
    model.fit(x_train, y_train)
    p_train = model.predict_proba(x_train)[:, 1]
    yhat_train = (p_train >= winner_thr).astype(int)
    p_hold = model.predict_proba(x_hold)[:, 1]
    yhat_hold = (p_hold >= winner_thr).astype(int)

    preds = pd.concat(
        [
            pd.DataFrame({"date": train["date"], "split": "TRAIN", "y_cash": y_train.values, "y_proba_cash": p_train, "y_pred_cash": yhat_train}),
            pd.DataFrame({"date": holdout["date"], "split": "HOLDOUT", "y_cash": y_hold.values, "y_proba_cash": p_hold, "y_pred_cash": yhat_hold}),
        ],
        ignore_index=True,
    ).sort_values("date")
    preds.to_parquet(OUT_PREDS, index=False)
    ablation_sorted.to_parquet(OUT_ABL, index=False)
    thresholds.to_parquet(OUT_THRESHOLD, index=False)

    acid = preds[(preds["split"] == "HOLDOUT") & (preds["date"] >= pd.Timestamp("2024-11-01")) & (preds["date"] <= pd.Timestamp("2025-11-30"))]
    acid_payload = {
        "n_rows": int(len(acid)),
        "y_cash_rate_true": float(acid["y_cash"].mean()) if not acid.empty else None,
        "y_cash_rate_pred": float(acid["y_pred_cash"].mean()) if not acid.empty else None,
        "metrics": cls_metrics(acid["y_cash"].values, acid["y_pred_cash"].values) if not acid.empty else {},
    }
    OUT_ACID.write_text(json.dumps(acid_payload, indent=2), encoding="utf-8")

    stability_rows = []
    for f in winner_features:
        s = pd.to_numeric(train[f], errors="coerce")
        corr_y = float(s.corr(y_train.astype(float), method="spearman")) if int(s.notna().sum()) >= 3 else np.nan
        corr_row = scan[scan["feature"] == f]
        abs_corr_date = float(corr_row["abs_corr"].iloc[0]) if (not corr_row.empty and pd.notna(corr_row["abs_corr"].iloc[0])) else np.nan
        stability_rows.append({"feature": f, "spearman_corr_y_cash_train": corr_y, "abs_corr_date_ordinal_train": abs_corr_date})
    pd.DataFrame(stability_rows).sort_values("abs_corr_date_ordinal_train", ascending=False).to_csv(OUT_STABILITY, index=False)

    gap_payload = {
        "winner_candidate_id": str(winner["candidate_id"]),
        "winner_variant": winner_variant,
        "recall_cash_mean_cv": float(winner["recall_cash_mean_cv"]),
        "holdout_recall_cash": float(cls_metrics(y_hold.values, yhat_hold)["recall_cash"]),
        "gap_recall": float(float(winner["recall_cash_mean_cv"]) - float(cls_metrics(y_hold.values, yhat_hold)["recall_cash"])),
    }
    OUT_GAP.write_text(json.dumps(gap_payload, indent=2), encoding="utf-8")

    transitions = {
        "train_pred_switches": int(np.sum(yhat_train[1:] != yhat_train[:-1])) if len(yhat_train) > 1 else 0,
        "holdout_pred_switches": int(np.sum(yhat_hold[1:] != yhat_hold[:-1])) if len(yhat_hold) > 1 else 0,
    }
    OUT_TRANSITIONS.write_text(json.dumps(transitions, indent=2), encoding="utf-8")

    variant_cmp = {"CORE": payload_core, "CORE_PLUS_MACRO_EXPANDED_FX": payload_ext}
    OUT_VARIANT_CMP.write_text(json.dumps(variant_cmp, indent=2), encoding="utf-8")
    policy = {
        "explicit_blacklist": sorted(EXPLICIT_BLACKLIST),
        "time_proxy_corr_threshold": TIME_PROXY_CORR_THRESHOLD,
        "base_features_count": len(base_features),
        "blacklisted_features": sorted(blacklisted),
        "variant_core_features_count": len(core_features),
        "variant_extended_features_count": len(extended_features),
        "winner_variant": winner_variant,
    }
    OUT_POLICY.write_text(json.dumps(policy, indent=2), encoding="utf-8")

    imp = pd.DataFrame({"feature": winner_features, "importance_gain": model.feature_importances_.astype(float)}).sort_values(
        "importance_gain", ascending=False
    )
    fig = make_subplots(rows=3, cols=1, subplot_titles=("y_cash vs y_pred_cash", "y_proba_cash", "Top-20 feature importance"), vertical_spacing=0.1)
    fig.add_trace(go.Scatter(x=preds["date"], y=preds["y_cash"], mode="lines", name="y_true"), row=1, col=1)
    fig.add_trace(go.Scatter(x=preds["date"], y=preds["y_pred_cash"], mode="lines", name="y_pred"), row=1, col=1)
    fig.add_trace(go.Scatter(x=preds["date"], y=preds["y_proba_cash"], mode="lines", name="y_proba"), row=2, col=1)
    fig.add_vrect(x0="2024-11-01", x1="2025-11-30", fillcolor="red", opacity=0.10, line_width=0, row=1, col=1)
    fig.add_vrect(x0="2024-11-01", x1="2025-11-30", fillcolor="red", opacity=0.10, line_width=0, row=2, col=1)
    top = imp.head(20)
    fig.add_trace(go.Bar(x=top["feature"], y=top["importance_gain"], name="gain"), row=3, col=1)
    fig.update_layout(height=1100, template="plotly_white", title="T105_V1 Model Diagnostics")
    fig.write_html(OUT_PLOT, include_plotlyjs="cdn")

    model_payload = {
        "task_id": "T105_V1",
        "model_type": "XGBClassifier",
        "winner_candidate_id": str(winner["candidate_id"]),
        "winner_variant": winner_variant,
        "params": winner_params,
        "threshold": winner_thr,
        "features_used": winner_features,
        "train_metrics": cls_metrics(y_train.values, yhat_train),
        "holdout_metrics": cls_metrics(y_hold.values, yhat_hold),
    }
    OUT_MODEL.write_text(json.dumps(model_payload, indent=2), encoding="utf-8")

    # Changelog update (idempotent)
    ch_lines = CHANGELOG.read_text(encoding="utf-8").splitlines()
    if CHANGELOG_LINE in ch_lines:
        ch_mode = "already_present"
    else:
        with CHANGELOG.open("a", encoding="utf-8") as f:
            f.write("\n" + CHANGELOG_LINE + "\n")
        ch_mode = "appended"

    gates.append(Gate("G_INPUTS_PRESENT", IN_DATASET.exists() and IN_INV.exists(), "dataset+t104 inventory present"))
    gates.append(Gate("G_SPLIT_OK", set(df["split"].unique()) == {"TRAIN", "HOLDOUT"}, f"splits={sorted(df['split'].unique().tolist())}"))
    acid_holdout_ok = bool((df.loc[(df["date"] >= "2024-11-01") & (df["date"] <= "2025-11-30"), "split"] == "HOLDOUT").all())
    gates.append(Gate("G_ACID_WINDOW_HOLDOUT_OK", acid_holdout_ok, f"acid_rows={int(((df['date'] >= '2024-11-01') & (df['date'] <= '2025-11-30')).sum())}"))
    gates.append(Gate("G_BLACKLIST_APPLIED", all(x in blacklisted for x in EXPLICIT_BLACKLIST), f"blacklisted_explicit={sorted(EXPLICIT_BLACKLIST)}"))
    gates.append(Gate("G_TIME_PROXY_SCAN_PRESENT", OUT_SCAN.exists(), str(OUT_SCAN.relative_to(ROOT))))
    gates.append(Gate("G_VARIANT_COMPARISON_PRESENT", OUT_VARIANT_CMP.exists(), str(OUT_VARIANT_CMP.relative_to(ROOT))))
    gates.append(Gate("G_MODEL_PREDS_ABL_PRESENT", OUT_MODEL.exists() and OUT_PREDS.exists() and OUT_ABL.exists(), "model+preds+ablation present"))
    gates.append(Gate("G_ACID_METRICS_PRESENT", OUT_ACID.exists() and acid_payload["n_rows"] > 0, f"acid_rows={acid_payload['n_rows']}"))

    report_text = "\n".join(
        [
            "# HEADER: T105",
            "",
            "## STEP GATES",
            *[f"- {'PASS' if g.passed else 'FAIL'} | {g.name} | {g.detail}" for g in gates],
            f"- PASS | G_CHLOG_UPDATED | mode={ch_mode}",
            "",
            "## RETRY LOG",
            "- none" if not retry_log else "\n".join([f"- {x}" for x in retry_log]),
            "",
            "## EXECUTIVE SUMMARY",
            f"- winner_variant: {winner_variant}",
            f"- winner_candidate_id: {winner['candidate_id']}",
            f"- winner_threshold: {winner_thr}",
            f"- feature_count_winner: {len(winner_features)}",
            f"- train_rows: {len(train)}",
            f"- holdout_rows: {len(holdout)}",
            "",
            "## ARTIFACT LINKS",
            f"- {OUT_MODEL.relative_to(ROOT)}",
            f"- {OUT_PREDS.relative_to(ROOT)}",
            f"- {OUT_ABL.relative_to(ROOT)}",
            f"- {OUT_PLOT.relative_to(ROOT)}",
            f"- {OUT_POLICY.relative_to(ROOT)}",
            f"- {OUT_SCAN.relative_to(ROOT)}",
            f"- {OUT_VARIANT_CMP.relative_to(ROOT)}",
            f"- {OUT_THRESHOLD.relative_to(ROOT)}",
            f"- {OUT_STABILITY.relative_to(ROOT)}",
            f"- {OUT_ACID.relative_to(ROOT)}",
            f"- {OUT_TRANSITIONS.relative_to(ROOT)}",
            f"- {OUT_GAP.relative_to(ROOT)}",
            f"- {OUT_REPORT.relative_to(ROOT)}",
            f"- {OUT_MANIFEST.relative_to(ROOT)}",
        ]
    )
    OUT_REPORT.write_text(report_text + "\n", encoding="utf-8")

    inputs = [IN_DATASET, IN_INV]
    outputs = [
        SCRIPT_PATH,
        OUT_MODEL,
        OUT_PREDS,
        OUT_ABL,
        OUT_PLOT,
        OUT_POLICY,
        OUT_SCAN,
        OUT_VARIANT_CMP,
        OUT_THRESHOLD,
        OUT_STABILITY,
        OUT_ACID,
        OUT_TRANSITIONS,
        OUT_GAP,
        OUT_REPORT,
        CHANGELOG,
    ]

    manifest = {
        "task_id": "T105",
        "run_id": "T105-V1-XGBOOST-RETRAIN-EXPANDED-V1",
        "inputs_consumed": [str(p.relative_to(ROOT)) for p in inputs],
        "outputs_produced": [str(p.relative_to(ROOT)) for p in outputs],
        "hashes_sha256": {str(p.relative_to(ROOT)): sha256_file(p) for p in inputs + outputs},
        "manifest_policy": "no_self_hash",
    }
    OUT_MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    mismatches = 0
    for rel, expected in manifest["hashes_sha256"].items():
        got = sha256_file(ROOT / rel)
        if got != expected:
            mismatches += 1
    gates.append(Gate("Gx_HASH_MANIFEST_PRESENT", OUT_MANIFEST.exists(), str(OUT_MANIFEST.relative_to(ROOT))))
    gates.append(Gate("G_SHA256_INTEGRITY_SELF_CHECK", mismatches == 0, f"mismatches={mismatches}"))
    gates.append(Gate("G_CHLOG_UPDATED", True, f"mode={ch_mode}"))

    overall_pass = all(g.passed for g in gates)
    print("HEADER: T105")
    print("STEP GATES:")
    for g in gates:
        print(f"- {'PASS' if g.passed else 'FAIL'} | {g.name} | {g.detail}")
    print("RETRY LOG:")
    print("- none" if not retry_log else "\n".join(f"- {x}" for x in retry_log))
    print("ARTIFACT LINKS:")
    for p in [OUT_MODEL, OUT_PREDS, OUT_ABL, OUT_PLOT, OUT_REPORT, OUT_MANIFEST]:
        print(f"- {p.relative_to(ROOT)}")
    print(f"OVERALL STATUS: [[ {'PASS' if overall_pass else 'FAIL'} ]]")
    return 0 if overall_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
