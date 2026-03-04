from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TASK_ID = "T101"
RUN_ID = "T101-PTAX-BDR-SYNTH-V2"
TRACEABILITY_LINE = (
    "- 2026-03-03T21:00:00Z | STATE3-P8A: T101-PTAX-BDR-SYNTH-V2 EXEC. Universo US completo (BDR+B3 + "
    "US_DIRECT) com PTAX (BCB SGS 1), `execution_venue` e `friction_one_way_rate`. Artefatos: "
    "scripts/t101_ingest_ptax_bdr_synth.py; src/data_engine/ssot/SSOT_FX_PTAX_USDBRL.parquet; "
    "src/data_engine/ssot/SSOT_BDR_B3_UNIVERSE.parquet; src/data_engine/ssot/SSOT_BDR_SYNTH_MARKET_DATA_RAW.parquet; "
    "outputs/governanca/T101-PTAX-BDR-SYNTH-V2_{report,manifest}.md"
)

IN_MACRO = ROOT / "src" / "data_engine" / "ssot" / "SSOT_MACRO.parquet"
IN_US_RAW = ROOT / "src" / "data_engine" / "ssot" / "SSOT_US_MARKET_DATA_RAW.parquet"
IN_US_UNIVERSE = ROOT / "src" / "data_engine" / "ssot" / "SSOT_US_UNIVERSE_OPERATIONAL.parquet"
IN_US_BLACKLIST = ROOT / "src" / "data_engine" / "ssot" / "SSOT_US_BLACKLIST_OPERATIONAL.csv"
CHANGELOG_PATH = ROOT / "00_Strategy" / "changelog.md"

OUT_SCRIPT = ROOT / "scripts" / "t101_ingest_ptax_bdr_synth.py"
OUT_PTAX = ROOT / "src" / "data_engine" / "ssot" / "SSOT_FX_PTAX_USDBRL.parquet"
OUT_BDR_UNIVERSE = ROOT / "src" / "data_engine" / "ssot" / "SSOT_BDR_B3_UNIVERSE.parquet"
OUT_BDR_SYNTH = ROOT / "src" / "data_engine" / "ssot" / "SSOT_BDR_SYNTH_MARKET_DATA_RAW.parquet"

OUT_DIR = ROOT / "outputs" / "governanca"
OUT_EVIDENCE = OUT_DIR / f"{RUN_ID}_evidence"
OUT_REPORT = OUT_DIR / f"{RUN_ID}_report.md"
OUT_MANIFEST = OUT_DIR / f"{RUN_ID}_manifest.json"
OUT_B3_XLSX = OUT_EVIDENCE / "BDRs_Listados_B3.xlsx"
OUT_B3_FETCH = OUT_EVIDENCE / "b3_fetch_metadata.json"
OUT_COVERAGE = OUT_EVIDENCE / "coverage_metrics.json"
OUT_MISSING_TICKERS = OUT_EVIDENCE / "us_tickers_without_bdr.csv"
OUT_MAPPING = OUT_EVIDENCE / "us_to_bdr_mapping.csv"

B3_BDR_XLSX_URL = "https://www.b3.com.br/data/files/09/65/8A/16/F6098810A1E6D588AC094EA8/BDRs%20Listados%20B3_06.06.xlsx"
PTAX_SERIES_ID = 1
START_DATE = date(2018, 1, 2)
END_DATE = date(2026, 2, 26)
ORDER_COST_RATE_B3 = 0.00025
ORDER_COST_PENALTY_CROSS_BORDER = 0.0078


@dataclass
class Gate:
    name: str
    passed: bool
    details: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


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
    if retry_log:
        for item in retry_log:
            lines.append(f"- {item}")
    else:
        lines.append("- none")
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
    lines.append("- Manifest segue política no_self_hash (sem auto-referência).")
    lines.append("")
    lines.append(f"OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]")
    lines.append("")
    return "\n".join(lines)


def fetch_b3_xlsx(url: str, out_path: Path, retry_log: list[str]) -> tuple[Path, dict[str, Any]]:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    max_retries = 5
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, timeout=40)
            resp.raise_for_status()
            out_path.write_bytes(resp.content)
            return out_path, {"status_code": int(resp.status_code), "bytes": int(len(resp.content))}
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < max_retries:
                retry_log.append(f"fetch_b3_xlsx retry {attempt}/{max_retries - 1}: {str(exc)[:200]}")
                time.sleep(0.8 * attempt)
                continue
            break
    assert last_exc is not None
    raise RuntimeError("Falha ao baixar XLSX oficial de BDRs da B3.") from last_exc


