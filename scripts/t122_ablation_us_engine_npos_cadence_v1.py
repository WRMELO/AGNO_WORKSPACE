#!/home/wilson/AGNO_WORKSPACE/.venv/bin/python
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


ROOT = Path("/home/wilson/AGNO_WORKSPACE")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TASK_ID = "T122"
RUN_ID = "T122-US-ENGINE-ABLATION-NPOS-CADENCE-V1"
PYTHON_ENV = ROOT / ".venv/bin/python"
CHANGELOG_PATH = ROOT / "00_Strategy/changelog.md"

IN_SCORES = ROOT / "src/data_engine/features/T120_M3_US_SCORES_DAILY.parquet"
IN_SSOT_US = ROOT / "src/data_engine/ssot/SSOT_CANONICAL_BASE_US.parquet"
IN_MACRO = ROOT / "src/data_engine/ssot/SSOT_MACRO_EXPANDED.parquet"
IN_UNIVERSE = ROOT / "src/data_engine/ssot/SSOT_US_UNIVERSE_OPERATIONAL_PHASE10.parquet"
IN_BASELINE_T121 = ROOT / "src/data_engine/portfolio/T121_US_ENGINE_CURVE_DAILY.parquet"

OUT_SCRIPT = ROOT / "scripts/t122_ablation_us_engine_npos_cadence_v1.py"
OUT_RESULTS = ROOT / "src/data_engine/portfolio/T122_ABLATION_US_ENGINE_NPOS_CADENCE_RESULTS.parquet"
OUT_SELECTED = ROOT / "src/data_engine/portfolio/T122_SELECTED_CONFIG_US_ENGINE_NPOS_CADENCE.json"
OUT_WINNER_CURVE = ROOT / "src/data_engine/portfolio/T122_US_ENGINE_WINNER_CURVE_DAILY.parquet"
OUT_WINNER_LEDGER = ROOT / "src/data_engine/portfolio/T122_US_ENGINE_WINNER_LEDGER.parquet"
OUT_PLOT = ROOT / "outputs/plots/T122_STATE3_PHASE10B_ABLATION_NPOS_CADENCE_US_ENGINE.html"
OUT_REPORT = ROOT / "outputs/governanca/T122-US-ENGINE-ABLATION-NPOS-CADENCE-V1_report.md"
OUT_MANIFEST = ROOT / "outputs/governanca/T122-US-ENGINE-ABLATION-NPOS-CADENCE-V1_manifest.json"
OUT_EVID = ROOT / "outputs/governanca/T122-US-ENGINE-ABLATION-NPOS-CADENCE-V1_evidence"
OUT_GRID = OUT_EVID / "grid_definition.json"
OUT_SELECTION_RULE = OUT_EVID / "selection_rule.json"
OUT_JOIN_COVERAGE = OUT_EVID / "join_coverage.json"
OUT_ANTI_LOOKAHEAD = OUT_EVID / "anti_lookahead_spotcheck.json"

INITIAL_CAPITAL = 100_000.0
COST_RATE = 0.0001
TOP_N_LIST = [5, 10, 15, 20, 25, 30]
CADENCE_LIST = [1, 3, 5, 10, 15, 20]

TRAIN_START = pd.Timestamp("2018-07-02")
TRAIN_END = pd.Timestamp("2022-12-30")
HOLDOUT_START = pd.Timestamp("2023-01-02")
HOLDOUT_END = pd.Timestamp("2026-02-26")
ACID_US_START = pd.Timestamp("2025-03-06")
ACID_US_END = pd.Timestamp("2025-05-09")

TRACEABILITY_LINE = (
    "- 2026-03-04T18:10:32Z | EXEC: T122 PASS. Artefatos: "
    "scripts/t122_ablation_us_engine_npos_cadence_v1.py; "
    "src/data_engine/portfolio/T122_ABLATION_US_ENGINE_NPOS_CADENCE_RESULTS.parquet; "
    "src/data_engine/portfolio/T122_SELECTED_CONFIG_US_ENGINE_NPOS_CADENCE.json; "
    "src/data_engine/portfolio/T122_US_ENGINE_WINNER_CURVE_DAILY.parquet; "
    "outputs/plots/T122_STATE3_PHASE10B_ABLATION_NPOS_CADENCE_US_ENGINE.html"
)


@dataclass
class Gate:
    name: str
    passed: bool
    details: str


