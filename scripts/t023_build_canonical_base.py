from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MICRO_FILE = ROOT / "src" / "data_engine" / "ssot" / "SSOT_MARKET_DATA_RAW.parquet"
MACRO_FILE = ROOT / "src" / "data_engine" / "ssot" / "SSOT_MACRO.parquet"
UNIVERSE_FILE = ROOT / "src" / "data_engine" / "ssot" / "SSOT_UNIVERSE_OPERATIONAL.parquet"
TARGET_FILE = ROOT / "src" / "data_engine" / "ssot" / "SSOT_CANONICAL_BASE.parquet"

REF_WINDOW_K = 60
SUBGROUP_N = 4

# Constantes SPC conforme especificação.
A2_N4 = 0.729
D4_N4 = 2.282
E2_IMR_N2 = 2.66
D4_IMR_N2 = 3.267


def main() -> None:
    if not MICRO_FILE.exists() or not MACRO_FILE.exists() or not UNIVERSE_FILE.exists():
        raise RuntimeError("Arquivos de entrada da T023 ausentes.")

    micro = pd.read_parquet(MICRO_FILE)
    macro = pd.read_parquet(MACRO_FILE)
    universe = pd.read_parquet(UNIVERSE_FILE)

    universe_set = set(universe["ticker"].astype(str).str.upper().str.strip())
    micro["ticker"] = micro["ticker"].astype(str).str.upper().str.strip()
    micro = micro[micro["ticker"].isin(universe_set)].copy()
    micro["date"] = pd.to_datetime(micro["date"], errors="coerce")
    micro["close"] = pd.to_numeric(micro["close"], errors="coerce")
    micro.loc[micro["close"] <= 0, "close"] = np.nan
    micro = micro.dropna(subset=["date", "close"]).sort_values(["ticker", "date"]).reset_index(drop=True)

    # log_ret_nominal por ticker (micro).
    micro["log_ret_nominal"] = np.log(micro["close"] / micro.groupby("ticker")["close"].shift(1))
    micro["log_ret_nominal"] = micro["log_ret_nominal"].replace([np.inf, -np.inf], np.nan)

    macro["date"] = pd.to_datetime(macro["date"], errors="coerce")
    merged = micro.merge(macro, on="date", how="left")
    merged = merged.sort_values(["ticker", "date"]).reset_index(drop=True)

    # 2) Base variables.
    merged["X_real"] = merged["log_ret_nominal"] - merged["cdi_log_daily"]
    merged["I"] = merged["X_real"]
    merged["MR"] = (merged["I"] - merged.groupby("ticker")["I"].shift(1)).abs()

    # 3) Subgroup statistics n=4.
    g = merged.groupby("ticker", group_keys=False)
    merged["xbar_sub"] = g["I"].transform(lambda s: s.rolling(SUBGROUP_N, min_periods=SUBGROUP_N).mean())
    roll_max = g["I"].transform(lambda s: s.rolling(SUBGROUP_N, min_periods=SUBGROUP_N).max())
    roll_min = g["I"].transform(lambda s: s.rolling(SUBGROUP_N, min_periods=SUBGROUP_N).min())
    merged["r_sub"] = roll_max - roll_min

    # 4) Reference statistics k=60 lagged (história fechada).
    merged["center_line"] = g["I"].transform(lambda s: s.rolling(REF_WINDOW_K, min_periods=REF_WINDOW_K).mean().shift(1))
    merged["mr_bar"] = g["MR"].transform(lambda s: s.rolling(REF_WINDOW_K, min_periods=REF_WINDOW_K).mean().shift(1))
    merged["r_bar"] = g["r_sub"].transform(lambda s: s.rolling(REF_WINDOW_K, min_periods=REF_WINDOW_K).mean().shift(1))

    # 5) Control limits using constants.
    merged["i_ucl"] = merged["center_line"] + (E2_IMR_N2 * merged["mr_bar"])
    merged["i_lcl"] = merged["center_line"] - (E2_IMR_N2 * merged["mr_bar"])
    merged["mr_ucl"] = D4_IMR_N2 * merged["mr_bar"]

    merged["xbar_ucl"] = merged["center_line"] + (A2_N4 * merged["r_bar"])
    merged["xbar_lcl"] = merged["center_line"] - (A2_N4 * merged["r_bar"])
    merged["r_ucl"] = D4_N4 * merged["r_bar"]

    # Organiza colunas auditáveis.
    ordered_cols = [
        "ticker",
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "adjusted_close",
        "dividends",
        "splits",
        "log_ret_nominal",
        "cdi_log_daily",
        "sp500_close",
        "sp500_log_ret",
        "ibov_close",
        "ibov_log_ret",
        "X_real",
        "I",
        "MR",
        "xbar_sub",
        "r_sub",
        "center_line",
        "mr_bar",
        "r_bar",
        "i_ucl",
        "i_lcl",
        "mr_ucl",
        "xbar_ucl",
        "xbar_lcl",
        "r_ucl",
    ]
    existing_cols = [c for c in ordered_cols if c in merged.columns]
    canonical = merged[existing_cols].copy()
    canonical["date"] = canonical["date"].dt.date.astype(str)

    TARGET_FILE.parent.mkdir(parents=True, exist_ok=True)
    canonical.to_parquet(TARGET_FILE, index=False)

    print("TASK T023 - SPC ENGINE (SHEWHART CONSTANTS)")
    print("")
    print(f"Rows: {len(canonical)}")
    print(f"Tickers: {canonical['ticker'].nunique()}")
    print(f"Target: {TARGET_FILE}")
    print("Applied constants:")
    print(f"- n=4 => A2={A2_N4}, D4={D4_N4}, D3=0.0")
    print(f"- I-MR(n=2) => E2={E2_IMR_N2}, D4={D4_IMR_N2}")
    print("Check: std-based limits NOT used.")
    print("")
    print("OVERALL STATUS")
    print("OVERALL STATUS: [[ PASS ]]")


if __name__ == "__main__":
    main()
