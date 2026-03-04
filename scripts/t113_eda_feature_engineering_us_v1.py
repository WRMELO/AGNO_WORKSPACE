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


if not ("agno_env" in sys.prefix or ".venv" in sys.prefix):
    raise RuntimeError("FATAL: Not in agno_env/.venv")


TASK_ID = "T113"
RUN_ID = "T113-PHASE9B-US-FEATURES-V1"
ROOT = Path("/home/wilson/AGNO_WORKSPACE")
PYTHON_ENV = ROOT / ".venv/bin/python"
CHANGELOG_PATH = ROOT / "00_Strategy/changelog.md"

TRACEABILITY_LINE = (
    "- 2026-03-04T00:00:00Z | EXEC: T113 Feature matrix US (macro + derivados do S&P 500) + EDA + "
    "validacao anti-lookahead (shift(1)), alinhada ao label oracle T112. Artefatos: "
    "scripts/t113_eda_feature_engineering_us_v1.py; "
    "src/data_engine/features/T113_US_{FEATURE_MATRIX,LABELS,DATASET}_DAILY.parquet; "
    "outputs/plots/T113_STATE3_PHASE9B_US_FEATURES_EDA.html; "
    "outputs/governanca/T113-PHASE9B-US-FEATURES-V1_{report,manifest}.md"
)

IN_MACRO = ROOT / "src/data_engine/ssot/SSOT_MACRO_EXPANDED.parquet"
IN_T112_LABELS = ROOT / "src/data_engine/features/T112_US_LABELS_DAILY.parquet"

OUT_SCRIPT = ROOT / "scripts/t113_eda_feature_engineering_us_v1.py"
OUT_FEATURES = ROOT / "src/data_engine/features/T113_US_FEATURE_MATRIX_DAILY.parquet"
OUT_LABELS = ROOT / "src/data_engine/features/T113_US_LABELS_DAILY.parquet"
OUT_DATASET = ROOT / "src/data_engine/features/T113_US_DATASET_DAILY.parquet"
OUT_HTML = ROOT / "outputs/plots/T113_STATE3_PHASE9B_US_FEATURES_EDA.html"
OUT_REPORT = ROOT / "outputs/governanca/T113-PHASE9B-US-FEATURES-V1_report.md"
OUT_MANIFEST = ROOT / "outputs/governanca/T113-PHASE9B-US-FEATURES-V1_manifest.json"
OUT_EVID_DIR = ROOT / "outputs/governanca/T113-PHASE9B-US-FEATURES-V1_evidence"
OUT_FEATURE_INVENTORY = OUT_EVID_DIR / "feature_inventory.csv"
OUT_MERGE_AUDIT = OUT_EVID_DIR / "merge_audit.json"
OUT_ANTI = OUT_EVID_DIR / "anti_lookahead_checks.json"
OUT_SCHEMA = OUT_EVID_DIR / "schema_contract.json"
OUT_EDA = OUT_EVID_DIR / "eda_snapshot.json"

RECORTE_START = pd.Timestamp("2018-07-02")
RECORTE_END = pd.Timestamp("2026-02-26")
TRAIN_END = pd.Timestamp("2022-12-30")
HOLDOUT_START = pd.Timestamp("2023-01-02")

EXPECTED_TOTAL = 1902
EXPECTED_TRAIN = 1115
EXPECTED_HOLDOUT = 787

REQUIRED_MACRO_COLS = [
    "date",
    "sp500_close",
    "vix_close",
    "usd_index_broad",
    "ust_2y_yield",
    "ust_10y_yield",
    "ust_10y_2y_spread",
    "fed_funds_rate",
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


def _roll_slope(series: pd.Series, window: int) -> pd.Series:
    x = np.arange(window, dtype=float)
    x_mean = x.mean()
    denom = float(np.sum((x - x_mean) ** 2))
    out = np.full(len(series), np.nan, dtype=float)
    vals = pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)
    for i in range(window - 1, len(vals)):
        y = vals[i - window + 1 : i + 1]
        if np.isnan(y).any():
            continue
        y_mean = float(np.mean(y))
        num = float(np.sum((x - x_mean) * (y - y_mean)))
        out[i] = num / denom if denom != 0 else np.nan
    return pd.Series(out, index=series.index)


