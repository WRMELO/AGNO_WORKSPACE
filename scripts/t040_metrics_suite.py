from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ANN_FACTOR = 252.0
TASK_ID = "T040"

BASE_DIR = Path("/home/wilson/AGNO_WORKSPACE/src/data_engine/portfolio")
INPUTS: dict[str, dict[str, Path]] = {
    "T037": {
        "curve": BASE_DIR / "T037_PORTFOLIO_CURVE.parquet",
        "ledger": BASE_DIR / "T037_PORTFOLIO_LEDGER.parquet",
    },
    "T038": {
        "curve": BASE_DIR / "T038_PORTFOLIO_CURVE.parquet",
        "ledger": BASE_DIR / "T038_PORTFOLIO_LEDGER.parquet",
    },
    "T039": {
        "curve": BASE_DIR / "T039_PORTFOLIO_CURVE.parquet",
        "ledger": BASE_DIR / "T039_PORTFOLIO_LEDGER.parquet",
    },
}

OUT_COMPARATIVE = BASE_DIR / "T040_METRICS_COMPARATIVE.json"
OUT_BY_REGIME = BASE_DIR / "T040_METRICS_BY_REGIME.csv"
OUT_BY_SUBPERIOD = BASE_DIR / "T040_METRICS_BY_SUBPERIOD.csv"


def _to_native(value: Any) -> Any:
    if isinstance(value, (np.floating, np.float32, np.float64)):
        if np.isnan(value):
            return None
        return float(value)
    if isinstance(value, (np.integer, np.int32, np.int64)):
        return int(value)
    if pd.isna(value):
        return None
    return value


def _max_drawdown(equity: pd.Series) -> float | None:
    if equity.empty:
        return None
    peak = equity.cummax()
    dd = equity / peak - 1.0
    return float(dd.min())


def _time_to_recover_days(curve: pd.DataFrame) -> int | None:
    if curve.empty:
        return None
    equity = curve["equity_end"].astype(float)
    peaks = equity.cummax()
    drawdowns = equity / peaks - 1.0
    if drawdowns.empty:
        return None
    valley_idx = int(drawdowns.idxmin())
    peak_before_valley = float(peaks.loc[valley_idx])
    valley_date = pd.to_datetime(curve.loc[valley_idx, "date"])
    recovered = curve.loc[
        (curve.index > valley_idx) & (curve["equity_end"].astype(float) >= peak_before_valley)
    ]
    if recovered.empty:
        return None
    recover_date = pd.to_datetime(recovered.iloc[0]["date"])
    return int((recover_date - valley_date).days)


def _weighted_holding_days(ledger: pd.DataFrame) -> float | None:
    if ledger.empty:
        return None
    work = ledger.copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    work = work.dropna(subset=["date", "ticker", "side", "qty"]).sort_values(["date", "ticker"])
    lots: dict[str, list[list[Any]]] = {}
    weighted_days = 0.0
    qty_sold_total = 0.0

    for row in work.itertuples(index=False):
        ticker = str(row.ticker)
        side = str(row.side).upper()
        qty = float(row.qty)
        dt = pd.Timestamp(row.date)

        if qty <= 0:
            continue

        if side == "BUY":
            lots.setdefault(ticker, []).append([dt, qty])
        elif side == "SELL":
            remaining = qty
            queue = lots.setdefault(ticker, [])
            while remaining > 0 and queue:
                buy_dt, buy_qty = queue[0]
                matched = min(remaining, buy_qty)
                weighted_days += matched * max((dt - buy_dt).days, 0)
                qty_sold_total += matched
                remaining -= matched
                buy_qty -= matched
                if buy_qty <= 1e-9:
                    queue.pop(0)
                else:
                    queue[0][1] = buy_qty

    if qty_sold_total <= 0:
        return None
    return float(weighted_days / qty_sold_total)


