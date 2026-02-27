from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TARGET_FILE = ROOT / "src" / "data_engine" / "ssot" / "SSOT_MACRO.parquet"
CALENDAR_TICKER_REF = "^BVSP"
START_DATE = date(2018, 1, 1)
END_DATE = date(2026, 2, 26)


def establish_master_calendar(brapi_adapter) -> pd.DataFrame:
    ibov_hist = brapi_adapter.get_historical_data(
        ticker=CALENDAR_TICKER_REF,
        start=START_DATE,
        end=END_DATE,
    )
    ibov_df = pd.DataFrame(ibov_hist.price_data)
    if ibov_df.empty:
        raise RuntimeError("BRAPI retornou histórico vazio para ^BVSP.")

    ibov_df["date"] = pd.to_datetime(ibov_df["date"], errors="coerce")
    ibov_df["ibov_close"] = pd.to_numeric(ibov_df["close"], errors="coerce")
    ibov_df = ibov_df[["date", "ibov_close"]].dropna().drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)

    if len(ibov_df) <= 1500:
        raise RuntimeError(f"Calendário mestre BRAPI inválido. Linhas ^BVSP: {len(ibov_df)}")

    b3_days = ibov_df[["date"]].drop_duplicates().sort_values("date").reset_index(drop=True)
    ibov_df = b3_days.merge(ibov_df, on="date", how="left")
    ibov_df["ibov_close"] = ibov_df["ibov_close"].ffill().bfill()
    return ibov_df


def main() -> None:
    load_dotenv(ROOT / ".env")

    from src.data_engine.adapters.brapi_adapter import BrapiAdapter
    from src.data_engine.adapters.bcb_adapter import BcbAdapter
    from src.data_engine.adapters.yahoo_adapter import YahooAdapter

    brapi = BrapiAdapter()
    bcb = BcbAdapter()
    yahoo = YahooAdapter()

    # A) Master calendar (B3 trading days) STRICTLY from BRAPI ^BVSP.
    ibov_master_df = establish_master_calendar(brapi)
    b3_days = ibov_master_df[["date"]].copy()

    # B) External data fetch.
    cdi_df = bcb.get_cdi_series_12(start=START_DATE, end=END_DATE).rename(columns={"value": "cdi_rate_annual_pct"})
    sp500_df = yahoo.get_daily_close("^GSPC", start=START_DATE, end=END_DATE).rename(columns={"close": "sp500_close"})

    # C) Alignment with B3 master clock.
    macro = b3_days.merge(cdi_df, on="date", how="left")
    macro = macro.merge(sp500_df, on="date", how="left")
    macro = macro.merge(ibov_master_df, on="date", how="left")

    macro = macro.sort_values("date").reset_index(drop=True)
    for col in ["cdi_rate_annual_pct", "sp500_close", "ibov_close"]:
        macro[col] = pd.to_numeric(macro[col], errors="coerce")
        macro[col] = macro[col].ffill().bfill()

    # D) Calculations.
    # BCB série 12 é taxa diária em percentual (% a.d.), não taxa anual.
    # Converter para log-ret diário diretamente: log(1 + r_d).
    macro["cdi_log_daily"] = np.log1p(macro["cdi_rate_annual_pct"] / 100.0)
    macro["sp500_log_ret"] = np.log(macro["sp500_close"] / macro["sp500_close"].shift(1))
    macro["ibov_log_ret"] = np.log(macro["ibov_close"] / macro["ibov_close"].shift(1))
    macro["sp500_log_ret"] = macro["sp500_log_ret"].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    macro["ibov_log_ret"] = macro["ibov_log_ret"].replace([np.inf, -np.inf], np.nan).fillna(0.0)

    output = macro[["date", "ibov_close", "ibov_log_ret", "sp500_close", "sp500_log_ret", "cdi_log_daily"]].copy()
    output["date"] = pd.to_datetime(output["date"]).dt.date.astype(str)

    if len(output) <= 1500:
        raise RuntimeError(f"Contagem insuficiente de linhas no SSOT_MACRO: {len(output)}")

    if output.isna().any().any():
        null_counts = output.isna().sum().to_dict()
        raise RuntimeError(f"SSOT_MACRO contém NaN após limpeza: {null_counts}")

    TARGET_FILE.parent.mkdir(parents=True, exist_ok=True)
    output.to_parquet(TARGET_FILE, index=False)

    print("TASK T022 - MACRO BUILDER (BRAPI SOURCE)")
    print("")
    print("Calendar source: BRAPI ^BVSP")
    print(f"Calendar Synced. Rows: {len(output)}.")
    print(f"Date range: {output['date'].min()} -> {output['date'].max()}")
    print(f"Target file: {TARGET_FILE}")
    print(f"No NaNs: {not output.isna().any().any()}")
    cdi_growth = float(np.expm1(output["cdi_log_daily"].astype(float).sum()))
    print(f"CDI Growth (from cdi_log_daily): {cdi_growth:.6f}")
    print("")
    print("LAST 5 ROWS")
    print(output.tail(5).to_string(index=False))
    print("")
    print("OVERALL STATUS")
    print("OVERALL STATUS: [[ PASS ]]")


if __name__ == "__main__":
    main()
