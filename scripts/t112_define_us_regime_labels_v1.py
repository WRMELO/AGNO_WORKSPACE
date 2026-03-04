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


TASK_ID = "T112"
RUN_ID = "T112-PHASE9A-US-LABELS-V1"
ROOT = Path("/home/wilson/AGNO_WORKSPACE")
CHANGELOG_PATH = ROOT / "00_Strategy/changelog.md"
PYTHON_ENV = ROOT / ".venv/bin/python"
TRACEABILITY_LINE = (
    "- 2026-03-04T00:00:00Z | PHASE9: T112 Definir labels de regime US (oracle drawdown S&P 500) "
    "com ablação (janela×threshold) e seleção TRAIN-only. Artefatos: scripts/t112_define_us_regime_labels_v1.py; "
    "src/data_engine/features/T112_US_LABELS_DAILY.parquet; outputs/plots/T112_STATE3_PHASE9A_US_LABELS_EDA.html"
)

IN_MACRO = ROOT / "src/data_engine/ssot/SSOT_MACRO_EXPANDED.parquet"

OUT_SCRIPT = ROOT / "scripts/t112_define_us_regime_labels_v1.py"
OUT_LABELS = ROOT / "src/data_engine/features/T112_US_LABELS_DAILY.parquet"
OUT_HTML = ROOT / "outputs/plots/T112_STATE3_PHASE9A_US_LABELS_EDA.html"
OUT_REPORT = ROOT / "outputs/governanca/T112-PHASE9A-US-LABELS-V1_report.md"
OUT_MANIFEST = ROOT / "outputs/governanca/T112-PHASE9A-US-LABELS-V1_manifest.json"
OUT_EVID_DIR = ROOT / "outputs/governanca/T112-PHASE9A-US-LABELS-V1_evidence"
OUT_CANDIDATES = OUT_EVID_DIR / "label_candidates_summary.json"
OUT_PREFLIGHT = OUT_EVID_DIR / "input_preflight.json"

RECORTE_START = pd.Timestamp("2018-07-02")
RECORTE_END = pd.Timestamp("2026-02-26")
TRAIN_END = pd.Timestamp("2022-12-30")
HOLDOUT_START = pd.Timestamp("2023-01-02")

EXPECTED_TOTAL = 2025
EXPECTED_RECORTE = 1902
EXPECTED_TRAIN = 1115
EXPECTED_HOLDOUT = 787

FWD_WINDOWS = [21, 42, 63]
DD_THRESHOLDS = [0.08, 0.10, 0.12, 0.15]


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


def drawdown_hist(close: pd.Series) -> pd.Series:
    c = pd.to_numeric(close, errors="coerce").astype(float)
    return c / c.cummax() - 1.0


def compute_forward_min_return(close: pd.Series, window: int) -> pd.Series:
    c = pd.to_numeric(close, errors="coerce").astype(float).to_numpy()
    n = len(c)
    out = np.zeros(n, dtype=float)
    for i in range(n):
        j0 = i + 1
        j1 = min(n, i + window + 1)
        if j0 < j1:
            fmin = float(np.min(c[j0:j1]))
        else:
            # Regra determinística para a última linha: sem futuro -> retorno 0.
            fmin = float(c[i])
        out[i] = (fmin / c[i]) - 1.0 if c[i] != 0 else 0.0
    return pd.Series(out, index=close.index)


def count_switches(y: pd.Series) -> int:
    return int((y.astype(int).diff().abs() == 1).sum())


def variant_id(window: int, threshold: float) -> str:
    return f"W{window}_D{int(round(threshold * 100)):02d}"