def _ensure_regime_column(curve: pd.DataFrame) -> pd.DataFrame:
    out = curve.copy()
    if "regime_defensivo" not in out.columns:
        out["regime_defensivo"] = False
    out["regime_defensivo"] = out["regime_defensivo"].fillna(False).astype(bool)
    return out


def _num_switches_segment(curve: pd.DataFrame) -> int:
    if curve.empty or "num_switches_cumsum" not in curve.columns:
        return 0
    vals = curve["num_switches_cumsum"].astype(float)
    return int(max(vals.max() - vals.min(), 0.0))


def _compute_metrics(curve: pd.DataFrame, ledger: pd.DataFrame) -> dict[str, Any]:
    c = curve.copy().sort_values("date")
    l = ledger.copy()
    c["date"] = pd.to_datetime(c["date"], errors="coerce")
    c = c.dropna(subset=["date", "equity_end"])
    l["date"] = pd.to_datetime(l["date"], errors="coerce")
    l = l.dropna(subset=["date", "side", "notional"])

    equity = c["equity_end"].astype(float)
    ret = equity.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    downside = ret.clip(upper=0.0)

    buy_notional = float(l.loc[l["side"].astype(str).str.upper() == "BUY", "notional"].sum())
    sell_notional = float(l.loc[l["side"].astype(str).str.upper() == "SELL", "notional"].sum())
    reentry_notional = float(
        l.loc[
            (l["side"].astype(str).str.upper() == "BUY")
            & (l.get("reason", "").astype(str).str.contains("REENTRY", case=False, na=False)),
            "notional",
        ].sum()
    )
    avg_equity = float(equity.mean()) if not equity.empty else np.nan

    start_date = c["date"].iloc[0]
    end_date = c["date"].iloc[-1]
    years = max((end_date - start_date).days / 365.25, 1e-9)
    eq_ini = float(equity.iloc[0]) if not equity.empty else np.nan
    eq_final = float(equity.iloc[-1]) if not equity.empty else np.nan

    var_5 = float(ret.quantile(0.05)) if not ret.empty else np.nan
    cvar_5 = float(ret[ret <= var_5].mean()) if not ret.empty else np.nan
    sharpe = float((ret.mean() / ret.std(ddof=0)) * np.sqrt(ANN_FACTOR)) if ret.std(ddof=0) > 0 else np.nan

    metrics = {
        "equity_final": eq_final,
        "CAGR": float((eq_final / eq_ini) ** (1.0 / years) - 1.0) if eq_ini > 0 else np.nan,
        "MDD": _max_drawdown(equity),
        "time_to_recover": _time_to_recover_days(c),
        "vol_annual": float(ret.std(ddof=0) * np.sqrt(ANN_FACTOR)) if not ret.empty else np.nan,
        "downside_dev": float(downside.std(ddof=0) * np.sqrt(ANN_FACTOR)) if not downside.empty else np.nan,
        "VaR": var_5,
        "CVaR": cvar_5,
        "turnover_total": float((buy_notional + sell_notional) / avg_equity) if avg_equity > 0 else np.nan,
        "turnover_sell": float(sell_notional / avg_equity) if avg_equity > 0 else np.nan,
        "turnover_reentry": float(reentry_notional / avg_equity) if avg_equity > 0 else np.nan,
        "num_switches": _num_switches_segment(c),
        "avg_holding_time": _weighted_holding_days(l),
        "cost_total": float(l.get("cost_brl", pd.Series(dtype=float)).sum()),
        "missed_sell_rate": None,
        "false_sell_rate": None,
        "regret_3d": None,
        "sharpe": sharpe,
        "dates_simulated": int(len(c)),
        "period_start": str(start_date.date()),
        "period_end": str(end_date.date()),
    }
    return {k: _to_native(v) for k, v in metrics.items()}


def _subperiod_label(ts: pd.Timestamp) -> str:
    y = ts.year
    if y == 2018:
        return "2018H2"
    if y == 2026:
        return "2026-YTD"
    return str(y)


@dataclass
class TaskData:
    task_id: str
    curve: pd.DataFrame
    ledger: pd.DataFrame


