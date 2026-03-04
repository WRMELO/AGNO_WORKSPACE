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


if not ("agno_env" in sys.prefix or ".venv" in sys.prefix):
    raise RuntimeError("FATAL: Not in agno_env/.venv")


TASK_ID = "T109"
RUN_ID = "T109-PHASE8-PLOTLY-COMPARATIVE-V1"
ROOT = Path("/home/wilson/AGNO_WORKSPACE")
BASE_CAPITAL = 100000.0

PYTHON_ENV = ROOT / ".venv/bin/python"
CHANGELOG_PATH = ROOT / "00_Strategy/changelog.md"
TRACEABILITY_LINE = (
    "- 2026-03-04T11:00:00Z | VISUALIZATION: T109 Phase 8 Comparative Plotly (winner Phase 8 vs C060 vs CDI vs Ibov). "
    "Artefatos: scripts/t109_plotly_phase8_comparative.py; outputs/plots/T109_STATE3_PHASE8E_COMPARATIVE.html; "
    "outputs/governanca/T109-PHASE8-PLOTLY-COMPARATIVE-V1_manifest.json"
)

IN_T108_CURVE_ML = ROOT / "src/data_engine/portfolio/T108_PORTFOLIO_CURVE_DUAL_MODE_EXPANDED_ML_TRIGGER_WINNER.parquet"
IN_T108_CURVE_BASE = ROOT / "src/data_engine/portfolio/T108_PORTFOLIO_CURVE_DUAL_MODE_EXPANDED_WINNER.parquet"
IN_C060_CURVE = ROOT / "outputs/governanca/T079-PHASE6-PLOTLY-COMPARATIVE-V1_evidence/c060_curve_snapshot.parquet"

OUT_SCRIPT = ROOT / "scripts/t109_plotly_phase8_comparative.py"
OUT_HTML = ROOT / "outputs/plots/T109_STATE3_PHASE8E_COMPARATIVE.html"
OUT_REPORT = ROOT / "outputs/governanca/T109-PHASE8-PLOTLY-COMPARATIVE-V1_report.md"
OUT_MANIFEST = ROOT / "outputs/governanca/T109-PHASE8-PLOTLY-COMPARATIVE-V1_manifest.json"
OUT_EVID_DIR = ROOT / "outputs/governanca/T109-PHASE8-PLOTLY-COMPARATIVE-V1_evidence"
OUT_METRICS = OUT_EVID_DIR / "metrics_snapshot.json"
OUT_PLOT_INV = OUT_EVID_DIR / "plot_inventory.json"
OUT_JOIN_COVERAGE = OUT_EVID_DIR / "join_coverage.json"
OUT_ACID_DEF = OUT_EVID_DIR / "acid_window_definition.json"

ACID_START = pd.Timestamp("2024-11-01")
ACID_END = pd.Timestamp("2025-11-30")


@dataclass
class Gate:
    name: str
    passed: bool
    detail: str


