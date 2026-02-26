from __future__ import annotations

import os
from datetime import UTC, date, datetime
from typing import Any, Mapping

import requests
from requests import Response
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import RequestException, Timeout

from src.data_engine.dtos.stock_data import StockData
from src.data_engine.ports.market_data_port import MarketDataPort


class BrapiAdapter(MarketDataPort):
    """Adapter concreto para consumo da API BRAPI."""

    def __init__(self, timeout_seconds: float = 10.0) -> None:
        api_key = os.getenv("BRAPI_API_KEY")
        if not api_key:
            raise ValueError("BRAPI_API_KEY não encontrado no ambiente.")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.base_url = "https://brapi.dev/api"

    def _request(self, endpoint: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        query = {"token": self.api_key}
        if params:
            query.update(dict(params))

        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        try:
            response: Response = requests.get(url, params=query, timeout=self.timeout_seconds)
            response.raise_for_status()
            return response.json()
        except RequestsConnectionError as exc:
            raise RuntimeError("Falha de conexão ao acessar BRAPI.") from exc
        except Timeout as exc:
            raise RuntimeError("Timeout ao acessar BRAPI.") from exc
        except RequestException as exc:
            raise RuntimeError(f"Erro HTTP na BRAPI: {exc}") from exc

    def get_current_price(self, ticker: str) -> float:
        payload = self._request(f"quote/{ticker}")
        results = payload.get("results") or []
        if not results:
            raise RuntimeError(f"Nenhum resultado retornado para ticker '{ticker}'.")
        regular_market_price = results[0].get("regularMarketPrice")
        if regular_market_price is None:
            raise RuntimeError(f"Campo regularMarketPrice ausente para ticker '{ticker}'.")
        return float(regular_market_price)

    @staticmethod
    def _parse_iso_date(value: Any) -> date | None:
        if not value or not isinstance(value, str):
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except ValueError:
            return None

    @staticmethod
    def _parse_unix_date(value: Any) -> date | None:
        if value is None:
            return None
        try:
            return datetime.fromtimestamp(int(value), tz=UTC).date()
        except (TypeError, ValueError, OSError):
            return None

    @staticmethod
    def _first_not_none(*values: Any) -> Any:
        for value in values:
            if value is not None:
                return value
        return None

    @staticmethod
    def _to_float_or_none(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _extract_events(self, result: Mapping[str, Any], start: date, end: date) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        dividends_data = result.get("dividendsData") or {}

        for item in dividends_data.get("cashDividends") or []:
            event_date = (
                self._parse_iso_date(item.get("lastDatePrior"))
                or self._parse_iso_date(item.get("paymentDate"))
                or self._parse_iso_date(item.get("approvedOn"))
            )
            if not event_date or event_date < start or event_date > end:
                continue
            events.append(
                {
                    "date": event_date.isoformat(),
                    "type": str(item.get("label") or "CASH_DIVIDEND"),
                    "value": self._to_float_or_none(item.get("rate")),
                    "ratio": None,
                }
            )

        for item in dividends_data.get("stockDividends") or []:
            event_date = self._parse_iso_date(item.get("lastDatePrior")) or self._parse_iso_date(item.get("approvedOn"))
            if not event_date or event_date < start or event_date > end:
                continue
            factor = self._first_not_none(item.get("completeFactor"), item.get("factor"))
            events.append(
                {
                    "date": event_date.isoformat(),
                    "type": str(item.get("label") or "STOCK_DIVIDEND"),
                    "value": self._to_float_or_none(item.get("factor")),
                    "ratio": str(factor) if factor is not None else None,
                }
            )

        for item in dividends_data.get("subscriptions") or []:
            event_date = (
                self._parse_iso_date(item.get("lastDatePrior"))
                or self._parse_iso_date(item.get("paymentDate"))
                or self._parse_iso_date(item.get("approvedOn"))
            )
            if not event_date or event_date < start or event_date > end:
                continue
            events.append(
                {
                    "date": event_date.isoformat(),
                    "type": str(item.get("label") or "SUBSCRIPTION"),
                    "value": self._to_float_or_none(item.get("rate")),
                    "ratio": str(item.get("percentage")) if item.get("percentage") is not None else None,
                }
            )

        events.sort(key=lambda x: x["date"])
        return events

    def get_historical_data(
        self,
        ticker: str,
        start: date,
        end: date,
    ) -> StockData:
        if end < start:
            raise ValueError("Data final menor que data inicial.")

        payload = self._request(
            f"quote/{ticker}",
            params={
                "range": "max",
                "interval": "1d",
                "dividends": "true",
            },
        )
        results = payload.get("results") or []
        if not results:
            raise RuntimeError(f"Nenhum histórico retornado para ticker '{ticker}'.")
        result = results[0]

        prices: list[dict[str, Any]] = []
        for row in result.get("historicalDataPrice") or []:
            row_date = self._parse_unix_date(row.get("date"))
            if not row_date or row_date < start or row_date > end:
                continue
            prices.append(
                {
                    "date": row_date.isoformat(),
                    "open": self._to_float_or_none(row.get("open")),
                    "high": self._to_float_or_none(row.get("high")),
                    "low": self._to_float_or_none(row.get("low")),
                    "close": self._to_float_or_none(row.get("close")),
                    "volume": int(row.get("volume") or 0),
                    "adjusted_close": self._to_float_or_none(row.get("adjustedClose")),
                }
            )

        events = self._extract_events(result, start=start, end=end)
        return StockData(price_data=prices, events_data=events)

    def get_fundamentals(self, ticker: str) -> Mapping[str, Any]:
        payload = self._request(
            f"quote/{ticker}",
            params={
                "modules": "summaryProfile,defaultKeyStatistics,financialData",
                "fundamental": "true",
            },
        )
        results = payload.get("results") or []
        if not results:
            raise RuntimeError(f"Nenhum fundamento retornado para ticker '{ticker}'.")
        result = results[0]

        summary_profile = result.get("summaryProfile") or {}
        default_stats = result.get("defaultKeyStatistics") or {}
        financial_data = result.get("financialData") or {}

        dy = self._first_not_none(
            default_stats.get("trailingAnnualDividendYield"),
            default_stats.get("dividendYield"),
            financial_data.get("dividendYield"),
        )

        return {
            "ticker": result.get("symbol") or ticker,
            "short_name": result.get("shortName"),
            "long_name": result.get("longName"),
            "currency": result.get("currency"),
            "price_to_earnings": self._to_float_or_none(result.get("priceEarnings")),
            "dividend_yield": self._to_float_or_none(dy),
            "market_cap": self._to_float_or_none(result.get("marketCap")),
            "sector": summary_profile.get("sector") or summary_profile.get("sectorDisp"),
            "industry": summary_profile.get("industry") or summary_profile.get("industryDisp"),
        }

    def get_current_quote(self, ticker: str) -> dict[str, Any]:
        """Retorna um dicionário limpo para inspeção/diagnóstico."""
        payload = self._request(f"quote/{ticker}")
        results = payload.get("results") or []
        if not results:
            raise RuntimeError(f"Nenhum resultado retornado para ticker '{ticker}'.")

        quote = results[0]
        return {
            "ticker": quote.get("symbol") or ticker,
            "short_name": quote.get("shortName"),
            "currency": quote.get("currency"),
            "market_price": quote.get("regularMarketPrice"),
            "market_time": quote.get("regularMarketTime"),
            "exchange": quote.get("exchangeName"),
        }
