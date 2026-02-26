from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import requests
from requests.exceptions import RequestException


class BcbAdapter:
    """Adapter para séries temporais do SGS/BCB."""

    BASE_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs."

    def __init__(self, timeout_seconds: float = 20.0) -> None:
        self.timeout_seconds = timeout_seconds

    def get_series(self, series_id: int, start: date, end: date) -> pd.DataFrame:
        url = f"{self.BASE_URL}{series_id}/dados"
        params = {
            "formato": "json",
            "dataInicial": start.strftime("%d/%m/%Y"),
            "dataFinal": end.strftime("%d/%m/%Y"),
        }
        try:
            response = requests.get(url, params=params, timeout=self.timeout_seconds)
            response.raise_for_status()
            payload: list[dict[str, Any]] = response.json()
        except RequestException as exc:
            raise RuntimeError(f"Erro ao consultar BCB série {series_id}.") from exc

        if not payload:
            return pd.DataFrame(columns=["date", "value"])

        df = pd.DataFrame(payload)
        df["date"] = pd.to_datetime(df["data"], format="%d/%m/%Y", errors="coerce")
        df["value"] = pd.to_numeric(df["valor"], errors="coerce")
        df = df[["date", "value"]].dropna().sort_values("date").reset_index(drop=True)
        return df

    def get_cdi_series_12(self, start: date, end: date) -> pd.DataFrame:
        """Retorna série 12 (taxa anualizada) como date/value."""
        return self.get_series(series_id=12, start=start, end=end)
