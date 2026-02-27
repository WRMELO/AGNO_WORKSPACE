from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

TASK_ID = "T041"
BASE_CAPITAL = 100000.0

BASE_DIR = Path("/home/wilson/AGNO_WORKSPACE/src/data_engine/portfolio")
OUT_HTML = Path("/home/wilson/AGNO_WORKSPACE/outputs/plots/T041_STATE3_PHASE1_COMPARATIVE.html")

CURVE_T037 = BASE_DIR / "T037_PORTFOLIO_CURVE.parquet"
CURVE_T038 = BASE_DIR / "T038_PORTFOLIO_CURVE.parquet"
CURVE_T039 = BASE_DIR / "T039_PORTFOLIO_CURVE.parquet"
METRICS_JSON = BASE_DIR / "T040_METRICS_COMPARATIVE.json"


def normalize_series(series: pd.Series) -> pd.Series:
    s = series.astype(float)
    return BASE_CAPITAL * (s / float(s.iloc[0]))


def find_true_intervals(mask: pd.Series, dates: pd.Series) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    intervals: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    start = None
    prev_date = None
    for is_true, dt in zip(mask.tolist(), dates.tolist()):
        if is_true and start is None:
            start = dt
        if not is_true and start is not None:
            intervals.append((start, prev_date if prev_date is not None else dt))
            start = None
        prev_date = dt
    if start is not None and prev_date is not None:
        intervals.append((start, prev_date))
    return intervals


def fmt_pct(x: float | None) -> str:
    if x is None:
        return "N/A"
    return f"{x * 100:.2f}%"


def fmt_num(x: float | None, dec: int = 2) -> str:
    if x is None:
        return "N/A"
    return f"{x:,.{dec}f}"


def build_metrics_table(metrics_by_task: dict) -> str:
    rows = [
        ("CAGR", "pct"),
        ("MDD", "pct"),
        ("sharpe", "num"),
        ("VaR", "pct"),
        ("CVaR", "pct"),
        ("vol_annual", "pct"),
        ("downside_dev", "pct"),
        ("turnover_total", "num"),
        ("avg_holding_time", "num"),
        ("cost_total", "brl"),
        ("num_switches", "int"),
    ]
    labels = {
        "CAGR": "CAGR",
        "MDD": "MDD",
        "sharpe": "Sharpe",
        "VaR": "VaR (5%)",
        "CVaR": "CVaR (5%)",
        "vol_annual": "Vol. Anual",
        "downside_dev": "Downside Dev",
        "turnover_total": "Turnover Total (x)",
        "avg_holding_time": "Holding Médio (dias)",
        "cost_total": "Custo Total (R$)",
        "num_switches": "Num Switches",
    }

    html = [
        "<h3 style='margin:10px 0 6px 0;'>Tabela Comparativa de Métricas (T040)</h3>",
        "<table style='border-collapse:collapse;width:100%;font-family:Arial,sans-serif;'>",
        "<thead><tr style='background:#f3f3f3;'>"
        "<th style='border:1px solid #ddd;padding:8px;text-align:left;'>Métrica</th>"
        "<th style='border:1px solid #ddd;padding:8px;text-align:right;'>T037</th>"
        "<th style='border:1px solid #ddd;padding:8px;text-align:right;'>T038</th>"
        "<th style='border:1px solid #ddd;padding:8px;text-align:right;'>T039</th>"
        "</tr></thead><tbody>",
    ]

    for metric, kind in rows:
        t037 = metrics_by_task["T037"].get(metric)
        t038 = metrics_by_task["T038"].get(metric)
        t039 = metrics_by_task["T039"].get(metric)

        if kind == "pct":
            v1, v2, v3 = fmt_pct(t037), fmt_pct(t038), fmt_pct(t039)
        elif kind == "brl":
            v1, v2, v3 = f"R$ {fmt_num(t037)}", f"R$ {fmt_num(t038)}", f"R$ {fmt_num(t039)}"
        elif kind == "int":
            v1, v2, v3 = fmt_num(t037, 0), fmt_num(t038, 0), fmt_num(t039, 0)
        else:
            v1, v2, v3 = fmt_num(t037), fmt_num(t038), fmt_num(t039)

        html.append(
            "<tr>"
            f"<td style='border:1px solid #ddd;padding:8px;'>{labels[metric]}</td>"
            f"<td style='border:1px solid #ddd;padding:8px;text-align:right;'>{v1}</td>"
            f"<td style='border:1px solid #ddd;padding:8px;text-align:right;'>{v2}</td>"
            f"<td style='border:1px solid #ddd;padding:8px;text-align:right;'>{v3}</td>"
            "</tr>"
        )
    html.append("</tbody></table>")
    return "".join(html)


