from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class StockData:
    """Estrutura de retorno com preços brutos e eventos corporativos."""

    price_data: list[dict[str, Any]] = field(default_factory=list)
    events_data: list[dict[str, Any]] = field(default_factory=list)
