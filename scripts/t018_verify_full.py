from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    load_dotenv(ROOT / ".env")

    from src.data_engine.adapters.brapi_adapter import BrapiAdapter

    adapter = BrapiAdapter()
    historical = adapter.get_historical_data(
        ticker="PETR4",
        start=date(2024, 1, 1),
        end=date.today(),
    )
    fundamentals = adapter.get_fundamentals("PETR4")

    first_prices = historical.price_data[:3]
    first_events = historical.events_data[:10]

    print("TASK T018 - FULL DATA EXTRACTION")
    print("")
    print("PRICE SAMPLE (FIRST 3)")
    print(json.dumps(first_prices, ensure_ascii=False, indent=2))
    print("")
    print(f"EVENTS FOUND ({len(historical.events_data)})")
    print(json.dumps(first_events, ensure_ascii=False, indent=2))
    print("")
    print("FUNDAMENTALS SNAPSHOT")
    print(json.dumps(fundamentals, ensure_ascii=False, indent=2))
    print("")
    print("OVERALL STATUS")
    has_prices = len(historical.price_data) > 0
    has_events = len(historical.events_data) > 0
    has_fundamentals = bool(fundamentals.get("market_cap")) and bool(fundamentals.get("sector"))
    overall = has_prices and has_events and has_fundamentals
    print("OVERALL STATUS: [[ PASS ]]" if overall else "OVERALL STATUS: [[ FAIL ]]")


if __name__ == "__main__":
    main()