def build_feature_matrix(base: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = base.copy()
    inv: list[dict[str, str]] = []

    def reg(name: str, block: str, definition: str) -> None:
        inv.append({"feature": name, "block": block, "definition": definition})

    for c in [
        "sp500_close",
        "vix_close",
        "usd_index_broad",
        "ust_2y_yield",
        "ust_10y_yield",
        "ust_10y_2y_spread",
        "fed_funds_rate",
    ]:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)

    # SP500 return, momentum, vol and slope
    df["sp500_ret_1d"] = df["sp500_close"].pct_change(1)
    df["sp500_ret_5d"] = df["sp500_close"].pct_change(5)
    df["sp500_ret_21d"] = df["sp500_close"].pct_change(21)
    df["sp500_logret_1d"] = np.log(df["sp500_close"]).diff(1)
    df["sp500_mom_21d"] = df["sp500_close"] / df["sp500_close"].shift(21) - 1.0
    df["sp500_mom_63d"] = df["sp500_close"] / df["sp500_close"].shift(63) - 1.0
    df["sp500_vol_21d"] = df["sp500_ret_1d"].rolling(21, min_periods=5).std()
    df["sp500_vol_63d"] = df["sp500_ret_1d"].rolling(63, min_periods=15).std()
    df["sp500_slope_21d"] = _roll_slope(df["sp500_close"], 21)
    df["sp500_slope_63d"] = _roll_slope(df["sp500_close"], 63)
    for c in [
        "sp500_ret_1d",
        "sp500_ret_5d",
        "sp500_ret_21d",
        "sp500_logret_1d",
        "sp500_mom_21d",
        "sp500_mom_63d",
        "sp500_vol_21d",
        "sp500_vol_63d",
        "sp500_slope_21d",
        "sp500_slope_63d",
    ]:
        reg(c, "sp500", f"sp500 derived feature: {c}")

    # VIX block
    df["vix_ret_1d"] = df["vix_close"].pct_change(1)
    df["vix_ret_5d"] = df["vix_close"].pct_change(5)
    df["vix_delta_1d"] = df["vix_close"].diff(1)
    df["vix_delta_5d"] = df["vix_close"].diff(5)
    df["vix_z_63d"] = (df["vix_close"] - df["vix_close"].rolling(63, min_periods=21).mean()) / df[
        "vix_close"
    ].rolling(63, min_periods=21).std()
    for c in ["vix_ret_1d", "vix_ret_5d", "vix_delta_1d", "vix_delta_5d", "vix_z_63d"]:
        reg(c, "vix", f"vix derived feature: {c}")

    # DXY block
    df["dxy_ret_1d"] = df["usd_index_broad"].pct_change(1)
    df["dxy_ret_5d"] = df["usd_index_broad"].pct_change(5)
    df["dxy_delta_1d"] = df["usd_index_broad"].diff(1)
    df["dxy_vol_21d"] = df["dxy_ret_1d"].rolling(21, min_periods=5).std()
    for c in ["dxy_ret_1d", "dxy_ret_5d", "dxy_delta_1d", "dxy_vol_21d"]:
        reg(c, "dxy", f"dxy derived feature: {c}")

    # Rates and curve block
    df["ust10y_delta_1d"] = df["ust_10y_yield"].diff(1)
    df["ust2y_delta_1d"] = df["ust_2y_yield"].diff(1)
    df["curve_delta_1d"] = df["ust_10y_2y_spread"].diff(1)
    df["curve_delta_5d"] = df["ust_10y_2y_spread"].diff(5)
    df["fed_delta_1d"] = df["fed_funds_rate"].diff(1)
    df["fed_delta_5d"] = df["fed_funds_rate"].diff(5)
    for c in [
        "ust10y_delta_1d",
        "ust2y_delta_1d",
        "curve_delta_1d",
        "curve_delta_5d",
        "fed_delta_1d",
        "fed_delta_5d",
    ]:
        reg(c, "rates_curve", f"rates/curve derived feature: {c}")

    # Cross features
    df["sp500_vix_corr_63d"] = df["sp500_ret_1d"].rolling(63, min_periods=21).corr(df["vix_ret_1d"])
    df["sp500_dxy_corr_63d"] = df["sp500_ret_1d"].rolling(63, min_periods=21).corr(df["dxy_ret_1d"])
    for c in ["sp500_vix_corr_63d", "sp500_dxy_corr_63d"]:
        reg(c, "cross", f"cross derived feature: {c}")

    inventory_df = pd.DataFrame(inv).drop_duplicates(subset=["feature"]).reset_index(drop=True)
    return df, inventory_df


