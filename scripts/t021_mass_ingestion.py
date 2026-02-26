from __future__ import annotations

import json
import sys
import time
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

UNIVERSE_FILE = ROOT / "src" / "data_engine" / "ssot" / "SSOT_UNIVERSE_S001_CLEAN.parquet"
TARGET_DIR = ROOT / "data" / "market_data" / "raw"
FUNDAMENTALS_JSON = ROOT / "data" / "market_data" / "fundamentals.json"
INGESTION_REPORT = ROOT / "data" / "market_data" / "ingestion_report.csv"
SSOT_MARKET = ROOT / "src" / "data_engine" / "ssot" / "SSOT_MARKET_DATA_RAW.parquet"
SSOT_FUNDAMENTALS = ROOT / "src" / "data_engine" / "ssot" / "SSOT_FUNDAMENTALS.parquet"

START_DATE = date(2018, 1, 1)
END_DATE = date(2026, 2, 26)
SLEEP_SECONDS = 0.5


def build_event_maps(events_data: list[dict[str, Any]]) -> tuple[dict[str, float], dict[str, str]]:
    dividends_by_date: dict[str, float] = {}
    splits_by_date: dict[str, str] = {}

    for event in events_data:
        event_date = str(event.get("date") or "")
        if not event_date:
            continue
        event_type = str(event.get("type") or "").upper()
        value = event.get("value")
        ratio = event.get("ratio")

        if any(key in event_type for key in ["DIV", "JCP", "RENDIMENTO", "SUBSCRIPTION"]):
            try:
                v = float(value) if value is not None else 0.0
            except (TypeError, ValueError):
                v = 0.0
            dividends_by_date[event_date] = dividends_by_date.get(event_date, 0.0) + v

        if any(key in event_type for key in ["DESDOBRAMENTO", "SPLIT", "GROUPING", "GRUPAMENTO"]):
            if ratio is not None:
                splits_by_date[event_date] = str(ratio)
            elif value is not None:
                splits_by_date[event_date] = str(value)

    return dividends_by_date, splits_by_date


