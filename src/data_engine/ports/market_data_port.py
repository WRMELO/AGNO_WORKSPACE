from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Any, Mapping

from src.data_engine.dtos.stock_data import StockData

class MarketDataPort(ABC):
    """Porta de dados de mercado para a arquitetura hexagonal."""

    @abstractmethod
    def get_current_price(self, ticker: str) -> float:
        raise NotImplementedError

    @abstractmethod
    def get_historical_data(
        self,
        ticker: str,
        start: date,
        end: date,
    ) -> StockData:
        raise NotImplementedError

    @abstractmethod
    def get_fundamentals(self, ticker: str) -> Mapping[str, Any]:
        raise NotImplementedError
