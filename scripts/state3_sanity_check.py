from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

TASK_ID = "M-013"
ROOT = Path("/home/wilson/AGNO_WORKSPACE")
PORT = ROOT / "src" / "data_engine" / "portfolio"
SSOT = ROOT / "src" / "data_engine" / "ssot"
FEAT = ROOT / "src" / "data_engine" / "features"
PLOT = ROOT / "outputs" / "plots" / "T041_STATE3_PHASE1_COMPARATIVE.html"


def _require(path: Path) -> None:
    if not path.exists():
        raise RuntimeError(f"Artefato ausente: {path}")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    print(f"HEADER: {TASK_ID}")
    print("STEP GATES:")

    required = [
        SSOT / "SSOT_MACRO.parquet",
        SSOT / "SSOT_CANONICAL_BASE.parquet",
        FEAT / "T037_M3_SCORES_DAILY.parquet",
        PORT / "T037_PORTFOLIO_CURVE.parquet",
        PORT / "T038_PORTFOLIO_CURVE.parquet",
        PORT / "T039_PORTFOLIO_CURVE.parquet",
        PORT / "T037_BASELINE_SUMMARY.json",
        PORT / "T038_BASELINE_SUMMARY.json",
        PORT / "T039_BASELINE_SUMMARY.json",
        PORT / "T040_METRICS_COMPARATIVE.json",
        PLOT,
    ]
    for p in required:
        _require(p)
    print(" - G1_ARTIFACTS_PRESENCE: PASS")

    macro = pd.read_parquet(SSOT / "SSOT_MACRO.parquet").copy()
    macro["date"] = pd.to_datetime(macro["date"], errors="coerce")
    macro = macro.dropna(subset=["date", "cdi_log_daily"]).sort_values("date")

    summaries = {t: _load_json(PORT / f"{t}_BASELINE_SUMMARY.json") for t in ["T037", "T038", "T039"]}
    curves = {}
    for t in ["T037", "T038", "T039"]:
        c = pd.read_parquet(PORT / f"{t}_PORTFOLIO_CURVE.parquet").copy()
        c["date"] = pd.to_datetime(c["date"], errors="coerce")
        c = c.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
        curves[t] = c

    for t, c in curves.items():
        diff = (c["equity_end"].astype(float) - (c["cash_end"].astype(float) + c["positions_value_end"].astype(float))).abs()
        if float(diff.max()) > 1e-6:
            raise RuntimeError(f"{t}: equity_end != cash_end + positions_value_end")
    print(" - G2_EQUITY_DECOMPOSITION: PASS")

    for t, c in curves.items():
        s = summaries[t]
        eq_curve = float(c["equity_end"].iloc[-1])
        cdi_w = (1.0 + c["cdi_daily"].astype(float)).cumprod()
        cdi_curve = float(100000.0 * cdi_w.iloc[-1] / cdi_w.iloc[0])
        if abs(eq_curve - float(s["equity_final"])) > 1e-6:
            raise RuntimeError(f"{t}: summary equity_final inconsistente")
        if abs(cdi_curve - float(s["cdi_final"])) > 1e-6:
            raise RuntimeError(f"{t}: summary cdi_final inconsistente")
    print(" - G3_SUMMARY_CURVE_CONSISTENCY: PASS")

    t037 = summaries["T037"]
    t038 = summaries["T038"]
    t039 = summaries["T039"]
    if float(t038["t037_baseline"]["equity_final"]) != float(t037["equity_final"]):
        raise RuntimeError("T038.t037_baseline inconsistente com T037 summary")
    if float(t039["t037_baseline"]["equity_final"]) != float(t037["equity_final"]):
        raise RuntimeError("T039.t037_baseline inconsistente com T037 summary")
    if float(t039["t038_baseline"]["equity_final"]) != float(t038["equity_final"]):
        raise RuntimeError("T039.t038_baseline inconsistente com T038 summary")
    print(" - G4_NESTED_BASELINE_CONSISTENCY: PASS")

    for t, c in curves.items():
        m = macro[macro["date"].isin(c["date"])].sort_values("date")
        simple_growth = float((1.0 + c["cdi_daily"].astype(float)).iloc[1:].prod() - 1.0)
        log_growth = float(np.expm1(m["cdi_log_daily"].astype(float).iloc[1:].sum()))
        rel_err = abs(simple_growth - log_growth) / max(1e-12, abs(log_growth))
        if rel_err > 1e-6:
            raise RuntimeError(f"{t}: CDI sanity rel_err={rel_err} > 1e-6")
    print(" - G5_CDI_SANITY: PASS")

    metrics = _load_json(PORT / "T040_METRICS_COMPARATIVE.json")["metrics_by_task"]
    for t in ["T037", "T038", "T039"]:
        cagr_diff_pp = abs(float(metrics[t]["CAGR"]) - float(summaries[t]["cagr"])) * 100.0
        if cagr_diff_pp >= 0.2:
            raise RuntimeError(f"{t}: CAGR diff >= 0.2pp ({cagr_diff_pp:.4f}pp)")
    print(" - G6_T040_CAGR_ALIGNMENT: PASS")

    html = PLOT.read_text(encoding="utf-8")
    for key in ["T037 M3 Puro", "T038 M3+Gate", "T039 M3+Gate+Severity [BASELINE]", "CDI Acumulado", "Ibovespa ^BVSP"]:
        if key not in html:
            raise RuntimeError(f"T041 HTML sem trace esperado: {key}")
    print(" - G7_T041_PLOTLY_SIGNATURE: PASS")

    print("RETRY LOG: NONE")
    print("ARTIFACT LINKS:")
    print(f" - {PORT / 'T037_BASELINE_SUMMARY.json'}")
    print(f" - {PORT / 'T038_BASELINE_SUMMARY.json'}")
    print(f" - {PORT / 'T039_BASELINE_SUMMARY.json'}")
    print(f" - {PORT / 'T040_METRICS_COMPARATIVE.json'}")
    print(f" - {PLOT}")
    print("OVERALL STATUS: [[ PASS ]]")


if __name__ == "__main__":
    main()
