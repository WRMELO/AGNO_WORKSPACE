#!/home/wilson/AGNO_WORKSPACE/.venv/bin/python
"""CTO diagnostic: US market (S&P 500 in BRL) vs CDI during C060X cash periods.

Answers: when C060X is in cash (CDI), would S&P 500 in BRL (net of FX+IOF costs)
have been better?
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

if not ("agno_env" in sys.prefix or ".venv" in sys.prefix):
    raise RuntimeError("FATAL: Not in agno_env/.venv")

ROOT = Path("/home/wilson/AGNO_WORKSPACE")

INPUT_C060X_CURVE = ROOT / "src/data_engine/portfolio/CTO_C060_EXPANDED_ABLATION_WINNER_CURVE.parquet"
INPUT_MACRO = ROOT / "src/data_engine/ssot/SSOT_MACRO_EXPANDED.parquet"
INPUT_PTAX = ROOT / "src/data_engine/ssot/SSOT_FX_PTAX_USDBRL.parquet"

TRAIN_END = pd.Timestamp("2022-12-30")
HOLDOUT_START = pd.Timestamp("2023-01-02")
HOLDOUT_END = pd.Timestamp("2026-02-26")
ACID_START = pd.Timestamp("2024-11-01")
ACID_END = pd.Timestamp("2025-11-30")

FX_IOF_ONE_WAY = 0.0078


def main() -> int:
    print("=" * 80)
    print("CTO DIAGNOSTIC: S&P 500 em BRL vs CDI nos períodos de caixa da C060X")
    print("=" * 80)

    print("\n[1/5] Loading data...")
    c060x = pd.read_parquet(INPUT_C060X_CURVE)
    c060x["date"] = pd.to_datetime(c060x["date"]).dt.normalize()
    c060x = c060x.sort_values("date").reset_index(drop=True)

    macro = pd.read_parquet(INPUT_MACRO)
    macro["date"] = pd.to_datetime(macro["date"]).dt.normalize()
    macro = macro.sort_values("date")

    ptax = pd.read_parquet(INPUT_PTAX)
    ptax["date"] = pd.to_datetime(ptax["date"]).dt.normalize()
    ptax = ptax.sort_values("date")

    print(f"  C060X curve: {len(c060x)} rows")
    print(f"  Macro: {len(macro)} rows, cols: {macro.columns.tolist()}")
    print(f"  PTAX: {len(ptax)} rows, cols: {ptax.columns.tolist()}")

    print("\n[2/5] Building daily comparison frame...")

    sp500_col = None
    for c in ["sp500_close", "sp500", "spx_close"]:
        if c in macro.columns:
            sp500_col = c
            break
    if sp500_col is None:
        print("  WARNING: sp500 column not found in macro. Available:", macro.columns.tolist())
        print("  Trying ibov as proxy... NO — need actual S&P data.")
        return 1

    ptax_col = None
    for c in ["usdbrl_ptax", "ptax_sell", "ptax_usdbrl", "ptax", "close"]:
        if c in ptax.columns:
            ptax_col = c
            break
    if ptax_col is None:
        print("  WARNING: ptax column not found. Available:", ptax.columns.tolist())
        return 1

    print(f"  Using S&P 500 column: {sp500_col}")
    print(f"  Using PTAX column: {ptax_col}")

    df = c060x[["date", "split", "state_cash", "ret_cdi"]].copy()
    df = df.merge(macro[["date", sp500_col, "cdi_log_daily"]], on="date", how="inner")
    df = df.merge(ptax[["date", ptax_col]], on="date", how="inner")
    df = df.sort_values("date").reset_index(drop=True)

    df["sp500_usd"] = pd.to_numeric(df[sp500_col], errors="coerce")
    df["ptax_val"] = pd.to_numeric(df[ptax_col], errors="coerce")
    df["sp500_brl"] = df["sp500_usd"] * df["ptax_val"]

    df["logret_sp500_usd"] = np.log(df["sp500_usd"] / df["sp500_usd"].shift(1))
    df["logret_ptax"] = np.log(df["ptax_val"] / df["ptax_val"].shift(1))
    df["logret_sp500_brl"] = df["logret_sp500_usd"] + df["logret_ptax"]
    df["logret_cdi"] = pd.to_numeric(df["cdi_log_daily"], errors="coerce").fillna(0.0)

    df = df.dropna(subset=["logret_sp500_brl"]).reset_index(drop=True)
    print(f"  Merged frame: {len(df)} rows")

    print("\n[3/5] Analyzing cash periods...")
    df["is_cash"] = (df["state_cash"] == 1).astype(int)
    df["cash_block"] = (df["is_cash"].diff().abs() == 1).cumsum()

    for split_name, split_filter in [("FULL", df["date"] > pd.Timestamp("1900-01-01")),
                                      ("TRAIN", df["split"] == "TRAIN"),
                                      ("HOLDOUT", df["split"] == "HOLDOUT"),
                                      ("ACID", (df["split"] == "HOLDOUT") & (df["date"] >= ACID_START) & (df["date"] <= ACID_END))]:
        sub = df[split_filter].copy()
        cash_days = sub[sub["is_cash"] == 1]
        market_days = sub[sub["is_cash"] == 0]

        print(f"\n  --- {split_name} ---")
        print(f"  Total days: {len(sub)}")
        print(f"  Cash days: {len(cash_days)} ({len(cash_days)/max(len(sub),1)*100:.1f}%)")
        print(f"  Market days: {len(market_days)} ({len(market_days)/max(len(sub),1)*100:.1f}%)")

        if len(cash_days) > 0:
            cdi_accum = (np.exp(cash_days["logret_cdi"].sum()) - 1) * 100
            sp500_brl_accum = (np.exp(cash_days["logret_sp500_brl"].sum()) - 1) * 100

            cdi_ann = cash_days["logret_cdi"].mean() * 252 * 100
            sp500_brl_ann = cash_days["logret_sp500_brl"].mean() * 252 * 100
            sp500_usd_ann = cash_days["logret_sp500_usd"].mean() * 252 * 100
            ptax_ann = cash_days["logret_ptax"].mean() * 252 * 100

            cash_blocks = cash_days.groupby("cash_block").size()
            n_blocks = len(cash_blocks)
            avg_block_len = cash_blocks.mean()

            cost_per_switch = FX_IOF_ONE_WAY * 2 * 100
            total_switch_cost = n_blocks * cost_per_switch

            sp500_brl_net = sp500_brl_accum - total_switch_cost

            print(f"  Cash blocks: {n_blocks} (avg length: {avg_block_len:.1f} days)")
            print(f"  CDI accumulated: {cdi_accum:+.2f}% ({cdi_ann:.1f}% ann.)")
            print(f"  S&P 500 USD accumulated (same days): {(np.exp(cash_days['logret_sp500_usd'].sum()) - 1)*100:+.2f}% ({sp500_usd_ann:.1f}% ann.)")
            print(f"  PTAX (USD/BRL) accumulated (same days): {(np.exp(cash_days['logret_ptax'].sum()) - 1)*100:+.2f}% ({ptax_ann:.1f}% ann.)")
            print(f"  S&P 500 em BRL accumulated (same days): {sp500_brl_accum:+.2f}% ({sp500_brl_ann:.1f}% ann.)")
            print(f"  Switch cost ({n_blocks} round-trips × {cost_per_switch:.2f}%): -{total_switch_cost:.2f}%")
            print(f"  S&P 500 em BRL NET of switch costs: {sp500_brl_net:+.2f}%")
            print(f"  >>> DIFERENÇA (S&P BRL net - CDI): {sp500_brl_net - cdi_accum:+.2f}pp")

            if sp500_brl_net > cdi_accum:
                print(f"  >>> VEREDICTO: US GANHA por {sp500_brl_net - cdi_accum:.2f}pp líquidos")
            else:
                print(f"  >>> VEREDICTO: CDI GANHA por {cdi_accum - sp500_brl_net:.2f}pp líquidos")

    print("\n[4/5] Day-by-day comparison: logret_sp500_brl vs logret_cdi on cash days...")
    for split_name, split_filter in [("HOLDOUT", df["split"] == "HOLDOUT"),
                                      ("ACID", (df["split"] == "HOLDOUT") & (df["date"] >= ACID_START) & (df["date"] <= ACID_END))]:
        cash = df[split_filter & (df["is_cash"] == 1)].copy()
        if len(cash) == 0:
            continue

        cash["us_beats_cdi"] = cash["logret_sp500_brl"] > cash["logret_cdi"]
        pct_us_wins = cash["us_beats_cdi"].mean() * 100

        cash["excess_us_over_cdi"] = cash["logret_sp500_brl"] - cash["logret_cdi"]
        avg_excess = cash["excess_us_over_cdi"].mean() * 252 * 100
        median_excess = cash["excess_us_over_cdi"].median() * 252 * 100

        print(f"\n  --- {split_name} cash days ({len(cash)} days) ---")
        print(f"  Days US logret > CDI: {pct_us_wins:.1f}%")
        print(f"  Avg excess (US - CDI) annualized: {avg_excess:+.1f}%")
        print(f"  Median excess (US - CDI) annualized: {median_excess:+.1f}%")

        sp500_dd = cash["logret_sp500_brl"].cumsum().apply(lambda x: x - cash["logret_sp500_brl"].cumsum().cummax().loc[x.name] if hasattr(x, 'name') else 0)
        sp500_brl_cumret = np.exp(cash["logret_sp500_brl"].cumsum()) - 1
        max_dd_us = (sp500_brl_cumret - sp500_brl_cumret.cummax()).min()
        print(f"  S&P BRL max drawdown during cash periods: {max_dd_us*100:.1f}%")

    print("\n[5/5] Quarterly breakdown — HOLDOUT cash periods...")
    holdout_cash = df[(df["split"] == "HOLDOUT") & (df["is_cash"] == 1)].copy()
    if len(holdout_cash) > 0:
        holdout_cash["quarter"] = holdout_cash["date"].dt.to_period("Q").astype(str)
        qtr = holdout_cash.groupby("quarter").agg(
            days=("logret_cdi", "size"),
            cdi_accum=("logret_cdi", "sum"),
            sp500_brl_accum=("logret_sp500_brl", "sum"),
            sp500_usd_accum=("logret_sp500_usd", "sum"),
            ptax_accum=("logret_ptax", "sum"),
        ).reset_index()
        qtr["cdi_pct"] = (np.exp(qtr["cdi_accum"]) - 1) * 100
        qtr["sp500_brl_pct"] = (np.exp(qtr["sp500_brl_accum"]) - 1) * 100
        qtr["excess_pp"] = qtr["sp500_brl_pct"] - qtr["cdi_pct"]

        print(f"\n  {'Quarter':<10} {'Days':>5} {'CDI%':>8} {'SP BRL%':>9} {'Excess':>8}")
        print(f"  {'-'*10} {'-'*5} {'-'*8} {'-'*9} {'-'*8}")
        for _, r in qtr.iterrows():
            marker = " <<<" if r["excess_pp"] > 0 else ""
            print(f"  {r['quarter']:<10} {r['days']:>5.0f} {r['cdi_pct']:>+8.2f} {r['sp500_brl_pct']:>+9.2f} {r['excess_pp']:>+8.2f}{marker}")

        total_cdi = (np.exp(holdout_cash["logret_cdi"].sum()) - 1) * 100
        total_sp = (np.exp(holdout_cash["logret_sp500_brl"].sum()) - 1) * 100
        print(f"  {'TOTAL':<10} {len(holdout_cash):>5} {total_cdi:>+8.2f} {total_sp:>+9.2f} {total_sp-total_cdi:>+8.2f}")

    print(f"\n{'=' * 80}")
    print("DONE.")
    print(f"{'=' * 80}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
