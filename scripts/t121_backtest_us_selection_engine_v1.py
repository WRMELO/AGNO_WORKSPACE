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

TASK_ID = "T121"
RUN_ID = "T121-US-ENGINE-BACKTEST-V1"
PYTHON_ENV = ROOT / ".venv/bin/python"
CHANGELOG_PATH = ROOT / "00_Strategy/changelog.md"

IN_SCORES = ROOT / "src/data_engine/features/T120_M3_US_SCORES_DAILY.parquet"
IN_SSOT_US = ROOT / "src/data_engine/ssot/SSOT_CANONICAL_BASE_US.parquet"
IN_MACRO = ROOT / "src/data_engine/ssot/SSOT_MACRO_EXPANDED.parquet"
IN_UNIVERSE = ROOT / "src/data_engine/ssot/SSOT_US_UNIVERSE_OPERATIONAL_PHASE10.parquet"

OUT_SCRIPT = ROOT / "scripts/t121_backtest_us_selection_engine_v1.py"
OUT_CURVE = ROOT / "src/data_engine/portfolio/T121_US_ENGINE_CURVE_DAILY.parquet"
OUT_LEDGER = ROOT / "src/data_engine/portfolio/T121_US_ENGINE_LEDGER.parquet"
OUT_SUMMARY = ROOT / "src/data_engine/portfolio/T121_US_ENGINE_SUMMARY.json"
OUT_PLOT = ROOT / "outputs/plots/T121_STATE3_PHASE10B_US_ENGINE_BACKTEST.html"
OUT_REPORT = ROOT / "outputs/governanca/T121-US-ENGINE-BACKTEST-V1_report.md"
OUT_MANIFEST = ROOT / "outputs/governanca/T121-US-ENGINE-BACKTEST-V1_manifest.json"
OUT_EVID = ROOT / "outputs/governanca/T121-US-ENGINE-BACKTEST-V1_evidence"
OUT_METRICS = OUT_EVID / "metrics_snapshot.json"
OUT_SELECTION = OUT_EVID / "selection_coverage.json"
OUT_BENCH = OUT_EVID / "benchmarks_snapshot.json"

INITIAL_CAPITAL = 100_000.0
TOP_N = 10
CADENCE_DAYS = 5
COST_RATE = 0.0001  # 1bp

TRAIN_START = pd.Timestamp("2018-07-02")
TRAIN_END = pd.Timestamp("2022-12-30")
HOLDOUT_START = pd.Timestamp("2023-01-02")
HOLDOUT_END = pd.Timestamp("2026-02-26")
ACID_US_START = pd.Timestamp("2025-03-06")
ACID_US_END = pd.Timestamp("2025-05-09")

