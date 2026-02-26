from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    load_dotenv(ROOT / ".env")
    token = os.getenv("BRAPI_API_KEY")
    if not token:
        raise RuntimeError("BRAPI_API_KEY ausente.")

    url = "https://brapi.dev/api/quote/PETR4"
    params = {"range": "3mo", "interval": "1d", "fundamental": "true", "token": token}
    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()
    payload = response.json()

    out_file = ROOT / "scripts" / "t018_probe_petr4_raw.json"
    out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    result = (payload.get("results") or [{}])[0]
    print("PROBE FILE:", out_file)
    print("TOP KEYS:", sorted(list(result.keys()))[:40])
    print("HAS historicalDataPrice:", "historicalDataPrice" in result)
    print("HAS dividendsData:", "dividendsData" in result)
    print("HAS stockDividends:", "stockDividends" in result)
    print("HAS earningsData:", "earningsData" in result)
    print("HAS defaultKeyStatistics:", "defaultKeyStatistics" in result)
    if isinstance(result.get("dividendsData"), dict):
        print("DIVIDENDS KEYS:", list(result["dividendsData"].keys()))


if __name__ == "__main__":
    main()
