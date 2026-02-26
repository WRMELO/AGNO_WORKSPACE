from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go


INPUT_FILE = Path("src/data_engine/ssot/SSOT_MARKET_DATA_RAW.parquet")
OUTPUT_DIR = Path("data/verification_plots")
FOCUS_TICKERS = ["VIVT3", "PETR4", "MGLU3", "AMER3", "VALE3"]


def parse_split_value(raw: object) -> float:
    if raw is None:
        return 1.0
    text = str(raw).strip().lower()
    if text in {"", "nan", "none", "null"}:
        return 1.0

    # Caso "2 para 1", "10:1", etc.
    ratio_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:para|:|/)\s*(\d+(?:[.,]\d+)?)", text)
    if ratio_match:
        num = float(ratio_match.group(1).replace(",", "."))
        den = float(ratio_match.group(2).replace(",", "."))
        if den == 0:
            return 1.0
        return num / den

    # Caso numérico simples: 2.0 (split), 0.1 (reverse split).
    text_num = text.replace(",", ".")
    try:
        value = float(text_num)
    except ValueError:
        return 1.0

    if value <= 0:
        return 1.0
    return value


def calculate_split_adjusted(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy().sort_values("date").reset_index(drop=True)
    out["splits_factor"] = out["splits"].apply(parse_split_value)
    out["splits_factor"] = out["splits_factor"].replace([np.inf, -np.inf], np.nan).fillna(1.0)
    out.loc[out["splits_factor"] <= 0, "splits_factor"] = 1.0

    # Multiplicador para normalizar histórico ao basis atual (split-only).
    out["split_multiplier"] = 1.0 / out["splits_factor"]
    future_factor = out["split_multiplier"].shift(-1).fillna(1.0).iloc[::-1].cumprod().iloc[::-1]
    out["cumulative_factor"] = future_factor
    out["close_split_adj"] = pd.to_numeric(out["close"], errors="coerce") * out["cumulative_factor"]
    return out


def save_plot(df: pd.DataFrame, title: str, output_file: Path) -> None:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["date"], y=df["close"], mode="lines", name="close_raw"))
    fig.add_trace(go.Scatter(x=df["date"], y=df["close_split_adj"], mode="lines", name="close_split_adj"))
    fig.update_layout(
        title=title,
        xaxis_title="date",
        yaxis_title="price",
        template="plotly_white",
        legend=dict(orientation="h"),
    )
    output_file.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(output_file), include_plotlyjs="cdn")


def main() -> None:
    if not INPUT_FILE.exists():
        raise RuntimeError(f"Arquivo não encontrado: {INPUT_FILE}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    all_df = pd.read_parquet(INPUT_FILE, columns=["ticker", "date", "close", "splits", "dividends"])
    all_df["ticker"] = all_df["ticker"].astype(str).str.upper().str.strip()
    all_df["date"] = pd.to_datetime(all_df["date"], errors="coerce")
    all_df["close"] = pd.to_numeric(all_df["close"], errors="coerce")
    all_df = all_df.dropna(subset=["ticker", "date", "close"]).reset_index(drop=True)

    prepared: dict[str, pd.DataFrame] = {}
    for ticker in FOCUS_TICKERS:
        data = all_df[all_df["ticker"] == ticker].copy()
        if data.empty:
            continue
        prepared[ticker] = calculate_split_adjusted(data)

    # Plot 1: VIVT3
    if "VIVT3" in prepared:
        save_plot(
            prepared["VIVT3"],
            "VIVT3 Split Verification (Raw vs Split-Only Adjusted)",
            OUTPUT_DIR / "VIVT3_Split_Verification.html",
        )

    # Plot 2: MGLU3
    if "MGLU3" in prepared:
        save_plot(
            prepared["MGLU3"],
            "MGLU3 Split Verification (Raw vs Split-Only Adjusted)",
            OUTPUT_DIR / "MGLU3_Split_Verification.html",
        )

    # Plot 3: PETR4 dividend behavior
    if "PETR4" in prepared:
        save_plot(
            prepared["PETR4"],
            "PETR4 Dividend Check (Split-Only: Dividend Drops Preserved)",
            OUTPUT_DIR / "PETR4_Dividend_Check.html",
        )

    def split_dates(df: pd.DataFrame) -> list[str]:
        return df.loc[df["splits_factor"] != 1.0, "date"].dt.strftime("%Y-%m-%d").tolist()

    vivt_splits = split_dates(prepared["VIVT3"]) if "VIVT3" in prepared else []
    mglu_splits = split_dates(prepared["MGLU3"]) if "MGLU3" in prepared else []

    print("TASK V001 - SPLIT LOGIC CHECK")
    print("")
    print("FILES GENERATED")
    for file_name in ["VIVT3_Split_Verification.html", "MGLU3_Split_Verification.html", "PETR4_Dividend_Check.html"]:
        path = OUTPUT_DIR / file_name
        print(f"- {path}: {'PASS' if path.exists() else 'FAIL'}")
    print("")
    print("SPLIT EVENTS DETECTED")
    print(f"- VIVT3 split_dates: {vivt_splits if vivt_splits else 'NONE'}")
    print(f"- MGLU3 split_dates: {mglu_splits if mglu_splits else 'NONE'}")
    print("")
    print("CHECK")
    print("- Split-only adjustment applied (dividends not used for back-adjustment).")
    print("- PETR4 should keep dividend drops in close_split_adj curve.")
    print("")
    print("OVERALL STATUS")
    ok = all((OUTPUT_DIR / n).exists() for n in ["VIVT3_Split_Verification.html", "MGLU3_Split_Verification.html", "PETR4_Dividend_Check.html"])
    print("OVERALL STATUS: [[ PASS ]]" if ok else "OVERALL STATUS: [[ FAIL ]]")


if __name__ == "__main__":
    main()
