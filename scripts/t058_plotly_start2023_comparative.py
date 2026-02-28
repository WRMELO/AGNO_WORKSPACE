#!/usr/bin/env python3
"""T058 - Plotly comparativo Start-2023 (T044 vs T037 vs T039 vs CDI vs Ibov)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


TASK_ID = "T058-START2023-PLOTLY-V1"
BASE_CAPITAL = 100000.0
ROOT = Path("/home/wilson/AGNO_WORKSPACE")

INPUT_T037_CURVE = ROOT / "src/data_engine/portfolio/T037_PORTFOLIO_CURVE.parquet"
INPUT_T039_CURVE = ROOT / "src/data_engine/portfolio/T039_PORTFOLIO_CURVE.parquet"
INPUT_T044_CURVE = ROOT / "src/data_engine/portfolio/T044_PORTFOLIO_CURVE_GUARDRAILS.parquet"
INPUT_T037_SUMMARY = ROOT / "src/data_engine/portfolio/T037_BASELINE_SUMMARY.json"
INPUT_T039_SUMMARY = ROOT / "src/data_engine/portfolio/T039_BASELINE_SUMMARY.json"
INPUT_T044_SUMMARY = ROOT / "src/data_engine/portfolio/T044_BASELINE_SUMMARY.json"
INPUT_MACRO = ROOT / "src/data_engine/ssot/SSOT_MACRO.parquet"

OUTPUT_HTML = ROOT / "outputs/plots/T058_STATE3_START2023_COMPARATIVE.html"
OUTPUT_REPORT = ROOT / "outputs/governanca/T058-START2023-PLOTLY-V1_report.md"
OUTPUT_MANIFEST = ROOT / "outputs/governanca/T058-START2023-PLOTLY-V1_manifest.json"
OUTPUT_EVIDENCE_DIR = ROOT / "outputs/governanca/T058-START2023-PLOTLY-V1_evidence"
OUTPUT_METRICS_SNAPSHOT = OUTPUT_EVIDENCE_DIR / "metrics_snapshot.json"
OUTPUT_PLOT_INVENTORY = OUTPUT_EVIDENCE_DIR / "plot_inventory.json"
SCRIPT_PATH = ROOT / "scripts/t058_plotly_start2023_comparative.py"

CHANGELOG_PATH = ROOT / "00_Strategy/changelog.md"
TRACEABILITY_LINE = (
    "- 2026-02-28T17:35:47Z | VISUALIZATION: T058-START2023-PLOTLY-V1 EXEC. "
    "Artefatos: outputs/plots/T058_STATE3_START2023_COMPARATIVE.html; "
    "outputs/governanca/T058-START2023-PLOTLY-V1_report.md; "
    "outputs/governanca/T058-START2023-PLOTLY-V1_manifest.json"
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _json_safe(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, tuple):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, (np.floating, float)):
        val = float(obj)
        return val if np.isfinite(val) else None
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if pd.isna(obj):
        return None
    return obj


def write_json_strict(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    safe = _json_safe(payload)
    path.write_text(json.dumps(safe, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def parse_json_strict(path: Path) -> Any:
    txt = path.read_text(encoding="utf-8")
    return json.loads(txt, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(f"invalid constant: {x}")))


def normalize_to_base(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce").astype(float)
    return BASE_CAPITAL * (s / float(s.iloc[0]))


def compute_cdi_curve(macro: pd.DataFrame, start_date: pd.Timestamp) -> pd.DataFrame:
    m = macro.copy()
    m["date"] = pd.to_datetime(m["date"], errors="coerce").dt.normalize()
    m = m.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    m = m[m["date"] >= start_date].copy()
    if m.empty:
        raise RuntimeError("CDI: sem dados no recorte start_date.")

    if "cdi_log_daily" not in m.columns:
        raise RuntimeError("CDI: coluna cdi_log_daily ausente no SSOT_MACRO.")

    logret = pd.to_numeric(m["cdi_log_daily"], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
    # capital[t] = capital[t-1] * exp(logret[t]); define base no primeiro dia do recorte.
    growth = np.exp(np.cumsum(logret.to_numpy(dtype=float)))
    m["cdi_rebased"] = BASE_CAPITAL * (growth / float(growth[0]))
    return m[["date", "cdi_rebased"]]


def compute_ibov_curve(macro: pd.DataFrame, start_date: pd.Timestamp) -> pd.DataFrame:
    m = macro.copy()
    m["date"] = pd.to_datetime(m["date"], errors="coerce").dt.normalize()
    m = m.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    m = m[m["date"] >= start_date].copy()
    if m.empty:
        raise RuntimeError("Ibov: sem dados no recorte start_date.")
    if "ibov_close" not in m.columns:
        raise RuntimeError("Ibov: coluna ibov_close ausente no SSOT_MACRO.")
    close = pd.to_numeric(m["ibov_close"], errors="coerce").astype(float)
    m["ibov_rebased"] = normalize_to_base(close)
    return m[["date", "ibov_rebased"]]


def max_drawdown(level: pd.Series) -> float | None:
    s = pd.to_numeric(level, errors="coerce").astype(float)
    s = s.replace([np.inf, -np.inf], np.nan).dropna()
    if s.empty:
        return None
    dd = s / s.cummax() - 1.0
    return float(dd.min())


def sharpe_from_level(level: pd.Series, ann_factor: float = 252.0) -> float | None:
    s = pd.to_numeric(level, errors="coerce").astype(float)
    ret = s.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    if ret.empty:
        return None
    sd = float(ret.std(ddof=0))
    if sd <= 0:
        return None
    return float((ret.mean() / sd) * np.sqrt(ann_factor))


def cagr_from_level(level: pd.Series, dates: pd.Series) -> float | None:
    s = pd.to_numeric(level, errors="coerce").astype(float).replace([np.inf, -np.inf], np.nan).dropna()
    if len(s) < 2:
        return None
    d = pd.to_datetime(dates, errors="coerce").dropna()
    if len(d) < 2:
        return None
    years = max((d.iloc[-1] - d.iloc[0]).days / 365.25, 1e-9)
    return float((float(s.iloc[-1]) / float(s.iloc[0])) ** (1.0 / years) - 1.0)


def update_changelog_one_line() -> bool:
    CHANGELOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    before = CHANGELOG_PATH.read_text(encoding="utf-8") if CHANGELOG_PATH.exists() else ""
    before_len = len(before.encode("utf-8"))
    with CHANGELOG_PATH.open("a", encoding="utf-8") as f:
        if before and not before.endswith("\n"):
            f.write("\n")
        f.write(TRACEABILITY_LINE + "\n")
    after = CHANGELOG_PATH.read_text(encoding="utf-8")
    after_len = len(after.encode("utf-8"))
    appended = after_len > before_len
    ends_with_line = after.endswith(TRACEABILITY_LINE + "\n")
    return bool(appended and ends_with_line)


def main() -> int:
    print(f"HEADER: {TASK_ID}")

    required_inputs = [
        INPUT_T037_CURVE,
        INPUT_T039_CURVE,
        INPUT_T044_CURVE,
        INPUT_T037_SUMMARY,
        INPUT_T039_SUMMARY,
        INPUT_T044_SUMMARY,
        INPUT_MACRO,
        SCRIPT_PATH,
        CHANGELOG_PATH,
    ]

    missing = [str(p) for p in required_inputs if not p.exists()]
    if missing:
        print("STEP GATES:")
        print(f"- G0_INPUTS_PRESENT: FAIL (missing: {', '.join(missing)})")
        print("OVERALL STATUS: [[ FAIL ]]")
        return 1

    for p in [OUTPUT_HTML, OUTPUT_REPORT, OUTPUT_MANIFEST, OUTPUT_METRICS_SNAPSHOT, OUTPUT_PLOT_INVENTORY]:
        p.parent.mkdir(parents=True, exist_ok=True)

    # Load data
    t037 = pd.read_parquet(INPUT_T037_CURVE).copy()
    t039 = pd.read_parquet(INPUT_T039_CURVE).copy()
    t044 = pd.read_parquet(INPUT_T044_CURVE).copy()
    macro = pd.read_parquet(INPUT_MACRO).copy()

    for df in [t037, t039, t044]:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    macro["date"] = pd.to_datetime(macro["date"], errors="coerce").dt.normalize()

    # Determine START_DATE = first trading day of 2023 in intersection
    dates_inter = set(t037["date"].dropna()) & set(t039["date"].dropna()) & set(t044["date"].dropna()) & set(macro["date"].dropna())
    dates_2023 = sorted([d for d in dates_inter if pd.Timestamp(d).year == 2023])
    if not dates_2023:
        raise RuntimeError("Nao foi possivel determinar START_DATE (sem interseção em 2023).")
    start_date = pd.Timestamp(dates_2023[0]).normalize()

    def _slice_and_rebase(df: pd.DataFrame, label: str) -> pd.DataFrame:
        out = df[df["date"] >= start_date].copy().sort_values("date")
        if out.empty:
            raise RuntimeError(f"{label}: sem dados no recorte start_date.")
        out["equity_rebased"] = normalize_to_base(pd.to_numeric(out["equity_end"], errors="coerce"))
        out["dd"] = out["equity_rebased"] / out["equity_rebased"].cummax() - 1.0
        return out[["date", "equity_rebased", "dd"]]

    s037 = _slice_and_rebase(t037, "T037")
    s039 = _slice_and_rebase(t039, "T039")
    s044 = _slice_and_rebase(t044, "T044")

    cdi = compute_cdi_curve(macro, start_date)
    cdi["dd"] = cdi["cdi_rebased"] / cdi["cdi_rebased"].cummax() - 1.0
    ibov = compute_ibov_curve(macro, start_date)
    ibov["dd"] = ibov["ibov_rebased"] / ibov["ibov_rebased"].cummax() - 1.0

    # Metrics snapshot for the recorte
    metrics_snapshot = {
        "task_id": TASK_ID,
        "start_date": str(start_date.date()),
        "end_date": str(pd.to_datetime(s044["date"]).max().date()),
        "metrics": {
            "T044": {
                "equity_final": float(s044["equity_rebased"].iloc[-1]),
                "cagr": cagr_from_level(s044["equity_rebased"], s044["date"]),
                "mdd": max_drawdown(s044["equity_rebased"]),
                "sharpe": sharpe_from_level(s044["equity_rebased"]),
            },
            "T037": {
                "equity_final": float(s037["equity_rebased"].iloc[-1]),
                "cagr": cagr_from_level(s037["equity_rebased"], s037["date"]),
                "mdd": max_drawdown(s037["equity_rebased"]),
                "sharpe": sharpe_from_level(s037["equity_rebased"]),
            },
            "T039": {
                "equity_final": float(s039["equity_rebased"].iloc[-1]),
                "cagr": cagr_from_level(s039["equity_rebased"], s039["date"]),
                "mdd": max_drawdown(s039["equity_rebased"]),
                "sharpe": sharpe_from_level(s039["equity_rebased"]),
            },
            "CDI": {
                "equity_final": float(cdi["cdi_rebased"].iloc[-1]),
                "cagr": cagr_from_level(cdi["cdi_rebased"], cdi["date"]),
                "mdd": max_drawdown(cdi["cdi_rebased"]),
                "sharpe": sharpe_from_level(cdi["cdi_rebased"]),
            },
            "IBOV": {
                "equity_final": float(ibov["ibov_rebased"].iloc[-1]),
                "cagr": cagr_from_level(ibov["ibov_rebased"], ibov["date"]),
                "mdd": max_drawdown(ibov["ibov_rebased"]),
                "sharpe": sharpe_from_level(ibov["ibov_rebased"]),
            },
        },
    }
    write_json_strict(OUTPUT_METRICS_SNAPSHOT, metrics_snapshot)

    # Plotly
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=(
            f"Equity (rebased R$100k em {start_date.date()})",
            "Drawdown",
        ),
    )

    def add_line(df: pd.DataFrame, ycol: str, name: str, color: str, row: int) -> None:
        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=df[ycol],
                name=name,
                mode="lines",
                line=dict(color=color, width=2),
            ),
            row=row,
            col=1,
        )

    add_line(s044, "equity_rebased", "T044 (Solution)", "#d62728", 1)
    add_line(s037, "equity_rebased", "T037 (Meta)", "#2ca02c", 1)
    add_line(s039, "equity_rebased", "T039 (Baseline)", "#1f77b4", 1)
    add_line(cdi, "cdi_rebased", "CDI", "#111111", 1)
    add_line(ibov, "ibov_rebased", "Ibov", "#9467bd", 1)

    add_line(s044, "dd", "DD T044", "#d62728", 2)
    add_line(s037, "dd", "DD T037", "#2ca02c", 2)
    add_line(s039, "dd", "DD T039", "#1f77b4", 2)
    add_line(cdi, "dd", "DD CDI", "#111111", 2)
    add_line(ibov, "dd", "DD Ibov", "#9467bd", 2)

    fig.update_yaxes(title_text="R$ (rebased)", row=1, col=1)
    fig.update_yaxes(title_text="Drawdown", tickformat=".0%", row=2, col=1)
    fig.update_xaxes(title_text="Data", row=2, col=1)

    fig.update_layout(
        title=f"{TASK_ID} — Start 2023 Comparative",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0.0),
        height=900,
        template="plotly_white",
        margin=dict(l=40, r=40, t=90, b=40),
    )

    OUTPUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(OUTPUT_HTML), include_plotlyjs="cdn")

    plot_inventory = {
        "task_id": TASK_ID,
        "start_date": str(start_date.date()),
        "traces": [t.name for t in fig.data],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
    write_json_strict(OUTPUT_PLOT_INVENTORY, plot_inventory)

    report_lines = [
        f"# {TASK_ID} Report",
        "",
        f"- START_DATE (primeiro pregão 2023 na interseção): **{start_date.date()}**",
        f"- END_DATE: **{pd.to_datetime(s044['date']).max().date()}**",
        "",
        "## Inputs",
        f"- `{INPUT_T037_CURVE}`",
        f"- `{INPUT_T039_CURVE}`",
        f"- `{INPUT_T044_CURVE}`",
        f"- `{INPUT_MACRO}`",
        "",
        "## Outputs",
        f"- `{OUTPUT_HTML}`",
        f"- `{OUTPUT_REPORT}`",
        f"- `{OUTPUT_METRICS_SNAPSHOT}`",
        f"- `{OUTPUT_PLOT_INVENTORY}`",
        f"- `{OUTPUT_MANIFEST}`",
        "",
        "## Métricas (recorte 2023+; rebased em R$100k no START_DATE)",
        "```json",
        json.dumps(_json_safe(metrics_snapshot["metrics"]), indent=2, sort_keys=True, allow_nan=False),
        "```",
        "",
        "## Notas",
        "- CDI construído a partir de `cdi_log_daily` (acumulação exp(cumsum)).",
        "- Ibov construído a partir de `ibov_close` (rebased direto pelo nível).",
    ]
    OUTPUT_REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    # Changelog gate (append exactly 1 line)
    g_chlog = update_changelog_one_line()

    # Manifest (sem self-hash)
    outputs = [
        OUTPUT_HTML,
        OUTPUT_REPORT,
        OUTPUT_METRICS_SNAPSHOT,
        OUTPUT_PLOT_INVENTORY,
    ]
    manifest = {
        "task_id": TASK_ID,
        "inputs_consumed": [
            str(INPUT_T037_CURVE),
            str(INPUT_T039_CURVE),
            str(INPUT_T044_CURVE),
            str(INPUT_T037_SUMMARY),
            str(INPUT_T039_SUMMARY),
            str(INPUT_T044_SUMMARY),
            str(INPUT_MACRO),
            str(SCRIPT_PATH),
        ],
        "outputs_produced": [str(p) for p in outputs] + [str(OUTPUT_MANIFEST)],
        "hashes_sha256": {
            str(INPUT_T037_CURVE): sha256_file(INPUT_T037_CURVE),
            str(INPUT_T039_CURVE): sha256_file(INPUT_T039_CURVE),
            str(INPUT_T044_CURVE): sha256_file(INPUT_T044_CURVE),
            str(INPUT_T037_SUMMARY): sha256_file(INPUT_T037_SUMMARY),
            str(INPUT_T039_SUMMARY): sha256_file(INPUT_T039_SUMMARY),
            str(INPUT_T044_SUMMARY): sha256_file(INPUT_T044_SUMMARY),
            str(INPUT_MACRO): sha256_file(INPUT_MACRO),
            str(SCRIPT_PATH): sha256_file(SCRIPT_PATH),
            str(OUTPUT_HTML): sha256_file(OUTPUT_HTML),
            str(OUTPUT_REPORT): sha256_file(OUTPUT_REPORT),
            str(OUTPUT_METRICS_SNAPSHOT): sha256_file(OUTPUT_METRICS_SNAPSHOT),
            str(OUTPUT_PLOT_INVENTORY): sha256_file(OUTPUT_PLOT_INVENTORY),
        },
    }
    write_json_strict(OUTPUT_MANIFEST, manifest)

    g0 = True
    g1 = OUTPUT_HTML.exists() and OUTPUT_METRICS_SNAPSHOT.exists() and OUTPUT_PLOT_INVENTORY.exists()
    gx = OUTPUT_MANIFEST.exists()

    print("STEP GATES:")
    print("- G_MODEL_ROUTING: PASS_MODEL_ROUTING_UNVERIFIED (sem evidência explícita no chat)")
    print(f"- G0_INPUTS_PRESENT: {'PASS' if g0 else 'FAIL'}")
    print(f"- G1_PLOTLY_PRESENT: {'PASS' if g1 else 'FAIL'}")
    print(f"- G_CHLOG_UPDATED: {'PASS' if g_chlog else 'FAIL'}")
    print(f"- Gx_HASH_MANIFEST_PRESENT: {'PASS' if gx else 'FAIL'}")
    print("ARTIFACT LINKS:")
    print(f"- {OUTPUT_HTML}")
    print(f"- {OUTPUT_REPORT}")
    print(f"- {OUTPUT_METRICS_SNAPSHOT}")
    print(f"- {OUTPUT_PLOT_INVENTORY}")
    print(f"- {OUTPUT_MANIFEST}")
    print(f"- {CHANGELOG_PATH}")
    overall = g0 and g1 and g_chlog and gx
    print(f"OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())

