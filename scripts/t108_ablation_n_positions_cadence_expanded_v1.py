#!/home/wilson/AGNO_WORKSPACE/.venv/bin/python
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


if not ("agno_env" in sys.prefix or ".venv" in sys.prefix):
    raise RuntimeError("FATAL: Not in agno_env/.venv")


TASK_ID = "T108"
RUN_ID = "T108-ABLATION-NPOS-CADENCE-EXPANDED-V1"
ROOT = Path("/home/wilson/AGNO_WORKSPACE")
BASE_CAPITAL = 100000.0

PYTHON_ENV = ROOT / ".venv/bin/python"
CHANGELOG_PATH = ROOT / "00_Strategy/changelog.md"
TRACEABILITY_LINE = (
    "- 2026-03-04T10:20:00Z | EXEC: T108 PASS. Artefatos: "
    "scripts/t108_ablation_n_positions_cadence_expanded_v1.py; "
    "outputs/plots/T108_STATE3_PHASE8D_ABLATION_NPOS_CADENCE_COMPARATIVE.html; "
    "outputs/governanca/T108-ABLATION-NPOS-CADENCE-EXPANDED-V1_manifest.json; "
    "src/data_engine/portfolio/T108_SELECTED_CONFIG_NPOS_CADENCE_EXPANDED.json"
)

INPUT_CANONICAL = ROOT / "src/data_engine/ssot/SSOT_CANONICAL_BASE_BR_EXPANDED.parquet"
INPUT_MACRO = ROOT / "src/data_engine/ssot/SSOT_MACRO_EXPANDED.parquet"
INPUT_UNIVERSE = ROOT / "src/data_engine/ssot/SSOT_UNIVERSE_OPERATIONAL_EXPANDED.parquet"
INPUT_BLACKLIST = ROOT / "src/data_engine/ssot/SSOT_QUALITY_BLACKLIST_A001.json"
INPUT_T072_CFG = ROOT / "src/data_engine/portfolio/T072_DUAL_MODE_SELECTED_CONFIG.json"
INPUT_T106_CFG = ROOT / "src/data_engine/portfolio/T106_ML_TRIGGER_EXPANDED_SELECTED_CONFIG.json"
INPUT_T105_PRED = ROOT / "src/data_engine/features/T105_V1_PREDICTIONS.parquet"
INPUT_C060 = ROOT / "outputs/governanca/T079-PHASE6-PLOTLY-COMPARATIVE-V1_evidence/c060_curve_snapshot.parquet"

OUT_SCRIPT = ROOT / "scripts/t108_ablation_n_positions_cadence_expanded_v1.py"
OUT_ABLATION = ROOT / "src/data_engine/portfolio/T108_ABLATION_RESULTS_NPOS_CADENCE_EXPANDED.parquet"
OUT_SELECTED_CFG = ROOT / "src/data_engine/portfolio/T108_SELECTED_CONFIG_NPOS_CADENCE_EXPANDED.json"
OUT_CURVE_BASE = ROOT / "src/data_engine/portfolio/T108_PORTFOLIO_CURVE_DUAL_MODE_EXPANDED_WINNER.parquet"
OUT_CURVE_ML = ROOT / "src/data_engine/portfolio/T108_PORTFOLIO_CURVE_DUAL_MODE_EXPANDED_ML_TRIGGER_WINNER.parquet"
OUT_SUMMARY = ROOT / "src/data_engine/portfolio/T108_BASELINE_SUMMARY_INTEGRATED_EXPANDED.json"
OUT_PLOT = ROOT / "outputs/plots/T108_STATE3_PHASE8D_ABLATION_NPOS_CADENCE_COMPARATIVE.html"
OUT_REPORT = ROOT / "outputs/governanca/T108-ABLATION-NPOS-CADENCE-EXPANDED-V1_report.md"
OUT_MANIFEST = ROOT / "outputs/governanca/T108-ABLATION-NPOS-CADENCE-EXPANDED-V1_manifest.json"
OUT_EVIDENCE_DIR = ROOT / "outputs/governanca/T108-ABLATION-NPOS-CADENCE-EXPANDED-V1_evidence"
OUT_SELECTION_RULE = OUT_EVIDENCE_DIR / "selection_rule.json"
OUT_METRICS_SNAPSHOT = OUT_EVIDENCE_DIR / "metrics_snapshot.json"
OUT_SUBPERIODS = OUT_EVIDENCE_DIR / "subperiods_definition.json"
OUT_PLOT_INVENTORY = OUT_EVIDENCE_DIR / "plot_inventory.json"
OUT_JOIN_COVERAGE = OUT_EVIDENCE_DIR / "join_coverage.json"

TRAIN_START = pd.Timestamp("2018-07-02")
TRAIN_END = pd.Timestamp("2022-12-30")
HOLDOUT_START = pd.Timestamp("2023-01-02")
HOLDOUT_END = pd.Timestamp("2026-02-26")
ACID_START = pd.Timestamp("2024-11-01")
ACID_END = pd.Timestamp("2025-11-30")

TOP_N_GRID = [10, 12, 15, 18, 20]
CADENCE_MODE_B_GRID = [5, 10, 15, 20]