def normalize_text(value: Any) -> str:
    text = str(value).strip()
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_col(col: str) -> str:
    c = normalize_text(col).lower()
    c = c.replace("ã", "a").replace("á", "a").replace("à", "a").replace("â", "a")
    c = c.replace("é", "e").replace("ê", "e").replace("í", "i")
    c = c.replace("ó", "o").replace("ô", "o").replace("õ", "o")
    c = c.replace("ú", "u").replace("ç", "c")
    c = re.sub(r"[^a-z0-9]+", "_", c)
    c = c.strip("_")
    return c


def parse_b3_bdr_xlsx(path: Path) -> pd.DataFrame:
    # Layout legado conhecido: cabeçalho útil inicia por volta da linha 12 (0-based=11).
    raw = pd.read_excel(path, header=11, engine="openpyxl")
    raw = raw.copy()
    raw.columns = [normalize_col(str(c)) for c in raw.columns]

    expected_map = {
        "empresa": "empresa",
        "ticker": "ticker",
        "ticker_bdr": "ticker_bdr",
        "isin": "isin",
        "isin_bdr": "isin_bdr",
        "paridade_acao_bdr": "paridade_acao_bdr",
        "pais": "pais",
        "tipo_investidor": "tipo_investidor",
        "banco_depositario": "banco_depositario",
        "bolsa_de_origem": "bolsa_origem",
        "setor": "setor",
    }

    # Ajustes para nomes historicamente inconsistentes.
    rename_candidates = {
        "ticker_": "ticker",
        "ticker_bdr_": "ticker_bdr",
        "paridade_a_o_bdr": "paridade_acao_bdr",
        "pa_s": "pais",
        "banco_deposit_rio": "banco_depositario",
    }
    for src, dst in rename_candidates.items():
        if src in raw.columns and dst not in raw.columns:
            raw = raw.rename(columns={src: dst})

    cols = []
    for key in expected_map:
        if key in raw.columns:
            cols.append(key)
    if "ticker" not in cols or "ticker_bdr" not in cols or "paridade_acao_bdr" not in cols:
        raise RuntimeError(f"XLSX B3 sem colunas críticas. Colunas lidas: {list(raw.columns)}")

    if "isin" not in cols:
        raw["isin"] = ""
        cols.append("isin")
    if "isin_bdr" not in cols:
        raw["isin_bdr"] = ""
        cols.append("isin_bdr")
    for optional in ["empresa", "pais", "tipo_investidor", "banco_depositario", "bolsa_origem", "setor"]:
        if optional not in cols:
            raw[optional] = ""
            cols.append(optional)

    df = raw[cols].copy()
    for c in cols:
        df[c] = df[c].map(normalize_text)

    df["ticker"] = df["ticker"].str.upper()
    df["ticker_bdr"] = df["ticker_bdr"].str.upper()
    df = df[(df["ticker"] != "") & (df["ticker_bdr"] != "")]
    df = df[~df["ticker"].isin(["NAN", "-", "NULL"])]
    df = df[~df["ticker_bdr"].isin(["NAN", "-", "NULL"])]
    df = df.drop_duplicates(subset=["ticker_bdr"], keep="first").reset_index(drop=True)
    return df


def parity_to_ratio(text: str) -> float:
    # Formato esperado: "1:4" (acao:bdr) -> preço BDR = preço ação * (1/4)
    try:
        left_str, right_str = text.split(":")
        left = float(left_str.strip().replace(",", "."))
        right = float(right_str.strip().replace(",", "."))
        if left <= 0 or right <= 0:
            return 1.0
        return left / right
    except Exception:  # noqa: BLE001
        return 1.0


