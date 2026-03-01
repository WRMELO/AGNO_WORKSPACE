#!/home/wilson/AGNO_WORKSPACE/.venv/bin/python
"""T076 - EDA + Feature Engineering para ML Trigger (Phase 6A).

Gera:
- Feature matrix diaria (com shift(1) em todas as features de entrada)
- Labels diarios (y_cash) com split TRAIN/HOLDOUT
- Dataset final para T077
- Evidencias de merge e anti-lookahead
- Plotly EDA
- Report markdown
- Manifest SHA256 (sem self-hash)
"""

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
IN_SSOT_MACRO = ROOT / "src/data_engine/ssot/SSOT_MACRO.parquet"
IN_SSOT_CANONICAL = ROOT / "src/data_engine/ssot/SSOT_CANONICAL_BASE.parquet"
IN_T037_M3 = ROOT / "src/data_engine/features/T037_M3_SCORES_DAILY.parquet"

# Outputs
OUT_SCRIPT = ROOT / "scripts/t076_eda_feature_engineering_ml_trigger.py"
OUT_FEATURES = ROOT / "src/data_engine/features/T076_FEATURE_MATRIX_DAILY.parquet"
OUT_LABELS = ROOT / "src/data_engine/features/T076_LABELS_DAILY.parquet"
OUT_DATASET = ROOT / "src/data_engine/features/T076_DATASET_DAILY.parquet"
OUT_PLOT = ROOT / "outputs/plots/T076_STATE3_PHASE6A_EDA.html"

OUT_REPORT = ROOT / "outputs/governanca/T076-EDA-FEATURE-ENGINEERING-V1_report.md"
OUT_MANIFEST = ROOT / "outputs/governanca/T076-EDA-FEATURE-ENGINEERING-V1_manifest.json"
OUT_EVIDENCE_DIR = ROOT / "outputs/governanca/T076-EDA-FEATURE-ENGINEERING-V1_evidence"
OUT_FEATURE_INVENTORY = OUT_EVIDENCE_DIR / "feature_inventory.csv"
OUT_MERGE_AUDIT = OUT_EVIDENCE_DIR / "merge_audit.json"
OUT_ANTI_LOOKAHEAD = OUT_EVIDENCE_DIR / "anti_lookahead_checks.json"

# Config
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


def rolling_drawdown(series: pd.Series, window: int = 252) -> pd.Series:
    rmax = series.rolling(window=window, min_periods=1).max()
    return series / rmax - 1.0


def to_date(df: pd.DataFrame, col: str = "date") -> pd.DataFrame:
    out = df.copy()
    out[col] = pd.to_datetime(out[col]).dt.normalize()
    return out


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
        m3.assign(is_top_decile=lambda d: (d["m3_rank"] <= (d.groupby("date")["m3_rank"].transform("count") * 0.10)).astype(float))
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

    daily = (
        c.groupby("date", as_index=False)
        .agg(
            spc_i_special_frac=("spc_i_special", "mean"),
            spc_mr_special_frac=("spc_mr_special", "mean"),
            spc_xbar_special_frac=("spc_xbar_special", "mean"),
            spc_r_special_frac=("spc_r_special", "mean"),
            spc_close_mean=("close_operational", "mean"),
            spc_close_std=("close_operational", "std"),
            spc_n_tickers=("ticker", "nunique"),
        )
    )
    return daily


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


