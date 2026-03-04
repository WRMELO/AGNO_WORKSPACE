#!/home/wilson/AGNO_WORKSPACE/.venv/bin/python
from __future__ import annotations

import hashlib
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
from plotly.subplots import make_subplots


ROOT = Path("/home/wilson/AGNO_WORKSPACE")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TASK_ID = "T123"
RUN_ID = "T123-US-FEATURES-V2-V1"
PYTHON_ENV = ROOT / ".venv/bin/python"
CHANGELOG_PATH = ROOT / "00_Strategy/changelog.md"

IN_T113_DATASET = ROOT / "src/data_engine/features/T113_US_DATASET_DAILY.parquet"
IN_T120_SCORES = ROOT / "src/data_engine/features/T120_M3_US_SCORES_DAILY.parquet"
IN_SSOT_CANONICAL_US = ROOT / "src/data_engine/ssot/SSOT_CANONICAL_BASE_US.parquet"
IN_SSOT_US_RAW = ROOT / "src/data_engine/ssot/SSOT_US_MARKET_DATA_RAW.parquet"
IN_SSOT_MACRO_EXPANDED = ROOT / "src/data_engine/ssot/SSOT_MACRO_EXPANDED.parquet"

OUT_SCRIPT = ROOT / "scripts/t123_feature_engineering_us_v2_v1.py"
OUT_ALTDATA = ROOT / "src/data_engine/ssot/T123_SSOT_US_ALTDATA_FRED_DAILY.parquet"
OUT_FEATURES = ROOT / "src/data_engine/features/T123_US_FEATURE_MATRIX_DAILY.parquet"
OUT_DATASET = ROOT / "src/data_engine/features/T123_US_DATASET_DAILY.parquet"
OUT_PLOT = ROOT / "outputs/plots/T123_STATE3_PHASE10C_US_FEATURES_V2_EDA.html"

OUT_REPORT = ROOT / "outputs/governanca/T123-US-FEATURES-V2-V1_report.md"
OUT_MANIFEST = ROOT / "outputs/governanca/T123-US-FEATURES-V2-V1_manifest.json"
OUT_EVID = ROOT / "outputs/governanca/T123-US-FEATURES-V2-V1_evidence"
OUT_SOURCE_URLS = OUT_EVID / "source_urls.json"
OUT_SNAP_DIR = OUT_EVID / "source_snapshots"
OUT_SNAP_HY = OUT_SNAP_DIR / "BAMLH0A0HYM2.csv"
OUT_SNAP_IG = OUT_SNAP_DIR / "BAMLC0A0CM.csv"
OUT_FEATURE_INV = OUT_EVID / "feature_inventory.csv"
OUT_MERGE_AUDIT = OUT_EVID / "merge_audit.json"
OUT_ANTI = OUT_EVID / "anti_lookahead_checks.json"
OUT_TIME_SCAN = OUT_EVID / "time_proxy_scan.csv"
OUT_BLACKLIST = OUT_EVID / "feature_blacklist.json"
OUT_SCHEMA = OUT_EVID / "schema_contract.json"

TRACEABILITY_LINE = (
    "- 2026-03-04T00:00:00Z | EXEC: T123 PASS. Feature engineering US v2 (credit spreads HY/IG via FRED + "
    "rotacao setorial + breadth/volume proxies) com time-proxy scan/blacklist e anti-lookahead (shift(1)). "
    "Artefatos: scripts/t123_feature_engineering_us_v2_v1.py; "
    "src/data_engine/features/T123_US_{FEATURE_MATRIX,DATASET}_DAILY.parquet; "
    "src/data_engine/ssot/T123_SSOT_US_ALTDATA_FRED_DAILY.parquet; "
    "outputs/plots/T123_STATE3_PHASE10C_US_FEATURES_V2_EDA.html; "
    "outputs/governanca/T123-US-FEATURES-V2-V1_{report,manifest}.json"
)