def render_report(
    gates: list[Gate],
    retry_log: list[str],
    overall: bool,
    summary: dict[str, Any] | None = None,
) -> str:
    summary = summary or {}
    lines = [f"# HEADER: {TASK_ID}", "", "## STEP GATES"]
    for g in gates:
        lines.append(f"- {g.name}: {'PASS' if g.passed else 'FAIL'} | {g.detail}")
    lines.extend(
        [
            "",
            "## RESUMO",
            f"- rows_dataset={summary.get('rows_dataset', 'n/a')}",
            f"- rows_train={summary.get('rows_train', 'n/a')} | rows_holdout={summary.get('rows_holdout', 'n/a')}",
            f"- features_total={summary.get('features_total', 'n/a')}",
            f"- label_cash_train={summary.get('label_cash_train', 'n/a')} | label_cash_holdout={summary.get('label_cash_holdout', 'n/a')}",
            f"- anti_max_abs_diff={summary.get('anti_max_abs_diff', 'n/a')}",
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
            f"- {OUT_FEATURES.relative_to(ROOT)}",
            f"- {OUT_LABELS.relative_to(ROOT)}",
            f"- {OUT_DATASET.relative_to(ROOT)}",
            f"- {OUT_HTML.relative_to(ROOT)}",
            f"- {OUT_REPORT.relative_to(ROOT)}",
            f"- {OUT_MANIFEST.relative_to(ROOT)}",
            f"- {OUT_FEATURE_INVENTORY.relative_to(ROOT)}",
            f"- {OUT_MERGE_AUDIT.relative_to(ROOT)}",
            f"- {OUT_ANTI.relative_to(ROOT)}",
            f"- {OUT_SCHEMA.relative_to(ROOT)}",
            f"- {OUT_EDA.relative_to(ROOT)}",
            "",
            f"## OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]",
            "",
        ]
    )
    return "\n".join(lines)


