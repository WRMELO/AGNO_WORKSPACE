import json
import re
from datetime import datetime, timezone
from pathlib import Path

TASK_ID = "TASK-003-INGEST"
ROOT = Path(".")
LEGACY_DIR = ROOT / "00_Strategy" / "00_Legacy_Imports"
SYSTEM_CONTEXT_PATH = ROOT / "01_Architecture" / "System_Context.md"
REPORT_PATH = ROOT / "00_Strategy" / "Task_History" / "T003" / "report.md"
CHANGELOG_PATH = ROOT / "00_Strategy" / "changelog.md"


def log_status(status, message):
    print(f"[{status}] {message}")


def read_text_with_retry(path, retries=3):
    last_error = None
    for _ in range(retries):
        try:
            return path.read_text(encoding="utf-8")
        except Exception as exc:
            last_error = exc
    raise last_error


def write_text_with_retry(path, content, retries=3):
    last_error = None
    for _ in range(retries):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return
        except Exception as exc:
            last_error = exc
    raise last_error


def load_json_with_retry(path, retries=3):
    raw = read_text_with_retry(path, retries=retries)
    return json.loads(raw)


def upsert_section(document, section_title, section_body):
    pattern = re.compile(
        rf"(?ms)^## {re.escape(section_title)}\n.*?(?=^## |\Z)"
    )
    section_text = f"## {section_title}\n\n{section_body.strip()}\n"
    if pattern.search(document):
        return pattern.sub(section_text + "\n", document).rstrip() + "\n"
    return document.rstrip() + "\n\n" + section_text


def summarize_gates(gates):
    pass_count = sum(1 for state in gates.values() if state == "PASS")
    fail_count = sum(1 for state in gates.values() if state == "FAIL")
    pending = [name for name, state in gates.items() if state != "PASS"]
    return pass_count, fail_count, pending


def extract_md_definitions(md_text):
    definitions = []
    for line in md_text.splitlines():
        line_stripped = line.strip()
        if line_stripped.startswith("- definição:") or line_stripped.startswith("- definicao:"):
            definitions.append(line_stripped.split(":", 1)[1].strip())
    return definitions


def mark_processed(path, retries=3):
    processed_path = Path(str(path) + ".processed")
    if processed_path.exists():
        log_status("PASS", f"Arquivo ja marcado como processado: {processed_path}")
        return processed_path
    last_error = None
    for _ in range(retries):
        try:
            path.rename(processed_path)
            return processed_path
        except Exception as exc:
            last_error = exc
    raise last_error


