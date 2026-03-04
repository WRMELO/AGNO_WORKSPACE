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


TASK_ID = "T127"
RUN_ID = "T127-US-WINNER-COMPARATIVE-V1"
ROOT = Path("/home/wilson/AGNO_WORKSPACE")
PYTHON_ENV = ROOT / ".venv/bin/python"
CHANGELOG_PATH = ROOT / "00_Strategy/changelog.md"

IN_T122_CURVE = ROOT / "src/data_engine/portfolio/T122_US_ENGINE_WINNER_CURVE_DAILY.parquet"
IN_T122_CFG = ROOT / "src/data_engine/portfolio/T122_SELECTED_CONFIG_US_ENGINE_NPOS_CADENCE.json"
IN_T126_CURVE = ROOT / "src/data_engine/portfolio/T126_US_ENGINE_V2_TRIGGER_CURVE_DAILY.parquet"
IN_T126_SUMMARY = ROOT / "src/data_engine/portfolio/T126_US_ENGINE_V2_TRIGGER_SUMMARY.json"
IN_T115_CURVE = ROOT / "src/data_engine/portfolio/T115_US_FACTORY_CURVE_DAILY.parquet"

OUT_SCRIPT = ROOT / "scripts/t127_us_winner_declaration_and_comparative_plot_v1.py"
OUT_DECLARATION = ROOT / "src/data_engine/portfolio/T127_US_WINNER_DECLARATION.json"
OUT_PLOT = ROOT / "outputs/plots/T127_STATE3_PHASE10D_US_WINNER_COMPARATIVE.html"
OUT_REPORT = ROOT / "outputs/governanca/T127-US-WINNER-COMPARATIVE-V1_report.md"
OUT_MANIFEST = ROOT / "outputs/governanca/T127-US-WINNER-COMPARATIVE-V1_manifest.json"
OUT_EVID = ROOT / "outputs/governanca/T127-US-WINNER-COMPARATIVE-V1_evidence"
OUT_METRICS = OUT_EVID / "metrics_table.json"
OUT_INPUTS = OUT_EVID / "inputs_snapshot.json"

ACID_US_START = pd.Timestamp("2025-03-06")
ACID_US_END = pd.Timestamp("2025-05-09")

TRACEABILITY_LINE = "- 2026-03-04T20:54:52Z | EXEC: T127 PASS. US Winner Declaration + Comparative Plot (T122 winner; T126 trigger abandonado como baseline informativo). Artefatos: scripts/t127_us_winner_declaration_and_comparative_plot_v1.py; src/data_engine/portfolio/T127_US_WINNER_DECLARATION.json; outputs/plots/T127_STATE3_PHASE10D_US_WINNER_COMPARATIVE.html; outputs/governanca/T127-US-WINNER-COMPARATIVE-V1_{report,manifest}.json"


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


def split_metrics(df: pd.DataFrame, eq_col: str) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for split_name, mask in {
        "train": (df["split"].astype(str).str.upper() == "TRAIN"),
        "holdout": (df["split"].astype(str).str.upper() == "HOLDOUT"),
        "acid_us": ((df["date"] >= ACID_US_START) & (df["date"] <= ACID_US_END)),
    }.items():
        sub = df.loc[mask, ["date", eq_col]].copy().dropna(subset=[eq_col]).sort_values("date")
        if len(sub) == 0:
            out[split_name] = {"rows": 0.0, "equity_end": None, "cagr": 0.0, "mdd": 0.0, "sharpe": 0.0}
            continue
        eq = pd.to_numeric(sub[eq_col], errors="coerce").ffill().dropna()
        ret = eq.pct_change().fillna(0.0)
        out[split_name] = {
            "rows": float(len(eq)),
            "equity_end": float(eq.iloc[-1]),
            "cagr": compute_cagr(eq),
            "mdd": compute_mdd(eq),
            "sharpe": compute_sharpe(ret),
        }
    return out


