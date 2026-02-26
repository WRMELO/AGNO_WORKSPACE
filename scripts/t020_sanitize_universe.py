from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd


INPUT_FILE = Path("src/data_engine/ssot/SSOT_UNIVERSE_RAW_S001.parquet")
OUTPUT_FILE = Path("src/data_engine/ssot/SSOT_UNIVERSE_S001_CLEAN.parquet")
REJECTED_FILE = Path("src/data_engine/ssot/rejected_tickers_s001.csv")
VALID_SUFFIXES = ["3", "4", "5", "6", "11", "31", "32", "33", "34", "35", "39"]
VALID_SUFFIXES_SORTED = sorted(VALID_SUFFIXES, key=len, reverse=True)
ALNUM_REGEX = re.compile(r"^[A-Z0-9]+$")


def normalize_ticker(raw: object) -> str:
    ticker = str(raw).upper().strip()
    if ticker.endswith(".SA"):
        ticker = ticker[:-3]
    if ticker.endswith("F") and len(ticker) > 4:
        ticker = ticker[:-1]
    return ticker


def detect_suffix(ticker: str) -> str | None:
    for suffix in VALID_SUFFIXES_SORTED:
        if ticker.endswith(suffix):
            return suffix
    return None


def main() -> None:
    if not INPUT_FILE.exists():
        print("TASK T020 - UNIVERSE SANITY (SUFFIX LOGIC)")
        print("")
        print(f"FAIL: Input file not found: {INPUT_FILE}")
        print("OVERALL STATUS: [[ FAIL ]]")
        sys.exit(1)

    df = pd.read_parquet(INPUT_FILE).copy()
    if "ticker" not in df.columns:
        raise RuntimeError("Coluna 'ticker' não encontrada no input.")

    accepted_rows: list[dict[str, str]] = []
    rejected_rows: list[dict[str, str]] = []

    for raw in df["ticker"].tolist():
        if pd.isna(raw):
            rejected_rows.append({"ticker_raw": str(raw), "ticker_clean": "", "reason": "nan_or_null"})
            continue

        ticker = normalize_ticker(raw)
        if ticker in {"", "-", " "}:
            rejected_rows.append({"ticker_raw": str(raw), "ticker_clean": ticker, "reason": "garbage"})
            continue

        suffix = detect_suffix(ticker)
        if suffix is None:
            rejected_rows.append({"ticker_raw": str(raw), "ticker_clean": ticker, "reason": "invalid_suffix"})
            continue

        if not ALNUM_REGEX.match(ticker):
            rejected_rows.append({"ticker_raw": str(raw), "ticker_clean": ticker, "reason": "invalid_chars"})
            continue

        prefix = ticker[: -len(suffix)] if suffix else ticker
        if len(prefix) < 3:
            rejected_rows.append({"ticker_raw": str(raw), "ticker_clean": ticker, "reason": "invalid_syntax"})
            continue

        accepted_rows.append({"ticker": ticker, "suffix": suffix})

    clean_df = pd.DataFrame(accepted_rows).drop_duplicates(subset=["ticker"]).reset_index(drop=True)
    rejected_df = pd.DataFrame(rejected_rows)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    clean_df[["ticker"]].to_parquet(OUTPUT_FILE, index=False)
    rejected_df.to_csv(REJECTED_FILE, index=False)

    total_input = len(df)
    total_accepted = len(clean_df)
    total_rejected = total_input - total_accepted

    if total_accepted <= 0:
        raise RuntimeError("Final Output vazio após sanitização.")

    suffix_counts = clean_df["suffix"].value_counts().sort_index()

    required_bdr_suffixes = {"31", "32", "33", "34"}
    input_bdr_suffixes = set()
    for value in df["ticker"].tolist():
        ticker = normalize_ticker(value)
        suffix = detect_suffix(ticker)
        if suffix in required_bdr_suffixes:
            input_bdr_suffixes.add(suffix)

    present_bdr_suffixes = set(clean_df.loc[clean_df["suffix"].isin(required_bdr_suffixes), "suffix"].unique())
    missing_from_output = sorted(input_bdr_suffixes - present_bdr_suffixes)
    if missing_from_output:
        raise RuntimeError(f"Sufixos BDR presentes no input e ausentes no output: {missing_from_output}")

    print("TASK T020 - UNIVERSE SANITY (SUFFIX LOGIC)")
    print("")
    print(f"Total Input: {total_input} | Accepted: {total_accepted} | Rejected: {total_rejected}")
    print("")
    print("SUFFIX BREAKDOWN")
    for suffix in VALID_SUFFIXES:
        print(f"- Ends with {suffix}: {int(suffix_counts.get(suffix, 0))} tickers")
    print(f"- BDR suffixes present in INPUT: {sorted(input_bdr_suffixes)}")
    print(f"- BDR suffixes present in OUTPUT: {sorted(present_bdr_suffixes)}")
    suffix_39_count = int(suffix_counts.get("39", 0))
    ivvb39_present = bool((clean_df["ticker"] == "IVVB39").any())
    spxi39_present = bool((clean_df["ticker"] == "SPXI39").any())
    any_39_present = suffix_39_count > 0
    print(f"- IVVB39 present: {ivvb39_present}")
    print(f"- SPXI39 present: {spxi39_present}")
    print(f"- Any suffix 39 present: {any_39_present}")
    print(f"- Count suffix 39: {suffix_39_count}")
    print("")
    print("FIRST 5 CLEAN")
    for ticker in clean_df["ticker"].head(5).tolist():
        print(f"- {ticker}")
    print("")
    print("LAST 5 CLEAN")
    for ticker in clean_df["ticker"].tail(5).tolist():
        print(f"- {ticker}")
    print("")
    print("FILES")
    print(f"- clean_output: {OUTPUT_FILE}")
    print(f"- rejected_log: {REJECTED_FILE}")
    print("")
    print("OVERALL STATUS")
    print("OVERALL STATUS: [[ PASS ]]")


if __name__ == "__main__":
    main()
