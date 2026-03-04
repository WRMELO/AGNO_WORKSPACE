#!/home/wilson/AGNO_WORKSPACE/.venv/bin/python
"""CTO exploratory ablation: C060 Expanded — threshold [0.25..0.35] × MDD limits.

Reuses the motor from cto_analysis_c060_expanded_universe.py.
Grid: thr ∈ {0.25, 0.27, 0.29, 0.31, 0.33, 0.35} × mdd_limit ∈ {-0.08, -0.10, -0.12, -0.15, -0.20, None}
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

if not ("agno_env" in sys.prefix or ".venv" in sys.prefix):
    raise RuntimeError("FATAL: Not in agno_env/.venv")

ROOT = Path("/home/wilson/AGNO_WORKSPACE")
BASE_CAPITAL = 100_000.0

INPUT_CANONICAL = ROOT / "src/data_engine/ssot/SSOT_CANONICAL_BASE_BR_EXPANDED.parquet"
INPUT_MACRO = ROOT / "src/data_engine/ssot/SSOT_MACRO_EXPANDED.parquet"
INPUT_UNIVERSE = ROOT / "src/data_engine/ssot/SSOT_UNIVERSE_OPERATIONAL_EXPANDED.parquet"
INPUT_BLACKLIST = ROOT / "src/data_engine/ssot/SSOT_QUALITY_BLACKLIST_A001.json"
INPUT_T072_CFG = ROOT / "src/data_engine/portfolio/T072_DUAL_MODE_SELECTED_CONFIG.json"
INPUT_T105_PRED = ROOT / "src/data_engine/features/T105_V1_PREDICTIONS.parquet"
INPUT_C060_CURVE = ROOT / "outputs/governanca/T079-PHASE6-PLOTLY-COMPARATIVE-V1_evidence/c060_curve_snapshot.parquet"
INPUT_T108_WINNER = ROOT / "src/data_engine/portfolio/T108_PORTFOLIO_CURVE_DUAL_MODE_EXPANDED_ML_TRIGGER_WINNER.parquet"

OUT_ABLATION = ROOT / "src/data_engine/portfolio/CTO_C060_EXPANDED_ABLATION_RESULTS.parquet"
OUT_WINNER_CURVE = ROOT / "src/data_engine/portfolio/CTO_C060_EXPANDED_ABLATION_WINNER_CURVE.parquet"
OUT_PLOT = ROOT / "outputs/plots/CTO_C060_EXPANDED_ABLATION_FINAL.html"

TRAIN_START = pd.Timestamp("2018-07-02")
TRAIN_END = pd.Timestamp("2022-12-30")
HOLDOUT_START = pd.Timestamp("2023-01-02")
HOLDOUT_END = pd.Timestamp("2026-02-26")
ACID_START = pd.Timestamp("2024-11-01")
ACID_END = pd.Timestamp("2025-11-30")

TOP_N = 10
H_IN = 3
H_OUT = 2

THR_GRID = [0.20, 0.21, 0.22, 0.23, 0.24, 0.25]
MDD_LIMITS = [None]


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


def build_base_curve(t063, t072, engine, t072_cfg):
    """Run T072 dual-mode backtest once on expanded universe (top_n=10)."""
    t072.PROFILE_A["top_n"] = TOP_N
    t072.PROFILE_A["target_pct"] = 1.0 / TOP_N
    t072.PROFILE_A["max_pct"] = 0.15
    t072.PROFILE_B["top_n"] = TOP_N
    t072.PROFILE_B["target_pct"] = 1.0 / TOP_N
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

    _, curve_base, _ = t072.run_candidate_t072(
        t063, engine,
        signal_w=signal_w, thr=sig_thr, h_in=sig_h_in, h_out=sig_h_out,
        signal_variant=signal_variant, initial_mode=initial_mode,
    )
    curve_base = curve_base.copy()
    curve_base["date"] = pd.to_datetime(curve_base["date"]).dt.normalize()
    curve_base["split"] = curve_base["date"].apply(assign_split)
    return curve_base.sort_values("date").reset_index(drop=True)


def apply_ml_trigger(curve_base: pd.DataFrame, pred: pd.DataFrame, thr: float) -> pd.DataFrame:
    """Apply ML cash-override with given threshold and fixed h_in/h_out."""
    merged = curve_base.merge(
        pred[["date", "split", "y_proba_cash"]],
        on=["date", "split"], how="inner", validate="one_to_one",
    ).sort_values("date")

    state_cash = apply_hysteresis(merged["y_proba_cash"], thr=thr, h_in=H_IN, h_out=H_OUT)

    out = pd.DataFrame({"date": merged["date"].values, "split": merged["split"].values})
    out["ret_t072"] = pd.to_numeric(merged["equity_end"], errors="coerce").pct_change().fillna(0.0).values
    out["ret_cdi"] = pd.to_numeric(merged["cdi_daily"], errors="coerce").fillna(0.0).values
    out["state_cash"] = state_cash.values
    out["ret_strategy"] = np.where(out["state_cash"] == 1, out["ret_cdi"], out["ret_t072"])
    out["equity_end_norm"] = BASE_CAPITAL * (1.0 + out["ret_strategy"]).cumprod()
    out.loc[out.index[0], "equity_end_norm"] = BASE_CAPITAL
    out["drawdown"] = drawdown(out["equity_end_norm"]).values
    out["switches_cumsum"] = (out["state_cash"].diff().abs() == 1).fillna(False).astype(int).cumsum()
    return out


def compute_all_metrics(curve: pd.DataFrame) -> dict[str, dict[str, float]]:
    results = {}
    for name, sub in [
        ("FULL", curve),
        ("TRAIN", curve[curve["split"] == "TRAIN"]),
        ("HOLDOUT", curve[curve["split"] == "HOLDOUT"]),
        ("ACID", curve[(curve["split"] == "HOLDOUT") & (curve["date"] >= ACID_START) & (curve["date"] <= ACID_END)]),
    ]:
        if len(sub) < 2:
            continue
        m = metrics(sub["equity_end_norm"])
        sw = float((sub["state_cash"].diff().abs() == 1).sum()) if "state_cash" in sub.columns else 0.0
        cash_pct = float(sub["state_cash"].mean()) if "state_cash" in sub.columns else 0.0
        results[name] = {**m, "switches": sw, "cash_pct": cash_pct}
    return results


def make_plotly(
    winner_new: pd.DataFrame,
    winner_new_label: str,
    c060_orig: pd.DataFrame,
    c060_expanded: pd.DataFrame,
    phase8_winner: pd.DataFrame,
):
    """Build 4-panel Plotly dashboard."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.04,
        subplot_titles=["Equity (base R$100k)", "Drawdown", "Switches Cumulativos", "State Cash (1=caixa)"],
        row_heights=[0.35, 0.25, 0.20, 0.20],
    )

    traces_cfg = [
        ("Phase8 Winner (N15 thr=0.05)", phase8_winner, "#d62728"),
        ("C060 Original (BR N10)", c060_orig, "#1f77b4"),
        ("C060 Expanded (BR+BDR N10 thr=0.25)", c060_expanded, "#9467bd"),
        (winner_new_label, winner_new, "#2ca02c"),
    ]

    for label, df, color in traces_cfg:
        fig.add_trace(go.Scatter(x=df["date"], y=df["equity_end_norm"], name=label, line=dict(color=color, width=1.5)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df["date"], y=df["drawdown"], name=f"DD {label}", line=dict(color=color, width=1), showlegend=False), row=2, col=1)
        if "switches_cumsum" in df.columns:
            fig.add_trace(go.Scatter(x=df["date"], y=df["switches_cumsum"], name=f"Sw {label}", line=dict(color=color, width=1), showlegend=False), row=3, col=1)
        if "state_cash" in df.columns:
            fig.add_trace(go.Scatter(x=df["date"], y=df["state_cash"], name=f"Cash {label}", line=dict(color=color, width=0.8), showlegend=False), row=4, col=1)

    for row in range(1, 5):
        fig.add_vrect(x0=str(ACID_START.date()), x1=str(ACID_END.date()), fillcolor="gold", opacity=0.12, line_width=0, row=row, col=1)
        fig.add_vrect(x0=str(HOLDOUT_START.date()), x1=str(HOLDOUT_END.date()), fillcolor="lightyellow", opacity=0.10, line_width=0, row=row, col=1)

    fig.update_layout(
        title_text="CTO Analysis: C060 Expanded Ablation — Winner vs Benchmarks",
        height=1100, width=1400, template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
    )
    fig.update_yaxes(title_text="R$", row=1, col=1)
    fig.update_yaxes(title_text="DD", row=2, col=1)
    fig.update_yaxes(title_text="Switches", row=3, col=1)
    fig.update_yaxes(title_text="Cash", row=4, col=1)

    OUT_PLOT.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(OUT_PLOT), include_plotlyjs="cdn")
    print(f"\n  Dashboard saved: {OUT_PLOT}")