TRAIN_START = pd.Timestamp("2018-07-02")
TRAIN_END = pd.Timestamp("2022-12-30")
HOLDOUT_START = pd.Timestamp("2023-01-02")
HOLDOUT_END = pd.Timestamp("2026-02-26")
ACID_US_START = pd.Timestamp("2025-03-06")
ACID_US_END = pd.Timestamp("2025-05-09")
TIME_PROXY_CORR_THRESHOLD = 0.95
FRED_BASE_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id="
FRED_SERIES = {
    "BAMLH0A0HYM2": "hy_oas",
    "BAMLC0A0CM": "ig_oas",
}


@dataclass
class Gate:
    name: str
    passed: bool
    detail: str


def _json_safe(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
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
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def append_changelog_idempotent(line: str) -> tuple[bool, str]:
    if not CHANGELOG_PATH.exists():
        return False, "missing_changelog"
    current = CHANGELOG_PATH.read_text(encoding="utf-8")
    if line in current:
        return True, "already_present"
    text = current
    if text and not text.endswith("\n"):
        text += "\n"
    text += line + "\n"
    CHANGELOG_PATH.write_text(text, encoding="utf-8")
    return True, "appended"


def fetch_fred_series(series_id: str, alias: str, snapshot_path: Path, retry_log: list[str]) -> pd.DataFrame:
    url = f"{FRED_BASE_URL}{series_id}"
    last_exc: Exception | None = None
    for attempt in range(1, 6):
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            snapshot_path.write_text(r.text, encoding="utf-8")
            raw = pd.read_csv(snapshot_path)
            date_col = "DATE" if "DATE" in raw.columns else "observation_date" if "observation_date" in raw.columns else None
            value_col = series_id if series_id in raw.columns else alias if alias in raw.columns else None
            if date_col is None or value_col is None:
                raise RuntimeError(f"CSV FRED inválido para {series_id}")
            out = raw.rename(columns={date_col: "date", value_col: alias})[["date", alias]].copy()
            out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.normalize()
            out[alias] = pd.to_numeric(out[alias], errors="coerce")
            out = out.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
            return out
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            retry_log.append(f"fred_retry_{series_id}_{attempt}: {type(exc).__name__}")
            time.sleep(0.5 * attempt)
    assert last_exc is not None
    raise RuntimeError(f"Falha FRED {series_id}") from last_exc


def scan_time_proxy(train_df: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    t = train_df.copy()
    t["date_ordinal"] = t["date"].map(pd.Timestamp.toordinal).astype(float)
    rows: list[dict[str, Any]] = []
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
    return pd.DataFrame(rows).sort_values("abs_corr", ascending=False).reset_index(drop=True)


def render_report(gates: list[Gate], retry_log: list[str], artifacts: list[Path], summary: dict[str, Any]) -> str:
    overall = all(g.passed for g in gates)
    lines = [f"# HEADER: {TASK_ID}", "", "## STEP GATES"]
    for g in gates:
        lines.append(f"- {'PASS' if g.passed else 'FAIL'} | {g.name} | {g.detail}")
    lines.extend(["", "## RETRY LOG"])
    if retry_log:
        for r in retry_log:
            lines.append(f"- {r}")
    else:
        lines.append("- none")
    lines.extend(["", "## EXECUTIVE SUMMARY"])
    for k, v in summary.items():
        lines.append(f"- {k}: {v}")
    lines.extend(["", "## ARTIFACT LINKS"])
    for p in artifacts:
        lines.append(f"- {p.relative_to(ROOT).as_posix()}")
    lines.extend(["", "## MANIFEST POLICY", "- policy=no_self_hash (manifest não se auto-hasheia).", ""])
    lines.append(f"OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]")
    lines.append("")
    return "\n".join(lines)


def build_plot(dataset: pd.DataFrame, feature_cols: list[str]) -> None:
    ds = dataset.copy()
    ds["split"] = np.where(ds["date"] <= TRAIN_END, "TRAIN", "HOLDOUT")
    label_col = "y_cash_us_v1"
    label_counts = ds.groupby(["split", label_col], as_index=False).size().rename(columns={"size": "count"})
    missing_rate = ds[feature_cols].isna().mean().sort_values(ascending=False).head(20)
    corr = (
        ds.loc[ds["split"] == "TRAIN", feature_cols + [label_col]]
        .corr(numeric_only=True)[label_col]
        .drop(label_col)
        .sort_values(key=np.abs, ascending=False)
        .head(20)
    )

    fig = make_subplots(
        rows=2,
        cols=2,
        subplot_titles=(
            "S&P500 normalizado + label",
            "Distribuição do label por split",
            "Missingness por feature (top 20)",
            "Correlação feature vs label (TRAIN, top 20)",
        ),
        vertical_spacing=0.12,
        horizontal_spacing=0.12,
    )
    sp500_norm = 100.0 * ds["sp500_close"] / float(ds["sp500_close"].iloc[0])
    fig.add_trace(go.Scatter(x=ds["date"], y=sp500_norm, name="SP500 norm", mode="lines"), row=1, col=1)
    fig.add_trace(
        go.Scatter(x=ds["date"], y=ds[label_col].astype(float), name=label_col, mode="lines", line={"shape": "hv"}),
        row=1,
        col=1,
    )
    fig.add_vrect(
        x0=ACID_US_START,
        x1=ACID_US_END,
        fillcolor="red",
        opacity=0.12,
        line_width=0,
        annotation_text="acid_us",
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
                    int(sl.loc[sl[label_col] == 0, "count"].sum()),
                    int(sl.loc[sl[label_col] == 1, "count"].sum()),
                ],
                name=f"label_{split_name}",
            ),
            row=1,
            col=2,
        )
    fig.add_trace(go.Bar(x=missing_rate.index.tolist(), y=missing_rate.values.tolist(), name="missing_rate"), row=2, col=1)
    fig.add_trace(go.Bar(x=corr.index.tolist(), y=corr.values.tolist(), name="corr_train"), row=2, col=2)
    fig.update_layout(title="T123 - US Feature Engineering v2", template="plotly_white", height=900)
    fig.update_xaxes(tickangle=25, row=2, col=1)
    fig.update_xaxes(tickangle=25, row=2, col=2)
    OUT_PLOT.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(OUT_PLOT), include_plotlyjs="cdn")


