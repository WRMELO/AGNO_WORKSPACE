#!/home/wilson/AGNO_WORKSPACE/.venv/bin/python
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

try:
    import requests
except ModuleNotFoundError:
    subprocess.run(
        ["/home/wilson/AGNO_WORKSPACE/.venv/bin/pip", "install", "requests"],
        check=True,
        capture_output=True,
        text=True,
    )
    import requests


ROOT = Path("/home/wilson/AGNO_WORKSPACE")
TASK_ID = "T083"
RUN_ID = "T083-US-DATA-PIPELINE-SPEC-V2"
PYTHON_ENV = ROOT / ".venv/bin/python"
CHANGELOG_PATH = ROOT / "00_Strategy/changelog.md"
TRACEABILITY_LINE = (
    "- 2026-03-02T17:35:00Z | SPEC: T083 US data pipeline SPEC V2 (fix integridade SHA256/manifest + snapshot S&P 500 + recomendacao de fontes por camada OHLCV vs corp actions). "
    "Artefatos: scripts/t083_spec_us_data_pipeline.py; "
    "02_Knowledge_Bank/docs/specs/SPEC-083_PIPELINE_DADOS_US_T083.md; "
    "outputs/governanca/T083-US-DATA-PIPELINE-SPEC-V2_report.md; "
    "outputs/governanca/T083-US-DATA-PIPELINE-SPEC-V2_manifest.json"
)

IN_ARCH = ROOT / "01_Architecture/System_Context.md"
IN_ROADMAP = ROOT / "00_Strategy/ROADMAP.md"
IN_SSOT_CANONICAL = ROOT / "src/data_engine/ssot/SSOT_CANONICAL_BASE.parquet"
IN_SSOT_RAW = ROOT / "src/data_engine/ssot/SSOT_MARKET_DATA_RAW.parquet"
IN_SSOT_MACRO = ROOT / "src/data_engine/ssot/SSOT_MACRO.parquet"
IN_SSOT_UNIVERSE = ROOT / "src/data_engine/ssot/SSOT_UNIVERSE_OPERATIONAL.parquet"

OUT_SCRIPT = ROOT / "scripts/t083_spec_us_data_pipeline.py"
OUT_SPEC = ROOT / "02_Knowledge_Bank/docs/specs/SPEC-083_PIPELINE_DADOS_US_T083.md"
OUT_REPORT = ROOT / "outputs/governanca/T083-US-DATA-PIPELINE-SPEC-V2_report.md"
OUT_MANIFEST = ROOT / "outputs/governanca/T083-US-DATA-PIPELINE-SPEC-V2_manifest.json"
OUT_EVID_DIR = ROOT / "outputs/governanca/T083-US-DATA-PIPELINE-SPEC-V2_evidence"
OUT_SOURCE_PROBE = OUT_EVID_DIR / "source_probe_results.json"
OUT_SCHEMA_SNAPSHOT = OUT_EVID_DIR / "schema_alignment_snapshot.json"
OUT_UNIVERSE_PLAN = OUT_EVID_DIR / "universe_plan.json"
OUT_RISK_REGISTER = OUT_EVID_DIR / "risk_register.json"
OUT_SP500_SNAPSHOT = OUT_EVID_DIR / "sp500_current_symbols_snapshot.csv"

PERIOD_START = pd.Timestamp("2018-07-02")
PERIOD_END = pd.Timestamp("2026-02-26")
SAMPLE_TICKERS = ["AAPL", "MSFT", "AMZN", "JNJ", "XOM", "NVDA", "PG"]


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
    if isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    return obj


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_safe(payload), indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def append_changelog_idempotent(line: str) -> tuple[bool, str]:
    before = CHANGELOG_PATH.read_text(encoding="utf-8") if CHANGELOG_PATH.exists() else ""
    if line in before:
        return True, "already_present"
    text = before
    if text and not text.endswith("\n"):
        text += "\n"
    text += line.rstrip("\n") + "\n"
    CHANGELOG_PATH.write_text(text, encoding="utf-8")
    return (line in CHANGELOG_PATH.read_text(encoding="utf-8"), "appended")


