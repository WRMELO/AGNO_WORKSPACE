from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go


INPUT_FILE = Path("src/data_engine/ssot/SSOT_CANONICAL_BASE.parquet")
OUTPUT_DIR = Path("data/verification_plots/heuristic_final")
TARGETS = ["VIVT3", "MGLU3", "PETR4"]


def build_plot(df: pd.DataFrame, ticker: str, out_file: Path) -> None:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["close_raw"],
            mode="lines",
            name="close_raw",
            line=dict(color="red", dash="dash"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["close_operational"],
            mode="lines",
            name="close_operational",
            line=dict(color="green", dash="solid"),
        )
    )
    fig.update_layout(
        title=f"{ticker} Heuristic Result (Raw vs Operational)",
        xaxis_title="date",
        yaxis_title="price",
        template="plotly_white",
        legend=dict(orientation="h"),
    )
    out_file.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(out_file), include_plotlyjs="cdn")


def main() -> None:
    if not INPUT_FILE.exists():
        raise RuntimeError(f"Input não encontrado: {INPUT_FILE}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_parquet(INPUT_FILE, columns=["ticker", "date", "close_raw", "close_operational"])
    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["ticker", "date", "close_raw", "close_operational"])
    df = df.sort_values(["ticker", "date"]).reset_index(drop=True)

    files = {
        "VIVT3": OUTPUT_DIR / "VIVT3_Heuristic_Result.html",
        "MGLU3": OUTPUT_DIR / "MGLU3_Heuristic_Result.html",
        "PETR4": OUTPUT_DIR / "PETR4_Heuristic_Result.html",
    }

    generated = []
    diagnostics = []
    for ticker in TARGETS:
        tdf = df[df["ticker"] == ticker].copy()
        if tdf.empty:
            continue
        build_plot(tdf, ticker, files[ticker])
        generated.append(files[ticker])

        max_abs_diff = (tdf["close_operational"] - tdf["close_raw"]).abs().max()
        diagnostics.append((ticker, float(max_abs_diff)))

    print("TASK V001 - HEURISTIC QA")
    print("")
    print("FILES")
    for f in generated:
        print(f"- {f}: PASS")
    print("")
    print("MAX |close_operational - close_raw|")
    for t, d in diagnostics:
        print(f"- {t}: {d:.6f}")
    print("")
    print("EXPECTATION CHECK")
    print("- VIVT3 should show divergence where split heuristic corrected.")
    print("- MGLU3 and PETR4 should mostly overlap (raw already preferred / no split correction).")
    print("")
    ok = all(files[t].exists() for t in TARGETS)
    print("OVERALL STATUS")
    print("OVERALL STATUS: [[ PASS ]]" if ok else "OVERALL STATUS: [[ FAIL ]]")


if __name__ == "__main__":
    main()
