#!/home/wilson/AGNO_WORKSPACE/.venv/bin/python
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


TASK_ID = "T128"
RUN_ID = "T128-BR-US-BRL-DASHBOARD-V1"
ROOT = Path("/home/wilson/AGNO_WORKSPACE")
PYTHON_ENV = ROOT / ".venv/bin/python"
CHANGELOG_PATH = ROOT / "00_Strategy/changelog.md"

IN_BR_WINNER = ROOT / "src/data_engine/portfolio/T108_PORTFOLIO_CURVE_DUAL_MODE_EXPANDED_WINNER.parquet"
IN_US_WINNER = ROOT / "src/data_engine/portfolio/T122_US_ENGINE_WINNER_CURVE_DAILY.parquet"
IN_FX = ROOT / "src/data_engine/ssot/SSOT_FX_PTAX_USDBRL.parquet"
IN_DECL = ROOT / "src/data_engine/portfolio/T127_US_WINNER_DECLARATION.json"

OUT_SCRIPT = ROOT / "scripts/t128_dashboard_br_us_brl_v1.py"
OUT_PLOT = ROOT / "outputs/plots/T128_STATE3_PHASE10E_BR_US_BRL_DASHBOARD.html"
OUT_REPORT = ROOT / "outputs/governanca/T128-BR-US-BRL-DASHBOARD-V1_report.md"
OUT_MANIFEST = ROOT / "outputs/governanca/T128-BR-US-BRL-DASHBOARD-V1_manifest.json"
OUT_EVID = ROOT / "outputs/governanca/T128-BR-US-BRL-DASHBOARD-V1_evidence"
OUT_INPUTS = OUT_EVID / "inputs_snapshot.json"
OUT_FX_COVER = OUT_EVID / "fx_join_coverage.json"
OUT_METRICS = OUT_EVID / "metrics_table.json"

TRAIN_END = pd.Timestamp("2022-12-30")
HOLDOUT_START = pd.Timestamp("2023-01-02")
ACID_US_START = pd.Timestamp("2025-03-06")
ACID_US_END = pd.Timestamp("2025-05-09")
INITIAL_CAPITAL = 100000.0

TRACEABILITY_LINE = "- 2026-03-04T21:16:16Z | EXEC: T128 PASS. Dashboard BR+US em BRL (visual apenas, sem split; BR winner + US winner convertido por PTAX). Artefatos: scripts/t128_dashboard_br_us_brl_v1.py; outputs/plots/T128_STATE3_PHASE10E_BR_US_BRL_DASHBOARD.html; outputs/governanca/T128-BR-US-BRL-DASHBOARD-V1_{report,manifest}.json"


@dataclass
class Gate:
    name: str
    passed: bool
    detail: str


def _json_safe(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, (np.floating, float)):
        x = float(obj)
        return x if np.isfinite(x) else None
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
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def append_changelog_one_line_idempotent(line: str) -> bool:
    if not CHANGELOG_PATH.exists():
        return False
    existing = CHANGELOG_PATH.read_text(encoding="utf-8")
    if line in existing:
        return True
    txt = existing
    if txt and not txt.endswith("\n"):
        txt += "\n"
    txt += line + "\n"
    CHANGELOG_PATH.write_text(txt, encoding="utf-8")
    return line in CHANGELOG_PATH.read_text(encoding="utf-8")


def compute_mdd(equity: pd.Series) -> float:
    eq = pd.to_numeric(equity, errors="coerce").ffill().dropna().to_numpy(dtype=float)
    if len(eq) == 0:
        return 0.0
    peak = np.maximum.accumulate(eq)
    dd = eq / np.maximum(peak, 1e-12) - 1.0
    return float(np.min(dd))


def compute_sharpe(ret_1d: pd.Series) -> float:
    r = pd.to_numeric(ret_1d, errors="coerce").fillna(0.0).to_numpy(dtype=float)
    if len(r) < 2:
        return 0.0
    sd = float(np.std(r, ddof=1))
    if sd <= 0:
        return 0.0
    return float(np.mean(r) / sd * np.sqrt(252.0))


def compute_cagr(equity: pd.Series) -> float:
    eq = pd.to_numeric(equity, errors="coerce").ffill().dropna().to_numpy(dtype=float)
    if len(eq) < 2 or eq[0] <= 0:
        return 0.0
    years = len(eq) / 252.0
    if years <= 0:
        return 0.0
    return float((eq[-1] / eq[0]) ** (1.0 / years) - 1.0)