def build_dashboard(dataset: pd.DataFrame, feature_cols: list[str]) -> dict[str, Any]:
    ds = dataset.copy()
    ds["split"] = np.where(ds["date"] <= TRAIN_END, "TRAIN", "HOLDOUT")
    label_counts = ds.groupby(["split", "y_cash_us_v1"], as_index=False).size().rename(columns={"size": "count"})

    missing_after_warmup = ds.iloc[64:][feature_cols].isna().sum().sum()
    missing_rate_top = ds[feature_cols].isna().mean().sort_values(ascending=False).head(15)

    corr_train = (
        ds.loc[ds["split"] == "TRAIN", feature_cols + ["y_cash_us_v1"]]
        .corr(numeric_only=True)["y_cash_us_v1"]
        .drop("y_cash_us_v1")
        .sort_values(key=np.abs, ascending=False)
        .head(15)
    )

    sp500_norm = 100000.0 * (ds["sp500_close"] / float(ds["sp500_close"].iloc[0]))
    fig = make_subplots(
        rows=2,
        cols=2,
        subplot_titles=(
            "S&P500 normalizado + y_cash",
            "Distribuicao do label por split",
            "Missingness por feature (top 15)",
            "Correlacao com label (TRAIN, top 15)",
        ),
        vertical_spacing=0.12,
        horizontal_spacing=0.12,
    )
    fig.add_trace(go.Scatter(x=ds["date"], y=sp500_norm, name="SP500 norm"), row=1, col=1)
    fig.add_trace(
        go.Scatter(
            x=ds["date"],
            y=ds["y_cash_us_v1"].astype(int),
            name="y_cash_us_v1",
            yaxis="y2",
            mode="lines",
            line={"shape": "hv"},
        ),
        row=1,
        col=1,
    )
    for split_name in ["TRAIN", "HOLDOUT"]:
        sl = label_counts[label_counts["split"] == split_name]
        fig.add_trace(
            go.Bar(
                x=[f"{split_name}-market(0)", f"{split_name}-cash(1)"],
                y=[
                    int(sl.loc[sl["y_cash_us_v1"] == 0, "count"].sum()),
                    int(sl.loc[sl["y_cash_us_v1"] == 1, "count"].sum()),
                ],
                name=f"label_{split_name}",
            ),
            row=1,
            col=2,
        )
    fig.add_trace(
        go.Bar(x=missing_rate_top.index.tolist(), y=missing_rate_top.values.tolist(), name="missing_rate"),
        row=2,
        col=1,
    )
    fig.add_trace(go.Bar(x=corr_train.index.tolist(), y=corr_train.values.tolist(), name="corr_train"), row=2, col=2)
    fig.update_layout(height=950, template="plotly_white", title="T113 - US Feature Engineering EDA")
    fig.update_xaxes(tickangle=25, row=2, col=1)
    fig.update_xaxes(tickangle=25, row=2, col=2)
    fig.write_html(str(OUT_HTML), include_plotlyjs="cdn")

    return {
        "label_cash_frac_train": float(ds.loc[ds["split"] == "TRAIN", "y_cash_us_v1"].mean()),
        "label_cash_frac_holdout": float(ds.loc[ds["split"] == "HOLDOUT", "y_cash_us_v1"].mean()),
        "n_features": int(len(feature_cols)),
        "n_rows": int(len(ds)),
        "missing_after_warmup": int(missing_after_warmup),
    }