TRACEABILITY_LINE = (
    "- 2026-03-04T16:10:00Z | EXEC: T121 PASS/FAIL. Artefatos: "
    "scripts/t121_backtest_us_selection_engine_v1.py; "
    "src/data_engine/portfolio/T121_US_ENGINE_CURVE_DAILY.parquet; "
    "src/data_engine/portfolio/T121_US_ENGINE_LEDGER.parquet; "
    "src/data_engine/portfolio/T121_US_ENGINE_SUMMARY.json; "
    "outputs/plots/T121_STATE3_PHASE10B_US_ENGINE_BACKTEST.html"
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


def main() -> int:
    gates: list[Gate] = []
    retry_log: list[str] = []

    artifacts = [
        OUT_SCRIPT,
        OUT_CURVE,
        OUT_LEDGER,
        OUT_SUMMARY,
        OUT_PLOT,
        OUT_REPORT,
        OUT_MANIFEST,
        OUT_METRICS,
        OUT_SELECTION,
        OUT_BENCH,
    ]

    try:
        for p in artifacts:
            p.parent.mkdir(parents=True, exist_ok=True)
        OUT_EVID.mkdir(parents=True, exist_ok=True)

        env_ok = PYTHON_ENV.exists() and (".venv" in sys.prefix or "agno_env" in sys.prefix)
        gates.append(Gate("G_ENV_VENV", env_ok, f"python={sys.executable}"))
        if not env_ok:
            raise RuntimeError("Python env inválido.")

        inputs_ok = IN_SCORES.exists() and IN_SSOT_US.exists() and IN_MACRO.exists() and IN_UNIVERSE.exists() and CHANGELOG_PATH.exists()
        gates.append(
            Gate(
                "G_INPUTS_PRESENT",
                inputs_ok,
                (
                    f"scores={IN_SCORES.exists()} ssot_us={IN_SSOT_US.exists()} "
                    f"macro={IN_MACRO.exists()} universe={IN_UNIVERSE.exists()} changelog={CHANGELOG_PATH.exists()}"
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

        # Regra crítica pós-auditoria T120: usar APENAS campos *_exec.
        scores_valid = scores.dropna(subset=["score_m3_us_exec", "m3_rank_us_exec"]).copy()
        scores_valid["m3_rank_us_exec"] = pd.to_numeric(scores_valid["m3_rank_us_exec"], errors="coerce")
        scores_valid = scores_valid.dropna(subset=["m3_rank_us_exec"]).copy()
        scores_valid["m3_rank_us_exec"] = scores_valid["m3_rank_us_exec"].astype(int)

        by_day: dict[pd.Timestamp, pd.DataFrame] = {}
        for d, g in scores_valid.groupby("date", sort=True):
            day = g.sort_values(["m3_rank_us_exec", "ticker"], ascending=[True, True]).copy()
            by_day[pd.Timestamp(d)] = day

        # Garantia de cobertura mínima no início de simulação.
        train_start_day = by_day.get(TRAIN_START, pd.DataFrame())
        gates.append(
            Gate(
                "G_EXEC_COVERAGE_TRAIN_START",
                len(train_start_day) >= TOP_N,
                f"available_exec_on_train_start={len(train_start_day)} top_n={TOP_N}",
            )
        )

        ssot = pd.read_parquet(IN_SSOT_US, columns=["date", "ticker", "close_operational"]).copy()
        ssot["date"] = pd.to_datetime(ssot["date"], errors="coerce").dt.normalize()
        ssot["ticker"] = ssot["ticker"].astype(str).str.upper().str.strip()
        ssot["close_operational"] = pd.to_numeric(ssot["close_operational"], errors="coerce")
        ssot = ssot.dropna(subset=["date", "ticker", "close_operational"]).copy()
        ssot = ssot[(ssot["close_operational"] > 0) & (ssot["ticker"].isin(use_tickers))].copy()

        px_wide = (
            ssot.pivot_table(index="date", columns="ticker", values="close_operational", aggfunc="first")
            .sort_index()
            .ffill()
        )

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
        if not sim_dates:
            raise RuntimeError("Sem datas comuns para simulação T121.")

        prices_start = float(macro_day.loc[TRAIN_START, "sp500_close"])
        cash_bench = INITIAL_CAPITAL
        sp500_bench = INITIAL_CAPITAL

        cash = INITIAL_CAPITAL
        positions: dict[str, float] = {}
        days_since_rebal = 10**9
        switches = 0
        total_cost_paid = 0.0

        curve_rows: list[dict[str, Any]] = []
        ledger_rows: list[dict[str, Any]] = []
        days_nsel_lt_topn = 0

        for i, d in enumerate(sim_dates):
            # Remuneração diária do caixa antes de rebalance.
            cash_log = float(macro_day.loc[d, "cash_log_daily_us"])
            cash *= float(np.exp(cash_log))
            cash_bench *= float(np.exp(cash_log))

            px_row = px_wide.loc[d]

            # Valor corrente de posições antes de rebalance.
            current_values: dict[str, float] = {}
            for t, q in positions.items():
                px = float(px_row.get(t, np.nan))
                if np.isfinite(px) and px > 0 and q > 0:
                    current_values[t] = q * px
            port_before = float(sum(current_values.values()))
            equity_before = cash + port_before

            do_rebal = (i == 0) or (days_since_rebal >= CADENCE_DAYS)
            turnover_notional = 0.0
            cost_paid = 0.0
            selected: list[str] = []

            if do_rebal:
                day_scores = by_day.get(d, pd.DataFrame()).copy()
                if len(day_scores) > 0:
                    selected = day_scores.sort_values(["m3_rank_us_exec", "ticker"], ascending=[True, True]).head(TOP_N)["ticker"].tolist()

                n_selected = len(selected)
                if n_selected < TOP_N:
                    days_nsel_lt_topn += 1

                target_values: dict[str, float] = {}
                if n_selected > 0:
                    target_w = 1.0 / n_selected
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
                cash = cash + sells - buys - cost_paid
                if cash < 0:
                    # proteção numérica para arredondamentos.
                    cash = max(cash, -1e-6)
                positions = {k: v for k, v in new_positions.items() if v > 0}

                if i > 0:
                    prev_set = set(curve_rows[-1].get("holdings", []))
                    curr_set = set(positions.keys())
                    if prev_set != curr_set:
                        switches += 1

                ledger_rows.append(
                    {
                        "date": d,
                        "tickers_selected": ",".join(sorted(positions.keys())),
                        "n_selected": int(len(positions)),
                        "notional_buys": float(buys),
                        "notional_sells": float(sells),
                        "turnover_notional": float(turnover_notional),
                        "cost_paid": float(cost_paid),
                        "cash_end": float(cash),
                    }
                )
                days_since_rebal = 0
            else:
                days_since_rebal += 1

            # Mark-to-market no fechamento do dia.
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
                    "split": split_label(d),
                    "equity_strategy": equity_strategy,
                    "equity_sp500_bh": sp500_bench,
                    "equity_cash_fedfunds": float(cash_bench),
                    "n_selected": int(len(positions)),
                    "turnover_notional": float(turnover_notional),
                    "cost_paid": float(cost_paid),
                    "holdings": sorted(positions.keys()),
                }
            )

        curve = pd.DataFrame(curve_rows).sort_values("date").reset_index(drop=True)
        curve["ret_strategy_1d"] = curve["equity_strategy"].pct_change().fillna(0.0)
        curve["ret_sp500_1d"] = curve["equity_sp500_bh"].pct_change().fillna(0.0)
        curve["ret_cash_1d"] = curve["equity_cash_fedfunds"].pct_change().fillna(0.0)
        curve["drawdown_strategy"] = curve["equity_strategy"] / curve["equity_strategy"].cummax() - 1.0
        curve["drawdown_sp500"] = curve["equity_sp500_bh"] / curve["equity_sp500_bh"].cummax() - 1.0
        curve["drawdown_cash"] = curve["equity_cash_fedfunds"] / curve["equity_cash_fedfunds"].cummax() - 1.0
        curve = curve.drop(columns=["holdings"])

        curve.to_parquet(OUT_CURVE, index=False)
        ledger = pd.DataFrame(ledger_rows).sort_values("date").reset_index(drop=True)
        ledger.to_parquet(OUT_LEDGER, index=False)

        def sub(df: pd.DataFrame, col: str) -> dict[str, float]:
            return metrics_from_equity(df[col]) if len(df) else metrics_from_equity(pd.Series([INITIAL_CAPITAL]))

        train = curve[curve["split"] == "TRAIN"].copy()
        holdout = curve[curve["split"] == "HOLDOUT"].copy()
        acid = holdout[(holdout["date"] >= ACID_US_START) & (holdout["date"] <= ACID_US_END)].copy()

        summary = {
            "task_id": TASK_ID,
            "run_id": RUN_ID,
            "config": {
                "initial_capital_usd": INITIAL_CAPITAL,
                "top_n": TOP_N,
                "cadence_days": CADENCE_DAYS,
                "cost_rate_one_way": COST_RATE,
            },
            "coverage": {
                "n_dates": int(len(curve)),
                "date_min": str(pd.to_datetime(curve["date"]).min().date()),
                "date_max": str(pd.to_datetime(curve["date"]).max().date()),
                "switches": int(switches),
                "total_cost_paid": float(total_cost_paid),
                "days_n_selected_lt_topn": int(days_nsel_lt_topn),
            },
            "metrics_strategy": {
                "train": sub(train, "equity_strategy"),
                "holdout": sub(holdout, "equity_strategy"),
                "acid_us": sub(acid, "equity_strategy"),
            },
            "metrics_sp500_bh": {
                "train": sub(train, "equity_sp500_bh"),
                "holdout": sub(holdout, "equity_sp500_bh"),
                "acid_us": sub(acid, "equity_sp500_bh"),
            },
            "metrics_cash_fedfunds": {
                "train": sub(train, "equity_cash_fedfunds"),
                "holdout": sub(holdout, "equity_cash_fedfunds"),
                "acid_us": sub(acid, "equity_cash_fedfunds"),
            },
        }
        write_json(OUT_SUMMARY, summary)
        write_json(OUT_METRICS, summary)

        selection_coverage = {
            "n_days": int(len(curve)),
            "n_rebalance_days": int(len(ledger)),
            "n_selected_min": int(curve["n_selected"].min()),
            "n_selected_p50": float(curve["n_selected"].median()),
            "n_selected_max": int(curve["n_selected"].max()),
            "days_n_selected_lt_topn": int(days_nsel_lt_topn),
            "top_n_config": TOP_N,
        }
        write_json(OUT_SELECTION, selection_coverage)

        bench_snapshot = {
            "sp500_holdout": summary["metrics_sp500_bh"]["holdout"],
            "cash_holdout": summary["metrics_cash_fedfunds"]["holdout"],
        }
        write_json(OUT_BENCH, bench_snapshot)

        # Gates de aceitação.
        gates.append(Gate("G_CURVE_NONEMPTY", len(curve) > 0, f"rows={len(curve)}"))
        gates.append(
            Gate(
                "G_SIM_DATE_RANGE",
                bool(curve["date"].min() == TRAIN_START and curve["date"].max() == HOLDOUT_END),
                f"min={curve['date'].min()} max={curve['date'].max()}",
            )
        )
        gates.append(
            Gate(
                "G_EQUITY_NO_NAN",
                bool(curve["equity_strategy"].notna().all()),
                f"nan_equity={int(curve['equity_strategy'].isna().sum())}",
            )
        )
        gates.append(
            Gate(
                "G_ANTI_LOOKAHEAD_EXEC_ONLY",
                bool(scores_valid["score_m3_us_exec"].notna().all()),
                f"valid_rows_exec={len(scores_valid)}",
            )
        )
        gates.append(
            Gate(
                "G_TOPN_FEASIBLE",
                selection_coverage["n_selected_max"] >= TOP_N,
                f"n_selected_max={selection_coverage['n_selected_max']} top_n={TOP_N}",
            )
        )

        # Plotly comparativo.
        base = curve.iloc[0]
        norm_strategy = 100.0 * curve["equity_strategy"] / float(base["equity_strategy"])
        norm_sp500 = 100.0 * curve["equity_sp500_bh"] / float(base["equity_sp500_bh"])
        norm_cash = 100.0 * curve["equity_cash_fedfunds"] / float(base["equity_cash_fedfunds"])

        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.10,
            subplot_titles=("Equity Normalizada (Base 100)", "Drawdown"),
        )
        fig.add_trace(go.Scatter(x=curve["date"], y=norm_strategy, mode="lines", name="US Engine M3 Top10"), row=1, col=1)
        fig.add_trace(go.Scatter(x=curve["date"], y=norm_sp500, mode="lines", name="SP500 Buy&Hold"), row=1, col=1)
        fig.add_trace(go.Scatter(x=curve["date"], y=norm_cash, mode="lines", name="Cash FedFunds"), row=1, col=1)
        fig.add_trace(go.Scatter(x=curve["date"], y=curve["drawdown_strategy"], mode="lines", name="DD Strategy"), row=2, col=1)
        fig.add_trace(go.Scatter(x=curve["date"], y=curve["drawdown_sp500"], mode="lines", name="DD SP500"), row=2, col=1)
        fig.update_layout(
            title="T121 - US Selection Engine Backtest (TopN M3-US, sem ML)",
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
        gates.append(Gate("G_PLOT_PRESENT", OUT_PLOT.exists() and OUT_PLOT.stat().st_size > 50_000, f"size={OUT_PLOT.stat().st_size if OUT_PLOT.exists() else 0}"))

        # Changelog idempotente.
        ch_ok, ch_mode = append_changelog_idempotent(TRACEABILITY_LINE)
        gates.append(Gate("G_CHLOG_UPDATED", ch_ok, f"mode={ch_mode}"))

        report_summary = {
            "rows_curve": int(len(curve)),
            "rows_ledger": int(len(ledger)),
            "date_min": str(curve["date"].min().date()),
            "date_max": str(curve["date"].max().date()),
            "strategy_holdout_equity": float(summary["metrics_strategy"]["holdout"]["equity_final"]),
            "sp500_holdout_equity": float(summary["metrics_sp500_bh"]["holdout"]["equity_final"]),
            "switches": int(switches),
            "total_cost_paid": float(total_cost_paid),
        }

        # Passo 1: relatório preliminar.
        OUT_REPORT.write_text(render_report(gates, retry_log, artifacts, report_summary), encoding="utf-8")

        # Passo 2: manifest preliminar.
        inputs = [IN_SCORES, IN_SSOT_US, IN_MACRO, IN_UNIVERSE, CHANGELOG_PATH]
        outputs = [OUT_SCRIPT, OUT_CURVE, OUT_LEDGER, OUT_SUMMARY, OUT_PLOT, OUT_REPORT, OUT_METRICS, OUT_SELECTION, OUT_BENCH]
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

        # Passo 3: self-check e pass final.
        mismatches = 0
        for rel, exp in manifest["hashes_sha256"].items():
            fp = ROOT / rel
            if not fp.exists() or sha256_file(fp) != exp:
                mismatches += 1
        gates.append(Gate("G_SHA256_INTEGRITY_SELF_CHECK", mismatches == 0, f"mismatches={mismatches}"))

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
            raise RuntimeError("Um ou mais gates falharam em T121.")
        return 0

    except Exception as exc:  # pragma: no cover
        retry_log.append(f"error: {type(exc).__name__}: {exc}")
        fail_report = render_report(gates, retry_log, artifacts, {"error": str(exc)})
        OUT_REPORT.write_text(fail_report, encoding="utf-8")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
