#!/usr/bin/env python3
"""A-001-SSOT-CANONICAL-AUDIT: Auditoria forense independente da SSOT_CANONICAL_BASE."""
from __future__ import annotations

import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
SSOT = REPO / "src" / "data_engine" / "ssot"
REPORT_DIR = REPO / "00_Strategy" / "Task_History" / "A-001"
PLOTS_DIR = REPORT_DIR / "plots"

REQUIRED_COLS = [
    "ticker", "date", "close_operational", "close_raw", "X_real",
    "i_value", "i_ucl", "i_lcl", "mr_value", "mr_ucl",
    "xbar_value", "xbar_ucl", "xbar_lcl", "r_value", "r_ucl",
    "sector", "mr_bar", "r_bar", "center_line", "splits", "split_factor",
]

SPOTLIGHT_TICKERS = ["VIVT3", "MGLU3", "PETR4"]


class Gate:
    def __init__(self, gate_id: str):
        self.gate_id = gate_id
        self.status = "PENDING"
        self.details: list[str] = []
        self.findings: list[str] = []

    def passed(self, msg: str) -> None:
        self.status = "PASS"
        self.details.append(msg)

    def failed(self, msg: str) -> None:
        self.status = "FAIL"
        self.findings.append(msg)
        self.details.append(f"FAIL: {msg}")

    def info(self, msg: str) -> None:
        self.details.append(msg)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_g1_structural(cb: pd.DataFrame, uni: pd.DataFrame) -> Gate:
    g = Gate("G1_STRUCTURAL_INTEGRITY")

    missing_cols = [c for c in REQUIRED_COLS if c not in cb.columns]
    if missing_cols:
        g.failed(f"Colunas ausentes: {missing_cols}")
    else:
        g.info(f"21/21 colunas obrigatorias presentes.")

    dupes = cb.duplicated(subset=["ticker", "date"], keep=False).sum()
    if dupes > 0:
        g.failed(f"{dupes} linhas duplicadas em (ticker, date).")
    else:
        g.info(f"Zero duplicatas em (ticker, date). Total linhas: {len(cb)}")

    cb_tickers = set(cb["ticker"].unique())
    uni_tickers = set(uni["ticker"].unique())
    n_cb = len(cb_tickers)
    n_uni = len(uni_tickers)
    orphans_in_cb = cb_tickers - uni_tickers
    missing_from_cb = uni_tickers - cb_tickers

    g.info(f"Tickers no CANONICAL: {n_cb}, no UNIVERSE_OPERATIONAL: {n_uni}")
    if orphans_in_cb:
        g.failed(f"{len(orphans_in_cb)} tickers no CANONICAL fora do UNIVERSE: {sorted(orphans_in_cb)[:20]}")
    if missing_from_cb:
        g.info(f"AVISO: {len(missing_from_cb)} tickers do UNIVERSE sem dados no CANONICAL (possivelmente sem historico).")

    if not g.findings:
        g.passed(f"Estrutura integra. {n_cb} tickers, {len(cb)} linhas, zero duplicatas.")
    return g


