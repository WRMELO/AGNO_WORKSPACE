#!/home/wilson/AGNO_WORKSPACE/.venv/bin/python
"""CTO exploratory analysis: C060 (Phase 6 winner) params on expanded universe (BR+BDR+US).

Not a product task. This script reuses T107/T108 motor logic to run C060 params
(top_n=10, threshold=0.25, h_in=3, h_out=2) on the expanded universe and saves
the curve for dashboard overlay.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd

if not ("agno_env" in sys.prefix or ".venv" in sys.prefix):
    raise RuntimeError("FATAL: Not in agno_env/.venv")

ROOT = Path("/home/wilson/AGNO_WORKSPACE")
BASE_CAPITAL = 100000.0

INPUT_CANONICAL = ROOT / "src/data_engine/ssot/SSOT_CANONICAL_BASE_BR_EXPANDED.parquet"
INPUT_MACRO = ROOT / "src/data_engine/ssot/SSOT_MACRO_EXPANDED.parquet"
INPUT_UNIVERSE = ROOT / "src/data_engine/ssot/SSOT_UNIVERSE_OPERATIONAL_EXPANDED.parquet"
INPUT_BLACKLIST = ROOT / "src/data_engine/ssot/SSOT_QUALITY_BLACKLIST_A001.json"
INPUT_T072_CFG = ROOT / "src/data_engine/portfolio/T072_DUAL_MODE_SELECTED_CONFIG.json"
INPUT_T105_PRED = ROOT / "src/data_engine/features/T105_V1_PREDICTIONS.parquet"
INPUT_C060_CURVE = ROOT / "outputs/governanca/T079-PHASE6-PLOTLY-COMPARATIVE-V1_evidence/c060_curve_snapshot.parquet"

OUT_CURVE = ROOT / "src/data_engine/portfolio/CTO_C060_EXPANDED_UNIVERSE_CURVE.parquet"

TRAIN_START = pd.Timestamp("2018-07-02")
TRAIN_END = pd.Timestamp("2022-12-30")
HOLDOUT_START = pd.Timestamp("2023-01-02")
HOLDOUT_END = pd.Timestamp("2026-02-26")
ACID_START = pd.Timestamp("2024-11-01")
ACID_END = pd.Timestamp("2025-11-30")

C060_TOP_N = 10
C060_THR = 0.25
C060_H_IN = 3
C060_H_OUT = 2


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module: {path}")
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
        cs = pd.DataFrame({"score_m0": m0_row[common], "ret_62": r_row[common], "vol_62": v_row[common]})
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
    return "TRAIN" if d <= TRAIN_END else "HOLDOUT"


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


def main() -> int:
    print("=" * 70)
    print("CTO ANALYSIS: C060 params on expanded universe (BR+BDR+US)")
    print("=" * 70)

    t063 = load_module("t063_cto", ROOT / "scripts/t063_market_slope_reentry_ablation.py")
    t072 = load_module("t072_cto", ROOT / "scripts/t072_dual_mode_engine_ablation.py")

    print("[1/7] Loading canonical expanded...")
    canonical = pd.read_parquet(INPUT_CANONICAL).copy()
    canonical["ticker"] = canonical["ticker"].astype(str).str.upper().str.strip()
    canonical["date"] = pd.to_datetime(canonical["date"], errors="coerce").dt.normalize()
    canonical = canonical.dropna(subset=["ticker", "date", "close_operational"]).copy()

    universe = pd.read_parquet(INPUT_UNIVERSE).copy()
    universe_tickers = set(universe["ticker"].astype(str).str.upper().str.strip().tolist())
    blacklist = t063.load_blacklist()
    use_tickers = universe_tickers.difference(blacklist)
    canonical = canonical[canonical["ticker"].isin(use_tickers)].copy()
    print(f"  Tickers after blacklist: {canonical['ticker'].nunique()}")

    print("[2/7] Loading macro...")
    macro = pd.read_parquet(INPUT_MACRO).copy()
    macro["date"] = pd.to_datetime(macro["date"], errors="coerce").dt.normalize()
    macro = macro.dropna(subset=["date", "ibov_close", "cdi_log_daily"]).sort_values("date")
    macro_day = macro.set_index("date")

    print("[3/7] Building engine (px_wide, z_wide, scores M3, rule maps)...")
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
    print(f"  px_wide shape: {px_wide.shape}, scores_by_day days: {len(scores_by_day)}")

    sim_dates = sorted(set(px_wide.index).intersection(set(macro_day.index)))
    sim_dates = [pd.Timestamp(d) for d in sim_dates if TRAIN_START <= pd.Timestamp(d) <= HOLDOUT_END]
    print(f"  sim_dates: {len(sim_dates)} ({sim_dates[0]} -> {sim_dates[-1]})")

    engine = SimpleNamespace(
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

    print("[4/7] Configuring C060 params on T072 engine...")
    t072_cfg = json.loads(INPUT_T072_CFG.read_text(encoding="utf-8"))

    t072.PROFILE_A["top_n"] = C060_TOP_N
    t072.PROFILE_A["target_pct"] = 1.0 / C060_TOP_N
    t072.PROFILE_A["max_pct"] = 0.15
    t072.PROFILE_B["top_n"] = C060_TOP_N
    t072.PROFILE_B["target_pct"] = 1.0 / C060_TOP_N
    t072.PROFILE_B["max_pct"] = 0.15

    if "profiles_fixed" in t072_cfg:
        pf = t072_cfg["profiles_fixed"]
        t072.PROFILE_A["cadence_days"] = int(pf["mode_a"]["cadence_days"])
        t072.PROFILE_B["cadence_days"] = int(pf["mode_b"]["cadence_days"])
        t072.PROFILE_B["market_slope_window"] = int(pf["mode_b"]["market_slope_window"])
        t072.PROFILE_B["in_hyst_days"] = int(pf["mode_b"]["in_hyst_days"])
        t072.PROFILE_B["out_hyst_days"] = int(pf["mode_b"]["out_hyst_days"])

    signal_w = int(t072_cfg.get("signal_w", 30))
    sig_thr = float(t072_cfg.get("thr", 0.0005))
    sig_h_in = int(t072_cfg.get("h_in", 2))
    sig_h_out = int(t072_cfg.get("h_out", 4))
    signal_variant = str(t072_cfg.get("signal_variant", "SINAL-2"))
    initial_mode = str(t072_cfg.get("initial_mode", t072.MODE_B))

    print(f"  C060 params: top_n={C060_TOP_N}, thr={C060_THR}, h_in={C060_H_IN}, h_out={C060_H_OUT}")
    print(f"  Dual-mode: signal_w={signal_w}, sig_thr={sig_thr}, sig_h_in={sig_h_in}, sig_h_out={sig_h_out}")
    print(f"  Cadence: mode_a={t072.PROFILE_A['cadence_days']}, mode_b={t072.PROFILE_B['cadence_days']}")

    print("[5/7] Running dual-mode backtest on expanded universe...")
    _, curve_base, diag = t072.run_candidate_t072(
        t063, engine,
        signal_w=signal_w, thr=sig_thr, h_in=sig_h_in, h_out=sig_h_out,
        signal_variant=signal_variant, initial_mode=initial_mode,
    )
    curve_base = curve_base.copy()
    curve_base["date"] = pd.to_datetime(curve_base["date"]).dt.normalize()
    curve_base["split"] = curve_base["date"].apply(assign_split)
    curve_base = curve_base.sort_values("date").reset_index(drop=True)
    print(f"  curve_base rows: {len(curve_base)}")

    print("[6/7] Applying ML trigger (C060 hysteresis) on expanded base curve...")
    pred = pd.read_parquet(INPUT_T105_PRED).copy()
    pred["date"] = pd.to_datetime(pred["date"], errors="coerce").dt.normalize()

    merged = curve_base.merge(
        pred[["date", "split", "y_proba_cash"]],
        on=["date", "split"],
        how="inner",
        validate="one_to_one",
    ).sort_values("date")

    state_cash = apply_hysteresis(merged["y_proba_cash"], thr=C060_THR, h_in=C060_H_IN, h_out=C060_H_OUT)

    out_ml = pd.DataFrame({"date": merged["date"], "split": merged["split"]})
    out_ml["ret_t072"] = pd.to_numeric(merged["equity_end"], errors="coerce").pct_change().fillna(0.0)
    out_ml["ret_cdi"] = pd.to_numeric(merged["cdi_daily"], errors="coerce").fillna(0.0)
    out_ml["state_cash"] = state_cash.astype(int)
    out_ml["ret_strategy"] = np.where(out_ml["state_cash"] == 1, out_ml["ret_cdi"], out_ml["ret_t072"])
    out_ml["equity_end_norm"] = BASE_CAPITAL * (1.0 + out_ml["ret_strategy"]).cumprod()
    out_ml.loc[out_ml.index[0], "equity_end_norm"] = BASE_CAPITAL
    out_ml["drawdown"] = drawdown(out_ml["equity_end_norm"])
    out_ml["switches_cumsum"] = (out_ml["state_cash"].diff().abs() == 1).fillna(False).astype(int).cumsum()
    out_ml["curve_name"] = "CTO_C060_EXPANDED"

    OUT_CURVE.parent.mkdir(parents=True, exist_ok=True)
    out_ml.to_parquet(OUT_CURVE, index=False)
    print(f"  Saved: {OUT_CURVE}")

    print("[7/7] Computing metrics...")
    c060_orig = pd.read_parquet(INPUT_C060_CURVE).copy()
    c060_orig["date"] = pd.to_datetime(c060_orig["date"]).dt.normalize()
    c060_orig = c060_orig.sort_values("date")

    def report_metrics(label: str, curve: pd.DataFrame) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for split_name, sub in [
            ("FULL", curve),
            ("TRAIN", curve[curve["split"] == "TRAIN"]),
            ("HOLDOUT", curve[curve["split"] == "HOLDOUT"]),
            ("ACID", curve[(curve["split"] == "HOLDOUT") & (curve["date"] >= ACID_START) & (curve["date"] <= ACID_END)]),
        ]:
            if len(sub) < 2:
                continue
            m = metrics(sub["equity_end_norm"])
            sw = float((sub["state_cash"].diff().abs() == 1).sum()) if "state_cash" in sub.columns else 0.0
            results[split_name] = {**m, "switches": sw}
        print(f"\n  {label}:")
        for k, v in results.items():
            print(f"    {k}: equity={v['equity_final']:,.2f}  CAGR={v['cagr']*100:.2f}%  MDD={v['mdd']*100:.2f}%  Sharpe={v['sharpe']:.3f}  switches={v['switches']:.0f}")
        return results

    print("\n" + "=" * 70)
    print("METRICS COMPARISON")
    print("=" * 70)

    m_c060_orig = report_metrics("C060 ORIGINAL (BR, top_n=10)", c060_orig)
    m_c060_exp = report_metrics("C060 EXPANDED (BR+BDR+US, top_n=10)", out_ml)

    in_t108_ml = ROOT / "src/data_engine/portfolio/T108_PORTFOLIO_CURVE_DUAL_MODE_EXPANDED_ML_TRIGGER_WINNER.parquet"
    if in_t108_ml.exists():
        t108_winner = pd.read_parquet(in_t108_ml).copy()
        t108_winner["date"] = pd.to_datetime(t108_winner["date"]).dt.normalize()
        t108_winner = t108_winner.sort_values("date")
        m_p8 = report_metrics("PHASE 8 WINNER (BR+BDR+US, top_n=15)", t108_winner)
    else:
        print("\n  PHASE 8 WINNER: T108 curve not found, skipping.")

    print("\n" + "=" * 70)
    print("HOLDOUT HEAD-TO-HEAD")
    print("=" * 70)
    rows = []
    for label, m_dict in [
        ("C060 Original (BR, N=10)", m_c060_orig),
        ("C060 Expanded (BR+BDR, N=10)", m_c060_exp),
    ]:
        h = m_dict.get("HOLDOUT", {})
        rows.append({"Curve": label, **h})

    if in_t108_ml.exists():
        h_p8 = m_p8.get("HOLDOUT", {})
        rows.append({"Curve": "Phase 8 Winner (BR+BDR, N=15)", **h_p8})

    if rows:
        df_cmp = pd.DataFrame(rows)
        print(df_cmp.to_string(index=False))

    print(f"\nDone. Curve saved to: {OUT_CURVE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
