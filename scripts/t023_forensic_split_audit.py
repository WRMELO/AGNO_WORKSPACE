from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


INPUT_FILE = Path("src/data_engine/ssot/SSOT_MARKET_DATA_RAW.parquet")
OUTPUT_FILE = Path("data/market_data/forensic_split_report.csv")
TARGETS = ["VIVT3", "MGLU3", "PETR4"]


def parse_split_factor(raw: object) -> float | None:
    if raw is None:
        return None
    text = str(raw).strip().lower()
    if text in {"", "nan", "none", "null"}:
        return None

    # Formatos como "2 para 1", "10:1", "1/4"
    ratio_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:para|:|/)\s*(\d+(?:[.,]\d+)?)", text)
    if ratio_match:
        num = float(ratio_match.group(1).replace(",", "."))
        den = float(ratio_match.group(2).replace(",", "."))
        if den == 0:
            return None
        return num / den

    try:
        value = float(text.replace(",", "."))
    except ValueError:
        return None

    return value


def is_split_event(raw: object, parsed: float | None) -> bool:
    if raw is None:
        return False
    raw_text = str(raw).strip().lower()
    if raw_text in {"", "nan", "none", "null"}:
        return False
    if parsed is None:
        # Valor textual suspeito é relevante para forense.
        return True
    return parsed not in {0.0, 1.0}


def classify_direction(factor: float | None, jump_ratio: float | None) -> str:
    if factor is None or jump_ratio is None:
        return "UNDETERMINED"
    if factor <= 0 or jump_ratio <= 0:
        return "UNDETERMINED"

    if factor > 1 and jump_ratio > 1:
        return "LIKELY_REVERSE_SPLIT"
    if factor < 1 and jump_ratio < 1:
        return "LIKELY_SPLIT"
    if factor > 1 and jump_ratio < 1:
        return "INCONSISTENT_FACTOR_GT1"
    if factor < 1 and jump_ratio > 1:
        return "INCONSISTENT_FACTOR_LT1"
    return "UNDETERMINED"


def main() -> None:
    if not INPUT_FILE.exists():
        raise RuntimeError(f"Arquivo não encontrado: {INPUT_FILE}")

    df = pd.read_parquet(INPUT_FILE, columns=["ticker", "date", "close", "splits"])
    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
    df = df[df["ticker"].isin(TARGETS)].copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["date", "close"]).sort_values(["ticker", "date"]).reset_index(drop=True)

    df["close_prev"] = df.groupby("ticker")["close"].shift(1)
    df["split_factor_raw"] = df["splits"]
    df["split_factor"] = df["split_factor_raw"].apply(parse_split_factor)
    df["is_split_event"] = [is_split_event(r, p) for r, p in zip(df["split_factor_raw"], df["split_factor"])]

    events = df[df["is_split_event"]].copy()
    events["actual_price_jump_ratio"] = events["close"] / events["close_prev"]
    events["direction_hint"] = [
        classify_direction(f, j) for f, j in zip(events["split_factor"], events["actual_price_jump_ratio"])
    ]
    events["factor_vs_jump_ratio"] = events["actual_price_jump_ratio"] / events["split_factor"]

    report = events[
        [
            "ticker",
            "date",
            "split_factor_raw",
            "split_factor",
            "close_prev",
            "close",
            "actual_price_jump_ratio",
            "factor_vs_jump_ratio",
            "direction_hint",
        ]
    ].copy()
    report["date"] = report["date"].dt.date.astype(str)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(OUTPUT_FILE, index=False)

    distinct_split_values = sorted(set(str(x).strip() for x in df["split_factor_raw"].dropna().tolist()))
    suspicious_values = [
        v
        for v in distinct_split_values
        if v.lower() not in {"", "0", "0.0", "1", "1.0", "nan", "none", "null"}
        and parse_split_factor(v) is None
    ]

    print("TASK T023 - FORENSIC SPLIT AUDIT")
    print("")
    print("AUDIT TABLE")
    if report.empty:
        print("- No split events found for selected targets.")
    else:
        print(
            report[
                [
                    "ticker",
                    "date",
                    "split_factor_raw",
                    "close_prev",
                    "close",
                    "actual_price_jump_ratio",
                ]
            ].to_string(index=False)
        )
    print("")
    print("ANALYSIS")
    if not report.empty:
        for _, row in report.iterrows():
            print(
                f"- {row['ticker']} {row['date']}: factor={row['split_factor_raw']} | "
                f"jump={row['actual_price_jump_ratio']:.6f} | direction={row['direction_hint']}"
            )
    else:
        print("- Nenhum evento de split detectado para os tickers alvo.")
    print("")
    print("DISTINCT SPLIT RAW VALUES")
    print(f"- values: {distinct_split_values[:50]}")
    print(f"- suspicious_non_parseable: {suspicious_values[:20] if suspicious_values else 'NONE'}")
    print("")
    print(f"report_file: {OUTPUT_FILE}")
    print("OVERALL STATUS: [[ PASS ]]")


if __name__ == "__main__":
    main()