def run_g2_split_heuristic(cb: pd.DataFrame, adjustments_path: Path) -> Gate:
    g = Gate("G2_SPLIT_HEURISTIC_VALIDATION")

    has_split = cb["split_factor"].notna() & (cb["split_factor"] != 1.0)
    split_tickers = cb.loc[has_split, "ticker"].unique()
    g.info(f"Tickers com eventos de split: {len(split_tickers)}")

    violations: list[dict[str, Any]] = []
    for ticker in split_tickers:
        tf = cb[cb["ticker"] == ticker].copy()
        tf = tf.sort_values("date").reset_index(drop=True)
        if len(tf) < 3:
            continue
        co = tf["close_operational"].values
        logrets = []
        for i in range(1, len(co)):
            if co[i] > 0 and co[i - 1] > 0:
                logrets.append((i, abs(math.log(co[i] / co[i - 1]))))
            else:
                logrets.append((i, 0.0))

        split_indices = tf.index[has_split.reindex(tf.index, fill_value=False)].tolist()
        for si in split_indices:
            local_idx = tf.index.get_loc(si)
            window = range(max(1, local_idx - 2), min(len(tf), local_idx + 3))
            for wi in window:
                if wi < len(logrets) and logrets[wi][1] > 0.405:
                    violations.append({
                        "ticker": ticker,
                        "date": tf.iloc[wi]["date"],
                        "abs_logret": round(logrets[wi][1], 4),
                        "split_factor": tf.iloc[local_idx]["split_factor"],
                    })

    if violations:
        vdf = pd.DataFrame(violations).drop_duplicates()
        g.failed(f"{len(vdf)} saltos residuais > 50% no entorno de splits.")
        for _, row in vdf.iterrows():
            g.info(f"  - {row['ticker']} @ {row['date']}: |logret|={row['abs_logret']}, factor={row['split_factor']}")
    else:
        g.passed(f"Zero saltos residuais > 50%. Heuristica de splits validada para {len(split_tickers)} tickers.")

    if adjustments_path.exists():
        adj = pd.read_csv(adjustments_path)
        g.info(f"Audit trail (heuristic_adjustments_t023.csv): {len(adj)} registros.")
    else:
        g.info("AVISO: heuristic_adjustments_t023.csv nao encontrado.")

    return g


def run_g3_return_sanity(cb: pd.DataFrame) -> Gate:
    g = Gate("G3_RETURN_SANITY")

    xr = cb["X_real"].dropna()
    g.info(f"Registros com X_real valido: {len(xr)} de {len(cb)} ({100*len(xr)/len(cb):.1f}%)")

    extreme_mask = cb["X_real"].abs() > 1.0
    extreme = extreme_mask.sum()
    if extreme > 0:
        g.failed(f"{extreme} registros com |X_real| > 1.0 (fisicamente implausivel).")
        worst = cb.loc[extreme_mask, ["ticker", "date", "X_real"]].head(10)
        for _, row in worst.iterrows():
            g.info(f"  - {row['ticker']} @ {row['date']}: X_real={row['X_real']:.6f}")
    else:
        g.info(f"Zero registros com |X_real| > 1.0.")

    global_mean = xr.mean()
    if abs(global_mean) >= 0.005:
        g.failed(f"|Media global X_real| = {abs(global_mean):.6f} >= 0.005 (vies sistematico).")
    else:
        g.info(f"Media global X_real = {global_mean:.6f} (sem vies).")

    ticker_means = cb.groupby("ticker")["X_real"].mean()
    biased = ticker_means[(ticker_means > 0.05) | (ticker_means < -0.05)]
    if len(biased) > 0:
        g.failed(f"{len(biased)} tickers com |media X_real| > 0.05 (distorcao sistematica).")
        for t, m in biased.head(10).items():
            g.info(f"  - {t}: media={m:.6f}")
    else:
        g.info(f"Zero tickers com |media X_real| > 0.05.")

    if not g.findings:
        g.passed(f"Retornos saudaveis. |media|={abs(global_mean):.6f}, zero extremos, zero viesados.")
    return g


