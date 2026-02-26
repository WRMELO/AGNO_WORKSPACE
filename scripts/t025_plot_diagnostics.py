from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd


if not ("agno_env" in sys.prefix or ".venv" in sys.prefix):
    raise RuntimeError("FATAL: Not in agno_env!")


CANONICAL_FILE = Path("src/data_engine/ssot/SSOT_CANONICAL_BASE.parquet")
DIAGNOSTICS_FILE = Path("src/data_engine/diagnostics/SSOT_BURNER_DIAGNOSTICS.parquet")
OUT_DIR = Path("src/verification_plots/T025_DIAGNOSTIC_CHECK")
TICKERS = ["PETR4", "VALE3", "WEGE3"]
START_DATE = pd.Timestamp("2018-01-01")
END_DATE = pd.Timestamp("2018-12-31")
WARMUP_DAYS = 60


def load_joined() -> pd.DataFrame:
    canonical_cols = [
        "ticker",
        "date",
        "close_operational",
        "xbar_ucl",
        "xbar_lcl",
        "xbar_value",
    ]
    diagnostics_cols = [
        "ticker",
        "date",
        "execution_signal",
        "slope_60",
        "f1_points",
    ]

    cdf = pd.read_parquet(CANONICAL_FILE, columns=canonical_cols)
    ddf = pd.read_parquet(DIAGNOSTICS_FILE, columns=diagnostics_cols)

    for df in (cdf, ddf):
        df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()

    cdf = cdf.dropna(subset=["ticker", "date", "close_operational"])
    ddf = ddf.dropna(subset=["ticker", "date"])

    merged = cdf.merge(ddf, on=["ticker", "date"], how="inner")
    merged = merged.sort_values(["ticker", "date"], ascending=[True, True]).reset_index(drop=True)
    return merged


def plot_ticker(df: pd.DataFrame, ticker: str) -> Path:
    tdf = df[
        (df["ticker"] == ticker)
        & (df["date"] >= START_DATE)
        & (df["date"] <= END_DATE)
    ].copy()

    if tdf.empty:
        raise RuntimeError(f"Sem dados para ticker {ticker} no período solicitado.")

    tdf = tdf.sort_values("date").reset_index(drop=True)
    warmup_end_idx = min(WARMUP_DAYS - 1, len(tdf) - 1)
    warmup_start_date = tdf.loc[0, "date"]
    warmup_end_date = tdf.loc[warmup_end_idx, "date"]

    fig, (ax1, ax2) = plt.subplots(
        2,
        1,
        figsize=(16, 10),
        sharex=True,
        gridspec_kw={"height_ratios": [3, 2]},
    )

    # Subplot 1: preço + bandas SPC + execução BUY
    ax1.plot(tdf["date"], tdf["close_operational"], color="#1f77b4", linewidth=1.5, label="close_operational")
    ax1.plot(tdf["date"], tdf["xbar_value"], color="#ff7f0e", linewidth=1.2, label="XBar")
    ax1.plot(tdf["date"], tdf["xbar_ucl"], color="#d62728", linewidth=1.0, linestyle="--", label="UCL")
    ax1.plot(tdf["date"], tdf["xbar_lcl"], color="#2ca02c", linewidth=1.0, linestyle="--", label="LCL")

    buy_df = tdf[tdf["execution_signal"] == "BUY"]
    if not buy_df.empty:
        ax1.scatter(
            buy_df["date"],
            buy_df["close_operational"],
            marker="^",
            s=80,
            color="green",
            edgecolor="black",
            linewidth=0.5,
            label="execution_signal=BUY",
            zorder=5,
        )

    ax1.axvspan(warmup_start_date, warmup_end_date, color="gray", alpha=0.15, label="Warm-up (60 dias)")
    ax1.set_title(f"T025 Proof - {ticker} - 2018")
    ax1.set_ylabel("Preço")
    ax1.grid(alpha=0.25)
    ax1.legend(loc="upper left", ncol=3)

    # Subplot 2: slope + F1 score
    ax2.plot(tdf["date"], tdf["slope_60"], color="#9467bd", linewidth=1.5, label="slope_60")
    ax2.axhline(0.0, color="black", linewidth=1.0, linestyle=":", label="zero")
    ax2.set_ylabel("Slope 60d")
    ax2.grid(alpha=0.25)

    ax2b = ax2.twinx()
    ax2b.plot(tdf["date"], tdf["f1_points"], color="#8c564b", linewidth=1.2, alpha=0.9, label="f1_points")
    ax2b.set_ylabel("F1 Points")

    ax2.axvspan(warmup_start_date, warmup_end_date, color="gray", alpha=0.15)
    lines_l, labels_l = ax2.get_legend_handles_labels()
    lines_r, labels_r = ax2b.get_legend_handles_labels()
    ax2.legend(lines_l + lines_r, labels_l + labels_r, loc="upper left")

    ax2.set_xlabel("Data")
    ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    plt.setp(ax2.get_xticklabels(), rotation=45, ha="right")

    out_file = OUT_DIR / f"T025_{ticker}_2018_PROOF.png"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_file, dpi=150)
    plt.close(fig)
    return out_file


def main() -> None:
    if not CANONICAL_FILE.exists():
        raise RuntimeError(f"Arquivo ausente: {CANONICAL_FILE}")
    if not DIAGNOSTICS_FILE.exists():
        raise RuntimeError(f"Arquivo ausente: {DIAGNOSTICS_FILE}")

    joined = load_joined()

    print("TASK T025 - VISUAL VALIDATION DIAGNOSTICS")
    print("")
    print(f"JOIN ROWS: {len(joined)}")
    print(f"PERIOD: {START_DATE.date()} .. {END_DATE.date()}")
    print(f"WARM-UP: primeiros {WARMUP_DAYS} pregões por ticker")
    print("")

    generated: list[Path] = []
    for ticker in TICKERS:
        out_file = plot_ticker(joined, ticker)
        generated.append(out_file)
        sample = joined[
            (joined["ticker"] == ticker)
            & (joined["date"] >= START_DATE)
            & (joined["date"] <= END_DATE)
        ]
        buys = int((sample["execution_signal"] == "BUY").sum())
        print(f"- {ticker}: {len(sample)} linhas, BUY executions={buys}, file={out_file}")

    print("")
    print("OVERALL STATUS: [[ PASS ]]")


if __name__ == "__main__":
    main()