def main() -> int:
    print("=" * 80)
    print("CTO ABLATION: C060 Expanded — thr × MDD limit")
    print("=" * 80)

    t063 = load_module("t063_abl", ROOT / "scripts/t063_market_slope_reentry_ablation.py")
    t072 = load_module("t072_abl", ROOT / "scripts/t072_dual_mode_engine_ablation.py")

    print("\n[1/6] Loading data...")
    canonical = pd.read_parquet(INPUT_CANONICAL).copy()
    canonical["ticker"] = canonical["ticker"].astype(str).str.upper().str.strip()
    canonical["date"] = pd.to_datetime(canonical["date"], errors="coerce").dt.normalize()
    canonical = canonical.dropna(subset=["ticker", "date", "close_operational"]).copy()

    universe = pd.read_parquet(INPUT_UNIVERSE).copy()
    universe_tickers = set(universe["ticker"].astype(str).str.upper().str.strip().tolist())
    blacklist = t063.load_blacklist()
    use_tickers = universe_tickers.difference(blacklist)
    canonical = canonical[canonical["ticker"].isin(use_tickers)].copy()
    print(f"  Tickers: {canonical['ticker'].nunique()}")

    macro = pd.read_parquet(INPUT_MACRO).copy()
    macro["date"] = pd.to_datetime(macro["date"], errors="coerce").dt.normalize()
    macro = macro.dropna(subset=["date", "ibov_close", "cdi_log_daily"]).sort_values("date")
    macro_day = macro.set_index("date")

    print("\n[2/6] Building engine...")
    prices = canonical.sort_values(["ticker", "date"]).copy()
    px_wide = prices.pivot_table(index="date", columns="ticker", values="close_operational", aggfunc="first").sort_index().ffill()
    logret_wide = np.log(px_wide / px_wide.shift(1))
    mu = logret_wide.rolling(window=60, min_periods=20).mean()
    sd = logret_wide.rolling(window=60, min_periods=20).std(ddof=0)
    z_wide = (logret_wide - mu) / sd.replace(0.0, np.nan)
    any_rule_map, strong_rule_map, in_control_map = t063.build_rule_proxy_maps(prices)
    scores_by_day = compute_m3_scores(px_wide)

    sim_dates = sorted(set(px_wide.index).intersection(set(macro_day.index)))
    sim_dates = [pd.Timestamp(d) for d in sim_dates if TRAIN_START <= pd.Timestamp(d) <= HOLDOUT_END]
    print(f"  sim_dates: {len(sim_dates)}")

    engine = SimpleNamespace(
        px_wide=px_wide, z_wide=z_wide,
        any_rule_map=any_rule_map, strong_rule_map=strong_rule_map, in_control_map=in_control_map,
        macro_day=macro_day, scores_by_day=scores_by_day, sim_dates=sim_dates,
        ibov_base=float(macro_day.loc[sim_dates[0], "ibov_close"]),
    )

    t072_cfg = json.loads(INPUT_T072_CFG.read_text(encoding="utf-8"))

    print("\n[3/6] Running base curve (T072 dual-mode, N=10, expanded universe)...")
    curve_base = build_base_curve(t063, t072, engine, t072_cfg)
    print(f"  Base curve rows: {len(curve_base)}")

    pred = pd.read_parquet(INPUT_T105_PRED).copy()
    pred["date"] = pd.to_datetime(pred["date"], errors="coerce").dt.normalize()

    print("\n[4/6] Running ablation grid...")
    print(f"  thr grid: {THR_GRID}")
    print(f"  MDD limits: {MDD_LIMITS}")
    print(f"  Total candidates: {len(THR_GRID) * len(MDD_LIMITS)}")

    results_rows = []
    curves_cache: dict[float, pd.DataFrame] = {}

    for thr in THR_GRID:
        curve_ml = apply_ml_trigger(curve_base, pred, thr)
        curves_cache[thr] = curve_ml
        all_m = compute_all_metrics(curve_ml)

        h = all_m.get("HOLDOUT", {})
        t = all_m.get("TRAIN", {})
        a = all_m.get("ACID", {})

        for mdd_lim in MDD_LIMITS:
            mdd_train = t.get("mdd", -1.0)
            mdd_holdout = h.get("mdd", -1.0)
            feasible = True
            if mdd_lim is not None:
                if mdd_train < mdd_lim or mdd_holdout < mdd_lim:
                    feasible = False

            results_rows.append({
                "candidate_id": f"THR{thr:.2f}_MDD{abs(mdd_lim)*100:.0f}pct" if mdd_lim is not None else f"THR{thr:.2f}_MDDnone",
                "thr": thr, "mdd_limit": mdd_lim, "feasible": feasible,
                "holdout_equity": h.get("equity_final", 0), "holdout_cagr": h.get("cagr", 0),
                "holdout_mdd": h.get("mdd", 0), "holdout_sharpe": h.get("sharpe", 0),
                "holdout_switches": h.get("switches", 0), "holdout_cash_pct": h.get("cash_pct", 0),
                "train_equity": t.get("equity_final", 0), "train_cagr": t.get("cagr", 0),
                "train_mdd": t.get("mdd", 0), "train_sharpe": t.get("sharpe", 0),
                "acid_equity": a.get("equity_final", 0), "acid_cagr": a.get("cagr", 0),
                "acid_mdd": a.get("mdd", 0), "acid_sharpe": a.get("sharpe", 0),
                "acid_switches": a.get("switches", 0), "acid_cash_pct": a.get("cash_pct", 0),
            })

    df_abl = pd.DataFrame(results_rows)
    OUT_ABLATION.parent.mkdir(parents=True, exist_ok=True)
    df_abl.to_parquet(OUT_ABLATION, index=False)
    print(f"\n  Ablation results saved: {OUT_ABLATION}")

    print("\n" + "=" * 80)
    print("ABLATION RESULTS — ALL CANDIDATES")
    print("=" * 80)
    cols_show = ["candidate_id", "thr", "mdd_limit", "feasible",
                 "holdout_equity", "holdout_cagr", "holdout_mdd", "holdout_sharpe",
                 "holdout_switches", "holdout_cash_pct",
                 "acid_equity", "acid_mdd", "acid_sharpe"]
    print(df_abl[cols_show].to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    print("\n[5/6] Selecting winner...")
    feasible = df_abl[df_abl["feasible"]].copy()
    if feasible.empty:
        print("  WARNING: No feasible candidates! Relaxing MDD constraint...")
        feasible = df_abl.copy()

    feasible = feasible.sort_values(
        ["holdout_sharpe", "holdout_equity", "holdout_mdd"],
        ascending=[False, False, False],
    )

    print("\n  FEASIBLE CANDIDATES (sorted by Sharpe desc):")
    print(feasible[cols_show].to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    winner = feasible.iloc[0]
    winner_thr = float(winner["thr"])
    winner_mdd_lim = winner["mdd_limit"]
    winner_id = str(winner["candidate_id"])
    print(f"\n  >>> WINNER: {winner_id} (thr={winner_thr}, mdd_limit={winner_mdd_lim})")
    print(f"      HOLDOUT: equity=R${winner['holdout_equity']:,.0f}, CAGR={winner['holdout_cagr']*100:.1f}%, MDD={winner['holdout_mdd']*100:.1f}%, Sharpe={winner['holdout_sharpe']:.3f}")
    print(f"      ACID:    equity=R${winner['acid_equity']:,.0f}, MDD={winner['acid_mdd']*100:.1f}%, Sharpe={winner['acid_sharpe']:.3f}")

    winner_curve = curves_cache[winner_thr].copy()
    winner_curve.to_parquet(OUT_WINNER_CURVE, index=False)
    print(f"  Winner curve saved: {OUT_WINNER_CURVE}")

    print("\n[6/6] Building Plotly dashboard...")
    c060_orig = pd.read_parquet(INPUT_C060_CURVE).copy()
    c060_orig["date"] = pd.to_datetime(c060_orig["date"]).dt.normalize()
    c060_orig = c060_orig.sort_values("date")
    if "drawdown" not in c060_orig.columns:
        c060_orig["drawdown"] = drawdown(c060_orig["equity_end_norm"]).values
    if "switches_cumsum" not in c060_orig.columns and "state_cash" in c060_orig.columns:
        c060_orig["switches_cumsum"] = (c060_orig["state_cash"].diff().abs() == 1).fillna(False).astype(int).cumsum()

    c060_exp_curve_path = ROOT / "src/data_engine/portfolio/CTO_C060_EXPANDED_UNIVERSE_CURVE.parquet"
    c060_exp = pd.read_parquet(c060_exp_curve_path).copy()
    c060_exp["date"] = pd.to_datetime(c060_exp["date"]).dt.normalize()
    c060_exp = c060_exp.sort_values("date")

    phase8 = pd.read_parquet(INPUT_T108_WINNER).copy()
    phase8["date"] = pd.to_datetime(phase8["date"]).dt.normalize()
    phase8 = phase8.sort_values("date")
    if "drawdown" not in phase8.columns:
        phase8["drawdown"] = drawdown(phase8["equity_end_norm"]).values
    if "switches_cumsum" not in phase8.columns and "state_cash" in phase8.columns:
        phase8["switches_cumsum"] = (phase8["state_cash"].diff().abs() == 1).fillna(False).astype(int).cumsum()

    winner_label = f"NOVA WINNER ({winner_id})"
    make_plotly(winner_curve, winner_label, c060_orig, c060_exp, phase8)

    print("\n" + "=" * 80)
    print("FINAL COMPARISON — HOLDOUT")
    print("=" * 80)
    final_rows = []
    for label, crv in [
        ("Phase8 Winner (N15 thr=0.05)", phase8),
        ("C060 Original (BR N10 thr=0.25)", c060_orig),
        ("C060 Expanded (BR+BDR N10 thr=0.25)", c060_exp),
        (winner_label, winner_curve),
    ]:
        ho = crv[crv["split"] == "HOLDOUT"] if "split" in crv.columns else crv[crv["date"] >= HOLDOUT_START]
        if len(ho) < 2:
            continue
        m = metrics(ho["equity_end_norm"])
        sw = float((ho["state_cash"].diff().abs() == 1).sum()) if "state_cash" in ho.columns else 0.0
        cp = float(ho["state_cash"].mean()) if "state_cash" in ho.columns else 0.0
        final_rows.append({"Curve": label, **m, "switches": sw, "cash_pct": cp})

    df_final = pd.DataFrame(final_rows)
    print(df_final.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    print("\n" + "=" * 80)
    print("FINAL COMPARISON — ACID WINDOW")
    print("=" * 80)
    acid_rows = []
    for label, crv in [
        ("Phase8 Winner (N15 thr=0.05)", phase8),
        ("C060 Original (BR N10 thr=0.25)", c060_orig),
        ("C060 Expanded (BR+BDR N10 thr=0.25)", c060_exp),
        (winner_label, winner_curve),
    ]:
        ho = crv[crv["split"] == "HOLDOUT"] if "split" in crv.columns else crv[crv["date"] >= HOLDOUT_START]
        ac = ho[(ho["date"] >= ACID_START) & (ho["date"] <= ACID_END)]
        if len(ac) < 2:
            continue
        m = metrics(ac["equity_end_norm"])
        sw = float((ac["state_cash"].diff().abs() == 1).sum()) if "state_cash" in ac.columns else 0.0
        cp = float(ac["state_cash"].mean()) if "state_cash" in ac.columns else 0.0
        acid_rows.append({"Curve": label, **m, "switches": sw, "cash_pct": cp})

    df_acid = pd.DataFrame(acid_rows)
    print(df_acid.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    print(f"\n{'=' * 80}")
    print("DONE.")
    print(f"  Ablation: {OUT_ABLATION}")
    print(f"  Winner curve: {OUT_WINNER_CURVE}")
    print(f"  Dashboard: {OUT_PLOT}")
    print(f"{'=' * 80}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