def split_metrics(df: pd.DataFrame, equity_col: str) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    masks = {
        "train": (df["split"] == "TRAIN"),
        "holdout": (df["split"] == "HOLDOUT"),
        "acid_us": ((df["date"] >= ACID_US_START) & (df["date"] <= ACID_US_END)),
    }
    for split_name, mask in masks.items():
        sub = df.loc[mask, ["date", equity_col]].copy().dropna(subset=[equity_col]).sort_values("date")
        if len(sub) == 0:
            out[split_name] = {"rows": 0.0, "equity_end": None, "cagr": 0.0, "mdd": 0.0, "sharpe": 0.0}
            continue
        eq = pd.to_numeric(sub[equity_col], errors="coerce").ffill().dropna()
        ret = eq.pct_change().fillna(0.0)
        out[split_name] = {
            "rows": float(len(eq)),
            "equity_end": float(eq.iloc[-1]),
            "cagr": compute_cagr(eq),
            "mdd": compute_mdd(eq),
            "sharpe": compute_sharpe(ret),
        }
    return out


def snapshot(path: Path) -> dict[str, Any]:
    info: dict[str, Any] = {"path": str(path.relative_to(ROOT)), "exists": path.exists()}
    if not path.exists():
        return info
    try:
        if path.suffix == ".parquet":
            df = pd.read_parquet(path)
            info["rows"] = int(len(df))
            info["columns"] = [str(c) for c in df.columns]
            if "date" in df.columns:
                dt = pd.to_datetime(df["date"], errors="coerce").dropna()
                if len(dt):
                    info["date_min"] = str(dt.min().date())
                    info["date_max"] = str(dt.max().date())
        elif path.suffix == ".json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            info["keys"] = sorted([str(k) for k in payload.keys()]) if isinstance(payload, dict) else [type(payload).__name__]
    except Exception as e:
        info["read_error"] = f"{type(e).__name__}: {e}"
    return info


def make_report(gates: list[Gate], retry_log: list[str], artifacts: list[Path], status_txt: str) -> str:
    lines: list[str] = [f"# HEADER: {TASK_ID}", "", "## STEP GATES"]
    for g in gates:
        lines.append(f"- {'PASS' if g.passed else 'FAIL'} | {g.name} | {g.detail}")
    lines.extend(["", "## RETRY LOG"])
    if retry_log:
        lines.extend([f"- {x}" for x in retry_log])
    else:
        lines.append("- none")
    lines.extend(["", "## ARTIFACT LINKS"])
    for p in artifacts:
        if p.exists():
            lines.append(f"- {p.relative_to(ROOT)}")
    lines.extend(["", f"OVERALL STATUS: [[ {status_txt} ]]", ""])
    return "\n".join(lines)