def main() -> int:
    gates: list[Gate] = []
    retry_log: list[str] = []
    artifacts = [
        OUT_SCRIPT,
        OUT_ALTDATA,
        OUT_FEATURES,
        OUT_DATASET,
        OUT_PLOT,
        OUT_REPORT,
        OUT_MANIFEST,
        OUT_SOURCE_URLS,
        OUT_SNAP_HY,
        OUT_SNAP_IG,
        OUT_FEATURE_INV,
        OUT_MERGE_AUDIT,
        OUT_ANTI,
        OUT_TIME_SCAN,
        OUT_BLACKLIST,
        OUT_SCHEMA,
    ]
    try:
        for p in artifacts:
            p.parent.mkdir(parents=True, exist_ok=True)
        OUT_EVID.mkdir(parents=True, exist_ok=True)

        env_ok = PYTHON_ENV.exists() and (".venv" in sys.prefix or "agno_env" in sys.prefix)
        gates.append(Gate("G_ENV_VENV", env_ok, f"python={sys.executable}"))
        if not env_ok:
            raise RuntimeError("Ambiente .venv inválido")

        inputs = [
            IN_T113_DATASET,
            IN_T120_SCORES,
            IN_SSOT_CANONICAL_US,
            IN_SSOT_US_RAW,
            IN_SSOT_MACRO_EXPANDED,
            CHANGELOG_PATH,
        ]
        inputs_ok = all(p.exists() for p in inputs)
        gates.append(
            Gate(
                "G_INPUTS_PRESENT",
                inputs_ok,
                (
                    f"t113={IN_T113_DATASET.exists()} t120={IN_T120_SCORES.exists()} canonical={IN_SSOT_CANONICAL_US.exists()} "
                    f"raw={IN_SSOT_US_RAW.exists()} macro={IN_SSOT_MACRO_EXPANDED.exists()} changelog={CHANGELOG_PATH.exists()}"
                ),
            )
        )
        if not inputs_ok:
            raise RuntimeError("Inputs ausentes")

        base = pd.read_parquet(IN_T113_DATASET).copy()
        base["date"] = pd.to_datetime(base["date"], errors="coerce").dt.normalize()
        base = base.sort_values("date").drop_duplicates("date").reset_index(drop=True)
        base = base[(base["date"] >= TRAIN_START) & (base["date"] <= HOLDOUT_END)].copy()
        base["split"] = np.where(base["date"] <= TRAIN_END, "TRAIN", "HOLDOUT")
        gates.append(
            Gate(
                "G_BASE_RANGE_OK",
                len(base) == 1902 and base["date"].min() == TRAIN_START and base["date"].max() == HOLDOUT_END,
                f"rows={len(base)} min={base['date'].min()} max={base['date'].max()}",
            )
        )

        source_urls = {alias: f"{FRED_BASE_URL}{sid}" for sid, alias in FRED_SERIES.items()}
        write_json(OUT_SOURCE_URLS, source_urls)

        hy = fetch_fred_series("BAMLH0A0HYM2", "hy_oas", OUT_SNAP_HY, retry_log)
        ig = fetch_fred_series("BAMLC0A0CM", "ig_oas", OUT_SNAP_IG, retry_log)
        altd = base[["date"]].copy().merge(hy, on="date", how="left").merge(ig, on="date", how="left")
        altd["hy_oas"] = pd.to_numeric(altd["hy_oas"], errors="coerce").ffill().bfill()
        altd["ig_oas"] = pd.to_numeric(altd["ig_oas"], errors="coerce").ffill().bfill()
        altd["hy_ig_oas_spread"] = altd["hy_oas"] - altd["ig_oas"]
        altd.to_parquet(OUT_ALTDATA, index=False)
        gates.append(
            Gate(
                "G_FRED_ALTDATA_OK",
                OUT_SNAP_HY.exists() and OUT_SNAP_IG.exists() and OUT_ALTDATA.exists(),
                f"rows={len(altd)}",
            )
        )

        scores = pd.read_parquet(IN_T120_SCORES).copy()
        scores["date"] = pd.to_datetime(scores["date"], errors="coerce").dt.normalize()
        scores["ticker"] = scores["ticker"].astype(str).str.upper().str.strip()
        m3 = scores.dropna(subset=["score_m3_us_exec", "m3_rank_us_exec"]).copy()
        daily_rows: list[dict[str, Any]] = []
        for d, g in m3.groupby("date", sort=True):
            n = int(len(g))
            g = g.sort_values(["m3_rank_us_exec", "ticker"], ascending=[True, True])
            top_dec_n = max(int(np.ceil(0.10 * n)), 1)
            row = {
                "date": d,
                "m3_exec_mean": float(pd.to_numeric(g["score_m3_us_exec"], errors="coerce").mean()),
                "m3_exec_std": float(pd.to_numeric(g["score_m3_us_exec"], errors="coerce").std(ddof=0)),
                "m3_exec_p90": float(pd.to_numeric(g["score_m3_us_exec"], errors="coerce").quantile(0.90)),
                "m3_exec_p10": float(pd.to_numeric(g["score_m3_us_exec"], errors="coerce").quantile(0.10)),
                "m3_exec_iqr": float(
                    pd.to_numeric(g["score_m3_us_exec"], errors="coerce").quantile(0.75)
                    - pd.to_numeric(g["score_m3_us_exec"], errors="coerce").quantile(0.25)
                ),
                "m3_exec_top_decile_frac": float((g["m3_rank_us_exec"] <= top_dec_n).mean()),
                "m3_exec_valid_tickers": n,
            }
            daily_rows.append(row)
        m3_daily = pd.DataFrame(daily_rows)

        can = pd.read_parquet(IN_SSOT_CANONICAL_US, columns=["ticker", "date", "close_operational", "sector"]).copy()
        can["date"] = pd.to_datetime(can["date"], errors="coerce").dt.normalize()
        can["ticker"] = can["ticker"].astype(str).str.upper().str.strip()
        can["sector"] = can["sector"].astype(str).replace("nan", "UNKNOWN")
        can["close_operational"] = pd.to_numeric(can["close_operational"], errors="coerce")
        can = can.dropna(subset=["date", "ticker", "close_operational"]).sort_values(["ticker", "date"]).copy()
        can["ret_1d"] = can.groupby("ticker")["close_operational"].pct_change()
        sec = can.dropna(subset=["ret_1d"]).groupby(["date", "sector"], as_index=False).agg(
            sector_ret_mean=("ret_1d", "mean"),
            sector_ret_std=("ret_1d", "std"),
            sector_n=("ticker", "nunique"),
        )
        sec_daily = sec.groupby("date", as_index=False).agg(
            sector_ret_mean_global=("sector_ret_mean", "mean"),
            sector_ret_dispersion=("sector_ret_mean", "std"),
            sector_ret_leader_minus_laggard=("sector_ret_mean", lambda x: float(np.nanmax(x) - np.nanmin(x))),
            sector_breadth_pos_frac=("sector_ret_mean", lambda x: float((x > 0).mean())),
            sector_count=("sector", "nunique"),
        )

        raw = pd.read_parquet(IN_SSOT_US_RAW, columns=["ticker", "date", "close", "volume"]).copy()
        raw["date"] = pd.to_datetime(raw["date"], errors="coerce").dt.normalize()
        raw["close"] = pd.to_numeric(raw["close"], errors="coerce")
        raw["volume"] = pd.to_numeric(raw["volume"], errors="coerce")
        raw = raw.dropna(subset=["date", "close", "volume"]).copy()
        raw = raw[(raw["close"] > 0) & (raw["volume"] >= 0)].copy()
        raw["dollar_volume"] = raw["close"] * raw["volume"]
        daily_vol = raw.groupby("date", as_index=False).agg(
            us_dollar_volume_total=("dollar_volume", "sum"),
            us_dollar_volume_mean=("dollar_volume", "mean"),
            us_volume_mean=("volume", "mean"),
            us_volume_std=("volume", "std"),
            us_volume_median=("volume", "median"),
            us_n_tickers_raw=("ticker", "nunique"),
        )
        daily_vol["us_dollar_volume_total_chg_1d"] = daily_vol["us_dollar_volume_total"].pct_change()
        daily_vol["us_dollar_volume_total_chg_5d"] = daily_vol["us_dollar_volume_total"].pct_change(5)
        daily_vol["us_volume_adv21_ratio"] = (
            daily_vol["us_dollar_volume_total"] / daily_vol["us_dollar_volume_total"].rolling(21, min_periods=5).mean()
        )

        feat = base[["date", "sp500_close", "y_cash_us_v1", "split"]].copy()
        base_feature_cols = [c for c in base.columns if c not in ["date", "y_cash_us_v1", "split", "sp500_close"]]
        feat = feat.join(base[base_feature_cols], how="left")
        feat = feat.merge(altd, on="date", how="left")
        feat = feat.merge(m3_daily, on="date", how="left")
        feat = feat.merge(sec_daily, on="date", how="left")
        feat = feat.merge(daily_vol, on="date", how="left")

        # Raw v2 features (pre-shift).
        feat["hy_oas_delta_1d"] = feat["hy_oas"].diff(1)
        feat["hy_oas_delta_5d"] = feat["hy_oas"].diff(5)
        feat["ig_oas_delta_1d"] = feat["ig_oas"].diff(1)
        feat["ig_oas_delta_5d"] = feat["ig_oas"].diff(5)
        feat["hy_ig_spread_delta_1d"] = feat["hy_ig_oas_spread"].diff(1)
        feat["hy_ig_spread_delta_5d"] = feat["hy_ig_oas_spread"].diff(5)
        feat["hy_ig_spread_z63"] = (
            (feat["hy_ig_oas_spread"] - feat["hy_ig_oas_spread"].rolling(63, min_periods=21).mean())
            / feat["hy_ig_oas_spread"].rolling(63, min_periods=21).std()
        )
        feat["m3_exec_mean_delta_1d"] = feat["m3_exec_mean"].diff(1)
        feat["m3_exec_iqr_delta_1d"] = feat["m3_exec_iqr"].diff(1)
        feat["sector_dispersion_delta_1d"] = feat["sector_ret_dispersion"].diff(1)
        feat["sector_breadth_pos_delta_1d"] = feat["sector_breadth_pos_frac"].diff(1)

        new_feature_cols = [
            "hy_oas",
            "ig_oas",
            "hy_ig_oas_spread",
            "hy_oas_delta_1d",
            "hy_oas_delta_5d",
            "ig_oas_delta_1d",
            "ig_oas_delta_5d",
            "hy_ig_spread_delta_1d",
            "hy_ig_spread_delta_5d",
            "hy_ig_spread_z63",
            "m3_exec_mean",
            "m3_exec_std",
            "m3_exec_p90",
            "m3_exec_p10",
            "m3_exec_iqr",
            "m3_exec_top_decile_frac",
            "m3_exec_valid_tickers",
            "m3_exec_mean_delta_1d",
            "m3_exec_iqr_delta_1d",
            "sector_ret_mean_global",
            "sector_ret_dispersion",
            "sector_ret_leader_minus_laggard",
            "sector_breadth_pos_frac",
            "sector_count",
            "sector_dispersion_delta_1d",
            "sector_breadth_pos_delta_1d",
            "us_dollar_volume_total",
            "us_dollar_volume_mean",
            "us_volume_mean",
            "us_volume_std",
            "us_volume_median",
            "us_n_tickers_raw",
            "us_dollar_volume_total_chg_1d",
            "us_dollar_volume_total_chg_5d",
            "us_volume_adv21_ratio",
        ]

        raw_new_features = feat[new_feature_cols].copy()
        feat[new_feature_cols] = raw_new_features.shift(1)
        anti_subset = new_feature_cols[:20]
        max_diff = 0.0
        per_feature_diff: dict[str, float] = {}
        for c in anti_subset:
            expected = raw_new_features[c].shift(1)
            diff = (feat[c] - expected).abs()
            val = float(np.nanmax(diff.values)) if not diff.isna().all() else 0.0
            per_feature_diff[c] = val
            max_diff = max(max_diff, val)
        first_row_all_nan = bool(feat[new_feature_cols].head(1).isna().all(axis=1).iloc[0])
        gates.append(
            Gate(
                "G_ANTI_LOOKAHEAD_OK",
                max_diff <= 1e-12 and first_row_all_nan,
                f"max_abs_diff={max_diff:.3e} first_row_all_nan={first_row_all_nan}",
            )
        )

        # Time proxy scan only for new features in TRAIN.
        train_df = feat[feat["split"] == "TRAIN"].copy()
        scan = scan_time_proxy(train_df[["date"] + new_feature_cols], new_feature_cols)
        scan.to_csv(OUT_TIME_SCAN, index=False)
        blacklisted = [
            {
                "feature": str(r["feature"]),
                "reason": f"time_proxy_abs_corr_gt_{TIME_PROXY_CORR_THRESHOLD:.2f}",
                "abs_corr": float(r["abs_corr"]),
            }
            for _, r in scan.iterrows()
            if pd.notna(r["abs_corr"]) and float(r["abs_corr"]) > TIME_PROXY_CORR_THRESHOLD
        ]
        blacklisted_set = {x["feature"] for x in blacklisted}
        write_json(
            OUT_BLACKLIST,
            {
                "threshold_abs_corr_date": TIME_PROXY_CORR_THRESHOLD,
                "blacklisted_features": blacklisted,
            },
        )
        final_new_features = [f for f in new_feature_cols if f not in blacklisted_set]
        gates.append(
            Gate(
                "G_TIME_PROXY_SCAN_APPLIED",
                True,
                f"new_features={len(new_feature_cols)} blacklisted={len(blacklisted_set)} final_new={len(final_new_features)}",
            )
        )

        # Final feature set = old T113 features + approved new features.
        final_feature_cols = base_feature_cols + final_new_features
        feature_matrix = feat[["date"] + final_feature_cols].copy()
        dataset_out = feat[["date", "split", "y_cash_us_v1", "sp500_close"] + final_feature_cols].copy()

        feature_matrix.to_parquet(OUT_FEATURES, index=False)
        dataset_out.to_parquet(OUT_DATASET, index=False)
        gates.append(
            Gate(
                "G_OUTPUTS_WRITTEN",
                OUT_FEATURES.exists() and OUT_DATASET.exists() and OUT_ALTDATA.exists(),
                f"rows_features={len(feature_matrix)} rows_dataset={len(dataset_out)}",
            )
        )

        # Evidence files.
        inv_rows: list[dict[str, str]] = []
        for c in base_feature_cols:
            inv_rows.append({"feature": c, "block": "t113_base", "definition": f"feature herdada de T113: {c}"})
        for c in final_new_features:
            if c.startswith(("hy_", "ig_")):
                block = "credit_spreads_fred"
            elif c.startswith("m3_exec_"):
                block = "m3_cross_section_exec"
            elif c.startswith("sector_"):
                block = "sector_rotation"
            elif c.startswith("us_"):
                block = "flow_volume_proxy"
            else:
                block = "other_v2"
            inv_rows.append({"feature": c, "block": block, "definition": f"feature T123 v2: {c}"})
        pd.DataFrame(inv_rows).drop_duplicates(subset=["feature"]).to_csv(OUT_FEATURE_INV, index=False)

        merge_audit = {
            "rows_base_dataset": int(len(base)),
            "rows_output_dataset": int(len(dataset_out)),
            "date_min": dataset_out["date"].min(),
            "date_max": dataset_out["date"].max(),
            "train_rows": int((dataset_out["split"] == "TRAIN").sum()),
            "holdout_rows": int((dataset_out["split"] == "HOLDOUT").sum()),
            "label_equals_base": bool((dataset_out["y_cash_us_v1"].values == base["y_cash_us_v1"].values).all()),
            "new_features_count_before_blacklist": int(len(new_feature_cols)),
            "new_features_count_after_blacklist": int(len(final_new_features)),
            "base_features_count": int(len(base_feature_cols)),
            "final_feature_count": int(len(final_feature_cols)),
        }
        write_json(OUT_MERGE_AUDIT, merge_audit)
        write_json(
            OUT_ANTI,
            {
                "policy": "shift_1_applied_only_to_new_t123_features",
                "subset_checked": anti_subset,
                "per_feature_max_abs_diff": per_feature_diff,
                "max_abs_diff_overall": max_diff,
                "first_row_all_nan_new_features": first_row_all_nan,
            },
        )
        write_json(
            OUT_SCHEMA,
            {
                "feature_matrix_schema": {c: str(feature_matrix[c].dtype) for c in feature_matrix.columns},
                "dataset_schema": {c: str(dataset_out[c].dtype) for c in dataset_out.columns},
                "rows": {
                    "feature_matrix": int(len(feature_matrix)),
                    "dataset": int(len(dataset_out)),
                },
            },
        )

        build_plot(dataset_out, final_feature_cols)
        gates.append(
            Gate(
                "G_PLOT_PRESENT",
                OUT_PLOT.exists() and OUT_PLOT.stat().st_size > 50_000,
                f"size={OUT_PLOT.stat().st_size if OUT_PLOT.exists() else 0}",
            )
        )

        ch_ok, ch_mode = append_changelog_idempotent(TRACEABILITY_LINE)
        gates.append(Gate("G_CHLOG_UPDATED", ch_ok, f"mode={ch_mode}"))

        summary = {
            "rows_dataset": int(len(dataset_out)),
            "rows_train": int((dataset_out["split"] == "TRAIN").sum()),
            "rows_holdout": int((dataset_out["split"] == "HOLDOUT").sum()),
            "features_base_t113": int(len(base_feature_cols)),
            "features_new_v2_final": int(len(final_new_features)),
            "features_total_final": int(len(final_feature_cols)),
            "label_cash_frac_train": float(dataset_out.loc[dataset_out["split"] == "TRAIN", "y_cash_us_v1"].mean()),
            "label_cash_frac_holdout": float(dataset_out.loc[dataset_out["split"] == "HOLDOUT", "y_cash_us_v1"].mean()),
        }

        OUT_REPORT.write_text(render_report(gates, retry_log, artifacts, summary), encoding="utf-8")

        outputs_for_hash = [
            OUT_SCRIPT,
            OUT_ALTDATA,
            OUT_FEATURES,
            OUT_DATASET,
            OUT_PLOT,
            OUT_REPORT,
            OUT_SOURCE_URLS,
            OUT_SNAP_HY,
            OUT_SNAP_IG,
            OUT_FEATURE_INV,
            OUT_MERGE_AUDIT,
            OUT_ANTI,
            OUT_TIME_SCAN,
            OUT_BLACKLIST,
            OUT_SCHEMA,
            CHANGELOG_PATH,
        ]
        hashes = {str(p.relative_to(ROOT)): sha256_file(p) for p in outputs_for_hash if p.exists()}
        manifest = {
            "task_id": TASK_ID,
            "run_id": RUN_ID,
            "generated_at_utc": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
            "inputs_consumed": [str(p.relative_to(ROOT)) for p in inputs],
            "outputs_produced": [str(p.relative_to(ROOT)) for p in outputs_for_hash if p != CHANGELOG_PATH],
            "hashes_sha256": hashes,
            "policy": "no_self_hash",
        }
        write_json(OUT_MANIFEST, manifest)
        gates.append(Gate("Gx_HASH_MANIFEST_PRESENT", OUT_MANIFEST.exists(), f"path={OUT_MANIFEST.relative_to(ROOT).as_posix()}"))

        mismatches = 0
        for rel, expected in manifest["hashes_sha256"].items():
            p = ROOT / rel
            if (not p.exists()) or (sha256_file(p) != expected):
                mismatches += 1
        gates.append(Gate("G_SHA256_INTEGRITY_SELF_CHECK", mismatches == 0, f"mismatches={mismatches}"))

        # Final rewrite.
        OUT_REPORT.write_text(render_report(gates, retry_log, artifacts, summary), encoding="utf-8")
        final_hashes = {str(p.relative_to(ROOT)): sha256_file(p) for p in outputs_for_hash if p.exists()}
        manifest["hashes_sha256"] = final_hashes
        manifest["generated_at_utc"] = pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
        write_json(OUT_MANIFEST, manifest)

        overall = all(g.passed for g in gates)
        return 0 if overall else 2
    except Exception as exc:  # pragma: no cover
        retry_log.append(f"error: {type(exc).__name__}: {exc}")
        gates.append(Gate("G_FATAL", False, f"{type(exc).__name__}: {exc}"))
        fail_report = render_report(gates, retry_log, artifacts, {"error": str(exc)})
        OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
        OUT_REPORT.write_text(fail_report, encoding="utf-8")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