def main():
    overall_fail = False
    processed_status = []
    metadata = {}
    md_definitions = []

    patterns = list(LEGACY_DIR.glob("TRANSFER_PACKAGE_*"))
    candidates = [p for p in patterns if p.is_file() and not p.name.endswith(".processed")]

    if not candidates:
        log_status("PASS", "Nenhum arquivo novo para processamento em 00_Legacy_Imports.")
        return

    # 1) Leitura e parse dos arquivos alvo
    for file_path in sorted(candidates):
        try:
            if file_path.suffix.lower() == ".json":
                payload = load_json_with_retry(file_path, retries=3)
                metadata = {
                    "instruction_id": payload.get("instruction_id"),
                    "generated_at_utc": payload.get("generated_at_utc"),
                    "overall": payload.get("overall"),
                    "states": sorted((payload.get("states_rules_catalog") or {}).keys()),
                    "graph": (payload.get("state_progression_logic") or {}).get("graph"),
                    "rules": (payload.get("roles_and_governance_rules") or {}).get("rules", []),
                    "gates": payload.get("gates", {}),
                }
                log_status("PASS", f"JSON processado: {file_path}")
                processed_status.append((file_path, "PASS", "json"))
            elif file_path.suffix.lower() == ".md":
                md_text = read_text_with_retry(file_path, retries=3)
                md_definitions = extract_md_definitions(md_text)
                log_status("PASS", f"Markdown processado: {file_path}")
                processed_status.append((file_path, "PASS", "md"))
            else:
                log_status("PASS", f"Arquivo ignorado por extensao: {file_path}")
        except Exception as exc:
            log_status("FAIL", f"Erro ao processar {file_path}: {exc}")
            processed_status.append((file_path, "FAIL", "read"))
            overall_fail = True

    # 2) Merge no System_Context
    try:
        system_context = read_text_with_retry(SYSTEM_CONTEXT_PATH, retries=3)
        now_utc = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        gates = metadata.get("gates", {})
        pass_count, fail_count, pending_gates = summarize_gates(gates)
        state_list = ", ".join(metadata.get("states", [])) or "N/A"
        pending_text = ", ".join(pending_gates) if pending_gates else "nenhuma"

        section_body = f"""
### Arquitetura
- Fonte integrada: `00_Strategy/00_Legacy_Imports/TRANSFER_PACKAGE_*`.
- instruction_id: `{metadata.get("instruction_id", "N/A")}`
- generated_at_utc: `{metadata.get("generated_at_utc", "N/A")}`
- grafo de estados: `{metadata.get("graph", "N/A")}`
- modulos legados integrados: {state_list}

### Regras de Negocio
- Snapshot congelado em politica `PRE_2026_02_24`.
- Gate summary: `{pass_count} PASS` / `{fail_count} FAIL`.
- Pendencias criticas atuais: {pending_text}.
- Regras de governanca (origem legado):
{chr(10).join([f"- {rule}" for rule in metadata.get("rules", [])[:5]])}

### Roadmap
- Curto prazo: resolver gates de segredo (`S6`, `S6A`, `S6B`) para remover estado `TOKEN_PENDING`.
- Medio prazo: manter consolidacao S001->S008 com hashes e manifests auditaveis.
- Registro desta ingestao em: `00_Strategy/Task_History/T003/report.md`.
- Consolidado em: `{now_utc}`.
"""
        updated = upsert_section(system_context, "Legacy Integration History", section_body)
        write_text_with_retry(SYSTEM_CONTEXT_PATH, updated, retries=3)
        log_status("PASS", f"Merge aplicado em: {SYSTEM_CONTEXT_PATH}")
    except Exception as exc:
        log_status("FAIL", f"Erro de IO no System_Context: {exc}")
        overall_fail = True

    # 3) Relatorio de impacto
    try:
        modules = metadata.get("states", [])
        lines = [
            "# T003 - Legacy Ingestion Report",
            "",
            f"- task_id: `{TASK_ID}`",
            f"- generated_at_utc: `{datetime.now(timezone.utc).replace(microsecond=0).isoformat()}`",
            "",
            "## Arquivos Processados",
        ]
        for path, status, kind in processed_status:
            lines.append(f"- [{status}] `{path}` ({kind})")
        lines.extend(
            [
                "",
                "## Modulos Legados Integrados",
                *([f"- {module}" for module in modules] if modules else ["- N/A"]),
                "",
                "## Impacto",
                "- Consolidacao aplicada em `01_Architecture/System_Context.md`.",
                "- Seccao `## Legacy Integration History` criada/atualizada.",
                "- Referencias de importacao marcadas como `.processed`.",
            ]
        )
        write_text_with_retry(REPORT_PATH, "\n".join(lines) + "\n", retries=3)
        log_status("PASS", f"Relatorio salvo em: {REPORT_PATH}")
    except Exception as exc:
        log_status("FAIL", f"Erro de IO no report: {exc}")
        overall_fail = True

    # 4) Atualiza changelog
    try:
        ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        existing = CHANGELOG_PATH.read_text(encoding="utf-8") if CHANGELOG_PATH.exists() else "# Changelog\n\n"
        existing = existing.rstrip() + "\n"
        entry = f"- {ts} | INGEST: Consolidado legado de TRANSFER_PACKAGE para System_Context.md\n"
        write_text_with_retry(CHANGELOG_PATH, existing + entry, retries=3)
        log_status("PASS", f"Changelog atualizado: {CHANGELOG_PATH}")
    except Exception as exc:
        log_status("FAIL", f"Erro de IO no changelog: {exc}")
        overall_fail = True

    # 5) Marca arquivos como processados
    for file_path, status, _kind in processed_status:
        if status != "PASS":
            continue
        try:
            processed_path = mark_processed(file_path, retries=3)
            log_status("PASS", f"Marcado como processado: {processed_path}")
        except Exception as exc:
            log_status("FAIL", f"Erro ao marcar {file_path} como .processed: {exc}")
            overall_fail = True

    if overall_fail:
        log_status("FAIL", "Overall status: FAIL (erro persistente de IO).")
    else:
        log_status("PASS", "Overall status: PASS.")


if __name__ == "__main__":
    main()
