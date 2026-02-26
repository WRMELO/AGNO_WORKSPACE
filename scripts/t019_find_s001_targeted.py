from __future__ import annotations

import fnmatch
import os
import sys
from pathlib import Path

import pandas as pd


SEARCH_ROOTS = [
    Path("/home/wilson/CEP_BUNDLE_CORE"),
    Path("/home/wilson/CEP_COMPRA"),
    Path("/home/wilson/CEP_NA_BOLSA"),
]
TARGET_PATTERN = "*s001*.parquet"
TARGET_ROWS = 1690
OUTPUT_FILE = Path("src/data_engine/ssot/SSOT_UNIVERSE_RAW_S001.parquet")
FALLBACK_HINTS = ("universe", "candidate", "promoted", "ssot")


def find_candidates_by_pattern() -> list[Path]:
    candidates: list[Path] = []
    for root in SEARCH_ROOTS:
        if not root.exists():
            continue
        for base, _, files in os.walk(root):
            for name in files:
                full_path = str((Path(base) / name)).lower()
                if fnmatch.fnmatch(full_path, TARGET_PATTERN):
                    candidates.append(Path(base) / name)
    return sorted(candidates)


def find_fallback_candidates() -> list[Path]:
    candidates: list[Path] = []
    for root in SEARCH_ROOTS:
        if not root.exists():
            continue
        for base, _, files in os.walk(root):
            for name in files:
                if not name.lower().endswith(".parquet"):
                    continue
                full_path = str((Path(base) / name)).lower()
                if any(hint in full_path for hint in FALLBACK_HINTS):
                    candidates.append(Path(base) / name)
    return sorted(candidates)


def read_with_metadata(path: Path) -> tuple[Path, pd.DataFrame, int, list[str]]:
    df = pd.read_parquet(path)
    rows = int(len(df))
    cols = list(df.columns)
    return path, df, rows, cols


def has_ticker_column(columns: list[str]) -> bool:
    lowered = [c.lower() for c in columns]
    return any(c in lowered for c in ["ticker", "symbol", "ativo", "asset", "code"])


def pick_best_candidate(scanned: list[tuple[Path, pd.DataFrame, int, list[str]]]) -> tuple[Path, pd.DataFrame, int, list[str]]:
    if not scanned:
        raise RuntimeError("Nenhum candidato S001 encontrado.")
    ranked = sorted(scanned, key=lambda x: (abs(x[2] - TARGET_ROWS), -x[2]))
    return ranked[0]


def normalize_tickers(df: pd.DataFrame) -> pd.Series:
    ticker_col = None
    for candidate in ["ticker", "symbol", "ativo", "asset", "code"]:
        if candidate in df.columns:
            ticker_col = candidate
            break
    if ticker_col is None:
        raise RuntimeError("Coluna de ticker não encontrada no S001 selecionado.")

    tickers = df[ticker_col].astype(str).str.strip()
    tickers = tickers[tickers != ""]
    tickers = tickers.drop_duplicates().reset_index(drop=True)
    return tickers


def main() -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    print("TASK T019 - S001 HUNT")
    print("")
    print("CANDIDATE SCAN")

    candidates = find_candidates_by_pattern()
    strict_pattern_hit = bool(candidates)
    strict_scan: list[tuple[Path, pd.DataFrame, int, list[str]]] = []
    scanned: list[tuple[Path, pd.DataFrame, int, list[str]]] = []
    for path in candidates:
        try:
            item = read_with_metadata(path)
        except Exception as exc:  # noqa: BLE001
            print(f"- Path: {path}")
            print(f"  FAIL to read parquet: {exc}")
            continue
        strict_scan.append(item)
        print(f"- Path: {path}")
        print(f"  Shape: ({item[2]}, {len(item[3])})")
        print(f"  Columns: {item[3]}")

    scanned.extend(strict_scan)

    strict_eligible = [item for item in strict_scan if has_ticker_column(item[3])]
    if not strict_eligible:
        fallback_candidates = find_fallback_candidates()
        fallback_candidates = [p for p in fallback_candidates if p not in {x[0] for x in strict_scan}]
        if strict_pattern_hit:
            print("- STRICT PATTERN HIT, mas sem coluna de ticker.")
        else:
            print("- STRICT PATTERN MISS: *s001*.parquet não retornou candidatos.")
        print("- FALLBACK: aplicando busca por parquet com hints de universo/promoted/ssot.")
        for path in fallback_candidates:
            try:
                item = read_with_metadata(path)
            except Exception:
                continue
            scanned.append(item)

    eligible = [item for item in scanned if has_ticker_column(item[3])]
    if not eligible:
        print("")
        print("FAIL: S001 not found in target paths.")
        print("OVERALL STATUS: [[ FAIL ]]")
        raise SystemExit(1)

    best_path, best_df, best_rows, _ = pick_best_candidate(eligible)
    tickers = normalize_tickers(best_df)
    out_df = pd.DataFrame({"ticker": tickers})
    out_df.to_parquet(OUTPUT_FILE, index=False)

    print("")
    print(f"SUCCESS: Ingested {len(out_df)} tickers from {best_path}")
    print("")
    print("VERIFICATION")
    print(f"- output_exists: {OUTPUT_FILE.exists()}")
    print(f"- output_path: {OUTPUT_FILE}")
    print(f"- selected_source_rows: {best_rows}")
    print(f"- strict_pattern_hit: {strict_pattern_hit}")
    print("- first_5_tickers:")
    for ticker in out_df["ticker"].head(5).tolist():
        print(f"  - {ticker}")
    print("")
    print("OVERALL STATUS")
    print("OVERALL STATUS: [[ PASS ]]")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print("")
        print(f"FAIL: S001 not found in target paths. Details: {exc}")
        print("OVERALL STATUS: [[ FAIL ]]")
        sys.exit(1)