def render_report(
    gates: list[Gate],
    retry_log: list[str],
    overall: bool,
    selected: dict[str, Any] | None = None,
    preflight: dict[str, Any] | None = None,
) -> str:
    selected = selected or {}
    preflight = preflight or {}
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
            "## RESUMO",
            "- T112 define label de regime US (caixa/mercado) sobre o indice S&P 500 (`sp500_close`) com selecao TRAIN-only.",
            "- Regra semântica: o label e oracle e usa janela futura por design (target supervisionado). Anti-lookahead com `shift(1)` fica para features na T113.",
            f"- Variante selecionada: {selected.get('variant_id', 'n/a')}",
            (
                f"- Parametros selecionados: fwd_window={selected.get('fwd_window', 'n/a')}, "
                f"dd_threshold={selected.get('dd_threshold', 'n/a')}"
            ),
            (
                f"- Metricas TRAIN: cash_frac={selected.get('cash_frac_train', 'n/a')}, "
                f"switches={selected.get('switches_train', 'n/a')}, event_recall={selected.get('event_recall_train', 'n/a')}"
            ),
            "",
            "## PRE-FLIGHT",
            f"- input_exists={preflight.get('input_exists', 'n/a')}",
            f"- columns_ok={preflight.get('columns_ok', 'n/a')}",
            f"- total_rows={preflight.get('total_rows', 'n/a')} (esperado={EXPECTED_TOTAL})",
            (
                f"- recorte_rows={preflight.get('recorte_rows', 'n/a')} (esperado={EXPECTED_RECORTE}), "
                f"train_rows={preflight.get('train_rows', 'n/a')} (esperado={EXPECTED_TRAIN}), "
                f"holdout_rows={preflight.get('holdout_rows', 'n/a')} (esperado={EXPECTED_HOLDOUT})"
            ),
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
            f"- {OUT_LABELS.relative_to(ROOT)}",
            f"- {OUT_HTML.relative_to(ROOT)}",
            f"- {OUT_REPORT.relative_to(ROOT)}",
            f"- {OUT_MANIFEST.relative_to(ROOT)}",
            f"- {OUT_CANDIDATES.relative_to(ROOT)}",
            f"- {OUT_PREFLIGHT.relative_to(ROOT)}",
            "",
            f"## OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]",
            "",
        ]
    )
    return "\n".join(lines)