def flatten_timeseries(ticker: str, price_data: list[dict[str, Any]], events_data: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(price_data)
    if df.empty:
        return pd.DataFrame(
            columns=[
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
            ]
        )

    dividends_by_date, splits_by_date = build_event_maps(events_data)
    df["ticker"] = ticker
    df["date"] = pd.to_datetime(df["date"]).dt.date.astype(str)
    df["dividends"] = df["date"].map(dividends_by_date).fillna(0.0)
    df["splits"] = df["date"].map(splits_by_date).fillna("")
    return df[
        [
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
        ]
    ]


def main() -> None:
    load_dotenv(ROOT / ".env")

    from src.data_engine.adapters.brapi_adapter import BrapiAdapter

    if not UNIVERSE_FILE.exists():
        raise RuntimeError(f"Universe file not found: {UNIVERSE_FILE}")

    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    FUNDAMENTALS_JSON.parent.mkdir(parents=True, exist_ok=True)
    INGESTION_REPORT.parent.mkdir(parents=True, exist_ok=True)
    SSOT_MARKET.parent.mkdir(parents=True, exist_ok=True)

    universe_df = pd.read_parquet(UNIVERSE_FILE)
    tickers = (
        universe_df["ticker"]
        .astype(str)
        .str.upper()
        .str.strip()
        .dropna()
        .drop_duplicates()
        .tolist()
    )

    adapter = BrapiAdapter()
    report_rows: list[dict[str, Any]] = []
    fundamentals_rows: list[dict[str, Any]] = []

    fundamentals_cache: dict[str, dict[str, Any]] = {}
    if FUNDAMENTALS_JSON.exists():
        try:
            cached_items = json.loads(FUNDAMENTALS_JSON.read_text(encoding="utf-8"))
            if isinstance(cached_items, list):
                for item in cached_items:
                    ticker = str(item.get("ticker") or "").upper().strip()
                    if ticker:
                        fundamentals_cache[ticker] = item
        except Exception:
            fundamentals_cache = {}
    success_count = 0
    fail_count = 0

    print("TASK T021 - MASS DATA INGESTION")
    print("")
    print(f"Universe size: {len(tickers)}")
    print(f"Date range: {START_DATE.isoformat()} -> {END_DATE.isoformat()}")
    print("")

    for idx, ticker in enumerate(tickers, start=1):
        started_at = datetime.now(UTC).isoformat()
        try:
            ts_path = TARGET_DIR / f"{ticker}.parquet"
            if ts_path.exists():
                ts_df = pd.read_parquet(ts_path)
                events_rows = int((ts_df.get("dividends", pd.Series(dtype=float)) != 0).sum()) + int(
                    (ts_df.get("splits", pd.Series(dtype=str)) != "").sum()
                )
            else:
                historical = adapter.get_historical_data(ticker=ticker, start=START_DATE, end=END_DATE)
                ts_df = flatten_timeseries(ticker, historical.price_data, historical.events_data)
                ts_df.to_parquet(ts_path, index=False)
                events_rows = int(len(historical.events_data))

            if ticker in fundamentals_cache:
                fundamentals = fundamentals_cache[ticker]
            else:
                fundamentals = adapter.get_fundamentals(ticker=ticker)
                fundamentals_cache[ticker] = fundamentals

            fundamentals_rows.append(
                {
                    "ticker": ticker,
                    "short_name": fundamentals.get("short_name"),
                    "long_name": fundamentals.get("long_name"),
                    "currency": fundamentals.get("currency"),
                    "price_to_earnings": fundamentals.get("price_to_earnings"),
                    "dividend_yield": fundamentals.get("dividend_yield"),
                    "market_cap": fundamentals.get("market_cap"),
                    "sector": fundamentals.get("sector"),
                    "industry": fundamentals.get("industry"),
                }
            )

            report_rows.append(
                {
                    "ticker": ticker,
                    "status": "SUCCESS",
                    "rows": int(len(ts_df)),
                    "events_rows": events_rows,
                    "error": "",
                    "started_at_utc": started_at,
                    "finished_at_utc": datetime.now(UTC).isoformat(),
                }
            )
            success_count += 1
        except Exception as exc:  # noqa: BLE001
            report_rows.append(
                {
                    "ticker": ticker,
                    "status": "FAIL",
                    "rows": 0,
                    "events_rows": 0,
                    "error": str(exc)[:500],
                    "started_at_utc": started_at,
                    "finished_at_utc": datetime.now(UTC).isoformat(),
                }
            )
            fail_count += 1

        if idx % 25 == 0 or idx == len(tickers):
            print(f"Progress: {idx}/{len(tickers)} | success={success_count} fail={fail_count}")
        time.sleep(SLEEP_SECONDS)

    report_df = pd.DataFrame(report_rows)
    report_df.to_csv(INGESTION_REPORT, index=False)

    with FUNDAMENTALS_JSON.open("w", encoding="utf-8") as f:
        json.dump(fundamentals_rows, f, ensure_ascii=False, indent=2)

    fundamentals_df = pd.DataFrame(fundamentals_rows).drop_duplicates(subset=["ticker"]).reset_index(drop=True)
    fundamentals_df.to_parquet(SSOT_FUNDAMENTALS, index=False)

    all_ts_frames: list[pd.DataFrame] = []
    for ticker in report_df.loc[report_df["status"] == "SUCCESS", "ticker"].tolist():
        parquet_path = TARGET_DIR / f"{ticker}.parquet"
        if parquet_path.exists():
            all_ts_frames.append(pd.read_parquet(parquet_path))

    if all_ts_frames:
        market_df = pd.concat(all_ts_frames, ignore_index=True)
    else:
        market_df = pd.DataFrame(
            columns=[
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
            ]
        )
    market_df.to_parquet(SSOT_MARKET, index=False)

    success_rate = (success_count / len(tickers) * 100.0) if tickers else 0.0
    market_size_mb = SSOT_MARKET.stat().st_size / (1024 * 1024) if SSOT_MARKET.exists() else 0.0

    print("")
    print("SUMMARY")
    print(f"- success_count: {success_count}")
    print(f"- fail_count: {fail_count}")
    print(f"- success_rate: {success_rate:.2f}%")
    print(f"- ssot_market_rows: {len(market_df)}")
    print(f"- ssot_market_path: {SSOT_MARKET}")
    print(f"- ssot_fundamentals_rows: {len(fundamentals_df)}")
    print(f"- ssot_fundamentals_path: {SSOT_FUNDAMENTALS}")
    print(f"- ingestion_report: {INGESTION_REPORT}")
    print(f"- market_ssot_size_mb: {market_size_mb:.2f}")
    print("")
    print("OVERALL STATUS")
    pass_status = success_rate >= 90.0 and len(market_df) > 0 and len(fundamentals_df) > 0
    print("OVERALL STATUS: [[ PASS ]]" if pass_status else "OVERALL STATUS: [[ FAIL ]]")
    if not pass_status:
        sys.exit(1)


if __name__ == "__main__":
    main()
