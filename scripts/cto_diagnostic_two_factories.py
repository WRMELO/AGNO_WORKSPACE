#!/home/wilson/AGNO_WORKSPACE/.venv/bin/python
"""CTO diagnostic: Factory US — M3 engine on S&P 500 in USD, Treasury as tank.

Exploratory run: no ML trigger (always in market), just M3 dual-mode motor
on S&P 500 universe in USD. Treasury (Fed funds rate) as cash return.
Then consolidate with C060X (Factory BR) at various splits.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

if not ("agno_env" in sys.prefix or ".venv" in sys.prefix):
    raise RuntimeError("FATAL: Not in agno_env/.venv")

ROOT = Path("/home/wilson/AGNO_WORKSPACE")
BASE_CAPITAL = 100_000.0

INPUT_US_RAW = ROOT / "src/data_engine/ssot/SSOT_US_MARKET_DATA_RAW.parquet"
INPUT_US_UNIVERSE = ROOT / "src/data_engine/ssot/SSOT_US_UNIVERSE_OPERATIONAL.parquet"
INPUT_US_BLACKLIST = ROOT / "src/data_engine/ssot/SSOT_US_BLACKLIST_OPERATIONAL.csv"
INPUT_MACRO = ROOT / "src/data_engine/ssot/SSOT_MACRO_EXPANDED.parquet"
INPUT_PTAX = ROOT / "src/data_engine/ssot/SSOT_FX_PTAX_USDBRL.parquet"
INPUT_C060X = ROOT / "src/data_engine/portfolio/CTO_C060_EXPANDED_ABLATION_WINNER_CURVE.parquet"

TRAIN_START = pd.Timestamp("2018-07-02")
TRAIN_END = pd.Timestamp("2022-12-30")
HOLDOUT_START = pd.Timestamp("2023-01-02")
HOLDOUT_END = pd.Timestamp("2026-02-26")
ACID_START = pd.Timestamp("2024-11-01")
ACID_END = pd.Timestamp("2025-11-30")

TOP_N = 10
CADENCE = 10
TARGET_PCT = 1.0 / TOP_N
MAX_PCT = 0.15
COST_BPS = 0.0001


def zscore_cross_section(values: pd.Series) -> pd.Series:
    x = pd.to_numeric(values, errors="coerce").astype(float)
    mu = x.mean()
    sd = x.std(ddof=0)
    if not np.isfinite(sd) or sd <= 0:
        return pd.Series(np.zeros(len(x), dtype=float), index=x.index)
    return (x - mu) / sd


def drawdown(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce").astype(float)
    return s / s.cummax() - 1.0


def metrics(equity: pd.Series, label: str = "") -> dict[str, float]:
    s = pd.to_numeric(equity, errors="coerce").astype(float)
    r = s.pct_change().fillna(0.0)
    years = max((len(s) - 1) / 252.0, 1.0 / 252.0)
    cagr = float((s.iloc[-1] / s.iloc[0]) ** (1.0 / years) - 1.0)
    mdd = float(drawdown(s).min())
    vol = float(r.std(ddof=0))
    sharpe = float((r.mean() / vol) * np.sqrt(252.0)) if vol > 0 else np.nan
    return {"equity_final": float(s.iloc[-1]), "cagr": cagr, "mdd": mdd, "sharpe": sharpe}


def run_simple_m3_backtest(px_wide: pd.DataFrame, fed_funds_daily: pd.Series,
                           sim_dates: list[pd.Timestamp], capital: float) -> pd.DataFrame:
    """Simple M3-based portfolio: always in market, rebalance every CADENCE days."""
    logret = np.log(px_wide / px_wide.shift(1))
    score_m0 = logret.rolling(window=62, min_periods=62).mean()
    ret_62 = logret.rolling(window=62, min_periods=62).sum()
    vol_62 = logret.rolling(window=62, min_periods=62).std(ddof=0)

    cash = capital
    positions: dict[str, float] = {}
    days_since_rebal = CADENCE + 1
    rows = []

    for i, d in enumerate(sim_dates):
        pos_value = 0.0
        if positions:
            for tk, shares in positions.items():
                if tk in px_wide.columns and d in px_wide.index:
                    price = px_wide.loc[d, tk]
                    if pd.notna(price) and price > 0:
                        pos_value += shares * price

        equity = cash + pos_value
        ff_rate = fed_funds_daily.get(d, 0.0)
        cash_ret_day = float(np.exp(ff_rate / 252.0) - 1.0) if ff_rate > 0 else 0.0

        should_rebal = (days_since_rebal >= CADENCE) and (d in score_m0.index)

        if should_rebal:
            m0_row = score_m0.loc[d].dropna()
            r_row = ret_62.loc[d].dropna()
            v_row = vol_62.loc[d].dropna()
            common = m0_row.index.intersection(r_row.index).intersection(v_row.index)

            if len(common) >= TOP_N:
                cs = pd.DataFrame({
                    "score_m0": m0_row[common], "ret_62": r_row[common], "vol_62": v_row[common]
                })
                cs["z_m0"] = zscore_cross_section(cs["score_m0"])
                cs["z_ret"] = zscore_cross_section(cs["ret_62"])
                cs["z_vol"] = zscore_cross_section(cs["vol_62"])
                cs["score_m3"] = cs["z_m0"] + cs["z_ret"] - cs["z_vol"]
                top = cs.nlargest(TOP_N, "score_m3")

                if positions:
                    for tk, shares in positions.items():
                        if tk in px_wide.columns and d in px_wide.index:
                            price = px_wide.loc[d, tk]
                            if pd.notna(price) and price > 0:
                                proceeds = shares * price
                                cost = proceeds * COST_BPS
                                cash += proceeds - cost
                    positions = {}

                target_alloc = equity * TARGET_PCT
                for tk in top.index:
                    if tk in px_wide.columns and d in px_wide.index:
                        price = px_wide.loc[d, tk]
                        if pd.notna(price) and price > 0:
                            alloc = min(target_alloc, equity * MAX_PCT)
                            shares = alloc / price
                            cost = alloc * COST_BPS
                            if cash >= alloc + cost:
                                positions[tk] = shares
                                cash -= (alloc + cost)

                days_since_rebal = 0

        cash += cash * cash_ret_day
        days_since_rebal += 1

        pos_value_end = 0.0
        for tk, shares in positions.items():
            if tk in px_wide.columns and d in px_wide.index:
                price = px_wide.loc[d, tk]
                if pd.notna(price) and price > 0:
                    pos_value_end += shares * price

        equity_end = cash + pos_value_end
        split = "TRAIN" if d <= TRAIN_END else "HOLDOUT"
        rows.append({"date": d, "split": split, "equity_usd": equity_end, "cash_usd": cash,
                     "positions_usd": pos_value_end, "n_positions": len(positions)})

    return pd.DataFrame(rows)


def main() -> int:
    print("=" * 80)
    print("CTO DIAGNOSTIC: Factory US — M3 on S&P 500 (USD) + Treasury tank")
    print("=" * 80)

    print("\n[1/6] Loading US market data...")
    us_raw = pd.read_parquet(INPUT_US_RAW)
    us_raw["date"] = pd.to_datetime(us_raw["date"]).dt.normalize()
    us_raw["ticker"] = us_raw["ticker"].astype(str).str.upper().str.strip()

    us_universe = pd.read_parquet(INPUT_US_UNIVERSE)
    universe_tickers = set(us_universe["ticker"].astype(str).str.upper().str.strip())

    if INPUT_US_BLACKLIST.exists():
        bl = pd.read_csv(INPUT_US_BLACKLIST)
        blacklist_tickers = set(bl[bl.columns[0]].astype(str).str.upper().str.strip())
    else:
        blacklist_tickers = set()

    use_tickers = universe_tickers - blacklist_tickers
    us_raw = us_raw[us_raw["ticker"].isin(use_tickers)]
    print(f"  Tickers: {us_raw['ticker'].nunique()}")

    close_col = None
    for c in ["close", "close_adjusted", "adjusted_close", "close_operational"]:
        if c in us_raw.columns:
            close_col = c
            break
    if close_col is None:
        print(f"  Available columns: {us_raw.columns.tolist()}")
        print("  ERROR: no close column found")
        return 1
    print(f"  Using close column: {close_col}")

    px_wide = us_raw.pivot_table(index="date", columns="ticker", values=close_col, aggfunc="first").sort_index().ffill()
    px_wide = px_wide.loc[TRAIN_START:HOLDOUT_END]
    print(f"  px_wide: {px_wide.shape}")

    print("\n[2/6] Loading macro (Fed funds for Treasury tank)...")
    macro = pd.read_parquet(INPUT_MACRO)
    macro["date"] = pd.to_datetime(macro["date"]).dt.normalize()
    macro = macro.sort_values("date")
    ff = macro.set_index("date")["fed_funds_rate"].dropna()
    ff_daily = ff / 100.0
    print(f"  Fed funds data: {len(ff_daily)} days, range: {ff_daily.min()*100:.2f}% - {ff_daily.max()*100:.2f}%")

    print("\n[3/6] Running M3 backtest on S&P 500 in USD...")
    sim_dates = sorted(set(px_wide.index).intersection(set(ff_daily.index)))
    sim_dates = [pd.Timestamp(d) for d in sim_dates if TRAIN_START <= pd.Timestamp(d) <= HOLDOUT_END]
    print(f"  Sim dates: {len(sim_dates)}")

    us_curve = run_simple_m3_backtest(px_wide, ff_daily, sim_dates, BASE_CAPITAL)
    print(f"  US curve: {len(us_curve)} rows")

    print("\n[4/6] Computing Factory US metrics (in USD)...")
    for split_name in ["FULL", "TRAIN", "HOLDOUT"]:
        if split_name == "FULL":
            sub = us_curve
        else:
            sub = us_curve[us_curve["split"] == split_name]
        if len(sub) < 2:
            continue
        m = metrics(sub["equity_usd"])
        print(f"  {split_name}: equity=${m['equity_final']:,.0f}  CAGR={m['cagr']*100:.1f}%  MDD={m['mdd']*100:.1f}%  Sharpe={m['sharpe']:.3f}")

    print("\n[5/6] Consolidating with Factory BR (C060X) in BRL...")
    ptax = pd.read_parquet(INPUT_PTAX)
    ptax["date"] = pd.to_datetime(ptax["date"]).dt.normalize()
    ptax = ptax.sort_values("date").set_index("date")

    ptax_col = "usdbrl_ptax"

    c060x = pd.read_parquet(INPUT_C060X)
    c060x["date"] = pd.to_datetime(c060x["date"]).dt.normalize()
    c060x = c060x.sort_values("date")

    common_dates = sorted(
        set(c060x["date"]).intersection(set(us_curve["date"])).intersection(set(ptax.index))
    )
    print(f"  Common dates: {len(common_dates)}")

    br = c060x.set_index("date").loc[common_dates, ["split", "equity_end_norm"]].copy()
    br.columns = ["split", "equity_br_brl"]
    us = us_curve.set_index("date").loc[common_dates, ["equity_usd"]].copy()
    us.columns = ["equity_us_usd"]
    fx = ptax.loc[common_dates, [ptax_col]].copy()

    consol = br.join(us).join(fx)
    consol["equity_us_brl"] = consol["equity_us_usd"] * consol[ptax_col]

    ptax_day0 = consol[ptax_col].iloc[0]
    print(f"  PTAX day 0: {ptax_day0:.4f}")

    splits_to_test = [
        (1.0, 0.0, "100% BR"),
        (0.8, 0.2, "80/20 BR/US"),
        (0.7, 0.3, "70/30 BR/US"),
        (0.6, 0.4, "60/40 BR/US"),
        (0.5, 0.5, "50/50 BR/US"),
        (0.4, 0.6, "40/60 BR/US"),
        (0.3, 0.7, "30/70 BR/US"),
        (0.0, 1.0, "100% US"),
    ]

    print(f"\n{'=' * 80}")
    print("CONSOLIDATED RESULTS (BRL) — HOLDOUT")
    print(f"{'=' * 80}")
    print(f"  {'Split':<15} {'Equity BRL':>12} {'CAGR':>8} {'MDD':>8} {'Sharpe':>8}")
    print(f"  {'-'*15} {'-'*12} {'-'*8} {'-'*8} {'-'*8}")

    best_sharpe = -999
    best_split = ""
    best_curve = None

    for w_br, w_us, label in splits_to_test:
        cap_br = BASE_CAPITAL * w_br
        cap_us_usd = (BASE_CAPITAL * w_us) / ptax_day0

        if cap_br > 0:
            br_norm = consol["equity_br_brl"] / consol["equity_br_brl"].iloc[0] * cap_br
        else:
            br_norm = pd.Series(0.0, index=consol.index)

        if cap_us_usd > 0:
            us_usd_norm = consol["equity_us_usd"] / consol["equity_us_usd"].iloc[0] * cap_us_usd
            us_brl_norm = us_usd_norm * consol[ptax_col]
        else:
            us_brl_norm = pd.Series(0.0, index=consol.index)

        total_brl = br_norm + us_brl_norm

        ho = total_brl.loc[HOLDOUT_START:HOLDOUT_END]
        if len(ho) < 2:
            continue

        ho_rebased = ho / ho.iloc[0] * BASE_CAPITAL
        m = metrics(ho_rebased)

        marker = ""
        if m["sharpe"] > best_sharpe:
            best_sharpe = m["sharpe"]
            best_split = label
            best_curve = ho_rebased
            marker = " <<<"

        print(f"  {label:<15} R${m['equity_final']:>10,.0f} {m['cagr']*100:>7.1f}% {m['mdd']*100:>7.1f}% {m['sharpe']:>7.3f}{marker}")

    print(f"\n  >>> BEST SPLIT: {best_split} (Sharpe={best_sharpe:.3f})")

    print(f"\n[6/6] Factory US standalone (in USD) vs S&P 500 index...")
    sp500_series = macro.set_index("date")["sp500_close"].loc[common_dates]
    sp500_norm = sp500_series / sp500_series.iloc[0] * BASE_CAPITAL

    for split_name in ["HOLDOUT"]:
        us_ho = us_curve[us_curve["split"] == split_name].set_index("date")["equity_usd"]
        sp_ho = sp500_norm.loc[HOLDOUT_START:HOLDOUT_END]
        if len(us_ho) < 2 or len(sp_ho) < 2:
            continue
        us_ho_norm = us_ho / us_ho.iloc[0] * BASE_CAPITAL
        sp_ho_norm = sp_ho / sp_ho.iloc[0] * BASE_CAPITAL
        m_us = metrics(us_ho_norm)
        m_sp = metrics(sp_ho_norm)
        print(f"\n  Factory US (M3 on S&P): equity=${m_us['equity_final']:,.0f}  CAGR={m_us['cagr']*100:.1f}%  MDD={m_us['mdd']*100:.1f}%  Sharpe={m_us['sharpe']:.3f}")
        print(f"  S&P 500 buy-hold:       equity=${m_sp['equity_final']:,.0f}  CAGR={m_sp['cagr']*100:.1f}%  MDD={m_sp['mdd']*100:.1f}%  Sharpe={m_sp['sharpe']:.3f}")
        if m_us['equity_final'] > m_sp['equity_final']:
            print(f"  >>> M3 BEATS S&P by ${m_us['equity_final'] - m_sp['equity_final']:,.0f}")
        else:
            print(f"  >>> S&P BEATS M3 by ${m_sp['equity_final'] - m_us['equity_final']:,.0f}")

    print(f"\n{'=' * 80}")
    print("DONE.")
    print(f"{'=' * 80}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