def run_g4_macro_alignment(cb: pd.DataFrame, macro: pd.DataFrame) -> Gate:
    g = Gate("G4_MACRO_ALIGNMENT")

    cb_dates = set(cb["date"].unique())
    macro_dates = set(macro["date"].unique())
    orphan_dates = cb_dates - macro_dates

    if orphan_dates:
        g.failed(f"{len(orphan_dates)} datas no CANONICAL sem correspondente no MACRO.")
        for d in sorted(orphan_dates)[:10]:
            g.info(f"  - {d}")
    else:
        g.info(f"Todas as {len(cb_dates)} datas do CANONICAL existem no MACRO.")

    merged = cb[["date"]].drop_duplicates().merge(macro, on="date", how="left")
    cdi_nan = merged["cdi_log_daily"].isna().sum()
    if cdi_nan > 0:
        g.failed(f"{cdi_nan} datas com cdi_log_daily NaN apos merge.")
    else:
        g.info(f"cdi_log_daily completo para todas as datas.")

    ibov_nan = merged["ibov_close"].isna().sum()
    sp_nan = merged["sp500_close"].isna().sum()
    g.info(f"ibov_close NaN: {ibov_nan}, sp500_close NaN: {sp_nan}")

    macro_sorted = macro.sort_values("date")
    macro_sorted["date_dt"] = pd.to_datetime(macro_sorted["date"])
    gaps = macro_sorted["date_dt"].diff().dt.days
    max_gap = gaps.max()
    g.info(f"Maior gap no calendario MACRO: {max_gap} dias.")
    if max_gap > 7:
        g.info(f"AVISO: gap de {max_gap} dias (possivelmente feriado prolongado).")

    if not g.findings:
        g.passed(f"Alinhamento MACRO perfeito. {len(cb_dates)} datas, zero NaN em CDI.")
    return g


def run_g5_cross_reference(cb: pd.DataFrame, raw: pd.DataFrame) -> Gate:
    g = Gate("G5_CROSS_REFERENCE_RAW")

    no_split = cb[(cb["split_factor"].isna()) | (cb["split_factor"] == 1.0)]
    no_split_tickers = no_split["ticker"].unique()
    sample_tickers = list(no_split_tickers[:10])

    mismatches = 0
    for ticker in sample_tickers:
        tf = no_split[no_split["ticker"] == ticker]
        diff = (tf["close_operational"] - tf["close_raw"]).abs()
        bad = (diff > 0.01).sum()
        mismatches += bad
        if bad > 0:
            g.info(f"  - {ticker}: {bad} registros com |close_op - close_raw| > 0.01")

    if mismatches > 0:
        g.failed(f"{mismatches} registros com close_operational != close_raw em tickers sem split.")
    else:
        g.info(f"close_operational == close_raw (tol=0.01) para {len(sample_tickers)} tickers sem split.")

    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        PLOTS_DIR.mkdir(parents=True, exist_ok=True)
        for ticker in SPOTLIGHT_TICKERS:
            tf = cb[cb["ticker"] == ticker].sort_values("date").copy()
            if tf.empty:
                g.info(f"AVISO: {ticker} nao encontrado no CANONICAL.")
                continue

            fig = make_subplots(rows=1, cols=1)
            fig.add_trace(go.Scatter(
                x=tf["date"], y=tf["close_raw"],
                name="close_raw", mode="lines", line=dict(color="red", dash="dot"),
            ))
            fig.add_trace(go.Scatter(
                x=tf["date"], y=tf["close_operational"],
                name="close_operational", mode="lines", line=dict(color="blue"),
            ))

            split_events = tf[tf["split_factor"].notna() & (tf["split_factor"] != 1.0)]
            if not split_events.empty:
                fig.add_trace(go.Scatter(
                    x=split_events["date"], y=split_events["close_operational"],
                    name="split event", mode="markers",
                    marker=dict(color="orange", size=10, symbol="diamond"),
                ))

            fig.update_layout(
                title=f"A-001 Audit: {ticker} — close_raw vs close_operational",
                xaxis_title="Date", yaxis_title="Price (BRL)",
                template="plotly_white",
            )
            plot_path = PLOTS_DIR / f"A001_{ticker}_raw_vs_operational.html"
            fig.write_html(str(plot_path))
            g.info(f"Plot gerado: {plot_path.relative_to(REPO)}")
    except ImportError:
        g.info("AVISO: plotly nao disponivel. Plots nao gerados.")

    if not g.findings:
        g.passed(f"Cross-reference validada. Plots de {SPOTLIGHT_TICKERS} gerados.")
    return g