def snapshot(path: Path, optional: bool = False) -> dict[str, Any]:
    info: dict[str, Any] = {"path": str(path.relative_to(ROOT)), "exists": path.exists(), "optional": optional}
    if not path.exists():
        return info
    try:
        if path.suffix == ".parquet":
            df = pd.read_parquet(path)
            info["rows"] = int(len(df))
            info["columns"] = [str(c) for c in df.columns]
        elif path.suffix == ".json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                info["keys"] = sorted([str(k) for k in payload.keys()])
            else:
                info["type"] = type(payload).__name__
    except Exception as e:
        info["read_error"] = f"{type(e).__name__}: {e}"
    return info


def make_report(gates: list[Gate], retry_log: list[str], artifacts: list[Path], status_txt: str) -> str:
    lines = [f"# HEADER: {TASK_ID}", "", "## STEP GATES"]
    lines.extend([f"- {'PASS' if g.passed else 'FAIL'} | {g.name} | {g.detail}" for g in gates])
    lines.extend(["", "## RETRY LOG"])
    lines.extend(["- none"] if not retry_log else [f"- {x}" for x in retry_log])
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

    artifacts = [
        OUT_SCRIPT,
        OUT_DECLARATION,
        OUT_PLOT,
        OUT_REPORT,
        OUT_MANIFEST,
        OUT_METRICS,
        OUT_INPUTS,
    ]
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

        required_inputs = [IN_T122_CURVE, IN_T122_CFG, IN_T126_CURVE, IN_T126_SUMMARY, CHANGELOG_PATH]
        inputs_present = all(p.exists() for p in required_inputs)
        gates.append(Gate("G_INPUTS_PRESENT", inputs_present, f"required={len(required_inputs)}"))
        if not inputs_present:
            raise RuntimeError("required inputs missing for T127")

        t122 = pd.read_parquet(IN_T122_CURVE).copy()
        t126 = pd.read_parquet(IN_T126_CURVE).copy()
        for df in (t122, t126):
            df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
            df["split"] = df["split"].astype(str).str.upper().str.strip()
        t122 = t122.sort_values("date").reset_index(drop=True)
        t126 = t126.sort_values("date").reset_index(drop=True)

        cols_ok = {"date", "split", "equity_strategy", "equity_sp500_bh", "equity_cash_fedfunds"}.issubset(set(t122.columns))
        cols_ok = cols_ok and {"date", "split", "equity_strategy", "state_cash"}.issubset(set(t126.columns))
        gates.append(Gate("G_INPUT_SCHEMA_OK", cols_ok, "T122/T126 required columns"))
        if not cols_ok:
            raise RuntimeError("input schema mismatch")

        cfg122 = json.loads(IN_T122_CFG.read_text(encoding="utf-8"))
        top_n = int(cfg122.get("winner_top_n", 5))
        cadence_days = int(cfg122.get("winner_cadence_days", 10))
        cost_rate = float(cfg122.get("config_fixed", {}).get("cost_rate_one_way", 0.0001))

        t126_summary = json.loads(IN_T126_SUMMARY.read_text(encoding="utf-8"))
        t126_cfg = t126_summary.get("config", {})

        comp = t122[["date", "split", "equity_strategy", "equity_sp500_bh", "equity_cash_fedfunds"]].copy()
        comp = comp.rename(
            columns={
                "equity_strategy": "eq_t122_winner",
                "equity_sp500_bh": "eq_sp500_bh",
                "equity_cash_fedfunds": "eq_cash_fedfunds",
            }
        )
        comp = comp.merge(
            t126[["date", "equity_strategy", "state_cash"]].rename(
                columns={"equity_strategy": "eq_t126_informativo", "state_cash": "state_cash_t126"}
            ),
            on="date",
            how="left",
        )

        has_t115 = IN_T115_CURVE.exists()
        if has_t115:
            t115 = pd.read_parquet(IN_T115_CURVE).copy()
            t115["date"] = pd.to_datetime(t115["date"], errors="coerce").dt.normalize()
            if "equity" in t115.columns:
                t115_eq_col = "equity"
            elif "equity_strategy" in t115.columns:
                t115_eq_col = "equity_strategy"
            else:
                t115_eq_col = ""
            if t115_eq_col:
                comp = comp.merge(
                    t115[["date", t115_eq_col]].rename(columns={t115_eq_col: "eq_t115_ref"}),
                    on="date",
                    how="left",
                )
            else:
                has_t115 = False

        join_ok = len(comp) == len(t122) and int(comp["eq_t126_informativo"].isna().sum()) == 0
        gates.append(
            Gate(
                "G_JOIN_COVERAGE",
                join_ok,
                f"rows={len(comp)} t122_rows={len(t122)} t126_na={int(comp['eq_t126_informativo'].isna().sum())}",
            )
        )
        if not join_ok:
            raise RuntimeError("join coverage failed against T126")

        declaration = {
            "task_id": TASK_ID,
            "run_id": RUN_ID,
            "winner_task_id": "T122",
            "winner_label": "US Winner (T122 pure engine)",
            "winner_config": {
                "top_n": top_n,
                "cadence_days": cadence_days,
                "cost_rate_one_way": cost_rate,
            },
            "decision_reference": {
                "owner_decision": "Após discussão da auditoria de T126, Owner definiu abandono do trigger e adoção de T122 como winner americana.",
                "decision_date_utc": "2026-03-04T20:54:52Z",
            },
            "trigger_rejected": {
                "task_id": "T126",
                "component": "ML trigger",
                "decision": "abandoned",
                "rationale": "ganho marginal em HOLDOUT vs complexidade operacional significativamente maior",
                "t126_config_snapshot": {
                    "threshold": t126_cfg.get("trigger_threshold"),
                    "h_in": t126_cfg.get("h_in"),
                    "h_out": t126_cfg.get("h_out"),
                },
            },
            "status_note": "T126 mantido somente como baseline informativo para rastreabilidade.",
        }
        write_json(OUT_DECLARATION, declaration)

        strategy_cols = {
            "T122 Winner": "eq_t122_winner",
            "T126 Informativo": "eq_t126_informativo",
            "SP500 B&H": "eq_sp500_bh",
            "Cash FedFunds": "eq_cash_fedfunds",
        }
        if has_t115 and "eq_t115_ref" in comp.columns:
            strategy_cols["T115 Referencia"] = "eq_t115_ref"

        metrics_table = {
            "task_id": TASK_ID,
            "winner": "T122 Winner",
            "strategies": {},
            "comparative_holdout": {},
        }
        for label, col in strategy_cols.items():
            metrics_table["strategies"][label] = split_metrics(comp, col)
        t122_h = metrics_table["strategies"]["T122 Winner"]["holdout"]
        t126_h = metrics_table["strategies"]["T126 Informativo"]["holdout"]
        metrics_table["comparative_holdout"] = {
            "delta_cagr_t122_minus_t126": float(t122_h["cagr"] - t126_h["cagr"]),
            "delta_mdd_t122_minus_t126": float(t122_h["mdd"] - t126_h["mdd"]),
            "delta_sharpe_t122_minus_t126": float(t122_h["sharpe"] - t126_h["sharpe"]),
        }
        write_json(OUT_METRICS, metrics_table)

        snapshot_payload = {
            "task_id": TASK_ID,
            "required_inputs": [
                snapshot(IN_T122_CURVE),
                snapshot(IN_T122_CFG),
                snapshot(IN_T126_CURVE),
                snapshot(IN_T126_SUMMARY),
            ],
            "optional_inputs": [snapshot(IN_T115_CURVE, optional=True)],
            "curve_rows": int(len(comp)),
            "curve_date_min": str(comp["date"].min().date()),
            "curve_date_max": str(comp["date"].max().date()),
            "curve_columns": [str(c) for c in comp.columns],
        }
        write_json(OUT_INPUTS, snapshot_payload)

        for label, col in strategy_cols.items():
            base = float(comp[col].dropna().iloc[0])
            comp[f"norm_{col}"] = 100.0 * comp[col] / max(base, 1e-12)
            comp[f"dd_{col}"] = comp[col] / comp[col].cummax() - 1.0

        fig = make_subplots(
            rows=2,
            cols=2,
            subplot_titles=(
                "Equity Normalizado (Winner vs Baselines)",
                "Drawdown Comparativo",
                "Estado de Caixa do T126 (informativo)",
                "Métricas HOLDOUT (CAGR, MDD, Sharpe)",
            ),
            specs=[[{"type": "xy"}, {"type": "xy"}], [{"type": "xy"}, {"type": "table"}]],
            horizontal_spacing=0.08,
            vertical_spacing=0.12,
        )

        color_map = {
            "T122 Winner": "#00cc96",
            "T126 Informativo": "#636efa",
            "SP500 B&H": "#ef553b",
            "Cash FedFunds": "#ab63fa",
            "T115 Referencia": "#19d3f3",
        }
        for label, col in strategy_cols.items():
            fig.add_trace(
                go.Scatter(x=comp["date"], y=comp[f"norm_{col}"], mode="lines", name=label, line=dict(color=color_map.get(label))),
                row=1,
                col=1,
            )
        for label, col in strategy_cols.items():
            fig.add_trace(
                go.Scatter(
                    x=comp["date"],
                    y=comp[f"dd_{col}"],
                    mode="lines",
                    name=f"DD {label}",
                    showlegend=False,
                    line=dict(color=color_map.get(label)),
                ),
                row=1,
                col=2,
            )

        fig.add_trace(
            go.Scatter(x=comp["date"], y=comp["state_cash_t126"], mode="lines", name="state_cash T126", line=dict(color="#a6d854")),
            row=2,
            col=1,
        )

        rows_table = ["T122 Winner", "T126 Informativo", "SP500 B&H", "Cash FedFunds"] + (["T115 Referencia"] if "T115 Referencia" in strategy_cols else [])
        cagr_vals = [metrics_table["strategies"][k]["holdout"]["cagr"] for k in rows_table]
        mdd_vals = [metrics_table["strategies"][k]["holdout"]["mdd"] for k in rows_table]
        sharpe_vals = [metrics_table["strategies"][k]["holdout"]["sharpe"] for k in rows_table]
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
            height=950,
            width=1500,
            title=f"{RUN_ID} - Winner Declaration (T122 Winner, T126 Informativo)",
            legend=dict(orientation="h"),
        )
        fig.add_annotation(
            xref="paper",
            yref="paper",
            x=0.01,
            y=1.10,
            showarrow=False,
            text="Decisão do Owner: T122 declarado winner. T126 mantido apenas como baseline informativo (trigger abandonado).",
        )
        fig.write_html(OUT_PLOT, include_plotlyjs="cdn")

        outputs_ok = all(p.exists() for p in [OUT_DECLARATION, OUT_PLOT, OUT_METRICS, OUT_INPUTS])
        gates.append(Gate("G_OUTPUTS_PRESENT", outputs_ok, "declaration + html + evidences"))

        ch_ok = append_changelog_one_line_idempotent(TRACEABILITY_LINE)
        gates.append(Gate("G_CHLOG_UPDATED", ch_ok, "mode=idempotent"))

        inputs_consumed = [
            str(IN_T122_CURVE.relative_to(ROOT)),
            str(IN_T122_CFG.relative_to(ROOT)),
            str(IN_T126_CURVE.relative_to(ROOT)),
            str(IN_T126_SUMMARY.relative_to(ROOT)),
            str(CHANGELOG_PATH.relative_to(ROOT)),
        ]
        if IN_T115_CURVE.exists():
            inputs_consumed.append(str(IN_T115_CURVE.relative_to(ROOT)))

        outputs_produced = [
            str(OUT_SCRIPT.relative_to(ROOT)),
            str(OUT_DECLARATION.relative_to(ROOT)),
            str(OUT_PLOT.relative_to(ROOT)),
            str(OUT_REPORT.relative_to(ROOT)),
            str(OUT_METRICS.relative_to(ROOT)),
            str(OUT_INPUTS.relative_to(ROOT)),
        ]

        provisional = gates + [
            Gate("Gx_HASH_MANIFEST_PRESENT", True, f"path={OUT_MANIFEST.relative_to(ROOT)}"),
            Gate("G_SHA256_INTEGRITY_SELF_CHECK", True, "mismatches=0 (provisional)"),
        ]
        if any(not g.passed for g in provisional):
            overall_pass = False
        status = "PASS" if overall_pass else "FAIL"
        OUT_REPORT.write_text(make_report(provisional, retry_log, artifacts, status), encoding="utf-8")

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
        status = "PASS" if overall_pass else "FAIL"
        OUT_REPORT.write_text(make_report(gates, retry_log, artifacts, status), encoding="utf-8")

        # refresh manifest hash map after final report write
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
