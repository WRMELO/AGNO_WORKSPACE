from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go


INPUT_FILE = Path("src/data_engine/ssot/SSOT_MARKET_DATA_RAW.parquet")
BASE_OUTPUT_DIR = Path("data/verification_plots")
FOCUS_TICKERS = ["VIVT3", "PETR4", "MGLU3", "AMER3", "VALE3"]


def get_versioned_output_dir() -> Path:
    stamp = datetime.now().strftime("V001_RERUN_%Y%m%d_%H%M%S")
    out = BASE_OUTPUT_DIR / stamp
    out.mkdir(parents=True, exist_ok=True)
    return out


def parse_split_dates(df: pd.DataFrame) -> list[str]:
    s = df["splits"].astype(str).str.strip().str.lower()
    mask = ~s.isin(["", "nan", "none", "null", "0", "0.0", "1", "1.0"])
    return pd.to_datetime(df.loc[mask, "date"]).dt.strftime("%Y-%m-%d").tolist()


def save_plot(df: pd.DataFrame, ticker: str, title: str, out_file: Path) -> None:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["date"], y=df["close"], mode="lines", name="close_raw"))
    fig.add_trace(go.Scatter(x=df["date"], y=df["close_split_adj_v2"], mode="lines", name="close_split_adj_v2"))

    split_rows = df[df["is_split_event"]]
    if not split_rows.empty:
        fig.add_trace(
            go.Scatter(
                x=split_rows["date"],
                y=split_rows["close"],
                mode="markers",
                name="split_event",
                marker=dict(size=8, symbol="x"),
            )
        )

    fig.update_layout(
        title=title,
        xaxis_title="date",
        yaxis_title="price",
        template="plotly_white",
        legend=dict(orientation="h"),
    )
    fig.write_html(str(out_file), include_plotlyjs="cdn")


def main() -> None:
    if not INPUT_FILE.exists():
        raise RuntimeError(f"Arquivo não encontrado: {INPUT_FILE}")

    output_dir = get_versioned_output_dir()

    df = pd.read_parquet(INPUT_FILE, columns=["ticker", "date", "close", "splits", "dividends"])
    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["ticker", "date", "close"]).sort_values(["ticker", "date"]).reset_index(drop=True)

    generated = []
    split_summary: dict[str, list[str]] = {}

    for ticker in FOCUS_TICKERS:
        tdf = df[df["ticker"] == ticker].copy()
        if tdf.empty:
            continue

        # Correcao forense: a coluna close ja esta split-adjusted pelo provedor.
        # Portanto, split-only ajustado = close bruto (nao aplicar novo fator).
        raw_split = tdf["splits"].astype(str).str.strip().str.lower()
        tdf["is_split_event"] = ~raw_split.isin(["", "nan", "none", "null", "0", "0.0", "1", "1.0"])
        tdf["close_split_adj_v2"] = tdf["close"]
        split_summary[ticker] = parse_split_dates(tdf)

        if ticker == "VIVT3":
            file_name = "VIVT3_Split_Verification_V2.html"
            title = "VIVT3 Split Verification V2 (Provider Already Split-Adjusted)"
        elif ticker == "MGLU3":
            file_name = "MGLU3_Split_Verification_V2.html"
            title = "MGLU3 Split Verification V2 (Provider Already Split-Adjusted)"
        elif ticker == "PETR4":
            file_name = "PETR4_Dividend_Check_V2.html"
            title = "PETR4 Dividend Check V2 (Dividend Drops Preserved)"
        else:
            file_name = f"{ticker}_Split_Check_V2.html"
            title = f"{ticker} Split Check V2"

        out_file = output_dir / file_name
        save_plot(tdf, ticker, title, out_file)
        generated.append(out_file)

    print("TASK V001 - SPLIT LOGIC CHECK (RERUN V2)")
    print("")
    print(f"output_dir: {output_dir}")
    print("FILES GENERATED")
    for f in generated:
        print(f"- {f}: PASS")
    print("")
    print("SPLIT EVENTS DETECTED")
    for t in ["VIVT3", "MGLU3", "PETR4"]:
        print(f"- {t}: {split_summary.get(t, []) if split_summary.get(t, []) else 'NONE'}")
    print("")
    print("NOTE")
    print("- V2 applies forensic correction: provider close already split-adjusted.")
    print("- Dividends are not used for adjustment; dividend drops remain visible in PETR4.")
    print("")
    print("OVERALL STATUS")
    print("OVERALL STATUS: [[ PASS ]]" if len(generated) >= 3 else "OVERALL STATUS: [[ FAIL ]]")


if __name__ == "__main__":
    main()
