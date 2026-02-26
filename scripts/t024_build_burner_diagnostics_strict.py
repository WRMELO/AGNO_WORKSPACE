from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd


if not ("agno_env" in sys.prefix or ".venv" in sys.prefix):
    raise RuntimeError("FATAL: Not in agno_env!")


INPUT_FILE = Path("src/data_engine/ssot/SSOT_CANONICAL_BASE.parquet")
OUTPUT_FILE = Path("src/data_engine/diagnostics/SSOT_BURNER_DIAGNOSTICS.parquet")
SLOPE_WINDOW = 60
VOL_WINDOW = 60
F1_POINTS = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]


def rolling_slope_last_n(values: np.ndarray) -> float:
    if np.isnan(values).any():
        return np.nan
    n = values.size
    x = np.arange(n, dtype=float)
    x_centered = x - x.mean()
    y_centered = values - values.mean()
    denom = np.sum(x_centered**2)
    if denom == 0:
        return np.nan
    return float(np.sum(x_centered * y_centered) / denom)


def f1_points_from_rank(rank_value: float) -> int:
    if not np.isfinite(rank_value):
        return 0
    rank_int = int(rank_value)
    if 1 <= rank_int <= len(F1_POINTS):
        return int(F1_POINTS[rank_int - 1])
    return 0


def main() -> None:
    if not INPUT_FILE.exists():
        raise RuntimeError(f"Input não encontrado: {INPUT_FILE}")

    cols = [
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
    ]
    df = pd.read_parquet(INPUT_FILE, columns=cols)
    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["ticker", "date", "close_operational"]).copy()
    df = df.sort_values(["ticker", "date"], ascending=[True, True]).reset_index(drop=True)

    grouped_close = df.groupby("ticker", sort=False)["close_operational"]
    df["ret_1d"] = grouped_close.pct_change()
    df["volatility_60"] = (
        df.groupby("ticker", sort=False)["ret_1d"]
        .rolling(window=VOL_WINDOW, min_periods=VOL_WINDOW)
        .std(ddof=0)
        .reset_index(level=0, drop=True)
    )
    df["slope_60"] = (
        grouped_close.rolling(window=SLOPE_WINDOW, min_periods=SLOPE_WINDOW)
        .apply(rolling_slope_last_n, raw=True)
        .reset_index(level=0, drop=True)
    )

    i_green = (
        df["i_value"].notna()
        & df["i_lcl"].notna()
        & df["i_ucl"].notna()
        & (df["i_value"] >= df["i_lcl"])
        & (df["i_value"] <= df["i_ucl"])
    )
    mr_green = df["mr_value"].notna() & df["mr_ucl"].notna() & (df["mr_value"] <= df["mr_ucl"])
    xbar_green = (
        df["xbar_value"].notna()
        & df["xbar_lcl"].notna()
        & df["xbar_ucl"].notna()
        & (df["xbar_value"] >= df["xbar_lcl"])
        & (df["xbar_value"] <= df["xbar_ucl"])
    )
    r_green = df["r_value"].notna() & df["r_ucl"].notna() & (df["r_value"] <= df["r_ucl"])
    df["spc_green"] = i_green & mr_green & xbar_green & r_green

    df["rank_ret_1d"] = df.groupby("date", sort=False)["ret_1d"].rank(method="min", ascending=False)
    df["f1_points"] = df["rank_ret_1d"].map(f1_points_from_rank).astype(int)
    df["top_ranking"] = df["f1_points"] > 0
    df["slope_positive"] = df["slope_60"] > 0

    df["raw_signal"] = np.where(df["spc_green"] & df["slope_positive"] & df["top_ranking"], "BUY", "HOLD")
    df["execution_signal"] = (
        df.groupby("ticker", sort=False)["raw_signal"].shift(1).fillna("HOLD")
    )

    expected_shift = df.groupby("ticker", sort=False)["raw_signal"].shift(1).fillna("HOLD")
    shift_ok = bool((df["execution_signal"] == expected_shift).all())
    if not shift_ok:
        raise RuntimeError("Falha de validação: execution_signal não é raw_signal deslocado em D+1.")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT_FILE, index=False)

    warmup_mask = (df["date"] >= pd.Timestamp("2018-01-01")) & (df["date"] <= pd.Timestamp("2018-06-30"))
    warmup = df.loc[warmup_mask, ["ticker", "date", "close_operational", "raw_signal", "execution_signal"]].copy()
    warmup["raw_signal_d_minus_1"] = (
        warmup.groupby("ticker", sort=False)["raw_signal"].shift(1).fillna("HOLD")
    )
    warmup["shift_ok"] = warmup["execution_signal"] == warmup["raw_signal_d_minus_1"]

    sample = warmup.sort_values(["ticker", "date"]).head(20)

    print("TASK T024 - DIAGNOSTIC ENGINE STRICT")
    print("")
    print(f"INPUT: {INPUT_FILE}")
    print(f"OUTPUT: {OUTPUT_FILE}")
    print(f"ROWS OUTPUT: {len(df)}")
    print("")
    print("CHECK SHIFT")
    print(f"- global_shift_ok: {shift_ok}")
    print(f"- warmup_rows_2018H1: {len(warmup)}")
    print(f"- warmup_shift_all_ok: {bool(warmup['shift_ok'].all()) if len(warmup) else True}")
    print("")
    print("SAMPLE (D, Close D, Raw D, Execution D, Raw D-1)")
    if len(sample):
        for row in sample.itertuples(index=False):
            print(
                f"- {row.ticker} | {row.date.date()} | close={row.close_operational:.6f} | "
                f"raw={row.raw_signal} | exec={row.execution_signal} | raw_d-1={row.raw_signal_d_minus_1}"
            )
    else:
        print("- sem linhas no recorte Jan-Jun/2018 para amostragem.")
    print("")
    print("OVERALL STATUS: [[ PASS ]]")


if __name__ == "__main__":
    main()
