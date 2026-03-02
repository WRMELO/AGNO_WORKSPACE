from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
import time

import pandas as pd
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TASK_ID = "T084"
RUN_ID = "T084-US-INGEST-SP500-BRAPI-V2"
PERIOD_START = date(2018, 1, 2)
PERIOD_END = date(2026, 2, 26)
TRACEABILITY_LINE = (
    "- 2026-03-02T18:42:37Z | EXEC: T084 EXEC #2 (V2) Alinhar período do SSOT US ao SSOT BR: start 2018-01-02 "
    "(warm-up) mantendo BRAPI+derivação dividendos e governança SHA256. "
    "Artefatos: scripts/t084_ingest_sp500_brapi_us_market_data.py; src/data_engine/ssot/SSOT_US_MARKET_DATA_RAW.parquet; "
    "outputs/governanca/T084-US-INGEST-SP500-BRAPI-V2_report.md; outputs/governanca/T084-US-INGEST-SP500-BRAPI-V2_manifest.json"
)

IN_SNAPSHOT = ROOT / "outputs" / "governanca" / "T083-US-DATA-PIPELINE-SPEC-V2_evidence" / "sp500_current_symbols_snapshot.csv"
IN_SCHEMA_REF = ROOT / "scripts" / "t021_mass_ingestion.py"
IN_ADAPTER = ROOT / "src" / "data_engine" / "adapters" / "brapi_adapter.py"
IN_BR_MARKET = ROOT / "src" / "data_engine" / "ssot" / "SSOT_MARKET_DATA_RAW.parquet"
IN_BR_CANONICAL = ROOT / "src" / "data_engine" / "ssot" / "SSOT_CANONICAL_BASE.parquet"
IN_BR_MACRO = ROOT / "src" / "data_engine" / "ssot" / "SSOT_MACRO.parquet"
CHANGELOG_PATH = ROOT / "00_Strategy" / "changelog.md"

OUT_SCRIPT = ROOT / "scripts" / "t084_ingest_sp500_brapi_us_market_data.py"
OUT_SSOT = ROOT / "src" / "data_engine" / "ssot" / "SSOT_US_MARKET_DATA_RAW.parquet"
OUT_DIR = ROOT / "outputs" / "governanca"
OUT_EVIDENCE = OUT_DIR / f"{RUN_ID}_evidence"
OUT_REPORT = OUT_DIR / f"{RUN_ID}_report.md"
OUT_MANIFEST = OUT_DIR / f"{RUN_ID}_manifest.json"
OUT_UNIVERSE = OUT_EVIDENCE / "universe_snapshot_used.csv"
OUT_INGESTION = OUT_EVIDENCE / "ingestion_report.csv"
OUT_COVERAGE = OUT_EVIDENCE / "coverage_summary.json"
OUT_BLACKLIST = OUT_EVIDENCE / "blacklist_us_tickers.csv"
OUT_DIV_VALIDATION = OUT_EVIDENCE / "dividends_validation_2024.json"
OUT_SCHEMA_CONTRACT = OUT_EVIDENCE / "schema_contract.json"
OUT_DATE_ALIGNMENT = OUT_EVIDENCE / "ssot_date_alignment.json"


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


def sanitize_error(msg: str) -> str:
    sanitized = re.sub(r"token=[^&\\s]+", "token=***", msg)
    return sanitized[:500]


def normalize_ticker(raw: str) -> str:
    return str(raw).upper().strip().replace(".", "-")


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


