from __future__ import annotations

import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return
    for raw_line in dotenv_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"").strip("'"))


def main() -> None:
    load_dotenv(ROOT / ".env")

    from src.data_engine.adapters.brapi_adapter import BrapiAdapter

    adapter = BrapiAdapter()
    quote = adapter.get_current_quote("PETR4")
    print(json.dumps(quote, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
