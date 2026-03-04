#!/home/wilson/AGNO_WORKSPACE/.venv/bin/python
"""CTO exploratory ablation: US engine — TopN × Cadence × MDD hard constraint.

Grid:
  TopN      : [5, 7, 9, 11, 13, 15]
  Cadence   : [3, 5, 8]
  MDD filter: [None, -0.10, -0.15, -0.20, -0.25]  (applied on HOLDOUT)

Total candidates simulated: 6 × 3 = 18
Total selection scenarios : 18 × 5 = 90
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path("/home/wilson/AGNO_WORKSPACE")

IN_SCORES = ROOT / "src/data_engine/features/T120_M3_US_SCORES_DAILY.parquet"
IN_SSOT_US = ROOT / "src/data_engine/ssot/SSOT_CANONICAL_BASE_US.parquet"
IN_MACRO = ROOT / "src/data_engine/ssot/SSOT_MACRO_EXPANDED.parquet"
IN_UNIVERSE = ROOT / "src/data_engine/ssot/SSOT_US_UNIVERSE_OPERATIONAL_PHASE10.parquet"

INITIAL_CAPITAL = 100_000.0
COST_RATE = 0.0001

TOP_N_LIST = [5, 7, 9, 11, 13, 15]
CADENCE_LIST = [3, 5, 8]
MDD_LIMITS_HOLDOUT = [None, -0.10, -0.15, -0.20, -0.25]

TRAIN_START = pd.Timestamp("2018-07-02")
TRAIN_END = pd.Timestamp("2022-12-30")
HOLDOUT_START = pd.Timestamp("2023-01-02")
HOLDOUT_END = pd.Timestamp("2026-02-26")
ACID_US_START = pd.Timestamp("2025-03-06")
ACID_US_END = pd.Timestamp("2025-05-09")


def compute_mdd(equity: pd.Series) -> float:
    eq = pd.to_numeric(equity, errors="coerce").astype(float)
    if len(eq) == 0:
        return 0.0
    return float((eq / eq.cummax() - 1.0).min())


def compute_sharpe(ret_1d: pd.Series) -> float:
    r = pd.to_numeric(ret_1d, errors="coerce").fillna(0.0).astype(float)
    if len(r) < 2:
        return 0.0
    sd = float(r.std(ddof=1))
    if sd <= 0:
        return 0.0
    return float(np.sqrt(252.0) * r.mean() / sd)


def compute_cagr(equity: pd.Series) -> float:
    eq = pd.to_numeric(equity, errors="coerce").astype(float)
    if len(eq) < 2 or eq.iloc[0] <= 0:
        return 0.0
    years = len(eq) / 252.0
    if years <= 0:
        return 0.0
    return float((eq.iloc[-1] / eq.iloc[0]) ** (1.0 / years) - 1.0)


def metrics_from_equity(equity: pd.Series) -> dict[str, float]:
    eq = pd.to_numeric(equity, errors="coerce").astype(float)
    ret = eq.pct_change().fillna(0.0)
    return {
        "equity_final": float(eq.iloc[-1]) if len(eq) else float(INITIAL_CAPITAL),
        "cagr": compute_cagr(eq),
        "mdd": compute_mdd(eq),
        "sharpe": compute_sharpe(ret),
    }


def split_label(d: pd.Timestamp) -> str:
    return "TRAIN" if d <= TRAIN_END else "HOLDOUT"


def simulate_candidate(
    *,
    top_n: int,
    cadence_days: int,
    by_day: dict[pd.Timestamp, pd.DataFrame],
    px_wide: pd.DataFrame,
    macro_day: pd.DataFrame,
    sim_dates: list[pd.Timestamp],
) -> dict[str, Any]:
    prices_start = float(macro_day.loc[TRAIN_START, "sp500_close"])
    cash_bench = INITIAL_CAPITAL
    sp500_bench = INITIAL_CAPITAL
    cash = INITIAL_CAPITAL
    positions: dict[str, float] = {}
    days_since_rebal = 10**9
    switches = 0
    total_cost = 0.0
    total_cost_train = 0.0
    total_cost_holdout = 0.0

    curve_rows: list[dict[str, Any]] = []

    for i, d in enumerate(sim_dates):
        split = split_label(d)
        cash_log = float(macro_day.loc[d, "cash_log_daily_us"])
        cash *= float(np.exp(cash_log))
        cash_bench *= float(np.exp(cash_log))

        px_row = px_wide.loc[d]
        current_values: dict[str, float] = {}
        for t, q in positions.items():
            px = float(px_row.get(t, np.nan))
            if np.isfinite(px) and px > 0 and q > 0:
                current_values[t] = q * px
        port_before = float(sum(current_values.values()))
        equity_before = cash + port_before

        do_rebal = (i == 0) or (days_since_rebal >= cadence_days)

        if do_rebal:
            day_scores = by_day.get(d, pd.DataFrame()).copy()
            ranked = day_scores.sort_values(["m3_rank_us_exec", "ticker"], ascending=[True, True])
            selected = ranked.head(top_n)["ticker"].tolist() if len(ranked) else []

            target_values: dict[str, float] = {}
            if selected:
                target_w = 1.0 / len(selected)
                for t in selected:
                    px = float(px_row.get(t, np.nan))
                    if np.isfinite(px) and px > 0:
                        target_values[t] = equity_before * target_w

            all_tickers = set(current_values.keys()).union(set(target_values.keys()))
            sells = buys = 0.0
            new_positions: dict[str, float] = {}

            for t in sorted(all_tickers):
                cur_v = float(current_values.get(t, 0.0))
                tgt_v = float(target_values.get(t, 0.0))
                delta = tgt_v - cur_v
                if delta < 0:
                    sells += -delta
                elif delta > 0:
                    buys += delta
                if tgt_v > 0:
                    px = float(px_row.get(t, np.nan))
                    if np.isfinite(px) and px > 0:
                        new_positions[t] = tgt_v / px

            cost_paid = float((sells + buys) * COST_RATE)
            total_cost += cost_paid
            if split == "TRAIN":
                total_cost_train += cost_paid
            else:
                total_cost_holdout += cost_paid

            cash = cash + sells - buys - cost_paid
            if cash < 0:
                cash = max(cash, -1e-6)
            prev_set = set(positions.keys())
            positions = {k: v for k, v in new_positions.items() if v > 0}
            if i > 0 and prev_set != set(positions.keys()):
                switches += 1
            days_since_rebal = 0
        else:
            days_since_rebal += 1

        port_value = sum(
            q * float(px_row.get(t, 0.0))
            for t, q in positions.items()
            if np.isfinite(float(px_row.get(t, np.nan))) and float(px_row.get(t, 0.0)) > 0
        )
        equity_strategy = float(cash + port_value)
        spx = float(macro_day.loc[d, "sp500_close"])
        sp500_bench = float(INITIAL_CAPITAL * (spx / prices_start))

        curve_rows.append({
            "date": d,
            "split": split,
            "equity_strategy": equity_strategy,
            "equity_sp500_bh": sp500_bench,
            "equity_cash_fedfunds": float(cash_bench),
        })

    curve = pd.DataFrame(curve_rows).sort_values("date").reset_index(drop=True)

    train = curve[curve["split"] == "TRAIN"].copy()
    holdout = curve[curve["split"] == "HOLDOUT"].copy()
    acid = holdout[(holdout["date"] >= ACID_US_START) & (holdout["date"] <= ACID_US_END)].copy()

    m_train = metrics_from_equity(train["equity_strategy"])
    m_holdout = metrics_from_equity(holdout["equity_strategy"])
    m_acid = metrics_from_equity(acid["equity_strategy"])
    m_sp500_h = metrics_from_equity(holdout["equity_sp500_bh"])

    return {
        "top_n": top_n,
        "cadence_days": cadence_days,
        "equity_train": m_train["equity_final"],
        "cagr_train": m_train["cagr"],
        "mdd_train": m_train["mdd"],
        "sharpe_train": m_train["sharpe"],
        "equity_holdout": m_holdout["equity_final"],
        "cagr_holdout": m_holdout["cagr"],
        "mdd_holdout": m_holdout["mdd"],
        "sharpe_holdout": m_holdout["sharpe"],
        "equity_acid_us": m_acid["equity_final"],
        "cagr_acid_us": m_acid["cagr"],
        "mdd_acid_us": m_acid["mdd"],
        "sharpe_acid_us": m_acid["sharpe"],
        "sp500_sharpe_holdout": m_sp500_h["sharpe"],
        "sp500_cagr_holdout": m_sp500_h["cagr"],
        "sp500_mdd_holdout": m_sp500_h["mdd"],
        "switches": switches,
        "total_cost": total_cost,
        "total_cost_train": total_cost_train,
        "total_cost_holdout": total_cost_holdout,
    }


def main() -> int:
    print("=" * 80)
    print("CTO ABLATION: US Engine — TopN × Cadence × MDD constraint")
    print("=" * 80)

    universe = pd.read_parquet(IN_UNIVERSE, columns=["ticker"]).copy()
    universe["ticker"] = universe["ticker"].astype(str).str.upper().str.strip()
    use_tickers = set(universe["ticker"].tolist())
    print(f"  Universe: {len(use_tickers)} tickers")

    scores = pd.read_parquet(IN_SCORES).copy()
    scores["date"] = pd.to_datetime(scores["date"], errors="coerce").dt.normalize()
    scores["ticker"] = scores["ticker"].astype(str).str.upper().str.strip()
    scores = scores[scores["ticker"].isin(use_tickers)].copy()
    scores_valid = scores.dropna(subset=["score_m3_us_exec", "m3_rank_us_exec"]).copy()
    scores_valid["m3_rank_us_exec"] = pd.to_numeric(scores_valid["m3_rank_us_exec"], errors="coerce")
    scores_valid = scores_valid.dropna(subset=["m3_rank_us_exec"]).copy()
    scores_valid["m3_rank_us_exec"] = scores_valid["m3_rank_us_exec"].astype(int)

    by_day: dict[pd.Timestamp, pd.DataFrame] = {}
    for d, g in scores_valid.groupby("date", sort=True):
        by_day[pd.Timestamp(d)] = g.sort_values(["m3_rank_us_exec", "ticker"], ascending=[True, True]).copy()

    ssot = pd.read_parquet(IN_SSOT_US, columns=["date", "ticker", "close_operational"]).copy()
    ssot["date"] = pd.to_datetime(ssot["date"], errors="coerce").dt.normalize()
    ssot["ticker"] = ssot["ticker"].astype(str).str.upper().str.strip()
    ssot["close_operational"] = pd.to_numeric(ssot["close_operational"], errors="coerce")
    ssot = ssot.dropna(subset=["date", "ticker", "close_operational"]).copy()
    ssot = ssot[(ssot["close_operational"] > 0) & (ssot["ticker"].isin(use_tickers))].copy()
    px_wide = ssot.pivot_table(index="date", columns="ticker", values="close_operational", aggfunc="first").sort_index().ffill()

    macro = pd.read_parquet(IN_MACRO, columns=["date", "sp500_close", "fed_funds_rate"]).copy()
    macro["date"] = pd.to_datetime(macro["date"], errors="coerce").dt.normalize()
    macro["sp500_close"] = pd.to_numeric(macro["sp500_close"], errors="coerce")
    macro["fed_funds_rate"] = pd.to_numeric(macro["fed_funds_rate"], errors="coerce")
    macro = macro.dropna(subset=["date"]).drop_duplicates(subset=["date"], keep="last").sort_values("date")
    macro["sp500_close"] = macro["sp500_close"].ffill().bfill()
    macro["fed_funds_rate"] = macro["fed_funds_rate"].ffill().bfill()
    macro["cash_log_daily_us"] = np.log1p((macro["fed_funds_rate"] / 100.0) / 252.0)
    macro_day = macro.set_index("date")

    score_dates = set(by_day.keys())
    sim_dates = sorted(set(px_wide.index).intersection(set(macro_day.index)).intersection(score_dates))
    sim_dates = [d for d in sim_dates if TRAIN_START <= d <= HOLDOUT_END]
    print(f"  Sim dates: {len(sim_dates)} (from {sim_dates[0].date()} to {sim_dates[-1].date()})")

    # --- Run simulations ---
    print(f"\n[1/3] Running {len(TOP_N_LIST) * len(CADENCE_LIST)} simulations...")
    results: list[dict[str, Any]] = []
    for top_n in TOP_N_LIST:
        for cadence in CADENCE_LIST:
            print(f"  TopN={top_n:>2}, Cadence={cadence:>2} ...", end=" ", flush=True)
            r = simulate_candidate(
                top_n=top_n,
                cadence_days=cadence,
                by_day=by_day,
                px_wide=px_wide,
                macro_day=macro_day,
                sim_dates=sim_dates,
            )
            results.append(r)
            print(f"equity_holdout={r['equity_holdout']:>12,.2f}  mdd_holdout={r['mdd_holdout']:>7.2%}  sharpe_holdout={r['sharpe_holdout']:>6.3f}")

    df = pd.DataFrame(results)

    # --- Full table ---
    print("\n" + "=" * 80)
    print("[2/3] FULL ABLATION TABLE (all 18 candidates)")
    print("=" * 80)
    cols_show = ["top_n", "cadence_days", "sharpe_train", "cagr_train", "mdd_train",
                 "sharpe_holdout", "cagr_holdout", "mdd_holdout", "equity_holdout",
                 "sharpe_acid_us", "mdd_acid_us", "switches", "total_cost"]
    print(df[cols_show].to_string(index=False, float_format=lambda x: f"{x:>10.4f}"))

    # --- SP500 benchmarks ---
    sp500_sharpe = df["sp500_sharpe_holdout"].iloc[0]
    sp500_cagr = df["sp500_cagr_holdout"].iloc[0]
    sp500_mdd = df["sp500_mdd_holdout"].iloc[0]
    print(f"\n  SP500 HOLDOUT: sharpe={sp500_sharpe:.3f}, cagr={sp500_cagr:.2%}, mdd={sp500_mdd:.2%}")

    # --- Selection under MDD constraints ---
    print("\n" + "=" * 80)
    print("[3/3] WINNER SELECTION UNDER DIFFERENT MDD CONSTRAINTS")
    print("=" * 80)

    selection_rows: list[dict[str, Any]] = []
    for mdd_lim in MDD_LIMITS_HOLDOUT:
        lim_label = f"{abs(mdd_lim)*100:.0f}%" if mdd_lim is not None else "None"
        if mdd_lim is not None:
            feasible = df[df["mdd_holdout"] >= mdd_lim].copy()
        else:
            feasible = df.copy()

        n_feasible = len(feasible)
        if n_feasible == 0:
            print(f"\n  MDD_HOLDOUT >= {lim_label}: 0 feasible candidates")
            selection_rows.append({
                "mdd_limit": lim_label, "n_feasible": 0,
                "winner_top_n": None, "winner_cadence": None,
                "sharpe_holdout": None, "cagr_holdout": None,
                "mdd_holdout": None, "equity_holdout": None,
                "sharpe_train": None, "mdd_train": None,
                "beats_sp500_sharpe": None,
            })
            continue

        winner = feasible.sort_values(
            by=["sharpe_train", "cagr_train", "mdd_train", "total_cost_train", "top_n", "cadence_days"],
            ascending=[False, False, False, True, True, True],
        ).iloc[0]

        beats = winner["sharpe_holdout"] > sp500_sharpe
        print(f"\n  MDD_HOLDOUT >= {lim_label}: {n_feasible} feasible")
        print(f"    Winner: TopN={int(winner['top_n'])}, Cadence={int(winner['cadence_days'])}")
        print(f"    HOLDOUT: sharpe={winner['sharpe_holdout']:.3f}, cagr={winner['cagr_holdout']:.2%}, "
              f"mdd={winner['mdd_holdout']:.2%}, equity=${winner['equity_holdout']:,.0f}")
        print(f"    TRAIN:   sharpe={winner['sharpe_train']:.3f}, cagr={winner['cagr_train']:.2%}, "
              f"mdd={winner['mdd_train']:.2%}")
        print(f"    ACID_US: sharpe={winner['sharpe_acid_us']:.3f}, mdd={winner['mdd_acid_us']:.2%}")
        print(f"    Beats SP500 Sharpe? {'YES' if beats else 'NO'} ({winner['sharpe_holdout']:.3f} vs {sp500_sharpe:.3f})")

        selection_rows.append({
            "mdd_limit": lim_label,
            "n_feasible": n_feasible,
            "winner_top_n": int(winner["top_n"]),
            "winner_cadence": int(winner["cadence_days"]),
            "sharpe_holdout": float(winner["sharpe_holdout"]),
            "cagr_holdout": float(winner["cagr_holdout"]),
            "mdd_holdout": float(winner["mdd_holdout"]),
            "equity_holdout": float(winner["equity_holdout"]),
            "sharpe_train": float(winner["sharpe_train"]),
            "mdd_train": float(winner["mdd_train"]),
            "beats_sp500_sharpe": bool(beats),
        })

    print("\n" + "=" * 80)
    print("COMPARATIVE SELECTION TABLE")
    print("=" * 80)
    sel_df = pd.DataFrame(selection_rows)
    print(sel_df.to_string(index=False))

    # --- Also show: for each MDD limit, top-3 candidates by sharpe_holdout ---
    print("\n" + "=" * 80)
    print("TOP-3 CANDIDATES PER MDD LIMIT (ranked by sharpe_holdout)")
    print("=" * 80)
    for mdd_lim in MDD_LIMITS_HOLDOUT:
        lim_label = f"{abs(mdd_lim)*100:.0f}%" if mdd_lim is not None else "None"
        if mdd_lim is not None:
            feasible = df[df["mdd_holdout"] >= mdd_lim].copy()
        else:
            feasible = df.copy()
        if feasible.empty:
            print(f"\n  MDD <= {lim_label}: no candidates")
            continue
        top3 = feasible.sort_values("sharpe_holdout", ascending=False).head(3)
        print(f"\n  MDD_HOLDOUT >= {lim_label} ({len(feasible)} feasible):")
        for _, row in top3.iterrows():
            print(f"    TopN={int(row['top_n']):>2} Cad={int(row['cadence_days']):>2} | "
                  f"sharpe_h={row['sharpe_holdout']:.3f} cagr_h={row['cagr_holdout']:.2%} "
                  f"mdd_h={row['mdd_holdout']:.2%} eq_h=${row['equity_holdout']:>10,.0f} | "
                  f"sharpe_t={row['sharpe_train']:.3f} mdd_t={row['mdd_train']:.2%}")

    # --- Heatmap: sharpe_holdout by (top_n, cadence) ---
    print("\n" + "=" * 80)
    print("HEATMAP: sharpe_holdout by (TopN, Cadence)")
    print("=" * 80)
    pivot_sharpe = df.pivot_table(index="top_n", columns="cadence_days", values="sharpe_holdout")
    print(pivot_sharpe.to_string(float_format=lambda x: f"{x:.3f}"))

    print("\n" + "=" * 80)
    print("HEATMAP: mdd_holdout by (TopN, Cadence)")
    print("=" * 80)
    pivot_mdd = df.pivot_table(index="top_n", columns="cadence_days", values="mdd_holdout")
    print(pivot_mdd.to_string(float_format=lambda x: f"{x:.2%}"))

    print("\n" + "=" * 80)
    print("HEATMAP: cagr_holdout by (TopN, Cadence)")
    print("=" * 80)
    pivot_cagr = df.pivot_table(index="top_n", columns="cadence_days", values="cagr_holdout")
    print(pivot_cagr.to_string(float_format=lambda x: f"{x:.2%}"))

    print("\n" + "=" * 80)
    print("DONE — CTO diagnostic ablation complete")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
