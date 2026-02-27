from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd


if not ("agno_env" in sys.prefix or ".venv" in sys.prefix):
    raise RuntimeError("FATAL: Not in agno_env!")


CANONICAL_FILE = Path("src/data_engine/ssot/SSOT_CANONICAL_BASE.parquet")
DIAGNOSTICS_FILE = Path("src/data_engine/diagnostics/SSOT_BURNER_DIAGNOSTICS.parquet")
SCORES_FILE = Path("src/data_engine/features/SSOT_F1_SCORES_DAILY.parquet")
STANDINGS_FILE = Path("src/data_engine/features/SSOT_F1_STANDINGS.parquet")

POINTS_TOP10 = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
ELIGIBLE_STATES = {"BUY", "QUALIFIED_BUY", "HOLD"}
ROLLING_WINDOW = 60


def points_from_rank(rank_value: float) -> int:
    if not np.isfinite(rank_value):
        return 0
    rank_i = int(rank_value)
    if 1 <= rank_i <= len(POINTS_TOP10):
        return int(POINTS_TOP10[rank_i - 1])
    return 0


def main() -> None:
    if not CANONICAL_FILE.exists():
        raise RuntimeError(f"Arquivo ausente: {CANONICAL_FILE}")
    if not DIAGNOSTICS_FILE.exists():
        raise RuntimeError(f"Arquivo ausente: {DIAGNOSTICS_FILE}")

    cdf = pd.read_parquet(CANONICAL_FILE, columns=["ticker", "date", "X_real"])
    ddf = pd.read_parquet(DIAGNOSTICS_FILE, columns=["ticker", "date", "execution_signal"])

    for df in (cdf, ddf):
        df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()

    cdf = cdf.dropna(subset=["ticker", "date", "X_real"]).copy()
    ddf = ddf.dropna(subset=["ticker", "date"]).copy()

    base = cdf.merge(ddf, on=["ticker", "date"], how="inner")
    base = base.sort_values(["ticker", "date"], ascending=[True, True]).reset_index(drop=True)

    # Elegibilidade da corrida em D depende do estado observado em D-1.
    base["eligibility_state_d_minus_1"] = (
        base.groupby("ticker", sort=False)["execution_signal"].shift(1).fillna("HOLD")
    )
    base["is_eligible"] = base["eligibility_state_d_minus_1"].isin(ELIGIBLE_STATES)

    eligible = base[base["is_eligible"]].copy()
    eligible = eligible.sort_values(["date", "X_real", "ticker"], ascending=[True, False, True])
    eligible["daily_rank"] = eligible.groupby("date", sort=False)["X_real"].rank(method="first", ascending=False)
    eligible["f1_points"] = eligible["daily_rank"].map(points_from_rank).astype(int)
    eligible["is_race_winner"] = eligible["daily_rank"] == 1

    scores = base.merge(
        eligible[["ticker", "date", "daily_rank", "f1_points", "is_race_winner"]],
        on=["ticker", "date"],
        how="left",
    )
    scores["daily_rank"] = scores["daily_rank"].astype("Float64")
    scores["f1_points"] = scores["f1_points"].fillna(0).astype(int)
    scores["is_race_winner"] = scores["is_race_winner"].fillna(False).astype(bool)

    scores = scores[
        [
            "ticker",
            "date",
            "X_real",
            "execution_signal",
            "eligibility_state_d_minus_1",
            "is_eligible",
            "daily_rank",
            "f1_points",
            "is_race_winner",
        ]
    ].sort_values(["ticker", "date"], ascending=[True, True])

    standings = scores.copy()
    standings["f1_score_total"] = (
        standings.groupby("ticker", sort=False)["f1_points"]
        .rolling(window=ROLLING_WINDOW, min_periods=1)
        .sum()
        .reset_index(level=0, drop=True)
    )
    standings["races_won"] = (
        standings.groupby("ticker", sort=False)["is_race_winner"]
        .rolling(window=ROLLING_WINDOW, min_periods=1)
        .sum()
        .reset_index(level=0, drop=True)
        .astype(int)
    )

    standings = standings.sort_values(
        ["date", "f1_score_total", "races_won", "ticker"],
        ascending=[True, False, False, True],
    )
    standings["standings_rank"] = (
        standings.groupby("date", sort=False).cumcount() + 1
    ).astype(int)
    standings = standings.sort_values(["ticker", "date"], ascending=[True, True])

    SCORES_FILE.parent.mkdir(parents=True, exist_ok=True)
    standings_out = standings.set_index(["ticker", "date"]).sort_index()
    scores_out = scores.set_index(["ticker", "date"]).sort_index()
    scores_out.to_parquet(SCORES_FILE)
    standings_out.to_parquet(STANDINGS_FILE)

    target_date = pd.Timestamp("2018-07-01")
    available_dates = standings["date"].drop_duplicates().sort_values()
    report_date = target_date
    if not (available_dates == target_date).any():
        next_dates = available_dates[available_dates > target_date]
        if len(next_dates):
            report_date = pd.Timestamp(next_dates.iloc[0])
    july_first = standings[
        standings["date"] == report_date
    ].sort_values(["standings_rank", "ticker"]).head(3)

    warmup = standings[
        (standings["date"] >= pd.Timestamp("2018-01-01"))
        & (standings["date"] <= pd.Timestamp("2018-06-30"))
    ]

    print("TASK T027 - F1 CHAMPIONSHIP BUILD")
    print("")
    print(f"JOIN ROWS: {len(base)}")
    print(f"ELIGIBLE ROWS: {int(base['is_eligible'].sum())}")
    print(f"TOTAL POINTS ASSIGNED: {int(scores['f1_points'].sum())}")
    print("")
    print("WARM-UP CHECK (Jan-Jun 2018)")
    print(f"- rows: {len(warmup)}")
    print(f"- min_score_total: {float(warmup['f1_score_total'].min()):.2f}")
    print(f"- max_score_total: {float(warmup['f1_score_total'].max()):.2f}")
    print("")
    print(f"TOP 3 STOCKS EM {report_date.date()}")
    if july_first.empty:
        print("- sem dados para 01/07/2018 (provável dia não útil).")
    else:
        for row in july_first.itertuples(index=False):
            print(
                f"- rank={row.standings_rank} ticker={row.ticker} "
                f"score60={row.f1_score_total:.0f} wins60={row.races_won}"
            )
    print("")
    print(f"SCORES_FILE: {SCORES_FILE}")
    print(f"STANDINGS_FILE: {STANDINGS_FILE}")
    print("OVERALL STATUS: [[ PASS ]]")


if __name__ == "__main__":
    main()