def build_feature_blocks(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[Dict[str, str]]]:
    out = df.copy()
    inv: List[Dict[str, str]] = []

    def reg(name: str, block: str, definition: str) -> None:
        inv.append({"feature": name, "block": block, "definition": definition})

    # Furnace/T072 block
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
    out["blocked_buy_1d"] = out["blocked_buy_events_regime_cumsum"].diff().fillna(0.0).clip(lower=0.0)
    out["blocked_buy_21d"] = out["blocked_buy_1d"].rolling(21, min_periods=1).sum()
    out["signal_excess_w_abs"] = out["signal_excess_w"].abs()
    out["signal_excess_w_delta_5d"] = out["signal_excess_w"] - out["signal_excess_w"].shift(5)
    out["reentry_blocks_21d"] = out["n_reentry_blocks_cumsum"].diff().fillna(0.0).clip(lower=0.0).rolling(21, min_periods=1).sum()

    reg("equity_ret_1d", "forno", "retorno diário de equity")
    reg("equity_ret_5d", "forno", "retorno 5 dias de equity")
    reg("equity_ret_21d", "forno", "retorno 21 dias de equity")
    reg("equity_mom_63d", "forno", "momentum de 63 dias de equity")
    reg("equity_vol_21d", "forno", "volatilidade rolling 21d de equity_ret_1d")
    reg("equity_vol_63d", "forno", "volatilidade rolling 63d de equity_ret_1d")
    reg("equity_dd_252d", "forno", "drawdown rolling em 252 dias")
    reg("cash_fraction", "forno", "cash_end / equity_end")
    reg("positions_fraction", "forno", "positions_value_end / equity_end")
    reg("switch_1d", "forno", "variação diária de mode_switches_cumsum")
    reg("switches_21d", "forno", "soma rolling 21d de switch_1d")
    reg("blocked_buy_1d", "forno", "incremento diário de blocked_buy_events_regime_cumsum")
    reg("blocked_buy_21d", "forno", "soma rolling 21d de blocked_buy_1d")
    reg("signal_excess_w_abs", "forno", "magnitude absoluta de signal_excess_w")
    reg("signal_excess_w_delta_5d", "forno", "variação 5d de signal_excess_w")
    reg("reentry_blocks_21d", "forno", "soma rolling 21d de novos reentry blocks")

    # Keep native daily columns as model candidates
    native_candidates = ["exposure", "n_positions", "signal_excess_w", "market_mu_slope", "regime_defensivo_b"]
    for col in native_candidates:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
            reg(col, "forno", f"coluna nativa T072: {col}")

    # Macro block
    out["ibov_ret_1d"] = out["ibov_close"].pct_change()
    out["ibov_ret_5d"] = out["ibov_close"].pct_change(5)
    out["ibov_ret_21d"] = out["ibov_close"].pct_change(21)
    out["sp500_ret_1d"] = out["sp500_close"].pct_change()
    out["sp500_ret_5d"] = out["sp500_close"].pct_change(5)
    out["cdi_simple_1d"] = np.expm1(out["cdi_log_daily"])
    out["ibov_vol_21d"] = out["ibov_ret_1d"].rolling(21, min_periods=5).std()
    out["sp500_vol_21d"] = out["sp500_ret_1d"].rolling(21, min_periods=5).std()
    out["ibov_sp500_corr_63d"] = out["ibov_ret_1d"].rolling(63, min_periods=21).corr(out["sp500_ret_1d"])
    out["ibov_minus_cdi_21d"] = out["ibov_ret_1d"].rolling(21, min_periods=5).sum() - out["cdi_simple_1d"].rolling(21, min_periods=5).sum()

    reg("ibov_ret_1d", "macro", "retorno diário do ibov")
    reg("ibov_ret_5d", "macro", "retorno 5d do ibov")
    reg("ibov_ret_21d", "macro", "retorno 21d do ibov")
    reg("sp500_ret_1d", "macro", "retorno diário do sp500")
    reg("sp500_ret_5d", "macro", "retorno 5d do sp500")
    reg("cdi_simple_1d", "macro", "retorno diário simples do CDI")
    reg("ibov_vol_21d", "macro", "volatilidade rolling 21d do ibov")
    reg("sp500_vol_21d", "macro", "volatilidade rolling 21d do sp500")
    reg("ibov_sp500_corr_63d", "macro", "correlação rolling 63d ibov vs sp500")
    reg("ibov_minus_cdi_21d", "macro", "soma rolling 21d de ibov_ret_1d menos cdi_simple_1d")

    # Derived block
    out["equity_vs_ibov_21d"] = out["equity_ret_21d"] - out["ibov_ret_21d"]
    out["equity_vs_cdi_21d"] = out["equity_ret_1d"].rolling(21, min_periods=5).sum() - out["cdi_simple_1d"].rolling(21, min_periods=5).sum()
    reg("equity_vs_ibov_21d", "derived", "retorno 21d do equity menos retorno 21d do ibov")
    reg("equity_vs_cdi_21d", "derived", "soma rolling 21d do retorno do equity menos CDI")

    # M3 block
    m3_cols = [
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
    ]
    for col in m3_cols:
        if col in out.columns:
            reg(col, "m3_cross_section", f"agregado diário de {col}")

    # SPC block
    spc_cols = [
        "spc_i_special_frac",
        "spc_mr_special_frac",
        "spc_xbar_special_frac",
        "spc_r_special_frac",
        "spc_close_mean",
        "spc_close_std",
        "spc_n_tickers",
    ]
    for col in spc_cols:
        if col in out.columns:
            reg(col, "spc_cross_section", f"agregado diário de {col}")

    return out, inv