def main() -> None:
    print(f"HEADER: {TASK_ID}")
    print("STEP GATES:")

    for f in [CURVE_T037, CURVE_T038, CURVE_T039, METRICS_JSON]:
        if not f.exists():
            raise FileNotFoundError(f"Arquivo ausente: {f}")
    print(" - G1_INPUTS: PASS")

    t037 = pd.read_parquet(CURVE_T037).sort_values("date")
    t038 = pd.read_parquet(CURVE_T038).sort_values("date")
    t039 = pd.read_parquet(CURVE_T039).sort_values("date")
    for df in [t037, t038, t039]:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    with METRICS_JSON.open("r", encoding="utf-8") as f:
        metrics_payload = json.load(f)
    metrics = metrics_payload["metrics_by_task"]

    t037["equity_norm"] = normalize_series(t037["equity_end"])
    t038["equity_norm"] = normalize_series(t038["equity_end"])
    t039["equity_norm"] = normalize_series(t039["equity_end"])

    t039["cdi_equity"] = BASE_CAPITAL * (1.0 + t039["cdi_daily"].astype(float)).cumprod()
    t039["cdi_equity"] = BASE_CAPITAL * (t039["cdi_equity"] / float(t039["cdi_equity"].iloc[0]))
    t039["ibov_equity"] = BASE_CAPITAL * (
        t039["ibov_close"].astype(float) / float(t039["ibov_close"].astype(float).iloc[0])
    )

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=t037["date"],
            y=t037["equity_norm"],
            mode="lines",
            name="T037 M3 Puro",
            line=dict(color="#7f7f7f", dash="dash", width=1.5),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=t038["date"],
            y=t038["equity_norm"],
            mode="lines",
            name="T038 M3+Gate",
            line=dict(color="#1f77b4", dash="dash", width=1.5),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=t039["date"],
            y=t039["equity_norm"],
            mode="lines",
            name="T039 M3+Gate+Severity [BASELINE]",
            line=dict(color="#2ca02c", width=3),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=t039["date"],
            y=t039["cdi_equity"],
            mode="lines",
            name="CDI Acumulado",
            line=dict(color="#bdbdbd", dash="dash", width=1),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=t039["date"],
            y=t039["ibov_equity"],
            mode="lines",
            name="Ibovespa ^BVSP",
            line=dict(color="#ff7f0e", dash="dot", width=1.5),
        )
    )

    regime = t039["regime_defensivo"].fillna(False).astype(bool)
    intervals = find_true_intervals(regime, t039["date"])
    for x0, x1 in intervals:
        fig.add_vrect(x0=x0, x1=x1, fillcolor="rgba(255,0,0,0.08)", line_width=0)

    def nearest_y(df: pd.DataFrame, target: pd.Timestamp, col: str) -> float:
        idx = (df["date"] - target).abs().idxmin()
        return float(df.loc[idx, col])

    covid = pd.Timestamp("2020-03-23")
    selic = pd.Timestamp("2021-03-17")

    fig.add_annotation(
        x=covid,
        y=nearest_y(t039, covid, "equity_norm"),
        text="COVID Crash",
        showarrow=True,
        arrowhead=1,
        ay=-40,
    )
    fig.add_annotation(
        x=selic,
        y=nearest_y(t039, selic, "equity_norm"),
        text="Início Alta Selic",
        showarrow=True,
        arrowhead=1,
        ay=-40,
    )

    fig.update_layout(
        title="STATE 3 Phase 1 — M3 Canonical Strategy Comparative (Base R$100k)",
        xaxis_title="Data",
        yaxis_title="Patrimônio (R$)",
        template="plotly_white",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )

    plot_html = fig.to_html(full_html=False, include_plotlyjs="cdn")
    table_html = build_metrics_table(metrics)
    final_html = (
        "<html><head><meta charset='utf-8'><title>T041 STATE 3 Phase 1</title></head>"
        "<body style='max-width:1400px;margin:0 auto;padding:10px;'>"
        f"{plot_html}"
        f"{table_html}"
        "<p style='font-size:12px;color:#666;'>"
        "Fonte: T037/T038/T039 curves + T040 metrics comparative."
        "</p>"
        "</body></html>"
    )

    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(final_html, encoding="utf-8")
    print(" - G2_PLOT_BUILD: PASS")
    print(" - G3_ARTIFACT_WRITE: PASS")
    print("RETRY LOG: NONE")
    print("ARTIFACT LINKS:")
    print(f" - {OUT_HTML}")
    print("FINAL EQUITIES (BASE 100k):")
    print(f" - T037: {t037['equity_norm'].iloc[-1]:.2f}")
    print(f" - T038: {t038['equity_norm'].iloc[-1]:.2f}")
    print(f" - T039: {t039['equity_norm'].iloc[-1]:.2f}")
    print(f" - CDI : {t039['cdi_equity'].iloc[-1]:.2f}")
    print(f" - IBOV: {t039['ibov_equity'].iloc[-1]:.2f}")
    print("OVERALL STATUS: [[ PASS ]]")


if __name__ == "__main__":
    main()