def build_dashboard(
    df: pd.DataFrame,
    selected_vid: str,
    selected_params: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> None:
    date = df["date"]
    close_norm = 100000.0 * (df["sp500_close"] / float(df["sp500_close"].iloc[0]))
    dd = df["drawdown_hist_peak_to_date"]
    y_sel = df["y_cash_us_v1"].astype(int)

    reps = ["W21_D10", "W21_D15", "W63_D10", "W63_D15"]
    reps_present = [r for r in reps if f"y_{r}" in df.columns]

    fig = make_subplots(
        rows=4,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        specs=[[{"type": "xy"}], [{"type": "xy"}], [{"type": "xy"}], [{"type": "table"}]],
        subplot_titles=(
            "S&P 500 normalizado (base 100k) + shading y_cash selecionado",
            "Drawdown histórico peak-to-date (S&P 500)",
            "Sinais de caixa (variantes representativas)",
            "Resumo da variante selecionada",
        ),
    )

    fig.add_trace(go.Scatter(x=date, y=close_norm, name="S&P 500 norm"), row=1, col=1)
    # shading selected label
    starts = []
    ends = []
    in_seg = False
    start_idx = 0
    arr = y_sel.to_numpy()
    for i, v in enumerate(arr):
        if v == 1 and not in_seg:
            in_seg = True
            start_idx = i
        if v == 0 and in_seg:
            in_seg = False
            starts.append(start_idx)
            ends.append(i - 1)
    if in_seg:
        starts.append(start_idx)
        ends.append(len(arr) - 1)
    for s, e in zip(starts, ends):
        fig.add_vrect(
            x0=date.iloc[s],
            x1=date.iloc[e],
            fillcolor="orange",
            opacity=0.14,
            line_width=0,
            row=1,
            col=1,
        )

    fig.add_trace(go.Scatter(x=date, y=dd, name="DD hist"), row=2, col=1)
    fig.add_hline(y=-0.10, line_dash="dash", line_color="red", row=2, col=1)

    for rid in reps_present:
        fig.add_trace(
            go.Scatter(
                x=date,
                y=df[f"y_{rid}"].astype(int),
                name=rid,
                mode="lines",
                line={"shape": "hv"},
            ),
            row=3,
            col=1,
        )

    sel_row = next((c for c in candidates if c["variant_id"] == selected_vid), {})
    tbl = go.Table(
        header={"values": ["Campo", "Valor"]},
        cells={
            "values": [
                ["variant_id", "fwd_window", "dd_threshold", "cash_frac_train", "cash_frac_holdout", "switches_train", "event_recall_train"],
                [
                    str(sel_row.get("variant_id", "n/a")),
                    str(sel_row.get("fwd_window", "n/a")),
                    str(sel_row.get("dd_threshold", "n/a")),
                    f"{float(sel_row.get('cash_frac_train', np.nan)):.4f}" if sel_row else "n/a",
                    f"{float(sel_row.get('cash_frac_holdout', np.nan)):.4f}" if sel_row else "n/a",
                    str(sel_row.get("switches_train", "n/a")),
                    f"{float(sel_row.get('event_recall_train', np.nan)):.4f}" if sel_row else "n/a",
                ],
            ]
        },
    )
    fig.add_trace(tbl, row=4, col=1)

    fig.update_layout(
        height=1500,
        template="plotly_white",
        title=(
            "T112 - Phase 9A US Labels EDA | "
            f"Selected={selected_vid} (W={selected_params.get('fwd_window')}, D={selected_params.get('dd_threshold')})"
        ),
        legend={"orientation": "h", "y": 1.02, "x": 0.0},
    )
    fig.write_html(str(OUT_HTML), include_plotlyjs="cdn")


def main() -> int:
    gates: list[Gate] = []
    retry_log: list[str] = []
    selected_summary: dict[str, Any] = {}
    preflight_payload: dict[str, Any] = {}
    try:
        for p in [OUT_LABELS, OUT_HTML, OUT_REPORT, OUT_MANIFEST, OUT_CANDIDATES, OUT_PREFLIGHT]:
            p.parent.mkdir(parents=True, exist_ok=True)

        env_ok = PYTHON_ENV.exists() and (".venv" in sys.prefix or "agno_env" in sys.prefix)
        gates.append(Gate("G_ENV_VENV", env_ok, f"python={sys.executable}"))

        # STEP 0: preflight
        input_exists = IN_MACRO.exists()
        cols_ok = False
        total_rows = None
        date_min = None
        date_max = None
        recorte_rows = None
        train_rows = None
        holdout_rows = None

        if input_exists:
            df0 = pd.read_parquet(IN_MACRO).copy()
            cols_ok = {"date", "sp500_close"}.issubset(set(df0.columns))
            if cols_ok:
                df0["date"] = pd.to_datetime(df0["date"])
                total_rows = int(len(df0))
                date_min = df0["date"].min()
                date_max = df0["date"].max()
                recorte = df0[(df0["date"] >= RECORTE_START) & (df0["date"] <= RECORTE_END)].copy()
                recorte_rows = int(len(recorte))
                train_rows = int((recorte["date"] <= TRAIN_END).sum())
                holdout_rows = int((recorte["date"] >= HOLDOUT_START).sum())

        preflight_payload = {
            "input_path": str(IN_MACRO.relative_to(ROOT)),
            "input_exists": input_exists,
            "columns_ok": cols_ok,
            "required_columns": ["date", "sp500_close"],
            "total_rows": total_rows,
            "expected_total_rows": EXPECTED_TOTAL,
            "date_min": date_min,
            "date_max": date_max,
            "expected_date_min": pd.Timestamp("2018-01-02"),
            "expected_date_max": pd.Timestamp("2026-02-26"),
            "recorte_start": RECORTE_START,
            "recorte_end": RECORTE_END,
            "recorte_rows": recorte_rows,
            "expected_recorte_rows": EXPECTED_RECORTE,
            "train_rows": train_rows,
            "expected_train_rows": EXPECTED_TRAIN,
            "holdout_rows": holdout_rows,
            "expected_holdout_rows": EXPECTED_HOLDOUT,
        }
        write_json(OUT_PREFLIGHT, preflight_payload)

        preflight_ok = (
            input_exists
            and cols_ok
            and total_rows == EXPECTED_TOTAL
            and str(pd.Timestamp(date_min).date()) == "2018-01-02"
            and str(pd.Timestamp(date_max).date()) == "2026-02-26"
            and recorte_rows == EXPECTED_RECORTE
            and train_rows == EXPECTED_TRAIN
            and holdout_rows == EXPECTED_HOLDOUT
        )
        gates.append(Gate("G0_PREFLIGHT_INPUTS", preflight_ok, f"exists={input_exists}, cols_ok={cols_ok}"))
        if not preflight_ok:
            raise RuntimeError("Preflight failed: input artifact/shape/date checks mismatch.")

        df = pd.read_parquet(IN_MACRO)[["date", "sp500_close"]].copy()
        df["date"] = pd.to_datetime(df["date"])
        df = df[(df["date"] >= RECORTE_START) & (df["date"] <= RECORTE_END)].sort_values("date").reset_index(drop=True)
        df["split"] = np.where(df["date"] <= TRAIN_END, "TRAIN", "HOLDOUT")
        df["sp500_close"] = pd.to_numeric(df["sp500_close"], errors="coerce").astype(float)
        if df["sp500_close"].isna().any():
            raise ValueError("sp500_close has NaN values in recorte.")

        df["drawdown_hist_peak_to_date"] = drawdown_hist(df["sp500_close"])
        df["event_dd10_flag_train"] = ((df["split"] == "TRAIN") & (df["drawdown_hist_peak_to_date"] <= -0.10)).astype(int)
        n_events = int(df["event_dd10_flag_train"].sum())
        gates.append(Gate("G1_TRAIN_EVENTS_DEFINED", n_events > 0, f"event_dd10_train={n_events}"))
        if n_events <= 0:
            raise RuntimeError("No dd<=-10% train events found.")

        candidates: list[dict[str, Any]] = []
        for w in FWD_WINDOWS:
            fwd_min_ret = compute_forward_min_return(df["sp500_close"], w)
            for dthr in DD_THRESHOLDS:
                vid = variant_id(w, dthr)
                y = (fwd_min_ret <= -dthr).astype(int)
                df[f"y_{vid}"] = y

                train_mask = df["split"] == "TRAIN"
                hold_mask = df["split"] == "HOLDOUT"
                cash_frac_train = float(y[train_mask].mean())
                cash_frac_holdout = float(y[hold_mask].mean())
                switches_train = count_switches(y[train_mask])
                switches_holdout = count_switches(y[hold_mask])
                recall_num = int(((y == 1) & (df["event_dd10_flag_train"] == 1)).sum())
                event_recall_train = float(recall_num / n_events) if n_events > 0 else 0.0
                feasible_cash_range = 0.25 <= cash_frac_train <= 0.45

                candidates.append(
                    {
                        "variant_id": vid,
                        "fwd_window": w,
                        "dd_threshold": dthr,
                        "cash_frac_train": cash_frac_train,
                        "cash_frac_holdout": cash_frac_holdout,
                        "switches_train": switches_train,
                        "switches_holdout": switches_holdout,
                        "event_recall_train": event_recall_train,
                        "feasible_cash_range": feasible_cash_range,
                    }
                )

        gates.append(Gate("G2_ABLATION_12_VARIANTS", len(candidates) == 12, f"count={len(candidates)}"))
        if len(candidates) != 12:
            raise RuntimeError("Ablation candidate count mismatch.")

        # Seleção TRAIN-only:
        # 1) feasible_cash_range desc
        # 2) event_recall_train desc
        # 3) switches_train asc
        # 4) variant_id asc
        candidates_sorted = sorted(
            candidates,
            key=lambda c: (
                -int(bool(c["feasible_cash_range"])),
                -float(c["event_recall_train"]),
                int(c["switches_train"]),
                str(c["variant_id"]),
            ),
        )
        for i, c in enumerate(candidates_sorted, start=1):
            c["rank"] = i
        selected = candidates_sorted[0]
        selected_vid = str(selected["variant_id"])
        selected_summary = selected.copy()

        df["y_cash_us_v1"] = df[f"y_{selected_vid}"].astype(int)
        df["variant_id_selected"] = selected_vid
        df["fwd_window_selected"] = int(selected["fwd_window"])
        df["drawdown_threshold_selected"] = float(selected["dd_threshold"])
        df["fwd_min_ret_selected"] = compute_forward_min_return(df["sp500_close"], int(selected["fwd_window"]))

        # Parquet final sem NaN nas colunas principais exigidas
        out_df = df[
            [
                "date",
                "y_cash_us_v1",
                "variant_id_selected",
                "fwd_window_selected",
                "drawdown_threshold_selected",
                "fwd_min_ret_selected",
                "drawdown_hist_peak_to_date",
                "event_dd10_flag_train",
            ]
        ].copy()
        if out_df["y_cash_us_v1"].isna().any() or out_df["fwd_min_ret_selected"].isna().any():
            raise RuntimeError("Output has NaN in required columns.")
        out_df.to_parquet(OUT_LABELS, index=False)

        labels_ok = (
            OUT_LABELS.exists()
            and len(out_df) == EXPECTED_RECORTE
            and set(out_df["y_cash_us_v1"].astype(int).unique()).issubset({0, 1})
            and int((out_df["date"] <= TRAIN_END).sum()) == EXPECTED_TRAIN
            and int((out_df["date"] >= HOLDOUT_START).sum()) == EXPECTED_HOLDOUT
        )
        gates.append(Gate("G3_LABELS_PARQUET_OK", labels_ok, f"rows={len(out_df)} selected={selected_vid}"))
        if not labels_ok:
            raise RuntimeError("Output labels parquet validation failed.")

        write_json(
            OUT_CANDIDATES,
            {
                "task_id": TASK_ID,
                "selection_policy": {
                    "primary": "feasible_cash_range desc",
                    "secondary": "event_recall_train desc",
                    "tertiary": "switches_train asc",
                    "tiebreak": "variant_id asc",
                },
                "event_definition_train": "drawdown_hist_peak_to_date <= -0.10",
                "selected_variant": selected,
                "candidates": candidates_sorted,
            },
        )
        gates.append(Gate("G4_CANDIDATE_SUMMARY_WRITTEN", OUT_CANDIDATES.exists(), f"path={OUT_CANDIDATES}"))

        build_dashboard(
            df=df,
            selected_vid=selected_vid,
            selected_params={"fwd_window": selected["fwd_window"], "dd_threshold": selected["dd_threshold"]},
            candidates=candidates_sorted,
        )
        gates.append(Gate("G5_EDA_DASHBOARD_WRITTEN", OUT_HTML.exists(), f"path={OUT_HTML}"))

        ch_ok = append_changelog_one_line_idempotent(TRACEABILITY_LINE)
        gates.append(Gate("G_CHLOG_UPDATED", ch_ok, f"path={CHANGELOG_PATH}"))

        # Primeiro report (antes dos gates de hash)
        overall_pre = all(g.passed for g in gates)
        OUT_REPORT.write_text(
            render_report(gates=gates, retry_log=retry_log, overall=overall_pre, selected=selected_summary, preflight=preflight_payload),
            encoding="utf-8",
        )

        outputs = [OUT_SCRIPT, OUT_LABELS, OUT_HTML, OUT_REPORT, OUT_CANDIDATES, OUT_PREFLIGHT, CHANGELOG_PATH]
        hashes = {str(p.relative_to(ROOT)): sha256_file(p) for p in outputs}
        manifest = {
            "task_id": TASK_ID,
            "run_id": RUN_ID,
            "manifest_policy": "no_self_hash",
            "inputs_consumed": [str(IN_MACRO.relative_to(ROOT))],
            "outputs_produced": [
                str(OUT_LABELS.relative_to(ROOT)),
                str(OUT_HTML.relative_to(ROOT)),
                str(OUT_REPORT.relative_to(ROOT)),
                str(OUT_MANIFEST.relative_to(ROOT)),
                str(OUT_CANDIDATES.relative_to(ROOT)),
                str(OUT_PREFLIGHT.relative_to(ROOT)),
            ],
            "hashes_sha256": hashes,
        }
        write_json(OUT_MANIFEST, manifest)
        gates.append(Gate("Gx_HASH_MANIFEST_PRESENT", OUT_MANIFEST.exists(), f"path={OUT_MANIFEST}"))

        mismatches = []
        for rel, exp in manifest["hashes_sha256"].items():
            got = sha256_file(ROOT / rel)
            if got != exp:
                mismatches.append(rel)
        hash_ok = len(mismatches) == 0
        gates.append(Gate("G_SHA256_INTEGRITY_SELF_CHECK", hash_ok, f"mismatches={len(mismatches)}"))

        # Report final + manifest final
        overall = all(g.passed for g in gates)
        OUT_REPORT.write_text(
            render_report(gates=gates, retry_log=retry_log, overall=overall, selected=selected_summary, preflight=preflight_payload),
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
        print(f"- {OUT_LABELS}")
        print(f"- {OUT_HTML}")
        print(f"- {OUT_REPORT}")
        print(f"- {OUT_MANIFEST}")
        print(f"- {OUT_CANDIDATES}")
        print(f"- {OUT_PREFLIGHT}")
        print(f"OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]")
        return 0 if overall else 2
    except Exception as exc:
        retry_log.append(f"FATAL: {type(exc).__name__}: {exc}")
        gates.append(Gate("G_FATAL", False, f"{type(exc).__name__}: {exc}"))
        OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
        OUT_REPORT.write_text(
            render_report(gates=gates, retry_log=retry_log, overall=False, selected=selected_summary, preflight=preflight_payload),
            encoding="utf-8",
        )
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