def main() -> int:
    gates: list[Gate] = []
    retry_log: list[str] = []
    overall_pass = True

    artifacts = [OUT_SCRIPT, OUT_PLOT, OUT_REPORT, OUT_MANIFEST, OUT_INPUTS, OUT_FX_COVER, OUT_METRICS]
    OUT_EVID.mkdir(parents=True, exist_ok=True)
    OUT_PLOT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)

    try:
        in_venv = (".venv" in sys.executable) and (Path(sys.executable).resolve() == PYTHON_ENV.resolve())
        gates.append(Gate("G_ENV_VENV", in_venv, f"python={sys.executable}"))
        if not in_venv:
            raise RuntimeError("FATAL: execute with .venv python")

        dep_ok = True
        try:
            proc = subprocess.run([str(ROOT / ".venv/bin/pip"), "list"], check=True, capture_output=True, text=True)
            txt = proc.stdout.lower()
            for dep in ("pandas", "numpy", "plotly", "pyarrow"):
                if dep not in txt:
                    dep_ok = False
        except Exception as e:
            dep_ok = False
            retry_log.append(f"pip list error: {type(e).__name__}: {e}")
        gates.append(Gate("G_DEPENDENCIES_CHECK", dep_ok, "pip list baseline"))

        required_inputs = [IN_BR_WINNER, IN_US_WINNER, IN_FX, IN_DECL, CHANGELOG_PATH]
        inputs_present = all(p.exists() for p in required_inputs)
        gates.append(Gate("G_INPUTS_PRESENT", inputs_present, f"required={len(required_inputs)}"))
        if not inputs_present:
            raise RuntimeError("required inputs missing for T128")

        br = pd.read_parquet(IN_BR_WINNER).copy()
        us = pd.read_parquet(IN_US_WINNER).copy()
        fx = pd.read_parquet(IN_FX).copy()

        br["date"] = pd.to_datetime(br["date"], errors="coerce").dt.normalize()
        us["date"] = pd.to_datetime(us["date"], errors="coerce").dt.normalize()
        fx["date"] = pd.to_datetime(fx["date"], errors="coerce").dt.normalize()

        schema_ok = {"date", "equity_end", "cdi_daily"}.issubset(set(br.columns))
        schema_ok = schema_ok and {"date", "split", "equity_strategy", "equity_sp500_bh", "equity_cash_fedfunds"}.issubset(set(us.columns))
        schema_ok = schema_ok and {"date", "usdbrl_ptax"}.issubset(set(fx.columns))
        gates.append(Gate("G_INPUT_SCHEMA_OK", schema_ok, "BR/US/FX required columns"))
        if not schema_ok:
            raise RuntimeError("input schema mismatch")

        br = br.sort_values("date").dropna(subset=["date"]).reset_index(drop=True)
        us = us.sort_values("date").dropna(subset=["date"]).reset_index(drop=True)
        fx = fx.sort_values("date").dropna(subset=["date"]).drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)

        dates_common = sorted(set(br["date"]).intersection(set(us["date"])))
        if not dates_common:
            raise RuntimeError("no common dates between BR and US curves")

        br = br[br["date"].isin(dates_common)].copy()
        us = us[us["date"].isin(dates_common)].copy()
        br = br.sort_values("date").reset_index(drop=True)
        us = us.sort_values("date").reset_index(drop=True)

        us_fx = us.merge(fx[["date", "usdbrl_ptax"]], on="date", how="left")
        n_missing_pre = int(us_fx["usdbrl_ptax"].isna().sum())
        us_fx["usdbrl_ptax"] = pd.to_numeric(us_fx["usdbrl_ptax"], errors="coerce").ffill()
        n_missing_post = int(us_fx["usdbrl_ptax"].isna().sum())
        cover_ratio = float(1.0 - n_missing_post / max(len(us_fx), 1))

        join_ok = (len(us_fx) == len(us)) and (n_missing_post == 0)
        gates.append(
            Gate(
                "G_FX_JOIN_COVERAGE",
                join_ok,
                f"rows={len(us_fx)} missing_pre={n_missing_pre} missing_post={n_missing_post} coverage={cover_ratio:.3f}",
            )
        )
        if not join_ok:
            raise RuntimeError("FX join coverage failed after ffill")

        us_fx["equity_us_usd"] = pd.to_numeric(us_fx["equity_strategy"], errors="coerce")
        us_fx["equity_us_brl"] = us_fx["equity_us_usd"] * us_fx["usdbrl_ptax"]
        us_fx["equity_sp500_brl"] = pd.to_numeric(us_fx["equity_sp500_bh"], errors="coerce") * us_fx["usdbrl_ptax"]
        us_fx["equity_cash_us_brl"] = pd.to_numeric(us_fx["equity_cash_fedfunds"], errors="coerce") * us_fx["usdbrl_ptax"]

        br["equity_br_brl"] = pd.to_numeric(br["equity_end"], errors="coerce")
        br["cdi_daily"] = pd.to_numeric(br["cdi_daily"], errors="coerce").fillna(0.0)
        br["equity_cdi_brl"] = INITIAL_CAPITAL * (1.0 + br["cdi_daily"]).cumprod()

        panel = br[["date", "equity_br_brl", "equity_cdi_brl"]].merge(
            us_fx[["date", "split", "equity_us_usd", "equity_us_brl", "equity_sp500_brl", "equity_cash_us_brl"]],
            on="date",
            how="inner",
        )
        panel = panel.sort_values("date").reset_index(drop=True)

        panel["split"] = panel["split"].astype(str).str.upper().str.strip()
        panel.loc[panel["split"] == "", "split"] = np.where(panel["date"] <= TRAIN_END, "TRAIN", "HOLDOUT")
        panel.loc[~panel["split"].isin(["TRAIN", "HOLDOUT"]), "split"] = np.where(panel["date"] <= TRAIN_END, "TRAIN", "HOLDOUT")

        write_json(
            OUT_FX_COVER,
            {
                "task_id": TASK_ID,
                "rows_total": int(len(us_fx)),
                "rows_fx_missing_pre_ffill": n_missing_pre,
                "rows_fx_missing_post_ffill": n_missing_post,
                "coverage_ratio_post_ffill": cover_ratio,
                "date_min": str(panel["date"].min().date()),
                "date_max": str(panel["date"].max().date()),
            },
        )

        metrics = {
            "task_id": TASK_ID,
            "series": {
                "BR_Winner_BRL": split_metrics(panel, "equity_br_brl"),
                "US_Winner_USD": split_metrics(panel, "equity_us_usd"),
                "US_Winner_BRL": split_metrics(panel, "equity_us_brl"),
                "SP500_BRL": split_metrics(panel, "equity_sp500_brl"),
                "CDI_BRL": split_metrics(panel, "equity_cdi_brl"),
            },
        }
        write_json(OUT_METRICS, metrics)

        write_json(
            OUT_INPUTS,
            {
                "task_id": TASK_ID,
                "inputs": [snapshot(IN_BR_WINNER), snapshot(IN_US_WINNER), snapshot(IN_FX), snapshot(IN_DECL)],
                "panel_rows": int(len(panel)),
                "panel_columns": [str(c) for c in panel.columns],
                "date_min": str(panel["date"].min().date()),
                "date_max": str(panel["date"].max().date()),
            },
        )

        # normalized curves
        for col in ["equity_br_brl", "equity_us_brl", "equity_sp500_brl", "equity_cdi_brl", "equity_us_usd"]:
            base = float(panel[col].dropna().iloc[0])
            panel[f"norm_{col}"] = 100.0 * panel[col] / max(base, 1e-12)
            panel[f"dd_{col}"] = panel[col] / panel[col].cummax() - 1.0

        hold = metrics["series"]
        rows_table = ["BR_Winner_BRL", "US_Winner_USD", "US_Winner_BRL", "SP500_BRL", "CDI_BRL"]
        cagr_vals = [hold[r]["holdout"]["cagr"] for r in rows_table]
        mdd_vals = [hold[r]["holdout"]["mdd"] for r in rows_table]
        sharpe_vals = [hold[r]["holdout"]["sharpe"] for r in rows_table]

        fig = make_subplots(
            rows=2,
            cols=2,
            subplot_titles=(
                "Equity Normalizada em BRL (BR winner vs US winner convertido vs SP500 convertido vs CDI)",
                "Equity Normalizada em Moeda Original (BRL vs USD)",
                "Drawdown Comparativo (BRL)",
                "Métricas HOLDOUT",
            ),
            specs=[[{"type": "xy"}, {"type": "xy"}], [{"type": "xy"}, {"type": "table"}]],
            horizontal_spacing=0.08,
            vertical_spacing=0.12,
        )

        fig.add_trace(go.Scatter(x=panel["date"], y=panel["norm_equity_br_brl"], mode="lines", name="BR Winner (BRL)"), row=1, col=1)
        fig.add_trace(go.Scatter(x=panel["date"], y=panel["norm_equity_us_brl"], mode="lines", name="US Winner em BRL"), row=1, col=1)
        fig.add_trace(go.Scatter(x=panel["date"], y=panel["norm_equity_sp500_brl"], mode="lines", name="SP500 em BRL"), row=1, col=1)
        fig.add_trace(go.Scatter(x=panel["date"], y=panel["norm_equity_cdi_brl"], mode="lines", name="CDI em BRL"), row=1, col=1)

        fig.add_trace(go.Scatter(x=panel["date"], y=panel["norm_equity_br_brl"], mode="lines", name="BR Winner BRL", showlegend=False), row=1, col=2)
        fig.add_trace(go.Scatter(x=panel["date"], y=panel["norm_equity_us_usd"], mode="lines", name="US Winner USD", showlegend=False), row=1, col=2)

        fig.add_trace(go.Scatter(x=panel["date"], y=panel["dd_equity_br_brl"], mode="lines", name="DD BR Winner", showlegend=False), row=2, col=1)
        fig.add_trace(go.Scatter(x=panel["date"], y=panel["dd_equity_us_brl"], mode="lines", name="DD US Winner BRL", showlegend=False), row=2, col=1)
        fig.add_trace(go.Scatter(x=panel["date"], y=panel["dd_equity_sp500_brl"], mode="lines", name="DD SP500 BRL", showlegend=False), row=2, col=1)
        fig.add_trace(go.Scatter(x=panel["date"], y=panel["dd_equity_cdi_brl"], mode="lines", name="DD CDI BRL", showlegend=False), row=2, col=1)

        fig.add_trace(
            go.Table(
                header=dict(values=["Série", "CAGR HOLDOUT", "MDD HOLDOUT", "Sharpe HOLDOUT"]),
                cells=dict(
                    values=[
                        rows_table,
                        [f"{v:.2%}" for v in cagr_vals],
                        [f"{v:.2%}" for v in mdd_vals],
                        [f"{v:.3f}" for v in sharpe_vals],
                    ]
                ),
            ),
            row=2,
            col=2,
        )

        fig.update_layout(
            height=980,
            width=1520,
            title=f"{RUN_ID} - Dashboard BR+US em BRL (visualização apenas, sem split)",
            legend=dict(orientation="h"),
        )
        fig.add_annotation(
            xref="paper",
            yref="paper",
            x=0.01,
            y=1.11,
            showarrow=False,
            text="Fábricas independentes, capital próprio, sem split. Painel é somente visual/financeiro em BRL.",
        )
        fig.write_html(OUT_PLOT, include_plotlyjs="cdn")

        outputs_ok = all(p.exists() for p in [OUT_PLOT, OUT_INPUTS, OUT_FX_COVER, OUT_METRICS])
        gates.append(Gate("G_OUTPUTS_PRESENT", outputs_ok, "html + evidences"))

        ch_ok = append_changelog_one_line_idempotent(TRACEABILITY_LINE)
        gates.append(Gate("G_CHLOG_UPDATED", ch_ok, "mode=idempotent"))

        inputs_consumed = [
            str(IN_BR_WINNER.relative_to(ROOT)),
            str(IN_US_WINNER.relative_to(ROOT)),
            str(IN_FX.relative_to(ROOT)),
            str(IN_DECL.relative_to(ROOT)),
            str(CHANGELOG_PATH.relative_to(ROOT)),
        ]
        outputs_produced = [
            str(OUT_SCRIPT.relative_to(ROOT)),
            str(OUT_PLOT.relative_to(ROOT)),
            str(OUT_REPORT.relative_to(ROOT)),
            str(OUT_INPUTS.relative_to(ROOT)),
            str(OUT_FX_COVER.relative_to(ROOT)),
            str(OUT_METRICS.relative_to(ROOT)),
        ]

        provisional = gates + [
            Gate("Gx_HASH_MANIFEST_PRESENT", True, f"path={OUT_MANIFEST.relative_to(ROOT)}"),
            Gate("G_SHA256_INTEGRITY_SELF_CHECK", True, "mismatches=0 (provisional)"),
        ]
        if any(not g.passed for g in provisional):
            overall_pass = False
        status_txt = "PASS" if overall_pass else "FAIL"
        OUT_REPORT.write_text(make_report(provisional, retry_log, artifacts, status_txt), encoding="utf-8")

        hash_targets = [CHANGELOG_PATH] + [ROOT / p for p in outputs_produced]
        hashes: dict[str, str] = {}
        for p in hash_targets:
            if p.exists():
                hashes[str(p.relative_to(ROOT))] = sha256_file(p)
        manifest = {
            "task_id": TASK_ID,
            "run_id": RUN_ID,
            "policy": "no_self_hash",
            "generated_at_utc": pd.Timestamp.now("UTC").isoformat(),
            "inputs_consumed": inputs_consumed,
            "outputs_produced": outputs_produced,
            "hashes_sha256": hashes,
        }
        write_json(OUT_MANIFEST, manifest)

        mismatches = 0
        for rel, hv in hashes.items():
            p = ROOT / rel
            if (not p.exists()) or (sha256_file(p) != hv):
                mismatches += 1
        gates.append(Gate("Gx_HASH_MANIFEST_PRESENT", OUT_MANIFEST.exists(), f"path={OUT_MANIFEST.relative_to(ROOT)}"))
        gates.append(Gate("G_SHA256_INTEGRITY_SELF_CHECK", mismatches == 0, f"mismatches={mismatches}"))
        if any(not g.passed for g in gates):
            overall_pass = False
        status_txt = "PASS" if overall_pass else "FAIL"
        OUT_REPORT.write_text(make_report(gates, retry_log, artifacts, status_txt), encoding="utf-8")

        hashes[str(OUT_REPORT.relative_to(ROOT))] = sha256_file(OUT_REPORT)
        manifest["hashes_sha256"] = hashes
        manifest["generated_at_utc"] = pd.Timestamp.now("UTC").isoformat()
        write_json(OUT_MANIFEST, manifest)

    except Exception as e:
        overall_pass = False
        retry_log.append(f"{type(e).__name__}: {e}")
        gates.append(Gate("G_FATAL", False, retry_log[-1]))
        OUT_REPORT.write_text(make_report(gates, retry_log, artifacts, "FAIL"), encoding="utf-8")

    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