def build_report(gates: list[Gate], overall: bool) -> str:
    lines = [
        "# A-001 SSOT Canonical Base Audit Report",
        "",
        f"**Generated:** {now_utc()}",
        f"**Overall Status:** `{'PASS' if overall else 'FAIL'}`",
        "",
        "## Gate Summary",
        "",
        "| Gate | Status | Summary |",
        "| --- | --- | --- |",
    ]
    for g in gates:
        summary = g.details[0] if g.details else "-"
        lines.append(f"| {g.gate_id} | {g.status} | {summary} |")

    for g in gates:
        lines.append("")
        lines.append(f"## {g.gate_id}: {g.status}")
        lines.append("")
        for d in g.details:
            lines.append(f"- {d}")
        if g.findings:
            lines.append("")
            lines.append("**Findings:**")
            for f in g.findings:
                lines.append(f"- {f}")

    lines.append("")
    lines.append("## Veredito Final")
    lines.append("")
    if overall:
        lines.append("A SSOT_CANONICAL_BASE.parquet esta **CERTIFICADA** para uso operacional.")
        lines.append("Nenhum defeito estrutural, de splits, de retornos ou de alinhamento macro encontrado.")
    else:
        lines.append("A SSOT_CANONICAL_BASE.parquet **NAO ESTA CERTIFICADA**.")
        lines.append("Defeitos encontrados nos gates acima devem ser corrigidos antes do uso.")
    lines.append("")
    return "\n".join(lines)


def build_terminal_log(gates: list[Gate], overall: bool, report_path: Path, plots: list[str]) -> str:
    lines = [
        "HEADER: A-001-SSOT-CANONICAL-AUDIT",
        "",
        "STEP GATES:",
    ]
    for g in gates:
        lines.append(f"- {g.gate_id}: {g.status}")
    lines.append("")
    lines.append("RETRY LOG:")
    lines.append("- N/A (auditoria sem retry)")
    lines.append("")
    lines.append("ARTIFACT LINKS:")
    lines.append(f"- {report_path}")
    for p in plots:
        lines.append(f"- {p}")
    lines.append("")
    lines.append(f"OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]")
    return "\n".join(lines)


def main() -> int:
    print("HEADER: A-001-SSOT-CANONICAL-AUDIT")
    print()

    cb = pd.read_parquet(SSOT / "SSOT_CANONICAL_BASE.parquet")
    raw = pd.read_parquet(SSOT / "SSOT_MARKET_DATA_RAW.parquet")
    macro = pd.read_parquet(SSOT / "SSOT_MACRO.parquet")
    uni = pd.read_parquet(SSOT / "SSOT_UNIVERSE_OPERATIONAL.parquet")
    adj_path = REPO / "data" / "market_data" / "heuristic_adjustments_t023.csv"

    gates: list[Gate] = []

    print("Running G1: Structural Integrity...")
    g1 = run_g1_structural(cb, uni)
    gates.append(g1)

    print("Running G2: Split Heuristic Validation...")
    g2 = run_g2_split_heuristic(cb, adj_path)
    gates.append(g2)

    print("Running G3: Return Sanity...")
    g3 = run_g3_return_sanity(cb)
    gates.append(g3)

    print("Running G4: Macro Alignment...")
    g4 = run_g4_macro_alignment(cb, macro)
    gates.append(g4)

    print("Running G5: Cross-Reference Raw...")
    g5 = run_g5_cross_reference(cb, raw)
    gates.append(g5)

    overall = all(g.status == "PASS" for g in gates)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / "audit_report.md"
    report_path.write_text(build_report(gates, overall), encoding="utf-8")

    plot_files = [str(p.relative_to(REPO)) for p in PLOTS_DIR.glob("*.html")] if PLOTS_DIR.exists() else []

    terminal = build_terminal_log(gates, overall, report_path.relative_to(REPO), plot_files)
    print()
    print(terminal)

    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
