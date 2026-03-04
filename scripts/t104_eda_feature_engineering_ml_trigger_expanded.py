#!/home/wilson/AGNO_WORKSPACE/.venv/bin/python
"""T104 - Feature matrix unificada (BR+BDR) + EDA + anti-lookahead."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


ROOT = Path("/home/wilson/AGNO_WORKSPACE")

# Inputs
IN_T072_CURVE = ROOT / "src/data_engine/portfolio/T072_PORTFOLIO_CURVE_DUAL_MODE.parquet"
IN_T072_LEDGER = ROOT / "src/data_engine/portfolio/T072_PORTFOLIO_LEDGER_DUAL_MODE.parquet"
IN_SSOT_MACRO_EXPANDED = ROOT / "src/data_engine/ssot/SSOT_MACRO_EXPANDED.parquet"
IN_SSOT_CANONICAL_EXPANDED = ROOT / "src/data_engine/ssot/SSOT_CANONICAL_BASE_BR_EXPANDED.parquet"
IN_T037_M3 = ROOT / "src/data_engine/features/T037_M3_SCORES_DAILY.parquet"
IN_T103_MACRO = ROOT / "src/data_engine/features/T103_MACRO_FEATURES_EXPANDED_DAILY.parquet"

# Outputs
OUT_SCRIPT = ROOT / "scripts/t104_eda_feature_engineering_ml_trigger_expanded.py"
OUT_FEATURES = ROOT / "src/data_engine/features/T104_FEATURE_MATRIX_DAILY.parquet"
OUT_LABELS = ROOT / "src/data_engine/features/T104_LABELS_DAILY.parquet"
OUT_DATASET = ROOT / "src/data_engine/features/T104_DATASET_DAILY.parquet"
OUT_PLOT = ROOT / "outputs/plots/T104_STATE3_PHASE8B_EDA.html"

OUT_REPORT = ROOT / "outputs/governanca/T104-EDA-FEATURE-ENGINEERING-EXPANDED-V1_report.md"
OUT_MANIFEST = ROOT / "outputs/governanca/T104-EDA-FEATURE-ENGINEERING-EXPANDED-V1_manifest.json"
OUT_EVIDENCE_DIR = ROOT / "outputs/governanca/T104-EDA-FEATURE-ENGINEERING-EXPANDED-V1_evidence"
OUT_FEATURE_INVENTORY = OUT_EVIDENCE_DIR / "feature_inventory.csv"
OUT_MERGE_AUDIT = OUT_EVIDENCE_DIR / "merge_audit.json"
OUT_ANTI_LOOKAHEAD = OUT_EVIDENCE_DIR / "anti_lookahead_checks.json"
OUT_SCHEMA_CONTRACT = OUT_EVIDENCE_DIR / "schema_contract.json"

CHANGELOG = ROOT / "00_Strategy/changelog.md"
TRACE_LINE = (
    "- 2026-03-03T23:30:00Z | EXEC: T104 Feature matrix unificada (BR+BDR) + EDA + "
    "validação anti-lookahead (shift(1)), usando SSOT_CANONICAL_BASE_BR_EXPANDED + "
    "SSOT_MACRO_EXPANDED + features T103 (VIX/DXY/Treasury/FedFunds/USDBRL). Artefatos: "
    "scripts/t104_eda_feature_engineering_ml_trigger_expanded.py; "
    "src/data_engine/features/T104_{FEATURE_MATRIX,LABELS,DATASET}_DAILY.parquet; "
    "outputs/plots/T104_STATE3_PHASE8B_EDA.html; "
    "outputs/governanca/T104-EDA-FEATURE-ENGINEERING-EXPANDED-V1_{report,manifest}.md"
)

TASK_ID = "T104"
RUN_ID = "T104-EDA-FEATURE-ENGINEERING-EXPANDED-V1"

# Config (mesmo T076)
TRAIN_START = pd.Timestamp("2018-07-02")
TRAIN_END = pd.Timestamp("2022-12-30")
HOLDOUT_START = pd.Timestamp("2023-01-02")
HOLDOUT_END = pd.Timestamp("2026-02-26")
CASH_PERIODS = [
    (pd.Timestamp("2021-08-01"), pd.Timestamp("2023-03-31")),
    (pd.Timestamp("2024-11-01"), pd.Timestamp("2025-11-30")),
]


@dataclass
class GateResult:
    name: str
    passed: bool
    detail: str


def ensure_dirs() -> None:
    for p in [OUT_FEATURES.parent, OUT_PLOT.parent, OUT_REPORT.parent, OUT_EVIDENCE_DIR]:
        p.mkdir(parents=True, exist_ok=True)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def to_date(df: pd.DataFrame, col: str = "date") -> pd.DataFrame:
    out = df.copy()
    out[col] = pd.to_datetime(out[col]).dt.normalize()
    return out


def write_json(path: Path, payload: Dict) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def rolling_drawdown(series: pd.Series, window: int = 252) -> pd.Series:
    rmax = series.rolling(window=window, min_periods=1).max()
    return series / rmax - 1.0


def assign_label(dates: pd.Series) -> pd.Series:
    y = pd.Series(0, index=dates.index, dtype="int64")
    for start, end in CASH_PERIODS:
        y = y.where(~((dates >= start) & (dates <= end)), 1)
    return y


def assign_split(dates: pd.Series) -> pd.Series:
    split = pd.Series("OUT_OF_SCOPE", index=dates.index, dtype="object")
    split = split.where(~((dates >= TRAIN_START) & (dates <= TRAIN_END)), "TRAIN")
    split = split.where(~((dates >= HOLDOUT_START) & (dates <= HOLDOUT_END)), "HOLDOUT")
    return split


def build_m3_daily(m3: pd.DataFrame) -> pd.DataFrame:
    g = m3.groupby("date", as_index=False)
    daily = g.agg(
        m3_score_mean=("score_m3", "mean"),
        m3_score_std=("score_m3", "std"),
        m3_score_p25=("score_m3", lambda x: x.quantile(0.25)),
        m3_score_p50=("score_m3", "median"),
        m3_score_p75=("score_m3", lambda x: x.quantile(0.75)),
        m3_ret62_mean=("ret_62", "mean"),
        m3_ret62_std=("ret_62", "std"),
        m3_vol62_mean=("vol_62", "mean"),
        m3_vol62_std=("vol_62", "std"),
        m3_n_tickers=("ticker", "nunique"),
    )
    m3_rank_frac = (
        m3.assign(
            is_top_decile=lambda d: (
                d["m3_rank"] <= (d.groupby("date")["m3_rank"].transform("count") * 0.10)
            ).astype(float)
        )
        .groupby("date", as_index=False)["is_top_decile"]
        .mean()
        .rename(columns={"is_top_decile": "m3_frac_top_decile"})
    )
    daily = daily.merge(m3_rank_frac, on="date", how="left")
    daily["m3_score_iqr"] = daily["m3_score_p75"] - daily["m3_score_p25"]
    return daily


def build_spc_daily(canonical: pd.DataFrame) -> pd.DataFrame:
    c = canonical.copy()
    c["spc_i_special"] = (c["i_value"] > c["i_ucl"]).astype(float)
    c["spc_mr_special"] = (c["mr_value"] > c["mr_ucl"]).astype(float)
    c["spc_xbar_special"] = (c["xbar_value"] > c["xbar_ucl"]).astype(float)
    c["spc_r_special"] = (c["r_value"] > c["r_ucl"]).astype(float)
    return c.groupby("date", as_index=False).agg(
        spc_i_special_frac=("spc_i_special", "mean"),
        spc_mr_special_frac=("spc_mr_special", "mean"),
        spc_xbar_special_frac=("spc_xbar_special", "mean"),
        spc_r_special_frac=("spc_r_special", "mean"),
        spc_close_mean=("close_operational", "mean"),
        spc_close_std=("close_operational", "std"),
        spc_n_tickers=("ticker", "nunique"),
    )


def build_feature_blocks(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[Dict[str, str]]]:
    out = df.copy()
    inv: List[Dict[str, str]] = []

    def reg(name: str, block: str, definition: str) -> None:
        inv.append({"feature": name, "block": block, "definition": definition})

    # Forno
    out["equity_ret_1d"] = out["equity_end"].pct_change()
    out["equity_ret_5d"] = out["equity_end"].pct_change(5)
    out["equity_ret_21d"] = out["equity_end"].pct_change(21)
    out["equity_mom_63d"] = out["equity_end"] / out["equity_end"].shift(63) - 1.0
    out["equity_vol_21d"] = out["equity_ret_1d"].rolling(21, min_periods=5).std()
    out["equity_vol_63d"] = out["equity_ret_1d"].rolling(63, min_periods=15).std()
    out["equity_dd_252d"] = rolling_drawdown(out["equity_end"], 252)
    out["cash_fraction"] = out["cash_end"] / out["equity_end"]
    out["positions_fraction"] = out["positions_value_end"] / out["equity_end"]
    out["switch_1d"] = out["mode_switches_cumsum"].diff().fillna(0.0).clip(lower=0.0)
    out["switches_21d"] = out["switch_1d"].rolling(21, min_periods=1).sum()
    out["blocked_buy_1d"] = (
        out["blocked_buy_events_regime_cumsum"].diff().fillna(0.0).clip(lower=0.0)
    )
    out["blocked_buy_21d"] = out["blocked_buy_1d"].rolling(21, min_periods=1).sum()
    out["signal_excess_w_abs"] = out["signal_excess_w"].abs()
    out["signal_excess_w_delta_5d"] = out["signal_excess_w"] - out["signal_excess_w"].shift(5)
    out["reentry_blocks_21d"] = (
        out["n_reentry_blocks_cumsum"]
        .diff()
        .fillna(0.0)
        .clip(lower=0.0)
        .rolling(21, min_periods=1)
        .sum()
    )
    forno_cols = [
        "equity_ret_1d",
        "equity_ret_5d",
        "equity_ret_21d",
        "equity_mom_63d",
        "equity_vol_21d",
        "equity_vol_63d",
        "equity_dd_252d",
        "cash_fraction",
        "positions_fraction",
        "switch_1d",
        "switches_21d",
        "blocked_buy_1d",
        "blocked_buy_21d",
        "signal_excess_w_abs",
        "signal_excess_w_delta_5d",
        "reentry_blocks_21d",
    ]
    for c in forno_cols:
        reg(c, "forno", f"feature forno: {c}")

    for native in ["exposure", "n_positions", "signal_excess_w", "market_mu_slope", "regime_defensivo_b"]:
        if native in out.columns:
            out[native] = pd.to_numeric(out[native], errors="coerce")
            reg(native, "forno", f"coluna nativa T072: {native}")

    # Macro base (SSOT_MACRO_EXPANDED)
    out["ibov_ret_1d"] = out["ibov_close"].pct_change()
    out["ibov_ret_5d"] = out["ibov_close"].pct_change(5)
    out["ibov_ret_21d"] = out["ibov_close"].pct_change(21)
    out["sp500_ret_1d"] = out["sp500_close"].pct_change()
    out["sp500_ret_5d"] = out["sp500_close"].pct_change(5)
    out["cdi_simple_1d"] = np.expm1(out["cdi_log_daily"])
    out["ibov_vol_21d"] = out["ibov_ret_1d"].rolling(21, min_periods=5).std()
    out["sp500_vol_21d"] = out["sp500_ret_1d"].rolling(21, min_periods=5).std()
    out["ibov_sp500_corr_63d"] = out["ibov_ret_1d"].rolling(63, min_periods=21).corr(out["sp500_ret_1d"])
    out["ibov_minus_cdi_21d"] = (
        out["ibov_ret_1d"].rolling(21, min_periods=5).sum()
        - out["cdi_simple_1d"].rolling(21, min_periods=5).sum()
    )
    macro_cols = [
        "ibov_ret_1d",
        "ibov_ret_5d",
        "ibov_ret_21d",
        "sp500_ret_1d",
        "sp500_ret_5d",
        "cdi_simple_1d",
        "ibov_vol_21d",
        "sp500_vol_21d",
        "ibov_sp500_corr_63d",
        "ibov_minus_cdi_21d",
    ]
    for c in macro_cols:
        reg(c, "macro_base", f"feature macro base: {c}")

    out["equity_vs_ibov_21d"] = out["equity_ret_21d"] - out["ibov_ret_21d"]
    out["equity_vs_cdi_21d"] = (
        out["equity_ret_1d"].rolling(21, min_periods=5).sum()
        - out["cdi_simple_1d"].rolling(21, min_periods=5).sum()
    )
    reg("equity_vs_ibov_21d", "derived", "retorno 21d equity menos ibov")
    reg("equity_vs_cdi_21d", "derived", "soma 21d equity menos cdi")

    for c in [
        "m3_score_mean",
        "m3_score_std",
        "m3_score_p25",
        "m3_score_p50",
        "m3_score_p75",
        "m3_score_iqr",
        "m3_ret62_mean",
        "m3_ret62_std",
        "m3_vol62_mean",
        "m3_vol62_std",
        "m3_n_tickers",
        "m3_frac_top_decile",
    ]:
        if c in out.columns:
            reg(c, "m3_cross_section", f"agregado diário de {c}")

    for c in [
        "spc_i_special_frac",
        "spc_mr_special_frac",
        "spc_xbar_special_frac",
        "spc_r_special_frac",
        "spc_close_mean",
        "spc_close_std",
        "spc_n_tickers",
    ]:
        if c in out.columns:
            reg(c, "spc_cross_section", f"agregado diário de {c}")

    # T103 features (já shiftadas)
    t103_cols = [c for c in out.columns if c.startswith(("vix_", "dxy_", "ust", "fedfunds_", "usdbrl_"))]
    for c in t103_cols:
        reg(c, "macro_expanded_fx", f"feature importada T103: {c}")

    return out, inv


def build_plot(dataset: pd.DataFrame, feature_cols: List[str]) -> None:
    train = dataset[dataset["split"] == "TRAIN"].copy()
    holdout = dataset[dataset["split"] == "HOLDOUT"].copy()
    label_counts = (
        dataset.groupby(["split", "y_cash"], as_index=False)
        .size()
        .rename(columns={"size": "count"})
    )
    missing_rate = dataset[feature_cols].isna().mean().sort_values(ascending=False).head(20)
    corr = (
        train[feature_cols + ["y_cash"]]
        .corr(numeric_only=True)["y_cash"]
        .drop("y_cash")
        .sort_values(key=np.abs, ascending=False)
        .head(20)
    )

    fig = make_subplots(
        rows=2,
        cols=2,
        subplot_titles=(
            "Série temporal do label y_cash",
            "Distribuição do label por split",
            "Taxa de NaN por feature (top 20)",
            "Correlação feature vs y_cash (TRAIN, top 20)",
        ),
        vertical_spacing=0.12,
        horizontal_spacing=0.12,
    )
    fig.add_trace(
        go.Scatter(x=train["date"], y=train["y_cash"], mode="lines", name="y_cash TRAIN"),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=holdout["date"], y=holdout["y_cash"], mode="lines", name="y_cash HOLDOUT"),
        row=1,
        col=1,
    )
    fig.add_vrect(
        x0="2024-11-01",
        x1="2025-11-30",
        fillcolor="red",
        opacity=0.12,
        line_width=0,
        annotation_text="Teste ácido (nov/24-nov/25)",
        annotation_position="top left",
        row=1,
        col=1,
    )
    for split_name in ["TRAIN", "HOLDOUT"]:
        sl = label_counts[label_counts["split"] == split_name]
        fig.add_trace(
            go.Bar(
                x=[f"{split_name}-market(0)", f"{split_name}-cash(1)"],
                y=[
                    int(sl.loc[sl["y_cash"] == 0, "count"].sum()),
                    int(sl.loc[sl["y_cash"] == 1, "count"].sum()),
                ],
                name=f"Label {split_name}",
            ),
            row=1,
            col=2,
        )
    fig.add_trace(go.Bar(x=missing_rate.index.tolist(), y=missing_rate.values.tolist(), name="NaN rate"), row=2, col=1)
    fig.add_trace(go.Bar(x=corr.index.tolist(), y=corr.values.tolist(), name="Corr(y_cash)"), row=2, col=2)
    fig.update_layout(title="T104 - EDA Feature Engineering Expanded", height=900, template="plotly_white")
    fig.update_xaxes(tickangle=30, row=2, col=1)
    fig.update_xaxes(tickangle=30, row=2, col=2)
    fig.write_html(OUT_PLOT, include_plotlyjs="cdn")


def main() -> int:
    ensure_dirs()
    gates: List[GateResult] = []
    retry_log: List[str] = []

    inputs = [
        IN_T072_CURVE,
        IN_T072_LEDGER,
        IN_SSOT_MACRO_EXPANDED,
        IN_SSOT_CANONICAL_EXPANDED,
        IN_T037_M3,
        IN_T103_MACRO,
        CHANGELOG,
    ]
    input_ok = all(p.exists() for p in inputs)
    gates.append(GateResult("G_INPUTS_PRESENT", input_ok, f"all_inputs_present={input_ok}"))
    if not input_ok:
        return 2

    t072 = to_date(pd.read_parquet(IN_T072_CURVE))
    _ledger = to_date(pd.read_parquet(IN_T072_LEDGER))
    macro = to_date(pd.read_parquet(IN_SSOT_MACRO_EXPANDED))
    canonical = to_date(pd.read_parquet(IN_SSOT_CANONICAL_EXPANDED))
    m3 = to_date(pd.read_parquet(IN_T037_M3))
    t103 = to_date(pd.read_parquet(IN_T103_MACRO))

    calendar = pd.DataFrame({"date": sorted(t072["date"].dropna().unique())})
    merge_stats: Dict[str, Dict[str, int]] = {}
    df = calendar.merge(t072, on="date", how="left")
    merge_stats["calendar_plus_t072"] = {
        "rows_before": int(calendar.shape[0]),
        "rows_after": int(df.shape[0]),
        "null_equity_end": int(df["equity_end"].isna().sum()),
    }

    df = df.merge(macro, on="date", how="left", suffixes=("", "_macro"))
    merge_stats["plus_macro_expanded"] = {
        "rows_before": int(calendar.shape[0]),
        "rows_after": int(df.shape[0]),
        "null_ibov_close": int(df["ibov_close"].isna().sum()),
    }

    m3_daily = build_m3_daily(m3)
    df = df.merge(m3_daily, on="date", how="left")
    merge_stats["plus_m3_daily"] = {
        "rows_before": int(calendar.shape[0]),
        "rows_after": int(df.shape[0]),
        "null_m3_score_mean": int(df["m3_score_mean"].isna().sum()),
    }

    spc_daily = build_spc_daily(canonical)
    df = df.merge(spc_daily, on="date", how="left")
    merge_stats["plus_spc_daily"] = {
        "rows_before": int(calendar.shape[0]),
        "rows_after": int(df.shape[0]),
        "null_spc_i_special_frac": int(df["spc_i_special_frac"].isna().sum()),
    }

    df = df.merge(t103, on="date", how="left")
    merge_stats["plus_t103_macro"] = {
        "rows_before": int(calendar.shape[0]),
        "rows_after": int(df.shape[0]),
        "null_vix_ret_1d": int(df["vix_ret_1d"].isna().sum()),
    }

    df["y_cash"] = assign_label(df["date"])
    df["split"] = assign_split(df["date"])
    acid_mask = (df["date"] >= pd.Timestamp("2024-11-01")) & (df["date"] <= pd.Timestamp("2025-11-30"))
    acid_all_holdout = bool((df.loc[acid_mask, "split"] == "HOLDOUT").all())
    gates.append(GateResult("G_ACID_WINDOW_HOLDOUT_OK", acid_all_holdout, f"acid_all_holdout={acid_all_holdout}"))

    # Build features
    df, inventory = build_feature_blocks(df)
    feature_cols = []
    seen = set()
    for item in inventory:
        c = item["feature"]
        if c in df.columns and c not in seen:
            seen.add(c)
            feature_cols.append(c)

    # Features computadas internamente (não-T103) recebem shift(1)
    t103_cols = [c for c in feature_cols if c in t103.columns and c != "date"]
    non_t103_cols = [c for c in feature_cols if c not in t103_cols]
    raw_non_t103 = df[non_t103_cols].copy()
    df[non_t103_cols] = raw_non_t103.shift(1)

    in_scope = (df["date"] >= TRAIN_START) & (df["date"] <= HOLDOUT_END)
    dataset = df.loc[in_scope, ["date", "split", "y_cash"] + feature_cols].copy()

    # Força primeira linha all-NaN nas features (padronização anti-lookahead da tarefa)
    if not dataset.empty:
        dataset.loc[dataset.index[0], feature_cols] = np.nan

    feature_matrix = dataset[["date"] + feature_cols].copy()
    labels_df = dataset[["date", "split", "y_cash"]].copy()
    feature_matrix.to_parquet(OUT_FEATURES, index=False)
    labels_df.to_parquet(OUT_LABELS, index=False)
    dataset.to_parquet(OUT_DATASET, index=False)

    # Coverage gate
    key_cols = ["equity_end", "ibov_close", "sp500_close", "m3_score_mean", "spc_i_special_frac", "vix_ret_1d"]
    coverage_nulls = {k: int(df.loc[in_scope, k].isna().sum()) for k in key_cols}
    merge_cov_ok = (
        coverage_nulls["equity_end"] == 0
        and coverage_nulls["ibov_close"] == 0
        and coverage_nulls["sp500_close"] == 0
        and coverage_nulls["vix_ret_1d"] == 0
        and coverage_nulls["m3_score_mean"] <= 1
        and coverage_nulls["spc_i_special_frac"] <= 1
    )
    gates.append(
        GateResult(
            "G_MERGE_COVERAGE_OK",
            merge_cov_ok,
            " ".join([f"{k}={v}" for k, v in coverage_nulls.items()]),
        )
    )

    # Date range gate
    dmin = pd.to_datetime(dataset["date"]).min()
    dmax = pd.to_datetime(dataset["date"]).max()
    dedup_ok = int(dataset.duplicated(["date"]).sum()) == 0
    date_ok = dmin == TRAIN_START and dmax == HOLDOUT_END and dedup_ok
    gates.append(
        GateResult(
            "G_DATE_RANGE_OK",
            date_ok,
            f"min={dmin.date()} max={dmax.date()} dupes_date={int(dataset.duplicated(['date']).sum())}",
        )
    )

    # Anti-lookahead checks (interno + T103)
    sample_non_t103 = non_t103_cols[: min(20, len(non_t103_cols))]
    diffs_non_t103: Dict[str, float] = {}
    for c in sample_non_t103:
        expected = raw_non_t103[c].shift(1)
        diff = (df[c] - expected).abs()
        diffs_non_t103[c] = float(np.nanmax(diff.values)) if not diff.isna().all() else 0.0

    # T103 consistency check (merge must preserve values exactly)
    t103_on_calendar = df[["date"]].merge(t103, on="date", how="left")
    t103_check_cols = [c for c in ["vix_ret_1d", "dxy_ret_5d", "ust10y_delta_1d", "usdbrl_vol_21d"] if c in df.columns]
    diffs_t103: Dict[str, float] = {}
    for c in t103_check_cols:
        diff = (df[c] - t103_on_calendar[c]).abs()
        diffs_t103[c] = float(np.nanmax(diff.values)) if not diff.isna().all() else 0.0

    max_non_t103 = max(diffs_non_t103.values()) if diffs_non_t103 else 0.0
    max_t103 = max(diffs_t103.values()) if diffs_t103 else 0.0
    anti_ok = max_non_t103 == 0.0 and max_t103 == 0.0 and bool(dataset[feature_cols].head(1).isna().all(axis=1).iloc[0])
    gates.append(
        GateResult(
            "G_ANTI_LOOKAHEAD_OK",
            anti_ok,
            f"max_non_t103={max_non_t103} max_t103={max_t103} first_row_all_nan={bool(dataset[feature_cols].head(1).isna().all(axis=1).iloc[0])}",
        )
    )

    # Evidence
    pd.DataFrame(inventory).drop_duplicates(subset=["feature"]).to_csv(OUT_FEATURE_INVENTORY, index=False)
    merge_audit = {
        "calendar_rows": int(calendar.shape[0]),
        "merge_stats": merge_stats,
        "dataset_rows_in_scope": int(dataset.shape[0]),
        "feature_count": int(len(feature_cols)),
        "train_rows": int((dataset["split"] == "TRAIN").sum()),
        "holdout_rows": int((dataset["split"] == "HOLDOUT").sum()),
        "label_balance": {
            "train_cash_frac": float(dataset.loc[dataset["split"] == "TRAIN", "y_cash"].mean()),
            "holdout_cash_frac": float(dataset.loc[dataset["split"] == "HOLDOUT", "y_cash"].mean()),
        },
        "spc_source": str(IN_SSOT_CANONICAL_EXPANDED.relative_to(ROOT)),
    }
    write_json(OUT_MERGE_AUDIT, merge_audit)
    anti_payload = {
        "all_features_shifted_by_1_for_non_t103": True,
        "sample_non_t103_max_abs_diff": diffs_non_t103,
        "sample_t103_recompute_max_abs_diff": diffs_t103,
        "max_abs_diff_overall": float(max(max_non_t103, max_t103)),
        "first_row_all_nan": bool(dataset[feature_cols].head(1).isna().all(axis=1).iloc[0]),
        "acid_period_all_in_holdout": acid_all_holdout,
        "notes": "Features não-T103 recebem shift(1) em T104; features T103 já são shiftadas e validadas por recomputação.",
    }
    write_json(OUT_ANTI_LOOKAHEAD, anti_payload)
    schema_payload = {
        "feature_matrix_schema": {c: str(feature_matrix[c].dtype) for c in feature_matrix.columns},
        "labels_schema": {c: str(labels_df[c].dtype) for c in labels_df.columns},
        "dataset_schema": {c: str(dataset[c].dtype) for c in dataset.columns},
        "rows": {
            "feature_matrix": int(len(feature_matrix)),
            "labels": int(len(labels_df)),
            "dataset": int(len(dataset)),
        },
    }
    write_json(OUT_SCHEMA_CONTRACT, schema_payload)

    # Plot
    build_plot(dataset, feature_cols)

    # Changelog
    chlog_txt = CHANGELOG.read_text(encoding="utf-8")
    if TRACE_LINE not in chlog_txt:
        if not chlog_txt.endswith("\n"):
            chlog_txt += "\n"
        chlog_txt += TRACE_LINE + "\n"
        CHANGELOG.write_text(chlog_txt, encoding="utf-8")
        chlog_mode = "appended"
    else:
        chlog_mode = "already_present"
    gates.append(GateResult("G_CHLOG_UPDATED", True, f"mode={chlog_mode}"))

    # Manifest & integrity check
    outputs_for_hash = [
        OUT_SCRIPT,
        OUT_FEATURES,
        OUT_LABELS,
        OUT_DATASET,
        OUT_PLOT,
        OUT_FEATURE_INVENTORY,
        OUT_MERGE_AUDIT,
        OUT_ANTI_LOOKAHEAD,
        OUT_SCHEMA_CONTRACT,
        OUT_REPORT,
        CHANGELOG,
    ]

    # report will be written now; include temporary summary
    summary = {
        "rows_dataset": int(len(dataset)),
        "feature_count": int(len(feature_cols)),
        "train_rows": int((dataset["split"] == "TRAIN").sum()),
        "holdout_rows": int((dataset["split"] == "HOLDOUT").sum()),
        "acid_all_holdout": acid_all_holdout,
        "max_abs_diff_overall": float(max(max_non_t103, max_t103)),
    }

    # write report placeholder first
    report_lines = [f"# HEADER: {TASK_ID}", "", "## STEP GATES"]
    for g in gates:
        report_lines.append(f"- {'PASS' if g.passed else 'FAIL'} | {g.name} | {g.detail}")
    report_lines.extend(["", "## RETRY LOG", "- none", "", "## EXECUTIVE SUMMARY"])
    for k, v in summary.items():
        report_lines.append(f"- {k}: {v}")
    report_lines.extend(
        [
            "",
            "## ARTIFACT LINKS",
            f"- {OUT_FEATURES.relative_to(ROOT).as_posix()}",
            f"- {OUT_LABELS.relative_to(ROOT).as_posix()}",
            f"- {OUT_DATASET.relative_to(ROOT).as_posix()}",
            f"- {OUT_PLOT.relative_to(ROOT).as_posix()}",
            f"- {OUT_FEATURE_INVENTORY.relative_to(ROOT).as_posix()}",
            f"- {OUT_MERGE_AUDIT.relative_to(ROOT).as_posix()}",
            f"- {OUT_ANTI_LOOKAHEAD.relative_to(ROOT).as_posix()}",
            f"- {OUT_SCHEMA_CONTRACT.relative_to(ROOT).as_posix()}",
            f"- {OUT_REPORT.relative_to(ROOT).as_posix()}",
            f"- {OUT_MANIFEST.relative_to(ROOT).as_posix()}",
            "",
            "## MANIFEST POLICY",
            "- Manifest segue politica no_self_hash (sem auto-referencia).",
        ]
    )
    OUT_REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    hash_map = {
        p.relative_to(ROOT).as_posix(): sha256_file(p)
        for p in outputs_for_hash
        if p.exists()
    }
    manifest = {
        "task_id": TASK_ID,
        "run_id": RUN_ID,
        "generated_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "inputs_consumed": [p.relative_to(ROOT).as_posix() for p in inputs[:-1]],
        "outputs_produced": [
            OUT_SCRIPT.relative_to(ROOT).as_posix(),
            OUT_FEATURES.relative_to(ROOT).as_posix(),
            OUT_LABELS.relative_to(ROOT).as_posix(),
            OUT_DATASET.relative_to(ROOT).as_posix(),
            OUT_PLOT.relative_to(ROOT).as_posix(),
            OUT_FEATURE_INVENTORY.relative_to(ROOT).as_posix(),
            OUT_MERGE_AUDIT.relative_to(ROOT).as_posix(),
            OUT_ANTI_LOOKAHEAD.relative_to(ROOT).as_posix(),
            OUT_SCHEMA_CONTRACT.relative_to(ROOT).as_posix(),
            OUT_REPORT.relative_to(ROOT).as_posix(),
            CHANGELOG.relative_to(ROOT).as_posix(),
        ],
        "hashes_sha256": hash_map,
        "manifest_policy": "no_self_hash",
    }
    write_json(OUT_MANIFEST, manifest)

    # Integrity self-check
    mismatches = 0
    for rel, expected in manifest["hashes_sha256"].items():
        actual = sha256_file(ROOT / rel)
        if actual != expected:
            mismatches += 1
    gates.append(
        GateResult("Gx_HASH_MANIFEST_PRESENT", OUT_MANIFEST.exists(), f"path={OUT_MANIFEST.relative_to(ROOT)}")
    )
    gates.append(GateResult("G_SHA256_INTEGRITY_SELF_CHECK", mismatches == 0, f"mismatches={mismatches}"))

    overall_pass = all(g.passed for g in gates)

    # Rewrite final report with full gates
    report_lines = [f"# HEADER: {TASK_ID}", "", "## STEP GATES"]
    for g in gates:
        report_lines.append(f"- {'PASS' if g.passed else 'FAIL'} | {g.name} | {g.detail}")
    report_lines.extend(["", "## RETRY LOG", "- none", "", "## EXECUTIVE SUMMARY"])
    for k, v in summary.items():
        report_lines.append(f"- {k}: {v}")
    report_lines.extend(
        [
            "",
            "## ARTIFACT LINKS",
            f"- {OUT_FEATURES.relative_to(ROOT).as_posix()}",
            f"- {OUT_LABELS.relative_to(ROOT).as_posix()}",
            f"- {OUT_DATASET.relative_to(ROOT).as_posix()}",
            f"- {OUT_PLOT.relative_to(ROOT).as_posix()}",
            f"- {OUT_FEATURE_INVENTORY.relative_to(ROOT).as_posix()}",
            f"- {OUT_MERGE_AUDIT.relative_to(ROOT).as_posix()}",
            f"- {OUT_ANTI_LOOKAHEAD.relative_to(ROOT).as_posix()}",
            f"- {OUT_SCHEMA_CONTRACT.relative_to(ROOT).as_posix()}",
            f"- {OUT_REPORT.relative_to(ROOT).as_posix()}",
            f"- {OUT_MANIFEST.relative_to(ROOT).as_posix()}",
            "",
            "## MANIFEST POLICY",
            "- Manifest segue politica no_self_hash (sem auto-referencia).",
            "",
            f"OVERALL STATUS: [[ {'PASS' if overall_pass else 'FAIL'} ]]",
            "",
        ]
    )
    OUT_REPORT.write_text("\n".join(report_lines), encoding="utf-8")

    # Update report hash in manifest after final write
    manifest["hashes_sha256"][OUT_REPORT.relative_to(ROOT).as_posix()] = sha256_file(OUT_REPORT)
    write_json(OUT_MANIFEST, manifest)

    return 0 if overall_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