def main() -> int:
    gates: list[Gate] = []
    retry_log: list[str] = []
    summary: dict[str, Any] = {}
    try:
        for p in [
            OUT_FEATURES,
            OUT_LABELS,
            OUT_DATASET,
            OUT_HTML,
            OUT_REPORT,
            OUT_MANIFEST,
            OUT_FEATURE_INVENTORY,
            OUT_MERGE_AUDIT,
            OUT_ANTI,
            OUT_SCHEMA,
            OUT_EDA,
        ]:
            p.parent.mkdir(parents=True, exist_ok=True)

        env_ok = PYTHON_ENV.exists() and (".venv" in sys.prefix or "agno_env" in sys.prefix)
        gates.append(Gate("G_ENV_VENV", env_ok, f"python={sys.executable}"))
        if not env_ok:
            raise RuntimeError("python env check failed")

        macro_exists = IN_MACRO.exists()
        labels_exists = IN_T112_LABELS.exists()
        gates.append(Gate("G0_INPUTS_EXIST", macro_exists and labels_exists, f"macro={macro_exists} labels={labels_exists}"))
        if not (macro_exists and labels_exists):
            raise RuntimeError("required inputs missing")

        macro = pd.read_parquet(IN_MACRO).copy()
        labels = pd.read_parquet(IN_T112_LABELS).copy()
        macro_cols_ok = set(REQUIRED_MACRO_COLS).issubset(set(macro.columns))
        labels_cols_ok = {"date", "y_cash_us_v1"}.issubset(set(labels.columns))
        gates.append(Gate("G1_INPUT_COLUMNS_OK", macro_cols_ok and labels_cols_ok, f"macro_cols={macro_cols_ok} labels_cols={labels_cols_ok}"))
        if not (macro_cols_ok and labels_cols_ok):
            raise RuntimeError("input columns mismatch")

        macro["date"] = pd.to_datetime(macro["date"]).dt.normalize()
        labels["date"] = pd.to_datetime(labels["date"]).dt.normalize()
        macro = macro[(macro["date"] >= RECORTE_START) & (macro["date"] <= RECORTE_END)].copy()
        labels = labels[(labels["date"] >= RECORTE_START) & (labels["date"] <= RECORTE_END)].copy()
        macro = macro.sort_values("date").drop_duplicates("date").reset_index(drop=True)
        labels = labels.sort_values("date").drop_duplicates("date").reset_index(drop=True)
        if macro[REQUIRED_MACRO_COLS[1:]].isna().any().any():
            raise RuntimeError("macro raw required series has NaN in recorte")

        pre_rows_ok = len(macro) == EXPECTED_TOTAL and len(labels) == EXPECTED_TOTAL
        gates.append(Gate("G2_INPUT_ROWS_SCOPE_OK", pre_rows_ok, f"macro_rows={len(macro)} labels_rows={len(labels)}"))
        if not pre_rows_ok:
            raise RuntimeError("input rows in recorte are not 1902")

        base = macro.merge(labels, on="date", how="inner")
        merge_ok = len(base) == EXPECTED_TOTAL
        train_rows = int((base["date"] <= TRAIN_END).sum())
        holdout_rows = int((base["date"] >= HOLDOUT_START).sum())
        split_ok = train_rows == EXPECTED_TRAIN and holdout_rows == EXPECTED_HOLDOUT
        gates.append(
            Gate(
                "G3_JOIN_AND_SPLIT_OK",
                merge_ok and split_ok,
                f"rows={len(base)} train={train_rows} holdout={holdout_rows}",
            )
        )
        if not (merge_ok and split_ok):
            raise RuntimeError("join/split contract failed")

        base["y_cash_us_v1"] = pd.to_numeric(base["y_cash_us_v1"], errors="coerce")
        label_ok = (
            not base["y_cash_us_v1"].isna().any()
            and set(base["y_cash_us_v1"].astype(int).unique()).issubset({0, 1})
        )
        gates.append(Gate("G4_LABEL_BINARY_OK", label_ok, f"unique={sorted(base['y_cash_us_v1'].astype(int).unique().tolist())}"))
        if not label_ok:
            raise RuntimeError("labels not binary")

        engineered, inventory_df = build_feature_matrix(base)
        feature_cols = inventory_df["feature"].tolist()
        raw_feature_df = engineered[feature_cols].copy()
        engineered[feature_cols] = raw_feature_df.shift(1)

        # Anti-lookahead check
        diffs = {}
        for c in feature_cols:
            expected = raw_feature_df[c].shift(1)
            diff = (engineered[c] - expected).abs()
            diffs[c] = float(np.nanmax(diff.values)) if not diff.isna().all() else 0.0
        max_abs_diff = max(diffs.values()) if diffs else 0.0
        first_row_all_nan = bool(engineered[feature_cols].head(1).isna().all(axis=1).iloc[0])
        anti_ok = max_abs_diff <= 1e-12 and first_row_all_nan
        gates.append(
            Gate(
                "G5_ANTI_LOOKAHEAD_OK",
                anti_ok,
                f"max_abs_diff={max_abs_diff:.3e} first_row_all_nan={first_row_all_nan}",
            )
        )
        if not anti_ok:
            raise RuntimeError("anti-lookahead validation failed")

        keep_label_cols = [
            "date",
            "y_cash_us_v1",
            "variant_id_selected",
            "fwd_window_selected",
            "drawdown_threshold_selected",
        ]
        dataset_cols = ["date", "y_cash_us_v1"] + feature_cols + [
            "sp500_close",
            "variant_id_selected",
            "fwd_window_selected",
            "drawdown_threshold_selected",
        ]
        feature_out = engineered[["date"] + feature_cols].copy()
        label_out = engineered[keep_label_cols].copy()
        dataset_out = engineered[dataset_cols].copy()

        feature_out.to_parquet(OUT_FEATURES, index=False)
        label_out.to_parquet(OUT_LABELS, index=False)
        dataset_out.to_parquet(OUT_DATASET, index=False)
        artifact_ok = OUT_FEATURES.exists() and OUT_LABELS.exists() and OUT_DATASET.exists()
        gates.append(Gate("G6_PARQUETS_WRITTEN", artifact_ok, f"features={len(feature_out)} labels={len(label_out)} dataset={len(dataset_out)}"))
        if not artifact_ok:
            raise RuntimeError("parquet outputs missing")

        # Evidence artifacts
        inventory_df.to_csv(OUT_FEATURE_INVENTORY, index=False)
        write_json(
            OUT_MERGE_AUDIT,
            {
                "input_macro_path": str(IN_MACRO.relative_to(ROOT)),
                "input_labels_path": str(IN_T112_LABELS.relative_to(ROOT)),
                "merge_rows": int(len(base)),
                "expected_rows": EXPECTED_TOTAL,
                "train_rows": train_rows,
                "holdout_rows": holdout_rows,
                "date_min": base["date"].min(),
                "date_max": base["date"].max(),
                "required_macro_cols": REQUIRED_MACRO_COLS,
                "feature_count": len(feature_cols),
            },
        )
        write_json(
            OUT_ANTI,
            {
                "policy": "global_shift_1_on_all_features",
                "max_abs_diff_overall": max_abs_diff,
                "first_row_all_nan": first_row_all_nan,
                "per_feature_max_abs_diff": diffs,
                "tolerance": 1e-12,
            },
        )
        write_json(
            OUT_SCHEMA,
            {
                "feature_matrix_schema": {c: str(feature_out[c].dtype) for c in feature_out.columns},
                "labels_schema": {c: str(label_out[c].dtype) for c in label_out.columns},
                "dataset_schema": {c: str(dataset_out[c].dtype) for c in dataset_out.columns},
                "rows": {
                    "feature_matrix": len(feature_out),
                    "labels": len(label_out),
                    "dataset": len(dataset_out),
                },
            },
        )

        eda_snapshot = build_dashboard(dataset_out, feature_cols)
        write_json(OUT_EDA, eda_snapshot)
        gates.append(Gate("G7_EDA_WRITTEN", OUT_HTML.exists() and OUT_EDA.exists(), f"html={OUT_HTML.exists()}"))

        # After warm-up rows there should be no NaN for core features
        core_cols = ["sp500_ret_1d", "sp500_vol_21d", "vix_ret_1d", "dxy_ret_1d", "curve_delta_1d", "fed_delta_1d"]
        core_missing_after_warmup = int(dataset_out.iloc[64:][core_cols].isna().sum().sum())
        core_ok = core_missing_after_warmup == 0
        gates.append(
            Gate("G8_CORE_FEATURES_NO_NAN_AFTER_WARMUP", core_ok, f"missing_after_warmup={core_missing_after_warmup}")
        )
        if not core_ok:
            raise RuntimeError("core features still have NaN after warm-up")

        ch_ok = append_changelog_one_line_idempotent(TRACEABILITY_LINE)
        gates.append(Gate("G_CHLOG_UPDATED", ch_ok, f"path={CHANGELOG_PATH}"))

        summary = {
            "rows_dataset": len(dataset_out),
            "rows_train": train_rows,
            "rows_holdout": holdout_rows,
            "features_total": len(feature_cols),
            "label_cash_train": float(dataset_out.loc[dataset_out["date"] <= TRAIN_END, "y_cash_us_v1"].mean()),
            "label_cash_holdout": float(dataset_out.loc[dataset_out["date"] >= HOLDOUT_START, "y_cash_us_v1"].mean()),
            "anti_max_abs_diff": max_abs_diff,
        }

        # draft report before hash stage
        OUT_REPORT.write_text(render_report(gates, retry_log, all(g.passed for g in gates), summary), encoding="utf-8")

        outputs_for_hash = [
            OUT_SCRIPT,
            OUT_FEATURES,
            OUT_LABELS,
            OUT_DATASET,
            OUT_HTML,
            OUT_REPORT,
            OUT_FEATURE_INVENTORY,
            OUT_MERGE_AUDIT,
            OUT_ANTI,
            OUT_SCHEMA,
            OUT_EDA,
            CHANGELOG_PATH,
        ]
        hashes = {str(p.relative_to(ROOT)): sha256_file(p) for p in outputs_for_hash}
        manifest = {
            "task_id": TASK_ID,
            "run_id": RUN_ID,
            "manifest_policy": "no_self_hash",
            "inputs_consumed": [str(IN_MACRO.relative_to(ROOT)), str(IN_T112_LABELS.relative_to(ROOT))],
            "outputs_produced": [
                str(OUT_FEATURES.relative_to(ROOT)),
                str(OUT_LABELS.relative_to(ROOT)),
                str(OUT_DATASET.relative_to(ROOT)),
                str(OUT_HTML.relative_to(ROOT)),
                str(OUT_REPORT.relative_to(ROOT)),
                str(OUT_MANIFEST.relative_to(ROOT)),
                str(OUT_FEATURE_INVENTORY.relative_to(ROOT)),
                str(OUT_MERGE_AUDIT.relative_to(ROOT)),
                str(OUT_ANTI.relative_to(ROOT)),
                str(OUT_SCHEMA.relative_to(ROOT)),
                str(OUT_EDA.relative_to(ROOT)),
            ],
            "hashes_sha256": hashes,
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
        OUT_REPORT.write_text(render_report(gates, retry_log, overall, summary), encoding="utf-8")
        final_hashes = {str(p.relative_to(ROOT)): sha256_file(p) for p in outputs_for_hash}
        manifest["hashes_sha256"] = final_hashes
        write_json(OUT_MANIFEST, manifest)

        print(f"HEADER: {TASK_ID}")
        print("STEP GATES:")
        for g in gates:
            print(f"- {g.name}: {'PASS' if g.passed else 'FAIL'} | {g.detail}")
        print("RETRY LOG:")
        print("- none" if not retry_log else "\n".join(f"- {r}" for r in retry_log))
        print("ARTIFACT LINKS:")
        print(f"- {OUT_FEATURES}")
        print(f"- {OUT_LABELS}")
        print(f"- {OUT_DATASET}")
        print(f"- {OUT_HTML}")
        print(f"- {OUT_REPORT}")
        print(f"- {OUT_MANIFEST}")
        print(f"- {OUT_FEATURE_INVENTORY}")
        print(f"- {OUT_MERGE_AUDIT}")
        print(f"- {OUT_ANTI}")
        print(f"- {OUT_SCHEMA}")
        print(f"- {OUT_EDA}")
        print(f"OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]")
        return 0 if overall else 2
    except Exception as exc:
        retry_log.append(f"FATAL: {type(exc).__name__}: {exc}")
        gates.append(Gate("G_FATAL", False, f"{type(exc).__name__}: {exc}"))
        OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
        OUT_REPORT.write_text(render_report(gates, retry_log, False, summary), encoding="utf-8")
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