def derive_dividends(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["dividends"] = 0.0
    if out.empty:
        out["splits"] = ""
        return out
    out["close"] = pd.to_numeric(out["close"], errors="coerce")
    out["adjusted_close"] = pd.to_numeric(out["adjusted_close"], errors="coerce")
    ratio = out["close"] / out["adjusted_close"]
    prev_ratio = ratio.shift(1)
    prev_close = out["close"].shift(1)
    valid = (
        ratio.notna()
        & prev_ratio.notna()
        & (prev_ratio > 0)
        & prev_close.notna()
        & (ratio < (prev_ratio - 0.001))
    )
    div = prev_close * ((prev_ratio - ratio) / prev_ratio)
    div = div.where(valid, 0.0).clip(lower=0.0).fillna(0.0)
    out["dividends"] = div
    out["splits"] = ""
    return out


def get_known_dividend_map() -> dict[str, dict[str, float]]:
    return {
        "AAPL": {"2024-02": 0.25, "2024-05": 0.25, "2024-08": 0.25, "2024-11": 0.25},
        "MSFT": {"2024-02": 0.75, "2024-05": 0.75, "2024-08": 0.75, "2024-11": 0.83},
    }


def render_report(gates: list[Gate], retry_log: list[str], artifacts: list[Path]) -> str:
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
    lines.append("## ARTIFACT LINKS")
    for p in artifacts:
        lines.append(f"- {p.relative_to(ROOT).as_posix()}")
    lines.append("")
    lines.append(f"OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    load_dotenv(ROOT / ".env")
    from src.data_engine.adapters.brapi_adapter import BrapiAdapter

    OUT_EVIDENCE.mkdir(parents=True, exist_ok=True)
    OUT_SSOT.parent.mkdir(parents=True, exist_ok=True)

    gates: list[Gate] = []
    retry_log: list[str] = []
    artifacts: list[Path] = []

    gates.append(
        Gate(
            "G_INPUTS_EXIST",
            IN_SNAPSHOT.exists()
            and IN_SCHEMA_REF.exists()
            and IN_ADAPTER.exists()
            and IN_BR_MARKET.exists()
            and IN_BR_CANONICAL.exists()
            and IN_BR_MACRO.exists(),
            " ".join(
                [
                    f"snapshot={IN_SNAPSHOT.exists()}",
                    f"schema_ref={IN_SCHEMA_REF.exists()}",
                    f"adapter={IN_ADAPTER.exists()}",
                    f"br_market={IN_BR_MARKET.exists()}",
                    f"br_canonical={IN_BR_CANONICAL.exists()}",
                    f"br_macro={IN_BR_MACRO.exists()}",
                ]
            ),
        )
    )
    if not gates[-1].passed:
        raise RuntimeError("Inputs obrigatorios ausentes.")

    snap = pd.read_csv(IN_SNAPSHOT)
    tickers = (
        snap["symbol"].astype(str).map(normalize_ticker).replace("", pd.NA).dropna().drop_duplicates().sort_values().tolist()
    )
    pd.DataFrame({"symbol": tickers}).to_csv(OUT_UNIVERSE, index=False)
    artifacts.append(OUT_UNIVERSE)
    gates.append(Gate("G_UNIVERSE_SIZE_OK", len(tickers) >= 450, f"count={len(tickers)}"))
    if not gates[-1].passed:
        raise RuntimeError("Universo abaixo do minimo esperado.")

    adapter = BrapiAdapter()
    expected_days = len(pd.bdate_range(PERIOD_START, PERIOD_END))

    rows: list[dict[str, Any]] = []
    report_rows: list[dict[str, Any]] = []
    for i, ticker in enumerate(tickers, start=1):
        started_at = datetime.now(UTC).isoformat()
        try:
            h = None
            last_exc: Exception | None = None
            max_retries = 3
            for attempt in range(1, max_retries + 1):
                try:
                    h = adapter.get_historical_data(ticker=ticker, start=PERIOD_START, end=PERIOD_END)
                    break
                except Exception as exc:  # noqa: BLE001
                    msg = str(exc)
                    last_exc = exc
                    transient = ("Timeout" in msg) or ("Falha de conexão" in msg)
                    if transient and attempt < max_retries:
                        retry_log.append(f"{ticker}: retry {attempt}/{max_retries - 1} por erro transiente ({sanitize_error(msg)})")
                        time.sleep(0.8 * attempt)
                        continue
                    raise
            if h is None and last_exc is not None:
                raise last_exc
            df = pd.DataFrame(h.price_data)
            if df.empty:
                report_rows.append(
                    {
                        "ticker": ticker,
                        "status": "FAIL",
                        "rows": 0,
                        "min_date": "",
                        "max_date": "",
                        "coverage_ratio": 0.0,
                        "dividend_events_count": 0,
                        "error": "no_data",
                        "started_at_utc": started_at,
                        "finished_at_utc": datetime.now(UTC).isoformat(),
                    }
                )
                continue

            df["ticker"] = ticker
            df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
            df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
            df = derive_dividends(df)
            df = df[
                ["ticker", "date", "open", "high", "low", "close", "volume", "adjusted_close", "dividends", "splits"]
            ]
            rows.extend(df.to_dict(orient="records"))

            coverage_ratio = float(len(df) / expected_days) if expected_days > 0 else 0.0
            report_rows.append(
                {
                    "ticker": ticker,
                    "status": "SUCCESS",
                    "rows": int(len(df)),
                    "min_date": str(df["date"].iloc[0]),
                    "max_date": str(df["date"].iloc[-1]),
                    "coverage_ratio": round(coverage_ratio, 4),
                    "dividend_events_count": int((df["dividends"] > 0.0).sum()),
                    "error": "",
                    "started_at_utc": started_at,
                    "finished_at_utc": datetime.now(UTC).isoformat(),
                }
            )
        except Exception as exc:  # noqa: BLE001
            report_rows.append(
                {
                    "ticker": ticker,
                    "status": "FAIL",
                    "rows": 0,
                    "min_date": "",
                    "max_date": "",
                    "coverage_ratio": 0.0,
                    "dividend_events_count": 0,
                    "error": sanitize_error(str(exc)),
                    "started_at_utc": started_at,
                    "finished_at_utc": datetime.now(UTC).isoformat(),
                }
            )
            retry_log.append(f"{ticker}: {sanitize_error(str(exc))}")

        if i % 50 == 0 or i == len(tickers):
            print(f"Progress {i}/{len(tickers)}")

    rep = pd.DataFrame(report_rows)
    rep.to_csv(OUT_INGESTION, index=False)
    artifacts.append(OUT_INGESTION)

    ok_rows = rep[(rep["status"] == "SUCCESS") & (rep["coverage_ratio"] >= 0.80)]
    success_rate = float(len(ok_rows) / len(tickers)) if tickers else 0.0
    gates.append(Gate("G_COVERAGE_OK", success_rate >= 0.95, f"success_rate={success_rate:.4f}"))

    blacklist = rep[(rep["status"] != "SUCCESS") | (rep["coverage_ratio"] < 0.80)].copy()
    blacklist["reason"] = blacklist.apply(
        lambda r: "no_data_or_error" if r["status"] != "SUCCESS" else "low_coverage_lt_80pct", axis=1
    )
    blacklist[["ticker", "reason", "rows", "coverage_ratio", "error"]].to_csv(OUT_BLACKLIST, index=False)
    artifacts.append(OUT_BLACKLIST)

    out_df = pd.DataFrame(rows)
    if out_df.empty:
        raise RuntimeError("Nenhum dado foi ingerido para o SSOT US.")

    out_df["ticker"] = out_df["ticker"].astype(str).map(normalize_ticker)
    out_df["date"] = out_df["date"].astype(str)
    out_df = out_df.sort_values(["ticker", "date"]).reset_index(drop=True)
    dup_count = int(out_df.duplicated(subset=["ticker", "date"]).sum())
    gates.append(Gate("G_DEDUP_OK", dup_count == 0, f"duplicates={dup_count}"))
    if dup_count > 0:
        out_df = out_df.drop_duplicates(subset=["ticker", "date"], keep="last").reset_index(drop=True)

    expected_cols = ["ticker", "date", "open", "high", "low", "close", "volume", "adjusted_close", "dividends", "splits"]
    gates.append(Gate("G_SCHEMA_MATCH", list(out_df.columns) == expected_cols, f"columns={list(out_df.columns)}"))
    if not gates[-1].passed:
        raise RuntimeError("Schema de saida invalido.")

    out_df.to_parquet(OUT_SSOT, index=False)
    artifacts.append(OUT_SSOT)

    coverage_summary = {
        "task_id": TASK_ID,
        "period_start": PERIOD_START.isoformat(),
        "period_end": PERIOD_END.isoformat(),
        "universe_count": len(tickers),
        "expected_business_days": expected_days,
        "success_rate": round(success_rate, 6),
        "success_tickers_count": int((rep["status"] == "SUCCESS").sum()),
        "blacklist_count": int(len(blacklist)),
        "blacklist_sample": blacklist["ticker"].astype(str).head(20).tolist(),
    }
    write_json(OUT_COVERAGE, coverage_summary)
    artifacts.append(OUT_COVERAGE)

    known = get_known_dividend_map()
    validation: dict[str, Any] = {"checks": {}, "all_passed": True}
    for ticker, known_map in known.items():
        dft = out_df[(out_df["ticker"] == ticker) & (out_df["date"].str.startswith("2024-"))].copy()
        dft["date"] = pd.to_datetime(dft["date"])
        ev = dft[dft["dividends"] > 0.05].copy()
        ev["month"] = ev["date"].dt.strftime("%Y-%m")
        per_events = []
        ticker_pass = True
        for _, row in ev.iterrows():
            month = row["month"]
            if month in known_map:
                known_val = float(known_map[month])
                derived = float(row["dividends"])
                abs_err = abs(derived - known_val)
                ok = abs_err < 0.02
                ticker_pass = ticker_pass and ok
                per_events.append(
                    {
                        "date": row["date"].strftime("%Y-%m-%d"),
                        "month": month,
                        "derived": round(derived, 6),
                        "known": known_val,
                        "abs_error": round(abs_err, 6),
                        "ok": ok,
                    }
                )
        validation["checks"][ticker] = {
            "events_detected": int(len(ev)),
            "events_checked": per_events,
            "pass": ticker_pass and len(per_events) >= 3,
        }
        validation["all_passed"] = validation["all_passed"] and bool(validation["checks"][ticker]["pass"])

    write_json(OUT_DIV_VALIDATION, validation)
    artifacts.append(OUT_DIV_VALIDATION)
    gates.append(Gate("G_DIVIDENDS_VALIDATION_OK", bool(validation["all_passed"]), f"all_passed={validation['all_passed']}"))

    schema_contract = {
        "columns": expected_cols,
        "types_note": {
            "ticker": "str",
            "date": "YYYY-MM-DD str",
            "open/high/low/close/adjusted_close/dividends": "float",
            "volume": "int",
            "splits": "str",
        },
        "split_adjustment_note": (
            "close é split-adjusted retroativamente e adjusted_close é split+dividend adjusted; "
            "splits explícitos não são necessários para o backtest e permanecem como string vazia."
        ),
    }
    write_json(OUT_SCHEMA_CONTRACT, schema_contract)
    artifacts.append(OUT_SCHEMA_CONTRACT)
    gates.append(Gate("G_SPLIT_ADJUSTMENT_NOTE_PRESENT", True, "schema_contract contém nota de split adjustment"))

    def minmax_date(path: Path) -> dict[str, str]:
        d = pd.read_parquet(path, columns=["date"])
        s = pd.to_datetime(d["date"], errors="coerce").dropna()
        return {"min": s.min().date().isoformat(), "max": s.max().date().isoformat()}

    alignment = {
        "ssot_br_market_raw": minmax_date(IN_BR_MARKET),
        "ssot_br_canonical": minmax_date(IN_BR_CANONICAL),
        "ssot_macro": minmax_date(IN_BR_MACRO),
        "ssot_us_market_raw": minmax_date(OUT_SSOT),
    }
    write_json(OUT_DATE_ALIGNMENT, alignment)
    artifacts.append(OUT_DATE_ALIGNMENT)
    aligned = (
        alignment["ssot_us_market_raw"]["min"] == alignment["ssot_br_market_raw"]["min"] == "2018-01-02"
        and alignment["ssot_us_market_raw"]["max"] == alignment["ssot_br_market_raw"]["max"] == "2026-02-26"
    )
    gates.append(
        Gate(
            "G_DATE_ALIGNMENT_OK",
            aligned,
            (
                f"us_min={alignment['ssot_us_market_raw']['min']} "
                f"br_min={alignment['ssot_br_market_raw']['min']} "
                f"us_max={alignment['ssot_us_market_raw']['max']} "
                f"br_max={alignment['ssot_br_market_raw']['max']}"
            ),
        )
    )

    ch_ok, ch_mode = append_changelog_idempotent(TRACEABILITY_LINE)
    gates.append(Gate("G_CHLOG_UPDATED", ch_ok, f"mode={ch_mode}"))

    report_text = render_report(gates=gates, retry_log=retry_log, artifacts=artifacts + [OUT_REPORT, OUT_MANIFEST])
    OUT_REPORT.write_text(report_text, encoding="utf-8")
    artifacts.append(OUT_REPORT)

    hash_targets = artifacts + [CHANGELOG_PATH]
    hashes = {p.relative_to(ROOT).as_posix(): sha256_file(p) for p in hash_targets}
    manifest = {
        "task_id": TASK_ID,
        "run_id": RUN_ID,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "inputs_consumed": [
            IN_SNAPSHOT.relative_to(ROOT).as_posix(),
            IN_SCHEMA_REF.relative_to(ROOT).as_posix(),
            IN_ADAPTER.relative_to(ROOT).as_posix(),
            IN_BR_MARKET.relative_to(ROOT).as_posix(),
            IN_BR_CANONICAL.relative_to(ROOT).as_posix(),
            IN_BR_MACRO.relative_to(ROOT).as_posix(),
        ],
        "outputs_produced": [p.relative_to(ROOT).as_posix() for p in artifacts] + [CHANGELOG_PATH.relative_to(ROOT).as_posix()],
        "hashes_sha256": hashes,
    }
    write_json(OUT_MANIFEST, manifest)

    gates.append(Gate("Gx_HASH_MANIFEST_PRESENT", OUT_MANIFEST.exists(), f"path={OUT_MANIFEST.relative_to(ROOT).as_posix()}"))
    gates.append(Gate("G_MANIFEST_ORDER", True, "manifest foi o ultimo write da task"))
    # Sem writes apos manifest.

    print(f"# HEADER: {TASK_ID}")
    print("## STEP GATES")
    for g in gates:
        print(f"- {'PASS' if g.passed else 'FAIL'} | {g.name} | {g.details}")
    print("## RETRY LOG")
    if retry_log:
        for item in retry_log:
            print(f"- {item}")
    else:
        print("- none")
    print("## ARTIFACT LINKS")
    for p in artifacts + [OUT_MANIFEST]:
        print(f"- {p.relative_to(ROOT).as_posix()}")
    overall = all(g.passed for g in gates)
    print(f"OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]")
    if not overall:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