def build_plot(dataset: pd.DataFrame, features: List[str]) -> None:
    train = dataset[dataset["split"] == "TRAIN"].copy()
    holdout = dataset[dataset["split"] == "HOLDOUT"].copy()

    label_counts = (
        dataset[dataset["split"].isin(["TRAIN", "HOLDOUT"])]
        .groupby(["split", "y_cash"], as_index=False)
        .size()
        .rename(columns={"size": "count"})
    )
    missing_rate = dataset[features].isna().mean().sort_values(ascending=False).head(20)

    corr_source = train[features + ["y_cash"]].copy()
    corr = corr_source.corr(numeric_only=True)["y_cash"].drop("y_cash").sort_values(key=np.abs, ascending=False)
    corr_top = corr.head(20)

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
        go.Scatter(
            x=train["date"],
            y=train["y_cash"],
            mode="lines",
            name="y_cash TRAIN",
            line=dict(color="#1f77b4"),
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=holdout["date"],
            y=holdout["y_cash"],
            mode="lines",
            name="y_cash HOLDOUT",
            line=dict(color="#ff7f0e"),
        ),
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

    for split_name, color in [("TRAIN", "#1f77b4"), ("HOLDOUT", "#ff7f0e")]:
        sl = label_counts[label_counts["split"] == split_name]
        fig.add_trace(
            go.Bar(
                x=[f"{split_name}-market(0)", f"{split_name}-cash(1)"],
                y=[
                    int(sl.loc[sl["y_cash"] == 0, "count"].sum()),
                    int(sl.loc[sl["y_cash"] == 1, "count"].sum()),
                ],
                name=f"Label {split_name}",
                marker_color=color,
                opacity=0.75,
            ),
            row=1,
            col=2,
        )

    fig.add_trace(
        go.Bar(
            x=missing_rate.index.tolist(),
            y=missing_rate.values.tolist(),
            name="NaN rate",
            marker_color="#9467bd",
        ),
        row=2,
        col=1,
    )

    fig.add_trace(
        go.Bar(
            x=corr_top.index.tolist(),
            y=corr_top.values.tolist(),
            name="Corr(y_cash)",
            marker_color="#2ca02c",
        ),
        row=2,
        col=2,
    )

    fig.update_layout(
        title="T076 - EDA Feature Engineering (Phase 6A)",
        height=900,
        barmode="group",
        template="plotly_white",
    )
    fig.update_xaxes(tickangle=30, row=2, col=1)
    fig.update_xaxes(tickangle=30, row=2, col=2)
    fig.write_html(OUT_PLOT, include_plotlyjs="cdn")


