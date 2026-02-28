#!/usr/bin/env python3
"""T049 - Build episode catalog from T048 condition ledger and T039 trade ledger."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


TASK_ID = "T049-EPISODE-CATALOG-V1"
ROOT = Path("/home/wilson/AGNO_WORKSPACE")
INPUT_T048 = ROOT / "src/data_engine/portfolio/T048_CONDITION_LEDGER_T039.parquet"
INPUT_T039_LEDGER = ROOT / "src/data_engine/portfolio/T039_PORTFOLIO_LEDGER.parquet"
OUTPUT_PARQUET = ROOT / "src/data_engine/portfolio/T049_EPISODE_CATALOG_T048_T039.parquet"
OUTPUT_REPORT = ROOT / "outputs/governanca/T049-EPISODE-CATALOG-V1_report.md"
OUTPUT_MANIFEST = ROOT / "outputs/governanca/T049-EPISODE-CATALOG-V1_manifest.json"
SCRIPT_PATH = ROOT / "scripts/t049_build_episode_catalog.py"


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def as_bool(series: pd.Series) -> pd.Series:
    return series.fillna(False).astype(bool)


def episode_class_from_market(df: pd.DataFrame) -> pd.Series:
    return np.where(as_bool(df["market_special_cause_flag"]), "MARKET_SPECIAL_CAUSE", "MARKET_NORMAL")


def episode_id_from_class(episode_class: pd.Series) -> pd.Series:
    starts = episode_class.ne(episode_class.shift(1)).astype(int)
    return starts.cumsum().astype(int)


def build_episode_table(daily: pd.DataFrame, trade_agg: pd.DataFrame) -> pd.DataFrame:
    grouped = daily.groupby("episode_id", as_index=False)

    episodes = grouped.agg(
        episode_class=("episode_class", "first"),
        episode_start_date=("date", "min"),
        episode_end_date=("date", "max"),
        n_days=("date", "size"),
        market_logret_sum=("market_logret_1d", "sum"),
        market_dd_min=("market_drawdown", "min"),
        market_dd_end=("market_drawdown", "last"),
        market_special_cause_days=("market_special_cause_flag", lambda s: int(as_bool(s).sum())),
        market_max_persistence=("market_signal_persistence", "max"),
        portfolio_logret_sum=("portfolio_logret_1d", "sum"),
        portfolio_dd_min=("portfolio_drawdown", "min"),
        portfolio_dd_end=("portfolio_drawdown", "last"),
        avg_cash_weight=("portfolio_cash_weight", "mean"),
        avg_exposure_risk=("portfolio_exposure_risk", "mean"),
        defensive_days=("portfolio_regime_defensivo", lambda s: int(as_bool(s).sum())),
        switch_days=("portfolio_switch_flag", lambda s: int(as_bool(s).sum())),
        blocked_buy_days=("portfolio_blocked_buy_flag", lambda s: int(as_bool(s).sum())),
    )

    episodes["market_return_simple"] = np.exp(episodes["market_logret_sum"]) - 1.0
    episodes["portfolio_return_simple"] = np.exp(episodes["portfolio_logret_sum"]) - 1.0

    episodes = episodes.merge(trade_agg, on="episode_id", how="left")
    episodes["n_trades"] = episodes["n_trades"].fillna(0).astype(int)
    episodes["cost_brl_sum"] = episodes["cost_brl_sum"].fillna(0.0)
    episodes["notional_abs_sum"] = episodes["notional_abs_sum"].fillna(0.0)
    episodes["net_notional_sum"] = episodes["net_notional_sum"].fillna(0.0)
    episodes["unique_tickers_traded"] = episodes["unique_tickers_traded"].fillna(0).astype(int)

    episodes = episodes.sort_values(["episode_start_date", "episode_id"]).reset_index(drop=True)
    return episodes


def render_report(episodes: pd.DataFrame, path: Path) -> None:
    top_worst_return = episodes.sort_values("portfolio_return_simple", ascending=True).head(10)
    top_cost = episodes.sort_values("cost_brl_sum", ascending=False).head(10)
    after_202108 = episodes[episodes["episode_start_date"] >= pd.Timestamp("2021-08-01")]

    lines = [
        f"# {TASK_ID} Report",
        "",
        "## Contagem geral",
        "",
        f"- Episodios totais: {len(episodes)}",
        f"- Inicio: {episodes['episode_start_date'].min().date()}",
        f"- Fim: {episodes['episode_end_date'].max().date()}",
        "",
        "## Top-10 episodios por pior portfolio_return_simple",
        "",
        "| episode_id | class | start | end | n_days | portfolio_return_simple | cost_brl_sum | n_trades |",
        "|---:|---|---|---|---:|---:|---:|---:|",
    ]
    for _, row in top_worst_return.iterrows():
        lines.append(
            f"| {int(row['episode_id'])} | {row['episode_class']} | "
            f"{row['episode_start_date'].date()} | {row['episode_end_date'].date()} | "
            f"{int(row['n_days'])} | {row['portfolio_return_simple']:.6f} | "
            f"{row['cost_brl_sum']:.2f} | {int(row['n_trades'])} |"
        )

    lines += [
        "",
        "## Top-10 episodios por maior cost_brl_sum",
        "",
        "| episode_id | class | start | end | n_days | cost_brl_sum | n_trades | portfolio_return_simple |",
        "|---:|---|---|---|---:|---:|---:|---:|",
    ]
    for _, row in top_cost.iterrows():
        lines.append(
            f"| {int(row['episode_id'])} | {row['episode_class']} | "
            f"{row['episode_start_date'].date()} | {row['episode_end_date'].date()} | "
            f"{int(row['n_days'])} | {row['cost_brl_sum']:.2f} | "
            f"{int(row['n_trades'])} | {row['portfolio_return_simple']:.6f} |"
        )

    lines += [
        "",
        "## Corte >= 2021-08-01",
        "",
        f"- Episodios com inicio >= 2021-08-01: {len(after_202108)}",
    ]
    if len(after_202108) > 0:
        lines += [
            f"- Retorno portfolio agregado (simples, multiplicativo): "
            f"{(after_202108['portfolio_return_simple'].add(1.0).prod() - 1.0):.6f}",
            f"- Custo total BRL: {after_202108['cost_brl_sum'].sum():.2f}",
            f"- Trades totais: {int(after_202108['n_trades'].sum())}",
        ]

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    print(f"HEADER: {TASK_ID}")

    if not INPUT_T048.exists() or not INPUT_T039_LEDGER.exists():
        print("STEP GATES:")
        print("- G1_EPISODE_CATALOG_PRESENT: FAIL (missing required inputs)")
        print("OVERALL STATUS: [[ FAIL ]]")
        return 1

    daily = pd.read_parquet(INPUT_T048).copy()
    trades = pd.read_parquet(INPUT_T039_LEDGER).copy()

    daily["date"] = pd.to_datetime(daily["date"])
    trades["date"] = pd.to_datetime(trades["date"])

    daily = daily.sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)
    daily["episode_class"] = episode_class_from_market(daily)
    daily["episode_id"] = episode_id_from_class(daily["episode_class"])

    date_to_episode = daily[["date", "episode_id"]]
    trades = trades.merge(date_to_episode, on="date", how="left")
    trades_valid = trades[trades["episode_id"].notna()].copy()

    if len(trades_valid) > 0:
        trade_agg = (
            trades_valid.groupby("episode_id", as_index=False)
            .agg(
                n_trades=("ticker", "size"),
                cost_brl_sum=("cost_brl", "sum"),
                notional_abs_sum=("notional", lambda s: s.abs().sum()),
                net_notional_sum=("net_notional", "sum"),
                unique_tickers_traded=("ticker", pd.Series.nunique),
            )
            .assign(episode_id=lambda d: d["episode_id"].astype(int))
        )
    else:
        trade_agg = pd.DataFrame(
            columns=["episode_id", "n_trades", "cost_brl_sum", "notional_abs_sum", "net_notional_sum", "unique_tickers_traded"]
        )

    episodes = build_episode_table(daily, trade_agg)

    OUTPUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MANIFEST.parent.mkdir(parents=True, exist_ok=True)

    episodes.to_parquet(OUTPUT_PARQUET, index=False)
    render_report(episodes, OUTPUT_REPORT)

    required_cols = {
        "episode_id",
        "episode_class",
        "episode_start_date",
        "episode_end_date",
        "n_days",
        "market_return_simple",
        "market_dd_min",
        "market_dd_end",
        "portfolio_return_simple",
        "portfolio_dd_min",
        "portfolio_dd_end",
        "avg_cash_weight",
        "switch_days",
        "blocked_buy_days",
        "n_trades",
        "cost_brl_sum",
        "notional_abs_sum",
    }

    forbidden_prefix_cols = [c for c in episodes.columns if c.startswith("master_")]
    has_market_master_mix = any(c.startswith("market_") and "portfolio" in c for c in episodes.columns)
    g0 = len(forbidden_prefix_cols) == 0 and not has_market_master_mix
    g1 = OUTPUT_PARQUET.exists() and len(episodes) >= 2 and episodes["episode_id"].is_unique
    g2 = required_cols.issubset(set(episodes.columns))

    manifest = {
        "task_id": TASK_ID,
        "inputs_consumed": [str(INPUT_T048), str(INPUT_T039_LEDGER)],
        "outputs_produced": [str(OUTPUT_PARQUET), str(OUTPUT_REPORT), str(OUTPUT_MANIFEST), str(SCRIPT_PATH)],
        "hashes_sha256": {
            str(INPUT_T048): sha256_file(INPUT_T048),
            str(INPUT_T039_LEDGER): sha256_file(INPUT_T039_LEDGER),
            str(OUTPUT_PARQUET): sha256_file(OUTPUT_PARQUET),
            str(OUTPUT_REPORT): sha256_file(OUTPUT_REPORT),
            str(SCRIPT_PATH): sha256_file(SCRIPT_PATH),
        },
    }
    OUTPUT_MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    manifest_data = json.loads(OUTPUT_MANIFEST.read_text(encoding="utf-8"))
    gx = OUTPUT_MANIFEST.exists() and all(
        key in manifest_data for key in ("inputs_consumed", "outputs_produced", "hashes_sha256")
    )

    print("STEP GATES:")
    print(f"- G0_GLOSSARY_COMPLIANCE: {'PASS' if g0 else 'FAIL'}")
    print(f"- G1_EPISODE_CATALOG_PRESENT: {'PASS' if g1 else 'FAIL'}")
    print(f"- G2_SCHEMA_OK: {'PASS' if g2 else 'FAIL'}")
    print(f"- Gx_HASH_MANIFEST_PRESENT: {'PASS' if gx else 'FAIL'}")

    print("RETRY LOG:")
    print("- none")

    print("ARTIFACT LINKS:")
    print(f"- {OUTPUT_PARQUET}")
    print(f"- {OUTPUT_REPORT}")
    print(f"- {OUTPUT_MANIFEST}")
    print(f"- {SCRIPT_PATH}")

    overall = g0 and g1 and g2 and gx
    print(f"OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