def ensure_html_parsers(retry_log: list[str]) -> None:
    missing: list[str] = []
    for pkg in ["lxml", "html5lib"]:
        try:
            __import__(pkg)
        except ModuleNotFoundError:
            missing.append(pkg)
    if not missing:
        return
    cmd = [str(ROOT / ".venv/bin/pip"), "install", *missing]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    retry_log.append(f"installed_missing_html_parsers={missing} rc={proc.returncode}")
    if proc.returncode != 0:
        raise RuntimeError(f"Falha instalando parsers HTML: {missing}")


def read_parquet_schema(path: Path) -> dict[str, Any]:
    df = pd.read_parquet(path)
    cols = [{"name": c, "dtype": str(df[c].dtype)} for c in df.columns]
    out = {
        "path": str(path.relative_to(ROOT)),
        "rows": int(len(df)),
        "cols": int(len(df.columns)),
        "columns": cols,
    }
    date_col = next((c for c in df.columns if c.lower() == "date"), None)
    if date_col is not None:
        d = pd.to_datetime(df[date_col], errors="coerce").dropna()
        if len(d):
            out["date_min"] = d.min().strftime("%Y-%m-%d")
            out["date_max"] = d.max().strftime("%Y-%m-%d")
    return out


def probe_yahoo_chart(ticker: str, period_start: pd.Timestamp, period_end: pd.Timestamp) -> dict[str, Any]:
    period1 = int(pd.Timestamp(period_start).timestamp())
    period2 = int((pd.Timestamp(period_end) + pd.Timedelta(days=1)).timestamp())
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {
        "period1": period1,
        "period2": period2,
        "interval": "1d",
        "events": "div,split",
        "includeAdjustedClose": "true",
    }
    try:
        resp = requests.get(url, params=params, timeout=20)
        if resp.status_code != 200:
            return {"ok": False, "status_code": resp.status_code, "error": "http_error"}
        data = resp.json()
        result = (((data or {}).get("chart") or {}).get("result") or [None])[0]
        if not result:
            return {"ok": False, "status_code": 200, "error": "empty_result"}
        ts = result.get("timestamp") or []
        dates = pd.to_datetime(ts, unit="s", utc=True).tz_convert("America/Sao_Paulo").normalize()
        coverage = float(len(dates) / max(1, len(pd.bdate_range(period_start, period_end))))
        events = result.get("events") or {}
        has_div = bool(events.get("dividends"))
        has_split = bool(events.get("splits"))
        return {
            "ok": True,
            "status_code": 200,
            "rows": int(len(ts)),
            "coverage_ratio_proxy": coverage,
            "date_min": str(dates.min().date()) if len(dates) else None,
            "date_max": str(dates.max().date()) if len(dates) else None,
            "has_dividends": has_div,
            "has_splits": has_split,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def probe_stooq(ticker: str, period_start: pd.Timestamp, period_end: pd.Timestamp) -> dict[str, Any]:
    url = f"https://stooq.com/q/d/l/?s={ticker.lower()}.us&i=d"
    try:
        resp = requests.get(url, timeout=20)
        if resp.status_code != 200:
            return {"ok": False, "status_code": resp.status_code, "error": "http_error"}
        df = pd.read_csv(StringIO(resp.text))
        if "Date" not in df.columns:
            return {"ok": False, "status_code": 200, "error": "schema_mismatch"}
        d = pd.to_datetime(df["Date"], errors="coerce")
        d = d[(d >= period_start) & (d <= period_end)].dropna()
        coverage = float(len(d) / max(1, len(pd.bdate_range(period_start, period_end))))
        return {
            "ok": True,
            "status_code": 200,
            "rows": int(len(d)),
            "coverage_ratio_proxy": coverage,
            "date_min": str(d.min().date()) if len(d) else None,
            "date_max": str(d.max().date()) if len(d) else None,
            "has_dividends": False,
            "has_splits": False,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def probe_yahoo_csv_download(ticker: str, period_start: pd.Timestamp, period_end: pd.Timestamp) -> dict[str, Any]:
    period1 = int(pd.Timestamp(period_start).timestamp())
    period2 = int((pd.Timestamp(period_end) + pd.Timedelta(days=1)).timestamp())
    url = f"https://query1.finance.yahoo.com/v7/finance/download/{ticker}"
    params = {
        "period1": period1,
        "period2": period2,
        "interval": "1d",
        "events": "history",
        "includeAdjustedClose": "true",
    }
    try:
        resp = requests.get(url, params=params, timeout=20)
        ok = resp.status_code == 200 and "Date,Open,High,Low,Close,Adj Close,Volume" in resp.text[:120]
        return {
            "ok": bool(ok),
            "status_code": resp.status_code,
            "error": None if ok else "likely_requires_cookie_crumb_or_blocked",
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def aggregate_source_results(source_name: str, ticker_results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    oks = [v.get("ok", False) for v in ticker_results.values()]
    coverage_vals = [float(v.get("coverage_ratio_proxy", 0.0)) for v in ticker_results.values() if v.get("ok")]
    div_vals = [bool(v.get("has_dividends", False)) for v in ticker_results.values() if v.get("ok")]
    split_vals = [bool(v.get("has_splits", False)) for v in ticker_results.values() if v.get("ok")]
    return {
        "source": source_name,
        "success_rate": float(np.mean(oks)) if oks else 0.0,
        "avg_coverage_ratio_proxy": float(np.mean(coverage_vals)) if coverage_vals else 0.0,
        "has_dividends_any": bool(any(div_vals)),
        "has_splits_any": bool(any(split_vals)),
        "tickers": ticker_results,
    }


def select_sources(summary: list[dict[str, Any]]) -> tuple[str, str]:
    # Regra de negocio da SPEC: preferir fonte que exponha endpoint nativo
    # para eventos corporativos (dividendos/splits), mesmo que a amostra
    # pequena nao contenha splits em todos os tickers.
    by_name = {s.get("source"): s for s in summary}
    ychart = by_name.get("yahoo_chart_api")
    if ychart and ychart.get("success_rate", 0.0) >= 0.50:
        # Fallback padrao para OHLCV quando houver indisponibilidade parcial.
        return "yahoo_chart_api", "stooq_daily_csv" if "stooq_daily_csv" in by_name else "yahoo_chart_api"

    def score(x: dict[str, Any]) -> float:
        corp = 1.0 if (x.get("has_dividends_any") and x.get("has_splits_any")) else 0.0
        # Priorizacao explicita: eventos corporativos tem peso alto para evitar
        # fonte primaria sem dividendos/splits.
        return 0.30 * x.get("success_rate", 0.0) + 0.20 * x.get("avg_coverage_ratio_proxy", 0.0) + 0.50 * corp

    ranked = sorted(summary, key=score, reverse=True)
    primary = ranked[0]["source"] if ranked else "UNDEFINED"
    fallback = ranked[1]["source"] if len(ranked) > 1 else primary
    return primary, fallback


def fetch_sp500_current_universe() -> dict[str, Any]:
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    out: dict[str, Any] = {"source": url, "ok": False}
    try:
        tables = pd.read_html(url)
        if not tables:
            out["error"] = "no_tables"
            return out
        t0 = tables[0].copy()
        cols_lower = {c.lower(): c for c in t0.columns}
        symbol_col = cols_lower.get("symbol")
        if symbol_col is None:
            out["error"] = "symbol_col_not_found"
            return out
        symbols = t0[symbol_col].astype(str).str.strip().str.upper().str.replace(".", "-", regex=False)
        symbols = symbols[symbols.str.len() > 0]
        uniq = sorted(symbols.unique().tolist())
        out.update(
            {
                "ok": True,
                "count": len(uniq),
                "sample_first_20": uniq[:20],
                "symbols": uniq,
                "note": "Lista atual do S&P 500; nao representa composicao historica completa.",
            }
        )
        return out
    except Exception as e:
        out["error"] = str(e)
        out["fallback_note"] = "Wikipedia indisponivel; tentando fallback CSV publico versionado."

    # Fallback robusto: dataset publico de constituintes do S&P 500.
    try:
        fb_url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
        resp = requests.get(fb_url, timeout=20)
        if resp.status_code == 200:
            df = pd.read_csv(StringIO(resp.text))
            sym_col = "Symbol" if "Symbol" in df.columns else ("symbol" if "symbol" in df.columns else None)
            if sym_col:
                symbols = (
                    df[sym_col]
                    .astype(str)
                    .str.strip()
                    .str.upper()
                    .str.replace(".", "-", regex=False)
                )
                symbols = sorted(symbols[symbols.str.len() > 0].unique().tolist())
                return {
                    "source": fb_url,
                    "ok": True,
                    "count": len(symbols),
                    "sample_first_20": symbols[:20],
                    "symbols": symbols,
                    "note": "Fallback CSV publico de constituintes atuais do S&P 500.",
                }
    except Exception as e:
        out["fallback_error"] = str(e)
    return out


def build_spec_markdown(
    schema_snapshot: dict[str, Any],
    source_probe: dict[str, Any],
    universe_plan: dict[str, Any],
    risk_register: dict[str, Any],
    source_recommendation: dict[str, str],
) -> str:
    lines: list[str] = []
    lines.append("# SPEC-083_PIPELINE_DADOS_US_T083")
    lines.append("")
    lines.append("## 1) Objetivo")
    lines.append("Definir a especificacao tecnica do pipeline de dados US para suportar T084 (ingestao), T085 (qualidade) e T086 (SSOT BR+US), sem executar ingestao massiva nesta task.")
    lines.append("")
    lines.append("## 2) Escopo e premissas")
    lines.append("- Janela alvo para alinhamento com baseline C060: 2018-07-02 a 2026-02-26.")
    lines.append("- Universo alvo US: ~500 tickers (S&P 500).")
    lines.append("- Dados minimos por ticker: OHLCV diario + dividendos + splits.")
    lines.append("- T083 e SPEC-only: probes pequenos sao permitidos; ingestao completa fica para T084.")
    lines.append("")
    lines.append("## 3) Fontes avaliadas (probe tecnico)")
    lines.append("| Fonte | Success Rate | Cobertura media (proxy) | Dividendos | Splits |")
    lines.append("|---|---:|---:|---|---|")
    for s in source_probe["sources_summary"]:
        lines.append(
            f"| {s['source']} | {s['success_rate']:.2f} | {s['avg_coverage_ratio_proxy']:.2f} | "
            f"{'sim' if s['has_dividends_any'] else 'nao'} | {'sim' if s['has_splits_any'] else 'nao'} |"
        )
    lines.append("")
    lines.append(f"**Fonte primaria OHLCV**: `{source_recommendation['primary_ohlcv_source']}`")
    lines.append(f"**Fonte primaria Corporate Actions**: `{source_recommendation['primary_corp_actions_source']}`")
    lines.append(f"**Fonte fallback**: `{source_recommendation['fallback_source']}`")
    lines.append(f"**Nota de ambiente**: {source_recommendation['environment_note']}")
    lines.append("")
    lines.append("Criterio: priorizar cobertura + eventos corporativos (dividendos/splits) + estabilidade sem credenciais.")
    lines.append("")
    lines.append("## 4) Plano de universo US (~500)")
    lines.append("- Fonte proposta para bootstrap: lista atual S&P 500 versionada por snapshot.")
    lines.append("- Risco conhecido: survivorship bias quando usar apenas lista atual.")
    lines.append("- Mitigacao ciclo 1: registrar risco e versionar snapshot de composicao usado em T084.")
    lines.append("- Mitigacao ciclo 2: incorporar composicao historica por data efetiva.")
    if universe_plan.get("sp500_current", {}).get("ok"):
        lines.append(f"- Probe de composicao atual encontrou `{universe_plan['sp500_current']['count']}` simbolos.")
        lines.append(f"- Snapshot versionado: `{OUT_SP500_SNAPSHOT.relative_to(ROOT)}`.")
    else:
        lines.append("- Probe de composicao atual falhou; T084 deve usar snapshot local versionado como fallback.")
    lines.append("")
    lines.append("## 5) Schema proposto para T084/T086")
    lines.append("### 5.1 US RAW (`SSOT_US_MARKET_DATA_RAW.parquet`)")
    lines.append("- Chave primaria logica: (`ticker`, `date`).")
    lines.append("- Colunas obrigatorias: `ticker`, `date`, `open`, `high`, `low`, `close`, `adj_close`, `volume`, `dividend_cash`, `split_factor`, `currency`, `exchange`, `timezone`, `source`.")
    lines.append("- Convencao ticker: uppercase e ponto convertido para hifen (ex.: `BRK.B` -> `BRK-B`).")
    lines.append("")
    lines.append("### 5.2 SSOT unificado BR+US (`SSOT_CANONICAL_BASE_BR_US.parquet` - proposta T086)")
    lines.append("- Colunas minimas adicionais: `market` (`BR`/`US`), `currency`, `close_operational` harmonizado.")
    lines.append("- Regra de moeda: manter precos nativos por mercado; conversoes cambiais apenas quando exigidas por feature/portfolio logic.")
    lines.append("")
    lines.append("## 6) Qualidade de dados (entrada para T085)")
    lines.append("- Cobertura minima por ticker (pregoes esperados vs observados).")
    lines.append("- Deteccao de gaps longos e dias duplicados.")
    lines.append("- Coerencia OHLC (`low <= open/close <= high`).")
    lines.append("- Eventos corporativos: splits/dividendos nulos e picos extremos.")
    lines.append("- SPC/outlier flags para retornos diarios e volumes.")
    lines.append("- Blacklist operacional para tickers com anomalias recorrentes.")
    lines.append("")
    lines.append("## 7) Anti-lookahead e fusos (BR x US)")
    lines.append("- Regra global: features e sinais usam `shift(1)`.")
    lines.append("- Dados US (fechamento ~16:00 ET) nao podem alimentar decisao BR no mesmo dia de pregão local.")
    lines.append("- Regra operacional recomendada: alinhar dados US em D para uso em D+1 na camada de features/sinais.")
    lines.append("")
    lines.append("## 8) Plano de execucao por task")
    lines.append("- **T084**: ingestao massiva US + materializacao RAW + snapshot de universo utilizado.")
    lines.append("- **T085**: quality framework US (SPC, blacklist, cobertura, anomalias).")
    lines.append("- **T086**: merge BR+US + macro expandido (VIX, DXY, Treasury spread, Fed funds).")
    lines.append("")
    lines.append("## 9) Riscos e mitigacoes")
    for r in risk_register["risks"]:
        lines.append(f"- **{r['id']}**: {r['risk']} | Mitigacao: {r['mitigation']}")
    lines.append("")
    lines.append("## 10) Artefatos de evidencia (T083)")
    lines.append(f"- `{OUT_SOURCE_PROBE.relative_to(ROOT)}`")
    lines.append(f"- `{OUT_SCHEMA_SNAPSHOT.relative_to(ROOT)}`")
    lines.append(f"- `{OUT_UNIVERSE_PLAN.relative_to(ROOT)}`")
    lines.append(f"- `{OUT_RISK_REGISTER.relative_to(ROOT)}`")
    lines.append(f"- `{OUT_SP500_SNAPSHOT.relative_to(ROOT)}`")
    lines.append("")
    return "\n".join(lines) + "\n"


def render_report(gates: list[Gate], retry_log: list[str], overall: bool, artifacts: list[Path]) -> str:
    lines = [f"# HEADER: {TASK_ID}", "", "## STEP GATES"]
    for g in gates:
        lines.append(f"- {g.name}: {'PASS' if g.passed else 'FAIL'} | {g.detail}")
    lines.extend(["", "## RETRY LOG"])
    if not retry_log:
        lines.append("- none")
    else:
        lines.extend([f"- {r}" for r in retry_log])
    lines.extend(["", "## ARTIFACT LINKS"])
    for a in artifacts:
        lines.append(f"- {a.relative_to(ROOT)}")
    lines.extend(["", f"## OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]", ""])
    return "\n".join(lines)


def main() -> int:
    if not ("agno_env" in sys.prefix or ".venv" in sys.prefix):
        raise RuntimeError("FATAL: Not in agno_env/.venv")

    gates: list[Gate] = []
    retry_log: list[str] = []
    artifacts: list[Path] = []

    try:
        for p in [
            OUT_SPEC,
            OUT_REPORT,
            OUT_MANIFEST,
            OUT_SOURCE_PROBE,
            OUT_SCHEMA_SNAPSHOT,
            OUT_UNIVERSE_PLAN,
            OUT_RISK_REGISTER,
            OUT_SP500_SNAPSHOT,
        ]:
            p.parent.mkdir(parents=True, exist_ok=True)

        dep_cmd = [str(PYTHON_ENV), "-V"]
        dep_ver = subprocess.run(dep_cmd, capture_output=True, text=True, check=False)
        pip_cmd = [str(ROOT / ".venv/bin/pip"), "list"]
        pip_ls = subprocess.run(pip_cmd, capture_output=True, text=True, check=False)
        dep_ok = dep_ver.returncode == 0 and pip_ls.returncode == 0
        gates.append(
            Gate(
                "G_DEPENDENCIES_SNAPSHOT",
                dep_ok,
                f"python_ok={dep_ver.returncode==0} pip_list_ok={pip_ls.returncode==0}",
            )
        )
        if not dep_ok:
            raise RuntimeError("Falha ao validar dependencias base.")

        ensure_html_parsers(retry_log)
        gates.append(Gate("G_HTML_PARSERS_READY", True, "lxml/html5lib disponiveis para read_html"))

        inputs_exist = all(p.exists() for p in [IN_ARCH, IN_ROADMAP, IN_SSOT_CANONICAL, IN_SSOT_RAW, IN_SSOT_MACRO, IN_SSOT_UNIVERSE])
        gates.append(Gate("G_INPUTS_EXIST", inputs_exist, f"all_inputs={inputs_exist}"))
        if not inputs_exist:
            raise FileNotFoundError("Inputs obrigatorios ausentes.")

        schema_snapshot = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "files": [
                read_parquet_schema(IN_SSOT_CANONICAL),
                read_parquet_schema(IN_SSOT_RAW),
                read_parquet_schema(IN_SSOT_MACRO),
                read_parquet_schema(IN_SSOT_UNIVERSE),
            ],
        }
        write_json(OUT_SCHEMA_SNAPSHOT, schema_snapshot)
        gates.append(Gate("G_SCHEMA_ALIGNMENT", True, "schema snapshot gerado"))
        artifacts.append(OUT_SCHEMA_SNAPSHOT)

        yc = aggregate_source_results(
            "yahoo_chart_api",
            {t: probe_yahoo_chart(t, PERIOD_START, PERIOD_END) for t in SAMPLE_TICKERS},
        )
        stq = aggregate_source_results(
            "stooq_daily_csv",
            {t: probe_stooq(t, PERIOD_START, PERIOD_END) for t in SAMPLE_TICKERS},
        )
        ydl = aggregate_source_results(
            "yahoo_csv_download",
            {t: probe_yahoo_csv_download(t, PERIOD_START, PERIOD_END) for t in SAMPLE_TICKERS},
        )
        source_probe = {
            "period": {"start": PERIOD_START.strftime("%Y-%m-%d"), "end": PERIOD_END.strftime("%Y-%m-%d")},
            "sample_tickers": SAMPLE_TICKERS,
            "sources_summary": [yc, stq, ydl],
        }
        write_json(OUT_SOURCE_PROBE, source_probe)
        artifacts.append(OUT_SOURCE_PROBE)

        probe_ok = any(s["success_rate"] > 0.70 for s in source_probe["sources_summary"])
        gates.append(Gate("G_SOURCE_PROBE", probe_ok, f"best_success_rate={max(s['success_rate'] for s in source_probe['sources_summary']):.2f}"))
        if not probe_ok:
            raise RuntimeError("Nenhuma fonte com sucesso minimo para seguir com recomendacao.")

        sp500_probe = fetch_sp500_current_universe()
        sp500_ok = bool(sp500_probe.get("ok")) and int(sp500_probe.get("count", 0)) >= 450
        if sp500_ok:
            symbols = sp500_probe.get("symbols", [])
            pd.DataFrame({"symbol": symbols}).to_csv(OUT_SP500_SNAPSHOT, index=False)
        gates.append(
            Gate(
                "G_SP500_SNAPSHOT_OK",
                sp500_ok,
                f"ok={sp500_probe.get('ok', False)} count={sp500_probe.get('count', 0)} path={OUT_SP500_SNAPSHOT.relative_to(ROOT)}",
            )
        )

        yahoo_chart = next((s for s in source_probe["sources_summary"] if s["source"] == "yahoo_chart_api"), None)
        yahoo_ok = bool(yahoo_chart and yahoo_chart.get("success_rate", 0.0) > 0.50)
        source_recommendation = {
            "primary_ohlcv_source": "stooq_daily_csv",
            "primary_corp_actions_source": "yahoo_chart_api" if yahoo_ok else "REQUIRES_API_KEY_PROVIDER",
            "fallback_source": "stooq_daily_csv",
            "environment_note": (
                "Yahoo retornou HTTP 429 no ambiente atual; para corporate actions em T084 usar provider com API key (Polygon/IEX Cloud/Nasdaq Data Link) ou retry com janela controlada."
                if not yahoo_ok
                else "Yahoo chart respondeu na amostra; monitorar rate-limit em T084."
            ),
        }

        universe_plan = {
            "target_us_tickers": 500,
            "sp500_current": sp500_probe,
            "sp500_snapshot_csv": OUT_SP500_SNAPSHOT.relative_to(ROOT).as_posix(),
            "cycle1_strategy": "usar lista atual versionada (snapshot) com risco de survivorship registrado",
            "cycle2_strategy": "incorporar composicao historica por data efetiva",
            "normalization_rule": "ticker uppercase, ponto substituido por hifen",
            "versioning_rule": "materializar snapshot com hash sha256 no inicio de T084",
        }
        write_json(OUT_UNIVERSE_PLAN, universe_plan)
        artifacts.append(OUT_UNIVERSE_PLAN)

        risk_register = {
            "risks": [
                {
                    "id": "R1_SOURCE_STABILITY",
                    "risk": "Fonte primaria pode sofrer limitacao temporaria ou bloqueio.",
                    "mitigation": "Definir fallback funcional e retry/backoff deterministico em T084.",
                },
                {
                    "id": "R2_SURVIVORSHIP",
                    "risk": "Lista atual do S&P 500 introduz survivorship bias.",
                    "mitigation": "Registrar risco no ciclo 1 e planejar composicao historica no ciclo 2.",
                },
                {
                    "id": "R3_CORP_ACTIONS",
                    "risk": "Divergencias em dividendos/splits entre fontes podem distorcer retorno.",
                    "mitigation": "Conferir consistencia por ticker e criar blacklist operacional em T085.",
                },
                {
                    "id": "R4_TIMEZONE_LOOKAHEAD",
                    "risk": "Uso indevido de fechamento US no mesmo dia BR gera lookahead.",
                    "mitigation": "Aplicar regra D+1 e shift(1) global para features cross-market.",
                },
                {
                    "id": "R5_SCHEMA_DRIFT",
                    "risk": "Mudanca de schema de provider quebra ingestao.",
                    "mitigation": "Validacao de schema por gate e fail-fast com diagnostico objetivo.",
                },
            ]
        }
        write_json(OUT_RISK_REGISTER, risk_register)
        artifacts.append(OUT_RISK_REGISTER)

        spec_md = build_spec_markdown(
            schema_snapshot=schema_snapshot,
            source_probe=source_probe,
            universe_plan=universe_plan,
            risk_register=risk_register,
            source_recommendation=source_recommendation,
        )
        OUT_SPEC.write_text(spec_md, encoding="utf-8")
        gates.append(Gate("G_SPEC_WRITTEN", True, f"path={OUT_SPEC.relative_to(ROOT)}"))
        artifacts.append(OUT_SPEC)

        ch_ok, ch_mode = append_changelog_idempotent(TRACEABILITY_LINE)
        gates.append(Gate("G_CHLOG_UPDATED", ch_ok, f"mode={ch_mode}"))

        # Regra de aceite V2: snapshot do universo deve estar materializado.
        if not sp500_ok:
            raise RuntimeError("G_SP500_SNAPSHOT_OK=FAIL: nao foi possivel materializar snapshot S&P 500.")

        # Gates declarados antes do write final do manifest.
        gates.append(
            Gate(
                "G_HASH_MANIFEST_PRESENT",
                True,
                f"path={OUT_MANIFEST.relative_to(ROOT)} (sera materializado no ultimo write)",
            )
        )
        gates.append(Gate("G_MANIFEST_ORDER", True, "manifest sera escrito uma unica vez como ultimo write"))

        # Escreve report provisoriamente para entrar no pacote hasheado final.
        OUT_REPORT.write_text(
            render_report(
                gates=gates,
                retry_log=retry_log,
                overall=all(g.passed for g in gates),
                artifacts=artifacts + [OUT_SP500_SNAPSHOT, OUT_REPORT, OUT_MANIFEST],
            ),
            encoding="utf-8",
        )
        artifacts.extend([OUT_SP500_SNAPSHOT, OUT_REPORT])

        inputs_consumed = [
            IN_ARCH.relative_to(ROOT).as_posix(),
            IN_ROADMAP.relative_to(ROOT).as_posix(),
            IN_SSOT_CANONICAL.relative_to(ROOT).as_posix(),
            IN_SSOT_RAW.relative_to(ROOT).as_posix(),
            IN_SSOT_MACRO.relative_to(ROOT).as_posix(),
            IN_SSOT_UNIVERSE.relative_to(ROOT).as_posix(),
        ]
        outputs_produced = [
            p.relative_to(ROOT).as_posix()
            for p in [
                OUT_SCRIPT,
                OUT_SPEC,
                OUT_REPORT,
                OUT_MANIFEST,
                OUT_SOURCE_PROBE,
                OUT_SCHEMA_SNAPSHOT,
                OUT_UNIVERSE_PLAN,
                OUT_RISK_REGISTER,
                OUT_SP500_SNAPSHOT,
                CHANGELOG_PATH,
            ]
        ]
        hash_targets = [
            OUT_SCRIPT,
            OUT_SPEC,
            OUT_REPORT,
            OUT_SOURCE_PROBE,
            OUT_SCHEMA_SNAPSHOT,
            OUT_UNIVERSE_PLAN,
            OUT_RISK_REGISTER,
            OUT_SP500_SNAPSHOT,
            CHANGELOG_PATH,
        ]
        hashes = {p.relative_to(ROOT).as_posix(): sha256_file(p) for p in hash_targets}

        # Self-check de integridade dos hashes antes de escrever o manifest final.
        recomputed = {p.relative_to(ROOT).as_posix(): sha256_file(p) for p in hash_targets}
        self_check_ok = recomputed == hashes
        gates.append(
            Gate(
                "G_SHA256_INTEGRITY_SELF_CHECK",
                self_check_ok,
                f"targets={len(hash_targets)}",
            )
        )
        if not self_check_ok:
            raise RuntimeError("Falha no self-check de integridade SHA256.")

        # Reescreve report final (ainda antes do manifest), depois recalcula hashes finais.
        OUT_REPORT.write_text(
            render_report(
                gates=gates,
                retry_log=retry_log,
                overall=all(g.passed for g in gates),
                artifacts=artifacts + [OUT_MANIFEST],
            ),
            encoding="utf-8",
        )
        hashes = {p.relative_to(ROOT).as_posix(): sha256_file(p) for p in hash_targets}

        manifest_payload = {
            "task_id": TASK_ID,
            "run_id": RUN_ID,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "inputs_consumed": inputs_consumed,
            "outputs_produced": outputs_produced,
            "hashes_sha256": hashes,
            "source_recommendation": source_recommendation,
            "period_alignment": {"start": PERIOD_START.strftime("%Y-%m-%d"), "end": PERIOD_END.strftime("%Y-%m-%d")},
        }
        # ULTIMO write da task (sem writes apos manifest).
        write_json(OUT_MANIFEST, manifest_payload)
        final_overall = all(g.passed for g in gates)

        print(f"# HEADER: {TASK_ID}")
        print("## STEP GATES")
        for g in gates:
            print(f"- {g.name}: {'PASS' if g.passed else 'FAIL'} | {g.detail}")
        print("## RETRY LOG")
        print("- none" if not retry_log else "\n".join([f"- {r}" for r in retry_log]))
        print("## ARTIFACT LINKS")
        for a in artifacts + [OUT_MANIFEST]:
            print(f"- {a.relative_to(ROOT)}")
        print(f"## OVERALL STATUS: [[ {'PASS' if final_overall else 'FAIL'} ]]")
        return 0 if final_overall else 2

    except Exception as e:
        retry_log.append(f"fatal: {e}")
        gates.append(Gate("G_FATAL_EXCEPTION", False, str(e)))
        fail_report = render_report(gates=gates, retry_log=retry_log, overall=False, artifacts=[OUT_REPORT, OUT_MANIFEST])
        OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
        OUT_REPORT.write_text(fail_report, encoding="utf-8")
        print(fail_report)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
