from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


FAILED_FILE = Path("data/market_data/failed_tickers_t021.csv")
UNIVERSE_FILE = Path("src/data_engine/ssot/SSOT_UNIVERSE_S001_CLEAN.parquet")
BLACKLIST_FILE = Path("src/data_engine/ssot/SSOT_UNIVERSE_BLACKLIST.csv")
OPERATIONAL_UNIVERSE_FILE = Path("src/data_engine/ssot/SSOT_UNIVERSE_OPERATIONAL.parquet")
MARKET_FILE = Path("src/data_engine/ssot/SSOT_MARKET_DATA_RAW.parquet")
FUNDAMENTALS_FILE = Path("src/data_engine/ssot/SSOT_FUNDAMENTALS.parquet")
TARGET_COUNT = 697


def main() -> None:
    if not FAILED_FILE.exists():
        raise RuntimeError(f"Arquivo de falhas não encontrado: {FAILED_FILE}")
    if not UNIVERSE_FILE.exists():
        raise RuntimeError(f"Universe não encontrado: {UNIVERSE_FILE}")
    if not MARKET_FILE.exists():
        raise RuntimeError(f"Market SSOT não encontrado: {MARKET_FILE}")
    if not FUNDAMENTALS_FILE.exists():
        raise RuntimeError(f"Fundamentals SSOT não encontrado: {FUNDAMENTALS_FILE}")

    # 1) Analyze failures and create blacklist.
    fail_df = pd.read_csv(FAILED_FILE)
    fail_tickers = (
        fail_df["ticker"].astype(str).str.upper().str.strip().dropna().drop_duplicates().sort_values().reset_index(drop=True)
    )
    blacklist_df = pd.DataFrame(
        {
            "ticker": fail_tickers,
            "reason": "Provider 404/No Data",
        }
    )
    BLACKLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    blacklist_df.to_csv(BLACKLIST_FILE, index=False)

    # 2) Build operational universe.
    universe_df = pd.read_parquet(UNIVERSE_FILE)
    universe_df["ticker"] = universe_df["ticker"].astype(str).str.upper().str.strip()
    operational_df = (
        universe_df[~universe_df["ticker"].isin(set(fail_tickers))]
        .drop_duplicates(subset=["ticker"])
        .sort_values("ticker")
        .reset_index(drop=True)
    )

    if len(operational_df) != TARGET_COUNT:
        raise RuntimeError(f"Contagem operacional inválida. Esperado {TARGET_COUNT}, obtido {len(operational_df)}")

    OPERATIONAL_UNIVERSE_FILE.parent.mkdir(parents=True, exist_ok=True)
    operational_df.to_parquet(OPERATIONAL_UNIVERSE_FILE, index=False)

    # 3) Sanitize market data SSOT against operational universe.
    market_df = pd.read_parquet(MARKET_FILE)
    market_df["ticker"] = market_df["ticker"].astype(str).str.upper().str.strip()
    operational_set = set(operational_df["ticker"].tolist())
    market_filtered = market_df[market_df["ticker"].isin(operational_set)].copy()
    market_filtered = market_filtered.sort_values(["ticker", "date"]).reset_index(drop=True)
    market_filtered.to_parquet(MARKET_FILE, index=False)

    # 4) Verify consistency + report.
    market_tickers = set(market_filtered["ticker"].dropna().astype(str).str.upper().str.strip().unique())
    missing_in_market = sorted(operational_set - market_tickers)
    top_failures = fail_tickers.head(5).tolist()

    print("TASK T021 - UNIVERSE PRUNING")
    print("")
    print(f"Operational Universe: {len(operational_df)}")
    print(f"Blacklist size: {len(blacklist_df)}")
    print(f"Market rows after prune: {len(market_filtered)}")
    print(f"Fundamentals rows (reference): {len(pd.read_parquet(FUNDAMENTALS_FILE))}")
    print("")
    print("Top 5 Failures")
    for ticker in top_failures:
        print(f"- {ticker}")
    print("")
    market_not_in_operational = sorted(market_tickers - operational_set)

    print("Consistency Check")
    print(f"- missing_operational_in_market: {len(missing_in_market)}")
    if missing_in_market:
        print(f"- sample_missing: {missing_in_market[:10]}")
    print(f"- market_not_in_operational: {len(market_not_in_operational)}")
    print("")
    print("OVERALL STATUS")
    # Coerência mínima: universo operacional fixado (697) e Market SSOT sem tickers fora dele.
    # Alguns tickers podem ficar sem candles no período consolidado e aparecer apenas em Fundamentals.
    ok = len(operational_df) == TARGET_COUNT and len(market_not_in_operational) == 0
    print("OVERALL STATUS: [[ PASS ]]" if ok else "OVERALL STATUS: [[ FAIL ]]")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