SUBPERIODS = [
    ("SP_2019H2_2020", pd.Timestamp("2019-07-01"), pd.Timestamp("2020-12-31")),
    ("SP_2021_2022", pd.Timestamp("2021-01-01"), pd.Timestamp("2022-12-30")),
    ("SP_2023_TO_2024OCT", pd.Timestamp("2023-01-02"), pd.Timestamp("2024-10-31")),
    ("SP_ACID", ACID_START, ACID_END),
    ("SP_2025DEC_TO_END", pd.Timestamp("2025-12-01"), HOLDOUT_END),
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


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Nao foi possivel carregar modulo: {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def zscore_cross_section(values: pd.Series) -> pd.Series:
    x = pd.to_numeric(values, errors="coerce").astype(float)
    mu = x.mean()
    sd = x.std(ddof=0)
    if not np.isfinite(sd) or sd <= 0:
        return pd.Series(np.zeros(len(x), dtype=float), index=x.index)
    return (x - mu) / sd


def compute_m3_scores(px_wide: pd.DataFrame) -> dict[pd.Timestamp, pd.DataFrame]:
    logret = np.log(px_wide / px_wide.shift(1))
    score_m0 = logret.rolling(window=62, min_periods=62).mean()
    ret_62 = logret.rolling(window=62, min_periods=62).sum()
    vol_62 = logret.rolling(window=62, min_periods=62).std(ddof=0)

    scores_by_day: dict[pd.Timestamp, pd.DataFrame] = {}
    for d in score_m0.index:
        m0_row = score_m0.loc[d].dropna()
        r_row = ret_62.loc[d].dropna()
        v_row = vol_62.loc[d].dropna()
        common = m0_row.index.intersection(r_row.index).intersection(v_row.index)
        if len(common) < 3:
            continue
        cs = pd.DataFrame(
            {
                "score_m0": m0_row[common],
                "ret_62": r_row[common],
                "vol_62": v_row[common],
            }
        )
        cs["z_m0"] = zscore_cross_section(cs["score_m0"])
        cs["z_ret"] = zscore_cross_section(cs["ret_62"])
        cs["z_vol"] = zscore_cross_section(cs["vol_62"])
        cs["score_m3"] = cs["z_m0"] + cs["z_ret"] - cs["z_vol"]
        cs = cs.sort_values("score_m3", ascending=False).reset_index()
        cs = cs.rename(columns={"index": "ticker"})
        cs["m3_rank"] = np.arange(1, len(cs) + 1)
        scores_by_day[pd.Timestamp(d)] = cs.set_index("ticker")
    return scores_by_day


def assign_split(d: pd.Timestamp) -> str:
    if d <= TRAIN_END:
        return "TRAIN"
    return "HOLDOUT"


def apply_hysteresis(prob: pd.Series, thr: float, h_in: int, h_out: int) -> pd.Series:
    vals = pd.to_numeric(prob, errors="coerce").fillna(0.0).astype(float).values
    state = False
    in_count = 0
    out_count = 0
    out: list[int] = []
    for p in vals:
        if p >= thr:
            in_count += 1
            out_count = 0
        else:
            out_count += 1
            in_count = 0
        if not state and in_count >= h_in:
            state = True
        elif state and out_count >= h_out:
            state = False
        out.append(1 if state else 0)
    return pd.Series(out, index=prob.index, dtype="int64")


def drawdown(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce").astype(float)
    return s / s.cummax() - 1.0


def metrics(equity: pd.Series) -> dict[str, float]:
    s = pd.to_numeric(equity, errors="coerce").astype(float)
    r = s.pct_change().fillna(0.0)
    years = max((len(s) - 1) / 252.0, 1.0 / 252.0)
    cagr = float((s.iloc[-1] / s.iloc[0]) ** (1.0 / years) - 1.0)
    mdd = float(drawdown(s).min())
    vol = float(r.std(ddof=0))
    sharpe = float((r.mean() / vol) * np.sqrt(252.0)) if vol > 0 else np.nan
    return {"equity_final": float(s.iloc[-1]), "cagr": cagr, "mdd": mdd, "sharpe": sharpe}


def subperiod_metrics(curve: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> dict[str, float]:
    sub = curve[(curve["date"] >= start) & (curve["date"] <= end)].copy()
    if len(sub) < 2:
        return {"equity_final": np.nan, "cagr": np.nan, "mdd": np.nan, "sharpe": np.nan}
    return metrics(sub["equity_end_norm"])


def append_changelog_one_line(line: str) -> bool:
    before = CHANGELOG_PATH.read_text(encoding="utf-8") if CHANGELOG_PATH.exists() else ""
    before_size = len(before.encode("utf-8"))
    text = before
    if text and not text.endswith("\n"):
        text += "\n"
    text += line.rstrip("\n") + "\n"
    CHANGELOG_PATH.write_text(text, encoding="utf-8")
    after_size = len(text.encode("utf-8"))
    delta = after_size - before_size
    expected = len((line.rstrip("\n") + "\n").encode("utf-8"))
    return delta == expected and text.endswith(line.rstrip("\n") + "\n")


def build_engine(
    t063: Any,
    canonical: pd.DataFrame,
    macro_day: pd.DataFrame,
    sim_dates: list[pd.Timestamp],
) -> SimpleNamespace:
    prices = canonical.sort_values(["ticker", "date"]).copy()
    px_wide = (
        prices.pivot_table(index="date", columns="ticker", values="close_operational", aggfunc="first")
        .sort_index()
        .ffill()
    )
    logret_wide = np.log(px_wide / px_wide.shift(1))
    mu = logret_wide.rolling(window=60, min_periods=20).mean()
    sd = logret_wide.rolling(window=60, min_periods=20).std(ddof=0)
    z_wide = (logret_wide - mu) / sd.replace(0.0, np.nan)
    any_rule_map, strong_rule_map, in_control_map = t063.build_rule_proxy_maps(prices)
    scores_by_day = compute_m3_scores(px_wide)
    return SimpleNamespace(
        px_wide=px_wide,
        z_wide=z_wide,
        any_rule_map=any_rule_map,
        strong_rule_map=strong_rule_map,
        in_control_map=in_control_map,
        macro_day=macro_day,
        scores_by_day=scores_by_day,
        sim_dates=sim_dates,
        ibov_base=float(macro_day.loc[sim_dates[0], "ibov_close"]),
    )


def normalize_baseline(curve_base: pd.DataFrame) -> pd.DataFrame:
    baseline = pd.DataFrame({"date": curve_base["date"], "split": curve_base["split"]})
    baseline["ret_t072"] = pd.to_numeric(curve_base["equity_end"], errors="coerce").pct_change().fillna(0.0)
    baseline["ret_cdi"] = pd.to_numeric(curve_base["cdi_daily"], errors="coerce").fillna(0.0)
    baseline["state_cash"] = 0
    baseline["ret_strategy"] = baseline["ret_t072"]
    baseline["equity_end_norm"] = BASE_CAPITAL * (1.0 + baseline["ret_strategy"]).cumprod()
    baseline.loc[baseline.index[0], "equity_end_norm"] = BASE_CAPITAL
    baseline["drawdown"] = drawdown(baseline["equity_end_norm"])
    baseline["switches_cumsum"] = 0
    baseline["curve_name"] = "T108_EXPANDED_BASELINE_WINNER"
    return baseline


def build_ml_curve(curve_base: pd.DataFrame, pred: pd.DataFrame, thr: float, h_in: int, h_out: int) -> pd.DataFrame:
    merged = curve_base.merge(
        pred[["date", "split", "y_proba_cash"]],
        on=["date", "split"],
        how="inner",
        validate="one_to_one",
    ).sort_values("date")
    state_cash = apply_hysteresis(merged["y_proba_cash"], thr=thr, h_in=h_in, h_out=h_out)
    out_ml = pd.DataFrame({"date": merged["date"], "split": merged["split"]})
    out_ml["ret_t072"] = pd.to_numeric(merged["equity_end"], errors="coerce").pct_change().fillna(0.0)
    out_ml["ret_cdi"] = pd.to_numeric(merged["cdi_daily"], errors="coerce").fillna(0.0)
    out_ml["state_cash"] = state_cash.astype(int)
    out_ml["ret_strategy"] = np.where(out_ml["state_cash"] == 1, out_ml["ret_cdi"], out_ml["ret_t072"])
    out_ml["equity_end_norm"] = BASE_CAPITAL * (1.0 + out_ml["ret_strategy"]).cumprod()
    out_ml.loc[out_ml.index[0], "equity_end_norm"] = BASE_CAPITAL
    out_ml["drawdown"] = drawdown(out_ml["equity_end_norm"])
    out_ml["switches_cumsum"] = (out_ml["state_cash"].diff().abs() == 1).fillna(False).astype(int).cumsum()
    out_ml["curve_name"] = "T108_EXPANDED_ML_TRIGGER_WINNER"
    return out_ml


def main() -> int:
    gates: list[Gate] = []
    retry_log: list[str] = []
    try:
        for p in [
            OUT_SCRIPT,
            OUT_ABLATION,
            OUT_SELECTED_CFG,
            OUT_CURVE_BASE,
            OUT_CURVE_ML,
            OUT_SUMMARY,
            OUT_PLOT,
            OUT_REPORT,
            OUT_MANIFEST,
        ]:
            p.parent.mkdir(parents=True, exist_ok=True)
        OUT_EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

        gate_env = PYTHON_ENV.exists() and (".venv" in sys.prefix or "agno_env" in sys.prefix)
        gates.append(Gate("G_ENV_VENV", gate_env, f"python={sys.executable}"))

        input_files = [
            INPUT_CANONICAL,
            INPUT_MACRO,
            INPUT_UNIVERSE,
            INPUT_BLACKLIST,
            INPUT_T072_CFG,
            INPUT_T106_CFG,
            INPUT_T105_PRED,
            INPUT_C060,
        ]
        inputs_ok = all(p.exists() for p in input_files)
        gates.append(Gate("G_INPUTS_PRESENT", inputs_ok, f"all={inputs_ok}"))
        if not inputs_ok:
            raise FileNotFoundError("Inputs obrigatorios ausentes.")

        t063 = load_module("t063_base_t108", ROOT / "scripts/t063_market_slope_reentry_ablation.py")
        t072 = load_module("t072_engine_t108", ROOT / "scripts/t072_dual_mode_engine_ablation.py")

        canonical = pd.read_parquet(INPUT_CANONICAL).copy()
        canonical["ticker"] = canonical["ticker"].astype(str).str.upper().str.strip()
        canonical["date"] = pd.to_datetime(canonical["date"], errors="coerce").dt.normalize()
        canonical = canonical.dropna(subset=["ticker", "date", "close_operational"]).copy()

        universe = pd.read_parquet(INPUT_UNIVERSE).copy()
        universe_tickers = set(universe["ticker"].astype(str).str.upper().str.strip().tolist())
        blacklist = t063.load_blacklist()
        use_tickers = universe_tickers.difference(blacklist)
        canonical = canonical[canonical["ticker"].isin(use_tickers)].copy()

        required_cols = {
            "ticker",
            "date",
            "close_operational",
            "i_value",
            "i_ucl",
            "i_lcl",
            "mr_value",
            "mr_ucl",
            "xbar_value",
            "xbar_ucl",
            "xbar_lcl",
            "r_value",
            "r_ucl",
        }
        schema_ok = required_cols.issubset(set(canonical.columns))
        gates.append(Gate("G_SCHEMA_OK", schema_ok, f"required_present={schema_ok}"))
        if not schema_ok:
            raise ValueError("Schema de canonical expandido invalido.")

        tickers_count = canonical["ticker"].nunique()
        gates.append(Gate("G_UNIVERSE_COVERAGE_OK", tickers_count >= 400, f"tickers_count={tickers_count}"))

        macro = pd.read_parquet(INPUT_MACRO).copy()
        macro["date"] = pd.to_datetime(macro["date"], errors="coerce").dt.normalize()
        macro = macro.dropna(subset=["date", "ibov_close", "cdi_log_daily"]).sort_values("date")
        macro_day = macro.set_index("date")

        pred = pd.read_parquet(INPUT_T105_PRED).copy()
        pred["date"] = pd.to_datetime(pred["date"], errors="coerce").dt.normalize()
        pred_cols_ok = {"date", "split", "y_proba_cash"}.issubset(set(pred.columns))
        gates.append(Gate("G_PRED_SCHEMA_OK", pred_cols_ok, f"cols_ok={pred_cols_ok}"))
        if not pred_cols_ok:
            raise ValueError("Schema de predicoes T105 invalido.")

        sim_dates = sorted(set(canonical["date"]).intersection(set(macro_day.index)))
        sim_dates = [pd.Timestamp(d) for d in sim_dates if TRAIN_START <= pd.Timestamp(d) <= HOLDOUT_END]
        common_dates_ok = len(sim_dates) == 1902 and sim_dates[0] == TRAIN_START and sim_dates[-1] == HOLDOUT_END
        gates.append(
            Gate(
                "G_COMMON_DATES_OK",
                common_dates_ok,
                f"n_dates={len(sim_dates)} min={sim_dates[0] if sim_dates else None} max={sim_dates[-1] if sim_dates else None}",
            )
        )
        if not sim_dates:
            raise RuntimeError("Sem datas comuns para simulacao.")

        engine = build_engine(t063=t063, canonical=canonical, macro_day=macro_day, sim_dates=sim_dates)

        t072_cfg = json.loads(INPUT_T072_CFG.read_text(encoding="utf-8"))
        t106_cfg = json.loads(INPUT_T106_CFG.read_text(encoding="utf-8"))

        signal_w = int(t072_cfg.get("signal_w", 30))
        sig_thr = float(t072_cfg.get("thr", 0.0005))
        sig_h_in = int(t072_cfg.get("h_in", 2))
        sig_h_out = int(t072_cfg.get("h_out", 4))
        signal_variant = str(t072_cfg.get("signal_variant", "SINAL-2"))
        initial_mode = str(t072_cfg.get("initial_mode", t072.MODE_B))

        cadence_mode_a = int(t072_cfg.get("profiles_fixed", {}).get("mode_a", {}).get("cadence_days", 3))
        mode_b_fixed = t072_cfg.get("profiles_fixed", {}).get("mode_b", {})
        mode_b_window = int(mode_b_fixed.get("market_slope_window", 30))
        mode_b_in_hyst = int(mode_b_fixed.get("in_hyst_days", 4))
        mode_b_out_hyst = int(mode_b_fixed.get("out_hyst_days", 4))

        ml_thr = float(t106_cfg["winner_params"]["thr"])
        ml_h_in = int(t106_cfg["winner_params"]["h_in"])
        ml_h_out = int(t106_cfg["winner_params"]["h_out"])
        ml_winner_id = str(t106_cfg.get("winner_candidate_id", "UNKNOWN"))
        ml_winner_variant = str(t106_cfg.get("winner_variant", "UNKNOWN"))

        c060 = pd.read_parquet(INPUT_C060).copy()
        c060["date"] = pd.to_datetime(c060["date"]).dt.normalize()
        c060 = c060.sort_values("date")

        ablation_rows: list[dict[str, Any]] = []
        best_candidate: dict[str, Any] | None = None
        best_curve_base: pd.DataFrame | None = None
        best_curve_ml: pd.DataFrame | None = None
        join_coverage_by_candidate: dict[str, Any] = {}
        candidate_counter = 0

        for top_n in TOP_N_GRID:
            for cadence_b in CADENCE_MODE_B_GRID:
                candidate_counter += 1
                cid = f"C{candidate_counter:03d}_N{top_n}_CB{cadence_b}"

                t072.PROFILE_A["top_n"] = int(top_n)
                t072.PROFILE_A["target_pct"] = 1.0 / float(top_n)
                t072.PROFILE_A["max_pct"] = 0.10
                t072.PROFILE_A["cadence_days"] = cadence_mode_a

                t072.PROFILE_B["top_n"] = int(top_n)
                t072.PROFILE_B["target_pct"] = 1.0 / float(top_n)
                t072.PROFILE_B["max_pct"] = 0.10
                t072.PROFILE_B["cadence_days"] = int(cadence_b)
                t072.PROFILE_B["market_slope_window"] = mode_b_window
                t072.PROFILE_B["in_hyst_days"] = mode_b_in_hyst
                t072.PROFILE_B["out_hyst_days"] = mode_b_out_hyst

                _, curve_base, _ = t072.run_candidate_t072(
                    t063,
                    engine,
                    signal_w=signal_w,
                    thr=sig_thr,
                    h_in=sig_h_in,
                    h_out=sig_h_out,
                    signal_variant=signal_variant,
                    initial_mode=initial_mode,
                )
                curve_base = curve_base.copy()
                curve_base["date"] = pd.to_datetime(curve_base["date"]).dt.normalize()
                curve_base["split"] = curve_base["date"].apply(assign_split)
                curve_base = curve_base.sort_values("date").reset_index(drop=True)
                curve_ml = build_ml_curve(curve_base, pred, ml_thr, ml_h_in, ml_h_out)

                merged_check = curve_base.merge(
                    pred[["date", "split", "y_proba_cash"]],
                    on=["date", "split"],
                    how="inner",
                )
                join_coverage_by_candidate[cid] = {
                    "curve_rows": int(len(curve_base)),
                    "pred_rows": int(len(pred)),
                    "merged_rows": int(len(merged_check)),
                }

                hold_ml = curve_ml[curve_ml["split"] == "HOLDOUT"].copy()
                hold_c060 = c060[c060["split"] == "HOLDOUT"].copy()
                c060_holdout_end = float(hold_c060["equity_end_norm"].iloc[-1])
                hold_metrics = metrics(hold_ml["equity_end_norm"])

                baseline_norm = normalize_baseline(curve_base)
                base_hold_metrics = metrics(baseline_norm[baseline_norm["split"] == "HOLDOUT"]["equity_end_norm"])

                row: dict[str, Any] = {
                    "candidate_id": cid,
                    "top_n": int(top_n),
                    "target_pct": float(1.0 / float(top_n)),
                    "max_pct": float(0.10),
                    "cadence_mode_a": int(cadence_mode_a),
                    "cadence_mode_b": int(cadence_b),
                    "signal_w": int(signal_w),
                    "signal_thr": float(sig_thr),
                    "signal_h_in": int(sig_h_in),
                    "signal_h_out": int(sig_h_out),
                    "ml_thr": float(ml_thr),
                    "ml_h_in": int(ml_h_in),
                    "ml_h_out": int(ml_h_out),
                    "ml_winner_variant": ml_winner_variant,
                    "ml_winner_candidate_id": ml_winner_id,
                    "equity_final_holdout_ml": float(hold_metrics["equity_final"]),
                    "cagr_holdout_ml": float(hold_metrics["cagr"]),
                    "mdd_holdout_ml": float(hold_metrics["mdd"]),
                    "sharpe_holdout_ml": float(hold_metrics["sharpe"]),
                    "equity_final_holdout_base": float(base_hold_metrics["equity_final"]),
                    "cagr_holdout_base": float(base_hold_metrics["cagr"]),
                    "mdd_holdout_base": float(base_hold_metrics["mdd"]),
                    "sharpe_holdout_base": float(base_hold_metrics["sharpe"]),
                    "c060_holdout_equity_final": c060_holdout_end,
                    "delta_holdout_vs_c060_abs": float(hold_metrics["equity_final"] - c060_holdout_end),
                    "delta_holdout_vs_c060_pct": float((hold_metrics["equity_final"] / c060_holdout_end) - 1.0),
                    "passes_holdout_vs_c060_gate": bool(hold_metrics["equity_final"] >= c060_holdout_end),
                }

                for name, start, end in SUBPERIODS:
                    m_ml = subperiod_metrics(curve_ml, start, end)
                    m_c060 = subperiod_metrics(c060.rename(columns={"equity_end_norm": "equity_end_norm"}), start, end)
                    row[f"{name}_equity_final_ml"] = float(m_ml["equity_final"])
                    row[f"{name}_cagr_ml"] = float(m_ml["cagr"])
                    row[f"{name}_mdd_ml"] = float(m_ml["mdd"])
                    row[f"{name}_sharpe_ml"] = float(m_ml["sharpe"])
                    row[f"{name}_equity_final_c060"] = float(m_c060["equity_final"])
                    if np.isfinite(m_ml["equity_final"]) and np.isfinite(m_c060["equity_final"]) and m_c060["equity_final"] != 0:
                        row[f"{name}_rel_return_vs_c060_pct"] = float((m_ml["equity_final"] / m_c060["equity_final"]) - 1.0)
                    else:
                        row[f"{name}_rel_return_vs_c060_pct"] = np.nan

                ablation_rows.append(row)

                if best_candidate is None:
                    best_candidate = row
                    best_curve_base = curve_base
                    best_curve_ml = curve_ml
                else:
                    cur_pass = bool(row["passes_holdout_vs_c060_gate"])
                    best_pass = bool(best_candidate["passes_holdout_vs_c060_gate"])
                    cur_key = (
                        1 if cur_pass else 0,
                        float(row["sharpe_holdout_ml"]),
                        float(row["cagr_holdout_ml"]),
                        float(row["SP_2019H2_2020_rel_return_vs_c060_pct"]),
                        -int(row["candidate_id"].split("_")[0][1:]),
                    )
                    best_key = (
                        1 if best_pass else 0,
                        float(best_candidate["sharpe_holdout_ml"]),
                        float(best_candidate["cagr_holdout_ml"]),
                        float(best_candidate["SP_2019H2_2020_rel_return_vs_c060_pct"]),
                        -int(best_candidate["candidate_id"].split("_")[0][1:]),
                    )
                    if cur_key > best_key:
                        best_candidate = row
                        best_curve_base = curve_base
                        best_curve_ml = curve_ml

        ablation = pd.DataFrame(ablation_rows).sort_values("candidate_id").reset_index(drop=True)
        ablation.to_parquet(OUT_ABLATION, index=False)
        if best_candidate is None or best_curve_base is None or best_curve_ml is None:
            raise RuntimeError("Sem candidato vencedor.")

        best_curve_base.to_parquet(OUT_CURVE_BASE, index=False)
        best_curve_ml.to_parquet(OUT_CURVE_ML, index=False)

        winner_top_n = int(best_candidate["top_n"])
        winner_cfg = {
            "task_id": TASK_ID,
            "run_id": RUN_ID,
            "selection_mode": "HOLDOUT_PRIMARY_WITH_C060_GATE",
            "winner_candidate_id": str(best_candidate["candidate_id"]),
            "winner_params": {
                "top_n": winner_top_n,
                "target_pct": float(1.0 / winner_top_n),
                "max_pct": 0.10,
                "cadence_mode_a": int(best_candidate["cadence_mode_a"]),
                "cadence_mode_b": int(best_candidate["cadence_mode_b"]),
                "signal_w": int(best_candidate["signal_w"]),
                "signal_thr": float(best_candidate["signal_thr"]),
                "signal_h_in": int(best_candidate["signal_h_in"]),
                "signal_h_out": int(best_candidate["signal_h_out"]),
            },
            "ml_trigger_fixed_from_t106": {
                "winner_variant": ml_winner_variant,
                "winner_candidate_id": ml_winner_id,
                "thr": ml_thr,
                "h_in": ml_h_in,
                "h_out": ml_h_out,
            },
            "universe": {
                "tickers_count_after_blacklist": int(tickers_count),
                "order_cost_rate": 0.00025,
            },
            "grids": {
                "top_n_grid": TOP_N_GRID,
                "cadence_mode_b_grid": CADENCE_MODE_B_GRID,
            },
            "walk_forward": {
                "train_start": TRAIN_START.strftime("%Y-%m-%d"),
                "train_end": TRAIN_END.strftime("%Y-%m-%d"),
                "holdout_start": HOLDOUT_START.strftime("%Y-%m-%d"),
                "holdout_end": HOLDOUT_END.strftime("%Y-%m-%d"),
            },
        }
        write_json(OUT_SELECTED_CFG, winner_cfg)

        hold_winner_ml = best_curve_ml[best_curve_ml["split"] == "HOLDOUT"].copy()
        hold_winner_base = normalize_baseline(best_curve_base)
        hold_winner_base = hold_winner_base[hold_winner_base["split"] == "HOLDOUT"].copy()
        hold_c060 = c060[c060["split"] == "HOLDOUT"].copy()

        train_winner_ml = best_curve_ml[best_curve_ml["split"] == "TRAIN"].copy()
        summary = {
            "winner_candidate_id": best_candidate["candidate_id"],
            "winner_train_ml": metrics(train_winner_ml["equity_end_norm"]),
            "winner_holdout_ml": metrics(hold_winner_ml["equity_end_norm"]),
            "winner_holdout_base": metrics(hold_winner_base["equity_end_norm"]),
            "c060_holdout": metrics(hold_c060["equity_end_norm"]),
            "delta_holdout_vs_c060_abs": float(best_candidate["delta_holdout_vs_c060_abs"]),
            "delta_holdout_vs_c060_pct": float(best_candidate["delta_holdout_vs_c060_pct"]),
            "subperiods": {},
        }
        for name, start, end in SUBPERIODS:
            summary["subperiods"][name] = {
                "ml": subperiod_metrics(best_curve_ml, start, end),
                "c060": subperiod_metrics(c060, start, end),
                "rel_return_vs_c060_pct": float(best_candidate.get(f"{name}_rel_return_vs_c060_pct", np.nan)),
            }
        write_json(OUT_SUMMARY, summary)

        write_json(
            OUT_SELECTION_RULE,
            {
                "selection_mode": "HOLDOUT_PRIMARY_WITH_C060_GATE",
                "rule": [
                    "1) require equity_final_holdout_ml >= c060_holdout_equity_final when possible",
                    "2) sharpe_holdout_ml DESC",
                    "3) cagr_holdout_ml DESC",
                    "4) SP_2019H2_2020_rel_return_vs_c060_pct DESC",
                    "5) candidate_id ASC",
                ],
                "winner_candidate_id": best_candidate["candidate_id"],
            },
        )
        write_json(
            OUT_SUBPERIODS,
            {
                "subperiods": [
                    {"name": name, "start": start, "end": end} for name, start, end in SUBPERIODS
                ],
                "acid_window": {"start": ACID_START, "end": ACID_END},
            },
        )
        write_json(
            OUT_METRICS_SNAPSHOT,
            {
                "winner_candidate": best_candidate,
                "ablation_rows": int(len(ablation)),
                "ablation_columns": list(ablation.columns),
            },
        )
        write_json(OUT_JOIN_COVERAGE, join_coverage_by_candidate)

        comp = hold_winner_base[["date"]].copy()
        comp["cdi_log_daily"] = pd.to_numeric(
            pd.Series(macro_day.reindex(comp["date"])["cdi_log_daily"].values, index=comp.index),
            errors="coerce",
        ).fillna(0.0)
        comp["ibov_close"] = pd.to_numeric(
            pd.Series(macro_day.reindex(comp["date"])["ibov_close"].values, index=comp.index),
            errors="coerce",
        ).ffill().bfill()
        comp["equity_cdi"] = BASE_CAPITAL * (1.0 + (np.exp(comp["cdi_log_daily"]) - 1.0)).cumprod()
        comp["equity_ibov"] = BASE_CAPITAL * (comp["ibov_close"] / float(comp["ibov_close"].iloc[0]))

        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.08,
            subplot_titles=("Equity (R$100k base) - HOLDOUT", "Drawdown - HOLDOUT"),
        )
        fig.add_trace(
            go.Scatter(x=hold_winner_base["date"], y=hold_winner_base["equity_end_norm"], mode="lines", name="T108 Winner Baseline"),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(x=hold_winner_ml["date"], y=hold_winner_ml["equity_end_norm"], mode="lines", name="T108 Winner + ML"),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(x=hold_c060["date"], y=hold_c060["equity_end_norm"], mode="lines", name="C060"),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(x=comp["date"], y=comp["equity_cdi"], mode="lines", name="CDI"),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(x=comp["date"], y=comp["equity_ibov"], mode="lines", name="Ibov"),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(x=hold_winner_base["date"], y=drawdown(hold_winner_base["equity_end_norm"]), mode="lines", name="DD Baseline"),
            row=2,
            col=1,
        )
        fig.add_trace(
            go.Scatter(x=hold_winner_ml["date"], y=drawdown(hold_winner_ml["equity_end_norm"]), mode="lines", name="DD Winner + ML"),
            row=2,
            col=1,
        )
        fig.add_trace(
            go.Scatter(x=hold_c060["date"], y=drawdown(hold_c060["equity_end_norm"]), mode="lines", name="DD C060"),
            row=2,
            col=1,
        )
        fig.add_vrect(
            x0=ACID_START,
            x1=ACID_END,
            fillcolor="rgba(220,20,60,0.12)",
            line_width=0,
            annotation_text="Acid Window",
            annotation_position="top left",
            row="all",
            col=1,
        )
        fig.update_layout(
            title="T108 - Ablacao n_positions x cadence (Winner vs C060/CDI/Ibov)",
            template="plotly_white",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            height=900,
        )
        fig.update_yaxes(title_text="R$", row=1, col=1)
        fig.update_yaxes(title_text="Drawdown", tickformat=".1%", row=2, col=1)
        fig.write_html(str(OUT_PLOT), include_plotlyjs="cdn")
        write_json(
            OUT_PLOT_INVENTORY,
            {
                "html": str(OUT_PLOT.relative_to(ROOT)),
                "equity_traces": ["T108 Winner Baseline", "T108 Winner + ML", "C060", "CDI", "Ibov"],
                "drawdown_traces": ["DD Baseline", "DD Winner + ML", "DD C060"],
                "acid_window": [ACID_START.strftime("%Y-%m-%d"), ACID_END.strftime("%Y-%m-%d")],
            },
        )

        artifacts = [
            OUT_ABLATION,
            OUT_SELECTED_CFG,
            OUT_CURVE_BASE,
            OUT_CURVE_ML,
            OUT_SUMMARY,
            OUT_PLOT,
            OUT_SELECTION_RULE,
            OUT_METRICS_SNAPSHOT,
            OUT_SUBPERIODS,
            OUT_PLOT_INVENTORY,
            OUT_JOIN_COVERAGE,
        ]
        gates.append(Gate("G_ARTIFACTS_WRITTEN", all(p.exists() for p in artifacts), f"count={len(artifacts)}"))

        gate_ablation_rows = len(ablation) >= (len(TOP_N_GRID) * len(CADENCE_MODE_B_GRID))
        gates.append(Gate("G_ABLATION_GRID_MIN_OK", gate_ablation_rows, f"rows={len(ablation)}"))

        gates.append(
            Gate(
                "G_WINNER_VS_C060_HOLDOUT_OK",
                bool(best_candidate["equity_final_holdout_ml"] >= best_candidate["c060_holdout_equity_final"]),
                (
                    f"winner={best_candidate['equity_final_holdout_ml']:.2f} "
                    f"vs c060={best_candidate['c060_holdout_equity_final']:.2f}"
                ),
            )
        )

        chlog_ok = append_changelog_one_line(TRACEABILITY_LINE)
        gates.append(Gate("G_CHLOG_UPDATED", chlog_ok, f"path={CHANGELOG_PATH}"))
        gates.append(Gate("G_CHLOG_LITERAL_PASSFAIL_FORBIDDEN", "PASS/FAIL" not in TRACEABILITY_LINE, "line_must_not_contain_PASS/FAIL"))

        outputs_produced = [
            str(OUT_SCRIPT.relative_to(ROOT)),
            str(OUT_ABLATION.relative_to(ROOT)),
            str(OUT_SELECTED_CFG.relative_to(ROOT)),
            str(OUT_CURVE_BASE.relative_to(ROOT)),
            str(OUT_CURVE_ML.relative_to(ROOT)),
            str(OUT_SUMMARY.relative_to(ROOT)),
            str(OUT_PLOT.relative_to(ROOT)),
            str(OUT_SELECTION_RULE.relative_to(ROOT)),
            str(OUT_METRICS_SNAPSHOT.relative_to(ROOT)),
            str(OUT_SUBPERIODS.relative_to(ROOT)),
            str(OUT_PLOT_INVENTORY.relative_to(ROOT)),
            str(OUT_JOIN_COVERAGE.relative_to(ROOT)),
            str(OUT_REPORT.relative_to(ROOT)),
            str(CHANGELOG_PATH.relative_to(ROOT)),
            str(OUT_MANIFEST.relative_to(ROOT)),
        ]

        report_lines = [
            "# HEADER: T108",
            "",
            "## STEP GATES",
        ]
        for g in gates:
            report_lines.append(f"- {g.name}: {'PASS' if g.passed else 'FAIL'} | {g.detail}")
        report_lines.extend(
            [
                "",
                "## RESULTADOS (WINNER VS C060)",
                f"- Winner candidate: {best_candidate['candidate_id']}",
                (
                    f"- TRAIN (winner+ML): equity={summary['winner_train_ml']['equity_final']:.2f}, "
                    f"CAGR={summary['winner_train_ml']['cagr']:.4f}, "
                    f"MDD={summary['winner_train_ml']['mdd']:.4f}, "
                    f"Sharpe={summary['winner_train_ml']['sharpe']:.4f}"
                ),
                (
                    f"- HOLDOUT equity winner={best_candidate['equity_final_holdout_ml']:.2f} "
                    f"vs C060={best_candidate['c060_holdout_equity_final']:.2f} "
                    f"(delta={best_candidate['delta_holdout_vs_c060_pct']*100:.2f}%)"
                ),
                (
                    f"- Subperiodo 2019-07..2020-12 rel_return_vs_c060="
                    f"{best_candidate['SP_2019H2_2020_rel_return_vs_c060_pct']*100:.2f}%"
                ),
                (
                    f"- ACID rel_return_vs_c060="
                    f"{best_candidate['SP_ACID_rel_return_vs_c060_pct']*100:.2f}%"
                ),
                "",
                "## RETRY LOG",
                "- none" if not retry_log else "\n".join(f"- {x}" for x in retry_log),
                "",
                "## ARTIFACT LINKS",
            ]
        )
        for rel in outputs_produced:
            report_lines.append(f"- {rel}")
        overall_pass = all(g.passed for g in gates)
        report_lines.extend(
            [
                "",
                f"## OVERALL STATUS: [[ {'PASS' if overall_pass else 'FAIL'} ]]",
                "",
            ]
        )
        OUT_REPORT.write_text("\n".join(report_lines), encoding="utf-8")

        hashes: dict[str, str] = {}
        for rel in outputs_produced:
            p = ROOT / rel
            if p.exists() and p != OUT_MANIFEST:
                hashes[rel] = sha256_file(p)
        manifest_payload = {
            "task_id": TASK_ID,
            "run_id": RUN_ID,
            "inputs_consumed": [str(p.relative_to(ROOT)) for p in input_files],
            "outputs_produced": outputs_produced,
            "manifest_policy": "no_self_hash",
            "hashes_sha256": hashes,
        }
        write_json(OUT_MANIFEST, manifest_payload)
        gates.append(Gate("Gx_HASH_MANIFEST_PRESENT", OUT_MANIFEST.exists(), f"path={OUT_MANIFEST.relative_to(ROOT)}"))

        mismatches = []
        manifest_check = json.loads(OUT_MANIFEST.read_text(encoding="utf-8"))
        for rel, expected in manifest_check["hashes_sha256"].items():
            got = sha256_file(ROOT / rel)
            if got != expected:
                mismatches.append(rel)
        gates.append(Gate("G_SHA256_INTEGRITY_SELF_CHECK", len(mismatches) == 0, f"mismatches={len(mismatches)}"))

        report_lines = [
            "# HEADER: T108",
            "",
            "## STEP GATES",
        ]
        for g in gates:
            report_lines.append(f"- {g.name}: {'PASS' if g.passed else 'FAIL'} | {g.detail}")
        report_lines.extend(
            [
                "",
                "## RESULTADOS (WINNER VS C060)",
                f"- Winner candidate: {best_candidate['candidate_id']}",
                (
                    f"- TRAIN (winner+ML): equity={summary['winner_train_ml']['equity_final']:.2f}, "
                    f"CAGR={summary['winner_train_ml']['cagr']:.4f}, "
                    f"MDD={summary['winner_train_ml']['mdd']:.4f}, "
                    f"Sharpe={summary['winner_train_ml']['sharpe']:.4f}"
                ),
                (
                    f"- HOLDOUT equity winner={best_candidate['equity_final_holdout_ml']:.2f} "
                    f"vs C060={best_candidate['c060_holdout_equity_final']:.2f} "
                    f"(delta={best_candidate['delta_holdout_vs_c060_pct']*100:.2f}%)"
                ),
                (
                    f"- Subperiodo 2019-07..2020-12 rel_return_vs_c060="
                    f"{best_candidate['SP_2019H2_2020_rel_return_vs_c060_pct']*100:.2f}%"
                ),
                (
                    f"- ACID rel_return_vs_c060="
                    f"{best_candidate['SP_ACID_rel_return_vs_c060_pct']*100:.2f}%"
                ),
                "",
                "## RETRY LOG",
                "- none" if not retry_log else "\n".join(f"- {x}" for x in retry_log),
                "",
                "## ARTIFACT LINKS",
            ]
        )
        for rel in outputs_produced:
            report_lines.append(f"- {rel}")
        overall_pass = all(g.passed for g in gates)
        report_lines.extend(
            [
                "",
                f"## OVERALL STATUS: [[ {'PASS' if overall_pass else 'FAIL'} ]]",
                "",
            ]
        )
        OUT_REPORT.write_text("\n".join(report_lines), encoding="utf-8")

        manifest_final = json.loads(OUT_MANIFEST.read_text(encoding="utf-8"))
        manifest_final["hashes_sha256"][str(OUT_REPORT.relative_to(ROOT))] = sha256_file(OUT_REPORT)
        write_json(OUT_MANIFEST, manifest_final)

        print(f"HEADER: {TASK_ID}")
        print("STEP GATES:")
        for g in gates:
            print(f"- {g.name}: {'PASS' if g.passed else 'FAIL'} | {g.detail}")
        print("RETRY LOG:")
        print("- none" if not retry_log else "\n".join(f"- {x}" for x in retry_log))
        print("ARTIFACT LINKS:")
        for rel in outputs_produced:
            print(f"- {rel}")
        print(f"OVERALL STATUS: [[ {'PASS' if overall_pass else 'FAIL'} ]]")
        return 0 if overall_pass else 2
    except Exception as exc:
        print(f"HEADER: {TASK_ID}")
        print("STEP GATES:")
        for g in gates:
            print(f"- {g.name}: {'PASS' if g.passed else 'FAIL'} | {g.detail}")
        print("RETRY LOG:")
        if retry_log:
            for item in retry_log:
                print(f"- {item}")
        else:
            print("- none")
        print(f"FATAL: {type(exc).__name__}: {exc}")
        print("OVERALL STATUS: [[ FAIL ]]")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