def _json_safe(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, tuple):
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
    path.write_text(
        json.dumps(_json_safe(payload), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def drawdown(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce").astype(float)
    return s / s.cummax() - 1.0


def metrics(equity: pd.Series) -> dict[str, float]:
    s = pd.to_numeric(equity, errors="coerce").astype(float)
    r = s.pct_change().fillna(0.0)
    years = max((len(s) - 1) / 252.0, 1.0 / 252.0)
    cagr = float((s.iloc[-1] / s.iloc[0]) ** (1.0 / years) - 1.0)
    mdd = float(drawdown(s).min())
    vol = float(r.std(ddof=0))
    sharpe = float((r.mean() / vol) * np.sqrt(252.0)) if vol > 0 else np.nan
    return {"equity_final": float(s.iloc[-1]), "cagr": cagr, "mdd": mdd, "sharpe": sharpe}


def split_metrics(curve: pd.DataFrame) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for key, sub in [
        ("train", curve[curve["split"] == "TRAIN"]),
        ("holdout", curve[curve["split"] == "HOLDOUT"]),
        ("acid", curve[(curve["split"] == "HOLDOUT") & (curve["date"] >= ACID_START) & (curve["date"] <= ACID_END)]),
    ]:
        if len(sub) < 2:
            out[key] = {"equity_final": np.nan, "cagr": np.nan, "mdd": np.nan, "sharpe": np.nan, "switches": np.nan}
            continue
        m = metrics(sub["equity_end_norm"])
        m["switches"] = float((sub["state_cash"].diff().abs() == 1).sum()) if "state_cash" in sub.columns else 0.0
        out[key] = m
    return out


def append_changelog_one_line_idempotent(line: str) -> bool:
    existing = CHANGELOG_PATH.read_text(encoding="utf-8") if CHANGELOG_PATH.exists() else ""
    if line in existing:
        return True
    text = existing
    if text and not text.endswith("\n"):
        text += "\n"
    text += line.rstrip("\n") + "\n"
    CHANGELOG_PATH.write_text(text, encoding="utf-8")
    return line in CHANGELOG_PATH.read_text(encoding="utf-8")


def _fmt_num(v: Any, digits: int = 2) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, (float, np.floating)) and not np.isfinite(float(v)):
        return "n/a"
    return f"{float(v):.{digits}f}"


def _fmt_pct(v: Any, digits: int = 2) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, (float, np.floating)) and not np.isfinite(float(v)):
        return "n/a"
    return f"{float(v) * 100.0:.{digits}f}%"


def render_report(
    gates: list[Gate],
    retry_log: list[str],
    overall: bool,
    metrics_snapshot: dict[str, dict[str, dict[str, float]]] | None = None,
    join_coverage: dict[str, Any] | None = None,
) -> str:
    metrics_snapshot = metrics_snapshot or {}
    join_coverage = join_coverage or {}
    p8_h = metrics_snapshot.get("phase8_winner_ml", {}).get("holdout", {})
    c0_h = metrics_snapshot.get("c060", {}).get("holdout", {})
    p8_a = metrics_snapshot.get("phase8_winner_ml", {}).get("acid", {})
    c0_a = metrics_snapshot.get("c060", {}).get("acid", {})
    holdout_rel = np.nan
    acid_rel = np.nan
    if p8_h.get("equity_final") and c0_h.get("equity_final"):
        holdout_rel = (float(p8_h["equity_final"]) / float(c0_h["equity_final"])) - 1.0
    if p8_a.get("equity_final") and c0_a.get("equity_final"):
        acid_rel = (float(p8_a["equity_final"]) / float(c0_a["equity_final"])) - 1.0

    def curve_line(curve_key: str, split_key: str, label: str) -> str:
        m = metrics_snapshot.get(curve_key, {}).get(split_key, {})
        return (
            f"| {label} | {_fmt_num(m.get('equity_final'))} | {_fmt_pct(m.get('cagr'))} | "
            f"{_fmt_pct(m.get('mdd'))} | {_fmt_num(m.get('sharpe'), 3)} | {_fmt_num(m.get('switches'), 0)} |"
        )

    lines = [
        f"# HEADER: {TASK_ID}",
        "",
        "## STEP GATES",
    ]
    for g in gates:
        lines.append(f"- {g.name}: {'PASS' if g.passed else 'FAIL'} | {g.detail}")
    lines.extend(
        [
            "",
            "## RESULTADOS HOLDOUT",
            "- Curvas comparadas: T108 Winner + ML, C060, CDI, Ibov.",
            "- Tabela de metricas (HOLDOUT):",
            "| Curva | Equity Final | CAGR | MDD | Sharpe | Switches |",
            "|---|---:|---:|---:|---:|---:|",
            curve_line("phase8_winner_ml", "holdout", "Phase8 Winner + ML"),
            curve_line("c060", "holdout", "C060"),
            curve_line("cdi", "holdout", "CDI"),
            curve_line("ibov", "holdout", "Ibov"),
            f"- Relativo Phase8 Winner + ML vs C060 (HOLDOUT): {_fmt_pct(holdout_rel)}",
            "- Leitura: valor positivo indica vantagem da winner da Phase 8 sobre C060 no periodo de validacao.",
            "",
            "## RESULTADOS ACID",
            f"- Janela ACID: {ACID_START.strftime('%Y-%m-%d')}..{ACID_END.strftime('%Y-%m-%d')}",
            "- Tabela de metricas (ACID):",
            "| Curva | Equity Final | CAGR | MDD | Sharpe | Switches |",
            "|---|---:|---:|---:|---:|---:|",
            curve_line("phase8_winner_ml", "acid", "Phase8 Winner + ML"),
            curve_line("c060", "acid", "C060"),
            curve_line("cdi", "acid", "CDI"),
            curve_line("ibov", "acid", "Ibov"),
            f"- Relativo Phase8 Winner + ML vs C060 (ACID): {_fmt_pct(acid_rel)}",
            "",
            "## QUALIDADE DE DADOS E COBERTURA",
            f"- Datas comuns: {join_coverage.get('common_dates', 'n/a')} linhas.",
            f"- Janela comum: {join_coverage.get('date_min', 'n/a')} ate {join_coverage.get('date_max', 'n/a')}.",
            f"- Cobertura por curva: winner={join_coverage.get('winner_rows', 'n/a')}, c060={join_coverage.get('c060_rows', 'n/a')}, "
            f"cdi={join_coverage.get('cdi_rows', 'n/a')}, ibov={join_coverage.get('ibov_rows', 'n/a')}.",
            "",
            "## RETRY LOG",
            "- none" if not retry_log else "",
        ]
    )
    if retry_log:
        for r in retry_log:
            lines.append(f"- {r}")
    lines.extend(
        [
            "",
            "## ARTIFACT LINKS",
            f"- {OUT_HTML.relative_to(ROOT)}",
            f"- {OUT_REPORT.relative_to(ROOT)}",
            f"- {OUT_MANIFEST.relative_to(ROOT)}",
            f"- {OUT_METRICS.relative_to(ROOT)}",
            f"- {OUT_PLOT_INV.relative_to(ROOT)}",
            f"- {OUT_JOIN_COVERAGE.relative_to(ROOT)}",
            f"- {OUT_ACID_DEF.relative_to(ROOT)}",
            "",
            f"## OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    gates: list[Gate] = []
    retry_log: list[str] = []
    try:
        for p in [OUT_HTML, OUT_REPORT, OUT_MANIFEST]:
            p.parent.mkdir(parents=True, exist_ok=True)
        OUT_EVID_DIR.mkdir(parents=True, exist_ok=True)

        gate_env = PYTHON_ENV.exists() and (".venv" in sys.prefix or "agno_env" in sys.prefix)
        gates.append(Gate("G_ENV_VENV", gate_env, f"python={sys.executable}"))

        inputs = [IN_T108_CURVE_ML, IN_T108_CURVE_BASE, IN_C060_CURVE]
        inputs_ok = all(p.exists() for p in inputs)
        gates.append(Gate("G_INPUTS_EXIST", inputs_ok, "all required inputs present"))
        if not inputs_ok:
            raise FileNotFoundError("Missing required input files.")

        w = pd.read_parquet(IN_T108_CURVE_ML).copy()
        b = pd.read_parquet(IN_T108_CURVE_BASE).copy()
        c = pd.read_parquet(IN_C060_CURVE).copy()
        for df in [w, b, c]:
            df["date"] = pd.to_datetime(df["date"])
            df["split"] = df["split"].astype(str)

        # Benchmarks from T108 base curve
        cdi = pd.DataFrame({"date": b["date"], "split": b["split"]})
        cdi["equity_end_norm"] = BASE_CAPITAL * (1.0 + pd.to_numeric(b["cdi_daily"], errors="coerce").fillna(0.0)).cumprod()
        cdi.loc[cdi.index[0], "equity_end_norm"] = BASE_CAPITAL
        cdi["drawdown"] = drawdown(cdi["equity_end_norm"])
        cdi["state_cash"] = 0
        cdi["switches_cumsum"] = 0

        ibov = pd.DataFrame({"date": b["date"], "split": b["split"]})
        ibov["equity_end_norm"] = pd.to_numeric(b["benchmark_ibov"], errors="coerce").astype(float)
        ibov["drawdown"] = drawdown(ibov["equity_end_norm"])
        ibov["state_cash"] = 0
        ibov["switches_cumsum"] = 0

        merged = w[["date"]].merge(c[["date"]], on="date", how="inner", validate="one_to_one")
        merged = merged.merge(cdi[["date"]], on="date", how="inner", validate="one_to_one")
        merged = merged.merge(ibov[["date"]], on="date", how="inner", validate="one_to_one").sort_values("date")
        common_ok = (
            len(merged) == 1902
            and str(merged["date"].min().date()) == "2018-07-02"
            and str(merged["date"].max().date()) == "2026-02-26"
        )
        gates.append(Gate("G_COMMON_DATES_OK", common_ok, f"rows={len(merged)}"))
        if not common_ok:
            raise ValueError("Common dates mismatch.")

        fig = make_subplots(
            rows=4,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.04,
            subplot_titles=("Equity (base 100k)", "Drawdown", "Switches Cumulativos", "State Cash (0/1)"),
        )
        fig.add_trace(go.Scatter(x=w["date"], y=w["equity_end_norm"], name="Phase8 Winner + ML"), row=1, col=1)
        fig.add_trace(go.Scatter(x=c["date"], y=c["equity_end_norm"], name="C060"), row=1, col=1)
        fig.add_trace(go.Scatter(x=cdi["date"], y=cdi["equity_end_norm"], name="CDI"), row=1, col=1)
        fig.add_trace(go.Scatter(x=ibov["date"], y=ibov["equity_end_norm"], name="Ibov"), row=1, col=1)

        fig.add_trace(go.Scatter(x=w["date"], y=drawdown(w["equity_end_norm"]), name="DD Phase8"), row=2, col=1)
        fig.add_trace(go.Scatter(x=c["date"], y=drawdown(c["equity_end_norm"]), name="DD C060"), row=2, col=1)
        fig.add_trace(go.Scatter(x=cdi["date"], y=drawdown(cdi["equity_end_norm"]), name="DD CDI"), row=2, col=1)
        fig.add_trace(go.Scatter(x=ibov["date"], y=drawdown(ibov["equity_end_norm"]), name="DD Ibov"), row=2, col=1)

        fig.add_trace(go.Scatter(x=w["date"], y=w["switches_cumsum"], name="Switches Phase8"), row=3, col=1)
        fig.add_trace(go.Scatter(x=c["date"], y=c["switches_cumsum"], name="Switches C060"), row=3, col=1)

        fig.add_trace(go.Scatter(x=w["date"], y=w["state_cash"], name="State Phase8"), row=4, col=1)
        fig.add_trace(go.Scatter(x=c["date"], y=c["state_cash"], name="State C060"), row=4, col=1)

        for r in [1, 2, 3, 4]:
            fig.add_vrect(
                x0=ACID_START,
                x1=ACID_END,
                fillcolor="orange",
                opacity=0.12,
                line_width=0,
                row=r,
                col=1,
            )

        fig.update_layout(
            height=1450,
            title="T109 - Phase 8 Comparative (Winner vs C060 vs CDI vs Ibov)",
            template="plotly_white",
            legend={"orientation": "h", "y": 1.02, "x": 0.0},
        )
        fig.write_html(str(OUT_HTML), include_plotlyjs="cdn")
        gates.append(Gate("G_DASHBOARD_WRITTEN", OUT_HTML.exists(), f"path={OUT_HTML}"))

        metrics_snapshot = {
            "phase8_winner_ml": split_metrics(w),
            "c060": split_metrics(c),
            "cdi": split_metrics(cdi),
            "ibov": split_metrics(ibov),
        }
        write_json(OUT_METRICS, metrics_snapshot)
        write_json(
            OUT_PLOT_INV,
            {
                "rows": 4,
                "panels": ["equity", "drawdown", "switches_cumsum", "state_cash"],
                "equity_traces": ["Phase8 Winner + ML", "C060", "CDI", "Ibov"],
                "acid_window": {"start": ACID_START, "end": ACID_END},
                "traces_count": len(fig.data),
            },
        )
        write_json(
            OUT_JOIN_COVERAGE,
            {
                "common_dates": int(len(merged)),
                "date_min": merged["date"].min(),
                "date_max": merged["date"].max(),
                "winner_rows": int(len(w)),
                "c060_rows": int(len(c)),
                "cdi_rows": int(len(cdi)),
                "ibov_rows": int(len(ibov)),
            },
        )
        acid_rows = int(len(w[(w["split"] == "HOLDOUT") & (w["date"] >= ACID_START) & (w["date"] <= ACID_END)]))
        write_json(
            OUT_ACID_DEF,
            {
                "acid_start": ACID_START,
                "acid_end": ACID_END,
                "expected_holdout_rows": 268,
                "observed_rows_phase8_winner": acid_rows,
            },
        )
        gates.append(
            Gate(
                "G_ACID_WINDOW_HOLDOUT_OK",
                acid_rows == 268,
                f"acid_rows={acid_rows}",
            )
        )

        ch_ok = append_changelog_one_line_idempotent(TRACEABILITY_LINE)
        gates.append(Gate("G_CHLOG_UPDATED", ch_ok, f"path={CHANGELOG_PATH}"))

        # First report write (before hash gates).
        overall_pre = all(g.passed for g in gates)
        OUT_REPORT.write_text(
            render_report(
                gates,
                retry_log,
                overall_pre,
                metrics_snapshot=metrics_snapshot,
                join_coverage={
                    "common_dates": int(len(merged)),
                    "date_min": merged["date"].min().strftime("%Y-%m-%d"),
                    "date_max": merged["date"].max().strftime("%Y-%m-%d"),
                    "winner_rows": int(len(w)),
                    "c060_rows": int(len(c)),
                    "cdi_rows": int(len(cdi)),
                    "ibov_rows": int(len(ibov)),
                },
            ),
            encoding="utf-8",
        )

        outputs = [OUT_SCRIPT, OUT_HTML, OUT_REPORT, OUT_METRICS, OUT_PLOT_INV, OUT_JOIN_COVERAGE, OUT_ACID_DEF, CHANGELOG_PATH]
        hashes = {str(p.relative_to(ROOT)): sha256_file(p) for p in outputs}
        manifest = {
            "task_id": TASK_ID,
            "run_id": RUN_ID,
            "manifest_policy": "no_self_hash",
            "inputs_consumed": [str(p.relative_to(ROOT)) for p in inputs],
            "outputs_produced": [
                str(OUT_HTML.relative_to(ROOT)),
                str(OUT_REPORT.relative_to(ROOT)),
                str(OUT_MANIFEST.relative_to(ROOT)),
                str(OUT_METRICS.relative_to(ROOT)),
                str(OUT_PLOT_INV.relative_to(ROOT)),
                str(OUT_JOIN_COVERAGE.relative_to(ROOT)),
                str(OUT_ACID_DEF.relative_to(ROOT)),
            ],
            "hashes_sha256": hashes,
        }
        write_json(OUT_MANIFEST, manifest)
        gates.append(Gate("Gx_HASH_MANIFEST_PRESENT", OUT_MANIFEST.exists(), f"path={OUT_MANIFEST}"))

        mismatches = []
        for rel, expected in manifest["hashes_sha256"].items():
            got = sha256_file(ROOT / rel)
            if got != expected:
                mismatches.append(rel)
        hash_ok = len(mismatches) == 0
        gates.append(Gate("G_SHA256_INTEGRITY_SELF_CHECK", hash_ok, f"mismatches={len(mismatches)}"))

        # Final report + final manifest with final report hash.
        overall = all(g.passed for g in gates)
        OUT_REPORT.write_text(
            render_report(
                gates,
                retry_log,
                overall,
                metrics_snapshot=metrics_snapshot,
                join_coverage={
                    "common_dates": int(len(merged)),
                    "date_min": merged["date"].min().strftime("%Y-%m-%d"),
                    "date_max": merged["date"].max().strftime("%Y-%m-%d"),
                    "winner_rows": int(len(w)),
                    "c060_rows": int(len(c)),
                    "cdi_rows": int(len(cdi)),
                    "ibov_rows": int(len(ibov)),
                },
            ),
            encoding="utf-8",
        )
        final_hashes = {str(p.relative_to(ROOT)): sha256_file(p) for p in outputs}
        manifest["hashes_sha256"] = final_hashes
        write_json(OUT_MANIFEST, manifest)

        print(f"HEADER: {TASK_ID}")
        print("STEP GATES:")
        for g in gates:
            print(f"- {g.name}: {'PASS' if g.passed else 'FAIL'} | {g.detail}")
        print("RETRY LOG:")
        print("- none" if not retry_log else "\n".join(f"- {r}" for r in retry_log))
        print("ARTIFACT LINKS:")
        print(f"- {OUT_HTML}")
        print(f"- {OUT_REPORT}")
        print(f"- {OUT_MANIFEST}")
        print(f"- {OUT_METRICS}")
        print(f"- {OUT_PLOT_INV}")
        print(f"- {OUT_JOIN_COVERAGE}")
        print(f"- {OUT_ACID_DEF}")
        print(f"OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]")
        return 0 if overall else 2
    except Exception as exc:
        retry_log.append(f"FATAL: {type(exc).__name__}: {exc}")
        gates.append(Gate("G_FATAL", False, f"{type(exc).__name__}: {exc}"))
        OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"# HEADER: {TASK_ID}", "", "## STEP GATES"]
        for g in gates:
            lines.append(f"- {g.name}: {'PASS' if g.passed else 'FAIL'} | {g.detail}")
        lines.extend(["", "## RETRY LOG"])
        for r in retry_log:
            lines.append(f"- {r}")
        lines.extend(["", "## OVERALL STATUS: [[ FAIL ]]", ""])
        OUT_REPORT.write_text("\n".join(lines), encoding="utf-8")
        print(f"HEADER: {TASK_ID}")
        print("STEP GATES:")
        for g in gates:
            print(f"- {g.name}: {'PASS' if g.passed else 'FAIL'} | {g.detail}")
        print("RETRY LOG:")
        for r in retry_log:
            print(f"- {r}")
        print("ARTIFACT LINKS:")
        print(f"- {OUT_REPORT}")
        print("OVERALL STATUS: [[ FAIL ]]")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