def main() -> None:
    from src.data_engine.adapters.bcb_adapter import BcbAdapter

    OUT_EVIDENCE.mkdir(parents=True, exist_ok=True)
    OUT_PTAX.parent.mkdir(parents=True, exist_ok=True)
    OUT_BDR_UNIVERSE.parent.mkdir(parents=True, exist_ok=True)
    OUT_BDR_SYNTH.parent.mkdir(parents=True, exist_ok=True)

    gates: list[Gate] = []
    retry_log: list[str] = []
    artifacts: list[Path] = []

    inputs_ok = (
        IN_MACRO.exists()
        and IN_US_RAW.exists()
        and IN_US_UNIVERSE.exists()
        and IN_US_BLACKLIST.exists()
        and CHANGELOG_PATH.exists()
    )
    gates.append(
        Gate(
            "G_INPUTS_PRESENT",
            inputs_ok,
            (
                f"macro={IN_MACRO.exists()} us_raw={IN_US_RAW.exists()} us_universe={IN_US_UNIVERSE.exists()} "
                f"us_blacklist={IN_US_BLACKLIST.exists()} changelog={CHANGELOG_PATH.exists()}"
            ),
        )
    )
    if not inputs_ok:
        raise RuntimeError("Inputs obrigatórios da T101 ausentes.")

    macro = pd.read_parquet(IN_MACRO).copy()
    macro["date"] = pd.to_datetime(macro["date"], errors="coerce")
    b3_calendar = (
        macro[["date"]]
        .dropna()
        .drop_duplicates()
        .sort_values("date")
        .reset_index(drop=True)
    )
    gates.append(
        Gate(
            "G_B3_CALENDAR_READY",
            len(b3_calendar) >= 1800,
            f"rows={len(b3_calendar)} min={b3_calendar['date'].min().date()} max={b3_calendar['date'].max().date()}",
        )
    )

    bcb = BcbAdapter(timeout_seconds=30.0)
    ptax = bcb.get_series(series_id=PTAX_SERIES_ID, start=START_DATE, end=END_DATE).rename(columns={"value": "usdbrl_ptax"})
    ptax["date"] = pd.to_datetime(ptax["date"], errors="coerce")
    ptax = ptax.dropna(subset=["date", "usdbrl_ptax"]).sort_values("date").reset_index(drop=True)
    ptax_b3 = b3_calendar.merge(ptax, on="date", how="left")
    ptax_missing_before = int(ptax_b3["usdbrl_ptax"].isna().sum())
    ptax_b3["usdbrl_ptax"] = pd.to_numeric(ptax_b3["usdbrl_ptax"], errors="coerce").ffill().bfill()
    ptax_missing_after = int(ptax_b3["usdbrl_ptax"].isna().sum())
    ptax_b3["date"] = ptax_b3["date"].dt.strftime("%Y-%m-%d")
    ptax_b3.to_parquet(OUT_PTAX, index=False)
    artifacts.append(OUT_PTAX)

    ptax_coverage = float(1.0 - (ptax_missing_after / max(len(ptax_b3), 1)))
    gates.append(
        Gate(
            "G_PTAX_COVERAGE",
            ptax_coverage >= 0.99,
            f"coverage={ptax_coverage:.6f} missing_before={ptax_missing_before} missing_after={ptax_missing_after}",
        )
    )

    b3_xlsx_path, b3_fetch = fetch_b3_xlsx(B3_BDR_XLSX_URL, OUT_B3_XLSX, retry_log)
    b3_df = parse_b3_bdr_xlsx(b3_xlsx_path)
    artifacts.append(OUT_B3_XLSX)
    write_json(
        OUT_B3_FETCH,
        {
            "source_url": B3_BDR_XLSX_URL,
            "download_status": b3_fetch,
            "rows_parsed": int(len(b3_df)),
            "sha256_xlsx": sha256_file(OUT_B3_XLSX),
            "columns": list(b3_df.columns),
        },
    )
    artifacts.append(OUT_B3_FETCH)
    gates.append(Gate("G_B3_BDR_UNIVERSE_ROWS", len(b3_df) >= 800, f"rows={len(b3_df)}"))

    us_uni = pd.read_parquet(IN_US_UNIVERSE).copy()
    us_uni["ticker"] = us_uni["ticker"].astype(str).str.upper().str.strip()
    approved_us = set(us_uni["ticker"].unique().tolist())

    us_black = pd.read_csv(IN_US_BLACKLIST).copy()
    us_black["ticker"] = us_black["ticker"].astype(str).str.upper().str.strip()
    hard_black = set(us_black["ticker"].unique().tolist())

    eligible_us = sorted(approved_us - hard_black)
    b3_df["ticker"] = b3_df["ticker"].astype(str).str.upper().str.strip()
    b3_df["ticker_bdr"] = b3_df["ticker_bdr"].astype(str).str.upper().str.strip()
    b3_map = b3_df[["ticker", "ticker_bdr", "paridade_acao_bdr"]].copy().drop_duplicates(subset=["ticker"], keep="first")
    b3_map["parity_ratio"] = b3_map["paridade_acao_bdr"].map(parity_to_ratio)

    mapped = pd.DataFrame({"ticker": eligible_us}).merge(b3_map, on="ticker", how="left")
    missing_map = mapped[mapped["ticker_bdr"].isna()].copy()
    mapped_ok = mapped[mapped["ticker_bdr"].notna()].copy()
    mapped_ok["execution_venue"] = "B3"
    mapped_ok["friction_one_way_rate"] = ORDER_COST_RATE_B3
    missing_map["ticker_bdr"] = missing_map["ticker"]
    missing_map["paridade_acao_bdr"] = "1:1"
    missing_map["parity_ratio"] = 1.0
    missing_map["execution_venue"] = "US_DIRECT"
    missing_map["friction_one_way_rate"] = ORDER_COST_PENALTY_CROSS_BORDER
    mapped_all = pd.concat([mapped_ok, missing_map], ignore_index=True)

    universe_operational = mapped_all[
        [
            "ticker",
            "ticker_bdr",
            "paridade_acao_bdr",
            "parity_ratio",
            "execution_venue",
            "friction_one_way_rate",
        ]
    ].copy()
    universe_operational = universe_operational.sort_values(["execution_venue", "ticker"]).reset_index(drop=True)
    universe_operational.to_parquet(OUT_BDR_UNIVERSE, index=False)
    artifacts.append(OUT_BDR_UNIVERSE)

    mapped_ok.to_csv(OUT_MAPPING, index=False)
    missing_map.to_csv(OUT_MISSING_TICKERS, index=False)
    artifacts.extend([OUT_MAPPING, OUT_MISSING_TICKERS])

    coverage_ratio = float(len(mapped_ok) / max(len(eligible_us), 1))
    gates.append(
        Gate(
            "G_SP500_TO_BDR_COVERAGE",
            coverage_ratio >= 0.80,
            f"mapped={len(mapped_ok)} eligible_us={len(eligible_us)} coverage={coverage_ratio:.6f}",
        )
    )

    us_raw = pd.read_parquet(IN_US_RAW).copy()
    us_raw["ticker"] = us_raw["ticker"].astype(str).str.upper().str.strip()
    us_raw["date"] = pd.to_datetime(us_raw["date"], errors="coerce")
    for c in ["open", "high", "low", "close", "adjusted_close"]:
        if c in us_raw.columns:
            us_raw[c] = pd.to_numeric(us_raw[c], errors="coerce")
        else:
            us_raw[c] = np.nan
    us_raw = us_raw.dropna(subset=["ticker", "date", "close"]).sort_values(["ticker", "date"]).reset_index(drop=True)
    us_raw = us_raw[us_raw["ticker"].isin(set(mapped_all["ticker"].tolist()))].copy()

    ptax_for_merge = pd.read_parquet(OUT_PTAX).copy()
    ptax_for_merge["date"] = pd.to_datetime(ptax_for_merge["date"], errors="coerce")
    b3_dates = pd.DataFrame({"date": pd.to_datetime(macro["date"], errors="coerce")}).dropna().drop_duplicates().sort_values("date")

    synth_parts: list[pd.DataFrame] = []
    for row in mapped_all.itertuples(index=False):
        t_us = str(row.ticker)
        t_bdr = str(row.ticker_bdr)
        ratio = float(row.parity_ratio) if pd.notna(row.parity_ratio) else 1.0
        venue = str(row.execution_venue)
        friction_one_way_rate = float(row.friction_one_way_rate) if pd.notna(row.friction_one_way_rate) else ORDER_COST_RATE_B3
        if ratio <= 0:
            ratio = 1.0

        tf = us_raw[us_raw["ticker"] == t_us][["date", "open", "high", "low", "close", "adjusted_close"]].copy()
        if tf.empty:
            continue

        merged = pd.merge_asof(
            b3_dates.sort_values("date"),
            tf.sort_values("date"),
            on="date",
            direction="backward",
        )
        first_trade = tf["date"].min()
        merged = merged[merged["date"] >= first_trade].copy()
        for c in ["open", "high", "low", "close", "adjusted_close"]:
            merged[c] = pd.to_numeric(merged[c], errors="coerce").ffill()

        merged = merged.merge(ptax_for_merge, on="date", how="left")
        merged["usdbrl_ptax"] = pd.to_numeric(merged["usdbrl_ptax"], errors="coerce").ffill().bfill()

        merged["open"] = merged["open"] * merged["usdbrl_ptax"] * ratio
        merged["high"] = merged["high"] * merged["usdbrl_ptax"] * ratio
        merged["low"] = merged["low"] * merged["usdbrl_ptax"] * ratio
        merged["close"] = merged["close"] * merged["usdbrl_ptax"] * ratio
        merged["adjusted_close"] = merged["adjusted_close"] * merged["usdbrl_ptax"] * ratio
        if venue == "US_DIRECT":
            penalty_factor = 1.0 - ORDER_COST_PENALTY_CROSS_BORDER
            merged["open"] = merged["open"] * penalty_factor
            merged["high"] = merged["high"] * penalty_factor
            merged["low"] = merged["low"] * penalty_factor
            merged["close"] = merged["close"] * penalty_factor
            merged["adjusted_close"] = merged["adjusted_close"] * penalty_factor

        merged["ticker"] = t_bdr
        merged["source_us_ticker"] = t_us
        merged["paridade_acao_bdr"] = str(row.paridade_acao_bdr)
        merged["execution_venue"] = venue
        merged["friction_one_way_rate"] = friction_one_way_rate
        merged["splits"] = 0.0
        merged["split_factor"] = 1.0
        merged["volume"] = 0
        synth_parts.append(
            merged[
                [
                    "ticker",
                    "source_us_ticker",
                    "date",
                    "open",
                    "high",
                    "low",
                    "close",
                    "adjusted_close",
                    "volume",
                    "splits",
                    "split_factor",
                    "usdbrl_ptax",
                    "paridade_acao_bdr",
                    "execution_venue",
                    "friction_one_way_rate",
                ]
            ].copy()
        )

    synth = pd.concat(synth_parts, ignore_index=True) if synth_parts else pd.DataFrame()
    if not synth.empty:
        synth["date"] = pd.to_datetime(synth["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        synth = synth.sort_values(["ticker", "date"]).reset_index(drop=True)
    OUT_BDR_SYNTH.parent.mkdir(parents=True, exist_ok=True)
    synth.to_parquet(OUT_BDR_SYNTH, index=False)
    artifacts.append(OUT_BDR_SYNTH)

    nan_close = int(synth["close"].isna().sum()) if not synth.empty else 999999
    gates.append(Gate("G_NO_NAN_CLOSE", nan_close == 0, f"nan_close={nan_close} rows={len(synth)}"))

    ticker_count = int(synth["ticker"].nunique()) if not synth.empty else 0
    gates.append(Gate("G_BDR_COUNT", ticker_count >= 490, f"ticker_count={ticker_count}"))

    # Retorno de sanidade: maioria absoluta dos pontos sem retorno absurdo.
    outlier_count = 0
    total_ret_points = 0
    if not synth.empty:
        for _, gdf in synth.groupby("ticker", sort=True):
            ret = np.log(gdf["close"] / gdf["close"].shift(1))
            ret = ret.replace([np.inf, -np.inf], np.nan).dropna()
            total_ret_points += int(len(ret))
            outlier_count += int((ret.abs() > 1.0).sum())
    outlier_ratio = float(outlier_count / max(total_ret_points, 1))
    gates.append(
        Gate(
            "G_SANITY_RETURNS",
            outlier_ratio <= 0.001,
            f"outlier_ratio={outlier_ratio:.6f} outliers={outlier_count} total={total_ret_points}",
        )
    )

    write_json(
        OUT_COVERAGE,
        {
            "eligible_us_after_blacklist": int(len(eligible_us)),
            "mapped_to_bdr": int(len(mapped_ok)),
            "us_direct_count": int(len(missing_map)),
            "total_included_count": int(len(mapped_all)),
            "mapping_coverage_ratio": coverage_ratio,
            "missing_bdr_count": int(len(missing_map)),
            "synth_ticker_count": ticker_count,
            "synth_rows": int(len(synth)),
            "ptax_missing_before_fill": ptax_missing_before,
            "ptax_missing_after_fill": ptax_missing_after,
            "return_outlier_ratio_abs_gt_1": outlier_ratio,
        },
    )
    artifacts.append(OUT_COVERAGE)

    ch_ok, ch_mode = append_changelog_idempotent(TRACEABILITY_LINE)
    gates.append(Gate("G_CHLOG_UPDATED", ch_ok, f"mode={ch_mode}"))

    # Draft manifest first (gate visibility in report).
    draft_manifest = {
        "task_id": TASK_ID,
        "run_id": RUN_ID,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "inputs_consumed": [
            IN_MACRO.relative_to(ROOT).as_posix(),
            IN_US_RAW.relative_to(ROOT).as_posix(),
            IN_US_UNIVERSE.relative_to(ROOT).as_posix(),
            IN_US_BLACKLIST.relative_to(ROOT).as_posix(),
        ],
        "outputs_produced": [OUT_SCRIPT.relative_to(ROOT).as_posix()]
        + [p.relative_to(ROOT).as_posix() for p in artifacts]
        + [OUT_REPORT.relative_to(ROOT).as_posix(), CHANGELOG_PATH.relative_to(ROOT).as_posix()],
        "hashes_sha256": {},
        "manifest_policy": "no_self_hash",
    }
    write_json(OUT_MANIFEST, draft_manifest)
    gates.append(Gate("Gx_HASH_MANIFEST_PRESENT", OUT_MANIFEST.exists(), f"path={OUT_MANIFEST.relative_to(ROOT).as_posix()}"))

    hash_targets_selfcheck = [OUT_SCRIPT] + artifacts + [CHANGELOG_PATH]
    hash_first = {p.relative_to(ROOT).as_posix(): sha256_file(p) for p in hash_targets_selfcheck}
    hash_second = {p.relative_to(ROOT).as_posix(): sha256_file(p) for p in hash_targets_selfcheck}
    mismatch = [k for k, v in hash_first.items() if hash_second.get(k) != v]
    gates.append(Gate("G_SHA256_INTEGRITY_SELF_CHECK", len(mismatch) == 0, f"mismatches={len(mismatch)}"))

    summary = {
        "ptax_rows": int(len(ptax_b3)),
        "b3_bdr_rows": int(len(b3_df)),
        "eligible_us": int(len(eligible_us)),
        "mapped_us_to_bdr": int(len(mapped_ok)),
        "us_direct_count": int(len(missing_map)),
        "total_included_count": int(len(mapped_all)),
        "synth_tickers": int(ticker_count),
        "synth_rows": int(len(synth)),
        "mapping_coverage_ratio": round(coverage_ratio, 6),
    }

    report_artifacts = artifacts + [OUT_REPORT, OUT_MANIFEST]
    report_text = render_report(gates=gates, retry_log=retry_log, artifacts=report_artifacts, summary=summary)
    OUT_REPORT.write_text(report_text, encoding="utf-8")
    artifacts.append(OUT_REPORT)

    # Final manifest must be last write.
    hash_targets_final = [OUT_SCRIPT] + artifacts + [CHANGELOG_PATH]
    hash_map_final = {p.relative_to(ROOT).as_posix(): sha256_file(p) for p in hash_targets_final}
    manifest = {
        "task_id": TASK_ID,
        "run_id": RUN_ID,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "inputs_consumed": draft_manifest["inputs_consumed"],
        "outputs_produced": [OUT_SCRIPT.relative_to(ROOT).as_posix()]
        + [p.relative_to(ROOT).as_posix() for p in artifacts]
        + [CHANGELOG_PATH.relative_to(ROOT).as_posix()],
        "hashes_sha256": hash_map_final,
        "manifest_policy": "no_self_hash",
    }
    write_json(OUT_MANIFEST, manifest)

    overall = all(g.passed for g in gates)
    print(f"HEADER: {TASK_ID}")
    print("STEP GATES:")
    for g in gates:
        print(f"- {'PASS' if g.passed else 'FAIL'} | {g.name} | {g.details}")
    print("RETRY LOG:")
    if retry_log:
        for item in retry_log:
            print(f"- {item}")
    else:
        print("- none")
    print("ARTIFACT LINKS:")
    for p in [OUT_SCRIPT] + artifacts + [OUT_MANIFEST]:
        print(f"- {p.relative_to(ROOT).as_posix()}")
    print(f"OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]")
    if not overall:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
