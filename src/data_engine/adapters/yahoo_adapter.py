from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

import pandas as pd
import requests
from requests.exceptions import RequestException


class YahooAdapter:
    """Adapter de preços diários via endpoint chart do Yahoo Finance."""

    BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart"

    def __init__(self, timeout_seconds: float = 20.0) -> None:
        self.timeout_seconds = timeout_seconds

    def get_daily_close(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        start_ts = int(datetime.combine(start, datetime.min.time(), tzinfo=UTC).timestamp())
        end_exclusive = end + timedelta(days=1)
        end_ts = int(datetime.combine(end_exclusive, datetime.min.time(), tzinfo=UTC).timestamp())

        url = f"{self.BASE_URL}/{symbol}"
        params = {
            "period1": start_ts,
            "period2": end_ts,
            "interval": "1d",
            "events": "div,splits",
            "includeAdjustedClose": "true",
        }
        headers = {"User-Agent": "Mozilla/5.0"}
        try:
            response = requests.get(url, params=params, headers=headers, timeout=self.timeout_seconds)
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
        except RequestException as exc:
            raise RuntimeError(f"Erro ao consultar Yahoo para símbolo {symbol}.") from exc

        result = ((payload.get("chart") or {}).get("result") or [None])[0]
        if not result:
            return pd.DataFrame(columns=["date", "close"])

        timestamps = result.get("timestamp") or []
        quote = (((result.get("indicators") or {}).get("quote") or [{}])[0]) or {}
        closes = quote.get("close") or []
        if not timestamps or not closes:
            return pd.DataFrame(columns=["date", "close"])

        df = pd.DataFrame({"timestamp": timestamps, "close": closes})
        df["date"] = pd.to_datetime(df["timestamp"], unit="s", utc=True).dt.tz_convert(None).dt.normalize()
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df = df[["date", "close"]].dropna().sort_values("date").reset_index(drop=True)
        return df