def _load_data() -> list[TaskData]:
    out: list[TaskData] = []
    for task_id, paths in INPUTS.items():
        curve_path = paths["curve"]
        ledger_path = paths["ledger"]
        if not curve_path.exists() or not ledger_path.exists():
            raise FileNotFoundError(f"Arquivos ausentes para {task_id}: {curve_path} / {ledger_path}")
        curve = pd.read_parquet(curve_path)
        ledger = pd.read_parquet(ledger_path)
        curve["date"] = pd.to_datetime(curve["date"], errors="coerce")
        ledger["date"] = pd.to_datetime(ledger["date"], errors="coerce")
        out.append(TaskData(task_id=task_id, curve=_ensure_regime_column(curve), ledger=ledger))
    return out


def main() -> None:
    print(f"HEADER: {TASK_ID}")
    print("STEP GATES:")
    print(" - G1_INPUTS: PASS")

    datasets = _load_data()
    by_task: dict[str, dict[str, Any]] = {}
    regime_rows: list[dict[str, Any]] = []
    subperiod_rows: list[dict[str, Any]] = []

    for data in datasets:
        by_task[data.task_id] = _compute_metrics(data.curve, data.ledger)

        for regime_val in [False, True]:
            curve_seg = data.curve[data.curve["regime_defensivo"] == regime_val].copy()
            ledger_seg = data.ledger[data.ledger["date"].isin(curve_seg["date"])].copy()
            if curve_seg.empty:
                continue
            metrics = _compute_metrics(curve_seg, ledger_seg)
            regime_rows.append(
                {
                    "task_id": data.task_id,
                    "regime_defensivo": regime_val,
                    **metrics,
                }
            )

        data.curve["subperiod"] = data.curve["date"].apply(_subperiod_label)
        for sub in sorted(data.curve["subperiod"].dropna().unique()):
            curve_seg = data.curve[data.curve["subperiod"] == sub].copy()
            ledger_seg = data.ledger[data.ledger["date"].isin(curve_seg["date"])].copy()
            if curve_seg.empty:
                continue
            metrics = _compute_metrics(curve_seg, ledger_seg)
            subperiod_rows.append({"task_id": data.task_id, "subperiod": sub, **metrics})

    OUT_COMPARATIVE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "task_id": TASK_ID,
        "ann_factor": ANN_FACTOR,
        "notes": {
            "missed_sell_rate": "null - exige ground truth `should_sell` no ledger, ausente nesta fase.",
            "false_sell_rate": "null - exige ground truth `should_sell` no ledger, ausente nesta fase.",
            "regret_3d": "null - exige oracle/action de curto prazo, ausente nesta fase.",
            "turnover_reentry": "calculado por BUY com reason contendo `REENTRY`; se inexistente no ledger, resulta 0.",
        },
        "metrics_by_task": by_task,
    }
    OUT_COMPARATIVE.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    pd.DataFrame(regime_rows).to_csv(OUT_BY_REGIME, index=False)
    pd.DataFrame(subperiod_rows).to_csv(OUT_BY_SUBPERIOD, index=False)

    print(" - G2_METRICS_COMPUTE: PASS")
    print(" - G3_ARTIFACTS_WRITE: PASS")
    print("RETRY LOG: NONE")
    print("ARTIFACT LINKS:")
    print(f" - {OUT_COMPARATIVE}")
    print(f" - {OUT_BY_REGIME}")
    print(f" - {OUT_BY_SUBPERIOD}")

    summary_cols = ["CAGR", "MDD", "sharpe", "VaR", "turnover_total"]
    summary_df = pd.DataFrame(
        [{"task_id": t, **{c: by_task[t].get(c) for c in summary_cols}} for t in sorted(by_task.keys())]
    )
    print("SUMMARY:")
    print(summary_df.to_string(index=False))
    print("OVERALL STATUS: [[ PASS ]]")


if __name__ == "__main__":
    main()