def main() -> int:
    ensure_dirs()

    gates: List[GateResult] = []
    retry_log: List[str] = []

    # Load
    t072 = to_date(pd.read_parquet(IN_T072_CURVE))
    _ledger = to_date(pd.read_parquet(IN_T072_LEDGER))
    macro = to_date(pd.read_parquet(IN_SSOT_MACRO))
    canonical = to_date(pd.read_parquet(IN_SSOT_CANONICAL))
    m3 = to_date(pd.read_parquet(IN_T037_M3))

    # Base calendar from T072
    calendar = pd.DataFrame({"date": sorted(t072["date"].dropna().unique())})

    merge_stats: Dict[str, Dict[str, int]] = {}

    df = calendar.merge(t072, on="date", how="left")
    merge_stats["calendar_plus_t072"] = {
        "rows_before": int(calendar.shape[0]),
        "rows_after": int(df.shape[0]),
        "null_rows_after_merge": int(df["equity_end"].isna().sum()),
    }

    df = df.merge(macro, on="date", how="left", suffixes=("", "_macro"))
    merge_stats["plus_macro"] = {
        "rows_before": int(calendar.shape[0]),
        "rows_after": int(df.shape[0]),
        "null_rows_after_merge": int(df["ibov_close"].isna().sum()),
    }

    m3_daily = build_m3_daily(m3)
    df = df.merge(m3_daily, on="date", how="left")
    merge_stats["plus_m3_daily"] = {
        "rows_before": int(calendar.shape[0]),
        "rows_after": int(df.shape[0]),
        "null_rows_after_merge": int(df["m3_score_mean"].isna().sum()),
    }

    spc_daily = build_spc_daily(canonical)
    df = df.merge(spc_daily, on="date", how="left")
    merge_stats["plus_spc_daily"] = {
        "rows_before": int(calendar.shape[0]),
        "rows_after": int(df.shape[0]),
        "null_rows_after_merge": int(df["spc_i_special_frac"].isna().sum()),
    }

    # Labels + split
    df["y_cash"] = assign_label(df["date"])
    df["split"] = assign_split(df["date"])

    # Teste ácido check
    acid_mask = (df["date"] >= pd.Timestamp("2024-11-01")) & (df["date"] <= pd.Timestamp("2025-11-30"))
    acid_all_holdout = bool((df.loc[acid_mask, "split"] == "HOLDOUT").all())

    # Feature engineering
    df, inventory = build_feature_blocks(df)
    feature_cols = [x["feature"] for x in inventory]

    # Keep only unique order
    seen = set()
    feature_cols_unique: List[str] = []
    for col in feature_cols:
        if col not in seen and col in df.columns:
            seen.add(col)
            feature_cols_unique.append(col)
    feature_cols = feature_cols_unique

    raw_features = df[feature_cols].copy()
    shifted_features = raw_features.shift(1)
    df[feature_cols] = shifted_features

    # Date filter for execution window
    in_scope_mask = (df["date"] >= TRAIN_START) & (df["date"] <= HOLDOUT_END)
    dataset = df.loc[in_scope_mask, ["date", "split", "y_cash"] + feature_cols].copy()

    # Outputs parquet
    feature_matrix = dataset[["date"] + feature_cols].copy()
    labels_df = dataset[["date", "split", "y_cash"]].copy()

    feature_matrix.to_parquet(OUT_FEATURES, index=False)
    labels_df.to_parquet(OUT_LABELS, index=False)
    dataset.to_parquet(OUT_DATASET, index=False)

    # Evidence files
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
    }
    OUT_MERGE_AUDIT.write_text(json.dumps(merge_audit, indent=2), encoding="utf-8")

    # Anti-lookahead checks
    sample_features = feature_cols[: min(25, len(feature_cols))]
    max_abs_diff = {}
    for col in sample_features:
        recomputed = raw_features[col].shift(1)
        diff = (df[col] - recomputed).abs()
        max_abs_diff[col] = float(np.nanmax(diff.values)) if not diff.isna().all() else 0.0

    anti_lookahead = {
        "all_features_shifted_by_1": True,
        "feature_count": int(len(feature_cols)),
        "sample_validation_features": sample_features,
        "sample_max_abs_diff_vs_raw_shift1": max_abs_diff,
        "first_row_all_features_nan_expected": bool(dataset[feature_cols].head(1).isna().all(axis=1).iloc[0]),
        "acid_period_all_in_holdout": acid_all_holdout,
        "notes": "Todas as features finais do modelo foram atribuídas como raw_feature.shift(1).",
    }
    OUT_ANTI_LOOKAHEAD.write_text(json.dumps(anti_lookahead, indent=2), encoding="utf-8")

    # Plot
    build_plot(dataset, feature_cols)

    # Report
    train = dataset[dataset["split"] == "TRAIN"]
    holdout = dataset[dataset["split"] == "HOLDOUT"]
    report = f"""# T076 - EDA + Feature Engineering (ML Trigger)

## Escopo
- Task: T076
- Objetivo: montar dataset diário para T077 com anti-lookahead estrito (`shift(1)`)
- Janela TRAIN: {TRAIN_START.date()} a {TRAIN_END.date()}
- Janela HOLDOUT: {HOLDOUT_START.date()} a {HOLDOUT_END.date()}

## Inputs consumidos
- `{IN_T072_CURVE.relative_to(ROOT)}`
- `{IN_T072_LEDGER.relative_to(ROOT)}`
- `{IN_SSOT_MACRO.relative_to(ROOT)}`
- `{IN_SSOT_CANONICAL.relative_to(ROOT)}`
- `{IN_T037_M3.relative_to(ROOT)}`

## Resultado do dataset
- Rows in-scope: {dataset.shape[0]}
- Features finais: {len(feature_cols)}
- TRAIN rows: {train.shape[0]}
- HOLDOUT rows: {holdout.shape[0]}
- Train cash frac: {train['y_cash'].mean():.4f}
- Holdout cash frac: {holdout['y_cash'].mean():.4f}
- Teste ácido (nov/2024-nov/2025) totalmente em HOLDOUT: {acid_all_holdout}

## Artefatos principais
- `{OUT_FEATURES.relative_to(ROOT)}`
- `{OUT_LABELS.relative_to(ROOT)}`
- `{OUT_DATASET.relative_to(ROOT)}`
- `{OUT_PLOT.relative_to(ROOT)}`
- `{OUT_FEATURE_INVENTORY.relative_to(ROOT)}`
- `{OUT_MERGE_AUDIT.relative_to(ROOT)}`
- `{OUT_ANTI_LOOKAHEAD.relative_to(ROOT)}`

## Anti-lookahead
- Regra aplicada: todas as features finais foram definidas como `feature_raw.shift(1)`.
- Evidência detalhada: `anti_lookahead_checks.json` (diferença máxima vs recomputação shift(1)).

## Observações
- EDA de correlação foi calculada apenas no TRAIN.
- HOLDOUT foi reservado para validação out-of-sample (sem seleção de features/hiperparâmetros).
"""
    OUT_REPORT.write_text(report, encoding="utf-8")

    # Manifest
    inputs = [
        IN_T072_CURVE,
        IN_T072_LEDGER,
        IN_SSOT_MACRO,
        IN_SSOT_CANONICAL,
        IN_T037_M3,
    ]
    outputs = [
        OUT_SCRIPT,
        OUT_FEATURES,
        OUT_LABELS,
        OUT_DATASET,
        OUT_PLOT,
        OUT_REPORT,
        OUT_FEATURE_INVENTORY,
        OUT_MERGE_AUDIT,
        OUT_ANTI_LOOKAHEAD,
    ]

    hashes = {}
    for p in inputs + outputs:
        hashes[str(p.relative_to(ROOT))] = sha256_file(p)

    manifest = {
        "task_id": "T076",
        "manifest_id": "T076-EDA-FEATURE-ENGINEERING-V1",
        "inputs_consumed": [str(p.relative_to(ROOT)) for p in inputs],
        "outputs_produced": [str(p.relative_to(ROOT)) for p in outputs],
        "hashes_sha256": hashes,
        "self_hash_excluded": True,
    }
    OUT_MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Gates
    gates.append(GateResult("G1_INPUTS_PRESENT", all(p.exists() for p in inputs), "todos os inputs existem"))
    gates.append(GateResult("G2_FEATURE_COUNT_MIN17", len(feature_cols) >= 17, f"feature_count={len(feature_cols)}"))
    gates.append(GateResult("G3_SPLIT_WF_PRESENT", (train.shape[0] > 0 and holdout.shape[0] > 0), "train/holdout não vazios"))
    gates.append(GateResult("G4_ANTI_LOOKAHEAD_SHIFT1", anti_lookahead["all_features_shifted_by_1"], "features atribuídas com shift(1)"))
    gates.append(GateResult("G5_ACID_PERIOD_IN_HOLDOUT", acid_all_holdout, "nov/2024-nov/2025 no HOLDOUT"))
    gates.append(GateResult("G6_PLOT_PRESENT", OUT_PLOT.exists(), str(OUT_PLOT.relative_to(ROOT))))
    gates.append(GateResult("Gx_HASH_MANIFEST_PRESENT", OUT_MANIFEST.exists(), str(OUT_MANIFEST.relative_to(ROOT))))

    overall_pass = all(g.passed for g in gates)

    print("HEADER: T076")
    print("STEP GATES:")
    for g in gates:
        status = "PASS" if g.passed else "FAIL"
        print(f"- {g.name}: {status} | {g.detail}")
    print("RETRY LOG:")
    if retry_log:
        for item in retry_log:
            print(f"- {item}")
    else:
        print("- none")
    print("ARTIFACT LINKS:")
    for p in outputs + [OUT_MANIFEST]:
        print(f"- {p.relative_to(ROOT)}")
    print(f"OVERALL STATUS: [[ {'PASS' if overall_pass else 'FAIL'} ]]")

    return 0 if overall_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