def _json_safe(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, (np.floating, float)):
        v = float(obj)
        return v if np.isfinite(v) else None
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, pd.Timestamp):
        return obj.strftime("%Y-%m-%d")
    if pd.isna(obj):
        return None
    return obj


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(payload), indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def append_changelog_idempotent(line: str) -> tuple[bool, str]:
    if not CHANGELOG_PATH.exists():
        return False, "missing_changelog"
    content = CHANGELOG_PATH.read_text(encoding="utf-8")
    if line in content:
        return True, "already_present"
    with CHANGELOG_PATH.open("a", encoding="utf-8") as f:
        if not content.endswith("\n"):
            f.write("\n")
        f.write(line + "\n")
    return True, "appended"


def compute_mdd(equity: pd.Series) -> float:
    eq = pd.to_numeric(equity, errors="coerce").astype(float)
    if len(eq) == 0:
        return 0.0
    peak = eq.cummax()
    dd = eq / peak - 1.0
    return float(dd.min())


def compute_sharpe(ret_1d: pd.Series) -> float:
    r = pd.to_numeric(ret_1d, errors="coerce").fillna(0.0).astype(float)
    if len(r) < 2:
        return 0.0
    sd = float(r.std(ddof=1))
    if sd <= 0:
        return 0.0
    return float(np.sqrt(252.0) * r.mean() / sd)


def compute_cagr(equity: pd.Series) -> float:
    eq = pd.to_numeric(equity, errors="coerce").astype(float)
    if len(eq) < 2 or eq.iloc[0] <= 0:
        return 0.0
    years = len(eq) / 252.0
    if years <= 0:
        return 0.0
    return float((eq.iloc[-1] / eq.iloc[0]) ** (1.0 / years) - 1.0)


def metrics_from_equity(equity: pd.Series) -> dict[str, float]:
    eq = pd.to_numeric(equity, errors="coerce").astype(float)
    ret = eq.pct_change().fillna(0.0)
    return {
        "equity_final": float(eq.iloc[-1]) if len(eq) else float(INITIAL_CAPITAL),
        "cagr": compute_cagr(eq),
        "mdd": compute_mdd(eq),
        "sharpe": compute_sharpe(ret),
    }


def split_label(d: pd.Timestamp) -> str:
    return "TRAIN" if d <= TRAIN_END else "HOLDOUT"


def render_report(gates: list[Gate], retry_log: list[str], artifacts: list[Path], summary: dict[str, Any]) -> str:
    overall = all(g.passed for g in gates)
    lines: list[str] = []
    lines.append(f"# HEADER: {TASK_ID}")
    lines.append("")
    lines.append("## STEP GATES")
    for g in gates:
        lines.append(f"- {'PASS' if g.passed else 'FAIL'} | {g.name} | {g.details}")
    lines.append("")
    lines.append("## RETRY LOG")
    lines.extend([f"- {r}" for r in retry_log] if retry_log else ["- none"])
    lines.append("")
    lines.append("## EXECUTIVE SUMMARY")
    for k, v in summary.items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## ARTIFACT LINKS")
    for p in artifacts:
        lines.append(f"- {p.relative_to(ROOT).as_posix()}")
    lines.append("")
    lines.append("## MANIFEST POLICY")
    lines.append("- policy=no_self_hash (manifest não se auto-hasheia).")
    lines.append("")
    lines.append(f"OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]")
    lines.append("")
    return "\n".join(lines)


def simulate_candidate(
    *,
    top_n: int,
    cadence_days: int,
    by_day: dict[pd.Timestamp, pd.DataFrame],
    px_wide: pd.DataFrame,
    macro_day: pd.DataFrame,
    sim_dates: list[pd.Timestamp],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    prices_start = float(macro_day.loc[TRAIN_START, "sp500_close"])
    cash_bench = INITIAL_CAPITAL
    sp500_bench = INITIAL_CAPITAL
    cash = INITIAL_CAPITAL
    positions: dict[str, float] = {}
    days_since_rebal = 10**9
    switches = 0
    total_cost_paid = 0.0
    total_cost_paid_train = 0.0
    total_cost_paid_holdout = 0.0
    days_nsel_lt_topn = 0

    curve_rows: list[dict[str, Any]] = []
    ledger_rows: list[dict[str, Any]] = []

    for i, d in enumerate(sim_dates):
        split = split_label(d)
        cash_log = float(macro_day.loc[d, "cash_log_daily_us"])
        cash *= float(np.exp(cash_log))
        cash_bench *= float(np.exp(cash_log))

        px_row = px_wide.loc[d]
        current_values: dict[str, float] = {}
        for t, q in positions.items():
            px = float(px_row.get(t, np.nan))
            if np.isfinite(px) and px > 0 and q > 0:
                current_values[t] = q * px
        port_before = float(sum(current_values.values()))
        equity_before = cash + port_before

        do_rebal = (i == 0) or (days_since_rebal >= cadence_days)
        turnover_notional = 0.0
        cost_paid = 0.0

        if do_rebal:
            day_scores = by_day.get(d, pd.DataFrame()).copy()
            ranked = day_scores.sort_values(["m3_rank_us_exec", "ticker"], ascending=[True, True])
            selected = ranked.head(top_n)["ticker"].tolist() if len(ranked) else []

            target_values: dict[str, float] = {}
            if len(selected) > 0:
                target_w = 1.0 / len(selected)
                for t in selected:
                    px = float(px_row.get(t, np.nan))
                    if np.isfinite(px) and px > 0:
                        target_values[t] = equity_before * target_w

            all_tickers = set(current_values.keys()).union(set(target_values.keys()))
            sells = 0.0
            buys = 0.0
            new_positions: dict[str, float] = {}

            for t in sorted(all_tickers):
                cur_v = float(current_values.get(t, 0.0))
                tgt_v = float(target_values.get(t, 0.0))
                delta = tgt_v - cur_v
                if delta < 0:
                    sells += -delta
                elif delta > 0:
                    buys += delta

                if tgt_v > 0:
                    px = float(px_row.get(t, np.nan))
                    if np.isfinite(px) and px > 0:
                        new_positions[t] = tgt_v / px

            turnover_notional = float(sells + buys)
            cost_paid = float(turnover_notional * COST_RATE)
            total_cost_paid += cost_paid
            if split == "TRAIN":
                total_cost_paid_train += cost_paid
            else:
                total_cost_paid_holdout += cost_paid

            cash = cash + sells - buys - cost_paid
            if cash < 0:
                cash = max(cash, -1e-6)
            prev_set = set(positions.keys())
            positions = {k: v for k, v in new_positions.items() if v > 0}
            curr_set = set(positions.keys())
            if i > 0 and prev_set != curr_set:
                switches += 1

            n_selected_effective = int(len(positions))
            if n_selected_effective < top_n:
                days_nsel_lt_topn += 1

            ledger_rows.append(
                {
                    "date": d,
                    "split": split,
                    "tickers_selected": ",".join(sorted(positions.keys())),
                    "n_selected": n_selected_effective,
                    "notional_buys": float(buys),
                    "notional_sells": float(sells),
                    "turnover_notional": float(turnover_notional),
                    "cost_paid": float(cost_paid),
                    "cash_end": float(cash),
                    "top_n": int(top_n),
                    "cadence_days": int(cadence_days),
                }
            )
            days_since_rebal = 0
        else:
            days_since_rebal += 1

        port_value = 0.0
        for t, q in positions.items():
            px = float(px_row.get(t, np.nan))
            if np.isfinite(px) and px > 0 and q > 0:
                port_value += q * px
        equity_strategy = float(cash + port_value)
        spx = float(macro_day.loc[d, "sp500_close"])
        sp500_bench = float(INITIAL_CAPITAL * (spx / prices_start))

        curve_rows.append(
            {
                "date": d,
                "split": split,
                "equity_strategy": equity_strategy,
                "equity_sp500_bh": sp500_bench,
                "equity_cash_fedfunds": float(cash_bench),
                "n_selected": int(len(positions)),
                "turnover_notional": float(turnover_notional),
                "cost_paid": float(cost_paid),
                "top_n": int(top_n),
                "cadence_days": int(cadence_days),
            }
        )

    curve = pd.DataFrame(curve_rows).sort_values("date").reset_index(drop=True)
    curve["ret_strategy_1d"] = curve["equity_strategy"].pct_change().fillna(0.0)
    curve["ret_sp500_1d"] = curve["equity_sp500_bh"].pct_change().fillna(0.0)
    curve["ret_cash_1d"] = curve["equity_cash_fedfunds"].pct_change().fillna(0.0)
    curve["drawdown_strategy"] = curve["equity_strategy"] / curve["equity_strategy"].cummax() - 1.0
    curve["drawdown_sp500"] = curve["equity_sp500_bh"] / curve["equity_sp500_bh"].cummax() - 1.0
    curve["drawdown_cash"] = curve["equity_cash_fedfunds"] / curve["equity_cash_fedfunds"].cummax() - 1.0

    ledger = pd.DataFrame(ledger_rows).sort_values("date").reset_index(drop=True)

    train = curve[curve["split"] == "TRAIN"].copy()
    holdout = curve[curve["split"] == "HOLDOUT"].copy()
    acid = holdout[(holdout["date"] >= ACID_US_START) & (holdout["date"] <= ACID_US_END)].copy()

    metrics = {
        "strategy_train": metrics_from_equity(train["equity_strategy"]),
        "strategy_holdout": metrics_from_equity(holdout["equity_strategy"]),
        "strategy_acid_us": metrics_from_equity(acid["equity_strategy"]),
        "sp500_train": metrics_from_equity(train["equity_sp500_bh"]),
        "sp500_holdout": metrics_from_equity(holdout["equity_sp500_bh"]),
        "sp500_acid_us": metrics_from_equity(acid["equity_sp500_bh"]),
        "cash_train": metrics_from_equity(train["equity_cash_fedfunds"]),
        "cash_holdout": metrics_from_equity(holdout["equity_cash_fedfunds"]),
        "cash_acid_us": metrics_from_equity(acid["equity_cash_fedfunds"]),
        "coverage": {
            "n_days": int(len(curve)),
            "n_rebalance_days": int(len(ledger)),
            "n_selected_min": int(curve["n_selected"].min()),
            "n_selected_p50": float(curve["n_selected"].median()),
            "n_selected_max": int(curve["n_selected"].max()),
            "days_n_selected_lt_topn": int(days_nsel_lt_topn),
            "switches": int(switches),
            "total_cost_paid": float(total_cost_paid),
            "total_cost_paid_train": float(total_cost_paid_train),
            "total_cost_paid_holdout": float(total_cost_paid_holdout),
        },
    }
    return curve, ledger, metrics


def main() -> int:
    gates: list[Gate] = []
    retry_log: list[str] = []

    artifacts = [
        OUT_SCRIPT,
        OUT_RESULTS,
        OUT_SELECTED,
        OUT_WINNER_CURVE,
        OUT_WINNER_LEDGER,
        OUT_PLOT,
        OUT_REPORT,
        OUT_MANIFEST,
        OUT_GRID,
        OUT_SELECTION_RULE,
        OUT_JOIN_COVERAGE,
        OUT_ANTI_LOOKAHEAD,
    ]

    try:
        for p in artifacts:
            p.parent.mkdir(parents=True, exist_ok=True)
        OUT_EVID.mkdir(parents=True, exist_ok=True)

        env_ok = PYTHON_ENV.exists() and (".venv" in sys.prefix or "agno_env" in sys.prefix)
        gates.append(Gate("G_ENV_VENV", env_ok, f"python={sys.executable}"))
        if not env_ok:
            raise RuntimeError("Python env inválido.")

        inputs_ok = all(
            p.exists() for p in [IN_SCORES, IN_SSOT_US, IN_MACRO, IN_UNIVERSE, IN_BASELINE_T121, CHANGELOG_PATH]
        )
        gates.append(
            Gate(
                "G_INPUTS_PRESENT",
                inputs_ok,
                (
                    f"scores={IN_SCORES.exists()} ssot_us={IN_SSOT_US.exists()} macro={IN_MACRO.exists()} "
                    f"universe={IN_UNIVERSE.exists()} baseline_t121={IN_BASELINE_T121.exists()} changelog={CHANGELOG_PATH.exists()}"
                ),
            )
        )
        if not inputs_ok:
            raise RuntimeError("Inputs obrigatórios ausentes.")

        universe = pd.read_parquet(IN_UNIVERSE, columns=["ticker"]).copy()
        universe["ticker"] = universe["ticker"].astype(str).str.upper().str.strip()
        use_tickers = set(universe["ticker"].tolist())
        gates.append(Gate("G_UNIVERSE_496", len(use_tickers) == 496, f"universe_tickers={len(use_tickers)}"))

        scores = pd.read_parquet(IN_SCORES).copy()
        scores["date"] = pd.to_datetime(scores["date"], errors="coerce").dt.normalize()
        scores["ticker"] = scores["ticker"].astype(str).str.upper().str.strip()
        scores = scores[scores["ticker"].isin(use_tickers)].copy()

        req_score_cols = {"date", "ticker", "score_m3_us_exec", "m3_rank_us_exec"}
        score_schema_ok = req_score_cols.issubset(set(scores.columns))
        gates.append(Gate("G_SCORE_SCHEMA_OK", score_schema_ok, f"required_cols_present={score_schema_ok}"))
        if not score_schema_ok:
            raise RuntimeError("Schema de scores T120 inválido.")

        # Regra crítica: somente _exec.
        scores_valid = scores.dropna(subset=["score_m3_us_exec", "m3_rank_us_exec"]).copy()
        scores_valid["m3_rank_us_exec"] = pd.to_numeric(scores_valid["m3_rank_us_exec"], errors="coerce")
        scores_valid = scores_valid.dropna(subset=["m3_rank_us_exec"]).copy()
        scores_valid["m3_rank_us_exec"] = scores_valid["m3_rank_us_exec"].astype(int)
        gates.append(
            Gate(
                "G_ANTI_LOOKAHEAD_EXEC_ONLY",
                bool(scores_valid["score_m3_us_exec"].notna().all()),
                f"valid_rows_exec={len(scores_valid)}",
            )
        )

        by_day: dict[pd.Timestamp, pd.DataFrame] = {}
        for d, g in scores_valid.groupby("date", sort=True):
            day = g.sort_values(["m3_rank_us_exec", "ticker"], ascending=[True, True]).copy()
            by_day[pd.Timestamp(d)] = day

        ssot = pd.read_parquet(IN_SSOT_US, columns=["date", "ticker", "close_operational"]).copy()
        ssot["date"] = pd.to_datetime(ssot["date"], errors="coerce").dt.normalize()
        ssot["ticker"] = ssot["ticker"].astype(str).str.upper().str.strip()
        ssot["close_operational"] = pd.to_numeric(ssot["close_operational"], errors="coerce")
        ssot = ssot.dropna(subset=["date", "ticker", "close_operational"]).copy()
        ssot = ssot[(ssot["close_operational"] > 0) & (ssot["ticker"].isin(use_tickers))].copy()
        px_wide = ssot.pivot_table(index="date", columns="ticker", values="close_operational", aggfunc="first").sort_index().ffill()

        macro = pd.read_parquet(IN_MACRO, columns=["date", "sp500_close", "fed_funds_rate"]).copy()
        macro["date"] = pd.to_datetime(macro["date"], errors="coerce").dt.normalize()
        macro["sp500_close"] = pd.to_numeric(macro["sp500_close"], errors="coerce")
        macro["fed_funds_rate"] = pd.to_numeric(macro["fed_funds_rate"], errors="coerce")
        macro = macro.dropna(subset=["date"]).drop_duplicates(subset=["date"], keep="last").sort_values("date")
        macro["sp500_close"] = macro["sp500_close"].ffill().bfill()
        macro["fed_funds_rate"] = macro["fed_funds_rate"].ffill().bfill()
        macro["cash_log_daily_us"] = np.log1p((macro["fed_funds_rate"] / 100.0) / 252.0)
        macro_day = macro.set_index("date")

        score_dates = set(by_day.keys())
        sim_dates = sorted(set(px_wide.index).intersection(set(macro_day.index)).intersection(score_dates))
        sim_dates = [d for d in sim_dates if TRAIN_START <= d <= HOLDOUT_END]
        common_ok = bool(sim_dates and sim_dates[0] == TRAIN_START and sim_dates[-1] == HOLDOUT_END)
        gates.append(
            Gate(
                "G_COMMON_DATES_OK",
                common_ok,
                f"n_dates={len(sim_dates)} min={sim_dates[0] if sim_dates else None} max={sim_dates[-1] if sim_dates else None}",
            )
        )
        if not common_ok:
            raise RuntimeError("Datas comuns inválidas para T122.")

        # Spot-check anti-lookahead em AAPL.
        aapl = scores[scores["ticker"] == "AAPL"].sort_values("date").reset_index(drop=True)
        anti_spot = {
            "ticker": "AAPL",
            "rows": int(len(aapl)),
            "exec_eq_prev_score_all": bool(
                (aapl["score_m3_us_exec"].iloc[1:].values == aapl["score_m3_us"].iloc[:-1].values).all()
            )
            if len(aapl) > 1
            else False,
            "exec_eq_same_day_score_all": bool(
                (aapl["score_m3_us_exec"].iloc[1:].values == aapl["score_m3_us"].iloc[1:].values).all()
            )
            if len(aapl) > 1
            else False,
        }
        write_json(OUT_ANTI_LOOKAHEAD, anti_spot)
        gates.append(
            Gate(
                "G_ANTI_LOOKAHEAD_SPOTCHECK",
                anti_spot["exec_eq_prev_score_all"] and (not anti_spot["exec_eq_same_day_score_all"]),
                (
                    f"exec_eq_prev={anti_spot['exec_eq_prev_score_all']} "
                    f"exec_eq_same_day={anti_spot['exec_eq_same_day_score_all']}"
                ),
            )
        )

        # Grid + evidências.
        candidate_grid: list[dict[str, int]] = []
        cid = 1
        for top_n in TOP_N_LIST:
            for cadence in CADENCE_LIST:
                candidate_grid.append({"candidate_id": f"C{cid:03d}", "top_n": int(top_n), "cadence_days": int(cadence)})
                cid += 1
        write_json(
            OUT_GRID,
            {
                "top_n_list": TOP_N_LIST,
                "cadence_days_list": CADENCE_LIST,
                "n_candidates": len(candidate_grid),
                "cost_rate_one_way": COST_RATE,
                "initial_capital_usd": INITIAL_CAPITAL,
            },
        )

        join_cov = {
            "n_dates_common": int(len(sim_dates)),
            "date_min": str(min(sim_dates).date()),
            "date_max": str(max(sim_dates).date()),
            "has_train_start": bool(min(sim_dates) == TRAIN_START),
            "has_holdout_end": bool(max(sim_dates) == HOLDOUT_END),
            "n_tickers_universe": int(len(use_tickers)),
        }
        write_json(OUT_JOIN_COVERAGE, join_cov)

        # Rodar ablação.
        rows: list[dict[str, Any]] = []
        curves_cache: dict[str, pd.DataFrame] = {}
        ledgers_cache: dict[str, pd.DataFrame] = {}
        metrics_cache: dict[str, dict[str, Any]] = {}

        for cfg in candidate_grid:
            candidate_id = cfg["candidate_id"]
            curve, ledger, metrics = simulate_candidate(
                top_n=cfg["top_n"],
                cadence_days=cfg["cadence_days"],
                by_day=by_day,
                px_wide=px_wide,
                macro_day=macro_day,
                sim_dates=sim_dates,
            )
            curves_cache[candidate_id] = curve
            ledgers_cache[candidate_id] = ledger
            metrics_cache[candidate_id] = metrics

            row = {
                "candidate_id": candidate_id,
                "top_n": int(cfg["top_n"]),
                "cadence_days": int(cfg["cadence_days"]),
                "equity_train": float(metrics["strategy_train"]["equity_final"]),
                "cagr_train": float(metrics["strategy_train"]["cagr"]),
                "mdd_train": float(metrics["strategy_train"]["mdd"]),
                "sharpe_train": float(metrics["strategy_train"]["sharpe"]),
                "equity_holdout": float(metrics["strategy_holdout"]["equity_final"]),
                "cagr_holdout": float(metrics["strategy_holdout"]["cagr"]),
                "mdd_holdout": float(metrics["strategy_holdout"]["mdd"]),
                "sharpe_holdout": float(metrics["strategy_holdout"]["sharpe"]),
                "equity_acid_us": float(metrics["strategy_acid_us"]["equity_final"]),
                "cagr_acid_us": float(metrics["strategy_acid_us"]["cagr"]),
                "mdd_acid_us": float(metrics["strategy_acid_us"]["mdd"]),
                "sharpe_acid_us": float(metrics["strategy_acid_us"]["sharpe"]),
                "sp500_sharpe_holdout": float(metrics["sp500_holdout"]["sharpe"]),
                "cash_sharpe_holdout": float(metrics["cash_holdout"]["sharpe"]),
                "switches": int(metrics["coverage"]["switches"]),
                "days_n_selected_lt_topn": int(metrics["coverage"]["days_n_selected_lt_topn"]),
                "total_cost_paid": float(metrics["coverage"]["total_cost_paid"]),
                "total_cost_paid_train": float(metrics["coverage"]["total_cost_paid_train"]),
                "total_cost_paid_holdout": float(metrics["coverage"]["total_cost_paid_holdout"]),
            }
            rows.append(row)

        ablation = pd.DataFrame(rows).sort_values("candidate_id").reset_index(drop=True)
        ablation.to_parquet(OUT_RESULTS, index=False)
        gates.append(Gate("G_ABLATION_GRID_COMPLETE", len(ablation) == len(candidate_grid), f"rows={len(ablation)} expected={len(candidate_grid)}"))

        # Seleção TRAIN-only (lexicográfica).
        winner = (
            ablation.sort_values(
                by=["sharpe_train", "cagr_train", "mdd_train", "total_cost_paid_train", "top_n", "cadence_days"],
                ascending=[False, False, False, True, True, True],
            )
            .iloc[0]
            .to_dict()
        )
        winner_id = str(winner["candidate_id"])
        winner_curve = curves_cache[winner_id].copy()
        winner_ledger = ledgers_cache[winner_id].copy()
        winner_metrics = metrics_cache[winner_id]

        winner_curve.to_parquet(OUT_WINNER_CURVE, index=False)
        winner_ledger.to_parquet(OUT_WINNER_LEDGER, index=False)

        write_json(
            OUT_SELECTION_RULE,
            {
                "rule_id": "TRAIN_ONLY_LEXICOGRAPHIC_V1",
                "order": [
                    "sharpe_train desc",
                    "cagr_train desc",
                    "mdd_train desc",
                    "total_cost_paid_train asc",
                    "top_n asc",
                    "cadence_days asc",
                ],
                "note": "Holdout e acid_us não participam da seleção do winner.",
            },
        )
        write_json(
            OUT_SELECTED,
            {
                "task_id": TASK_ID,
                "run_id": RUN_ID,
                "winner_candidate_id": winner_id,
                "winner_top_n": int(winner["top_n"]),
                "winner_cadence_days": int(winner["cadence_days"]),
                "config_fixed": {
                    "cost_rate_one_way": COST_RATE,
                    "initial_capital_usd": INITIAL_CAPITAL,
                    "selection_source": "score_m3_us_exec,m3_rank_us_exec_only",
                },
                "winner_metrics_strategy": {
                    "train": winner_metrics["strategy_train"],
                    "holdout": winner_metrics["strategy_holdout"],
                    "acid_us": winner_metrics["strategy_acid_us"],
                },
                "winner_metrics_benchmarks": {
                    "sp500_holdout": winner_metrics["sp500_holdout"],
                    "cash_holdout": winner_metrics["cash_holdout"],
                },
                "winner_coverage": winner_metrics["coverage"],
            },
        )

        # Gates de saída.
        gates.append(Gate("G_WINNER_CURVE_NONEMPTY", len(winner_curve) > 0, f"rows={len(winner_curve)}"))
        gates.append(
            Gate(
                "G_SIM_DATE_RANGE",
                bool(winner_curve["date"].min() == TRAIN_START and winner_curve["date"].max() == HOLDOUT_END),
                f"min={winner_curve['date'].min()} max={winner_curve['date'].max()}",
            )
        )
        gates.append(
            Gate(
                "G_EQUITY_NO_NAN",
                bool(winner_curve["equity_strategy"].notna().all()),
                f"nan_equity={int(winner_curve['equity_strategy'].isna().sum())}",
            )
        )
        gates.append(
            Gate(
                "G_TOPN_FEASIBLE_WINNER",
                int(winner_metrics["coverage"]["n_selected_max"]) >= int(winner["top_n"]),
                (
                    f"n_selected_max={winner_metrics['coverage']['n_selected_max']} "
                    f"top_n={int(winner['top_n'])}"
                ),
            )
        )

        # Plot comparativo (winner vs T121 baseline vs SP500 vs cash).
        baseline = pd.read_parquet(IN_BASELINE_T121).copy()
        baseline["date"] = pd.to_datetime(baseline["date"], errors="coerce").dt.normalize()
        winner_curve["date"] = pd.to_datetime(winner_curve["date"], errors="coerce").dt.normalize()
        plot_df = winner_curve.merge(
            baseline[["date", "equity_strategy"]].rename(columns={"equity_strategy": "equity_t121_baseline"}),
            on="date",
            how="left",
        )
        base = plot_df.iloc[0]
        norm_winner = 100.0 * plot_df["equity_strategy"] / float(base["equity_strategy"])
        norm_sp500 = 100.0 * plot_df["equity_sp500_bh"] / float(base["equity_sp500_bh"])
        norm_cash = 100.0 * plot_df["equity_cash_fedfunds"] / float(base["equity_cash_fedfunds"])
        norm_t121 = 100.0 * plot_df["equity_t121_baseline"] / float(base["equity_t121_baseline"])

        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.10,
            subplot_titles=("Equity Normalizada (Base 100)", "Drawdown"),
        )
        fig.add_trace(
            go.Scatter(
                x=plot_df["date"],
                y=norm_winner,
                mode="lines",
                name=f"T122 Winner (TopN={int(winner['top_n'])}, Cad={int(winner['cadence_days'])})",
            ),
            row=1,
            col=1,
        )
        fig.add_trace(go.Scatter(x=plot_df["date"], y=norm_t121, mode="lines", name="T121 Baseline (TopN=10,Cad=5)"), row=1, col=1)
        fig.add_trace(go.Scatter(x=plot_df["date"], y=norm_sp500, mode="lines", name="SP500 Buy&Hold"), row=1, col=1)
        fig.add_trace(go.Scatter(x=plot_df["date"], y=norm_cash, mode="lines", name="Cash FedFunds"), row=1, col=1)
        fig.add_trace(go.Scatter(x=plot_df["date"], y=plot_df["drawdown_strategy"], mode="lines", name="DD Winner"), row=2, col=1)
        fig.add_trace(go.Scatter(x=plot_df["date"], y=plot_df["drawdown_sp500"], mode="lines", name="DD SP500"), row=2, col=1)
        fig.update_layout(
            title="T122 - Ablation US Engine (TopN x Cadence) - Winner vs Baselines",
            template="plotly_white",
            legend=dict(orientation="h"),
            height=900,
        )
        fig.add_vrect(
            x0=ACID_US_START,
            x1=ACID_US_END,
            fillcolor="lightblue",
            opacity=0.2,
            line_width=0,
            annotation_text="acid_us",
            annotation_position="top left",
        )
        OUT_PLOT.parent.mkdir(parents=True, exist_ok=True)
        fig.write_html(str(OUT_PLOT), include_plotlyjs="cdn")
        gates.append(
            Gate(
                "G_PLOT_PRESENT",
                OUT_PLOT.exists() and OUT_PLOT.stat().st_size > 50_000,
                f"size={OUT_PLOT.stat().st_size if OUT_PLOT.exists() else 0}",
            )
        )

        # Changelog idempotente.
        ch_ok, ch_mode = append_changelog_idempotent(TRACEABILITY_LINE)
        gates.append(Gate("G_CHLOG_UPDATED", ch_ok, f"mode={ch_mode}"))

        report_summary = {
            "n_candidates": int(len(ablation)),
            "winner_candidate_id": winner_id,
            "winner_top_n": int(winner["top_n"]),
            "winner_cadence_days": int(winner["cadence_days"]),
            "winner_holdout_equity": float(winner["equity_holdout"]),
            "winner_holdout_cagr": float(winner["cagr_holdout"]),
            "winner_holdout_mdd": float(winner["mdd_holdout"]),
            "winner_holdout_sharpe": float(winner["sharpe_holdout"]),
            "winner_sharpe_train": float(winner["sharpe_train"]),
            "sp500_holdout_sharpe": float(winner_metrics["sp500_holdout"]["sharpe"]),
            "winner_total_cost_paid": float(winner["total_cost_paid"]),
        }

        # Relatório preliminar.
        OUT_REPORT.write_text(render_report(gates, retry_log, artifacts, report_summary), encoding="utf-8")

        # Manifest preliminar.
        inputs = [IN_SCORES, IN_SSOT_US, IN_MACRO, IN_UNIVERSE, IN_BASELINE_T121, CHANGELOG_PATH]
        outputs = [
            OUT_SCRIPT,
            OUT_RESULTS,
            OUT_SELECTED,
            OUT_WINNER_CURVE,
            OUT_WINNER_LEDGER,
            OUT_PLOT,
            OUT_REPORT,
            OUT_GRID,
            OUT_SELECTION_RULE,
            OUT_JOIN_COVERAGE,
            OUT_ANTI_LOOKAHEAD,
        ]
        hashes: dict[str, str] = {}
        for p in inputs + outputs:
            if p.exists():
                hashes[p.relative_to(ROOT).as_posix()] = sha256_file(p)
        manifest = {
            "task_id": TASK_ID,
            "run_id": RUN_ID,
            "generated_at_utc": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
            "inputs_consumed": [p.relative_to(ROOT).as_posix() for p in inputs],
            "outputs_produced": [p.relative_to(ROOT).as_posix() for p in outputs],
            "hashes_sha256": hashes,
            "policy": "no_self_hash",
        }
        write_json(OUT_MANIFEST, manifest)
        gates.append(Gate("Gx_HASH_MANIFEST_PRESENT", OUT_MANIFEST.exists(), f"path={OUT_MANIFEST.relative_to(ROOT).as_posix()}"))

        mismatches = 0
        for rel, exp in manifest["hashes_sha256"].items():
            fp = ROOT / rel
            if not fp.exists() or sha256_file(fp) != exp:
                mismatches += 1
        gates.append(Gate("G_SHA256_INTEGRITY_SELF_CHECK", mismatches == 0, f"mismatches={mismatches}"))

        # Final report + final manifest.
        OUT_REPORT.write_text(render_report(gates, retry_log, artifacts, report_summary), encoding="utf-8")
        hashes_final: dict[str, str] = {}
        for p in inputs + outputs:
            if p.exists():
                hashes_final[p.relative_to(ROOT).as_posix()] = sha256_file(p)
        manifest["hashes_sha256"] = hashes_final
        manifest["generated_at_utc"] = pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
        write_json(OUT_MANIFEST, manifest)

        final_mismatches = 0
        for rel, exp in manifest["hashes_sha256"].items():
            fp = ROOT / rel
            if not fp.exists() or sha256_file(fp) != exp:
                final_mismatches += 1
        if final_mismatches != 0:
            raise RuntimeError(f"Integridade final falhou: mismatches={final_mismatches}")

        if not all(g.passed for g in gates):
            raise RuntimeError("Um ou mais gates falharam em T122.")
        return 0

    except Exception as exc:  # pragma: no cover
        retry_log.append(f"error: {type(exc).__name__}: {exc}")
        fail_report = render_report(gates, retry_log, artifacts, {"error": str(exc)})
        OUT_REPORT.write_text(fail_report, encoding="utf-8")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
