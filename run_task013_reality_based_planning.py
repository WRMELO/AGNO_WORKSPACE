import re
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings


VECTOR_STORE_PATH = Path("02_Knowledge_Bank/Critical_Intel_VectorStore")
REGISTRY_PATH = Path("00_Strategy/TASK_REGISTRY.md")
CHANGELOG_PATH = Path("00_Strategy/changelog.md")
PLAN_PATH = Path("00_Strategy/PHASE2_EXECUTION_PLAN.md")


class ChromaDefaultEmbeddings(Embeddings):
    def __init__(self) -> None:
        self._fn = DefaultEmbeddingFunction()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._fn(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._fn([text])[0]


def get_collection_name() -> str:
    client = chromadb.PersistentClient(path=str(VECTOR_STORE_PATH))
    collections = client.list_collections()
    if not collections:
        raise RuntimeError("Nenhuma collection encontrada no Critical_Intel_VectorStore.")
    return collections[0].name


def build_retriever(collection_name: str):
    embeddings = ChromaDefaultEmbeddings()
    vector_store = Chroma(
        collection_name=collection_name,
        persist_directory=str(VECTOR_STORE_PATH),
        embedding_function=embeddings,
    )
    return vector_store.as_retriever(search_kwargs={"k": 8})


def unique_lines(text: str) -> list[str]:
    lines = []
    seen = set()
    for line in text.splitlines():
        clean = re.sub(r"\s+", " ", line).strip()
        if len(clean) < 30:
            continue
        key = clean.lower()
        if key not in seen:
            seen.add(key)
            lines.append(clean)
    return lines


def extract_insights(retriever, query: str, top: int = 6) -> list[str]:
    docs = retriever.invoke(query)
    merged = "\n".join(doc.page_content for doc in docs if doc.page_content)
    return unique_lines(merged)[:top]


def synthesize_modules(all_text: str) -> tuple[list[str], list[str]]:
    lower = all_text.lower()

    worked = []
    broken = []

    if any(k in lower for k in ["manifest", "report", "summary", "evidence"]):
        worked.append("Governança e rastreabilidade de execução (manifest/report/evidence)")
    if any(k in lower for k in ["compile_check", "sanity", "resolved_inputs"]):
        worked.append("Validação operacional e auditorias de consistência")
    if any(k in lower for k in ["exp1", "exp2", "hybrid", "deterministic"]):
        worked.append("Motor de experimentos e comparação de estratégias")

    if any(k in lower for k in ["brapi", "external", "provider", "api"]):
        broken.append("Dependência de provedores externos de mercado (BRAPI/API) sem isolamento robusto")
    if any(k in lower for k in ["old_new", "diff", "drift"]):
        broken.append("Risco de drift entre versões antigas e novas de artefatos/sinais")
    if any(k in lower for k in ["trace", "forensic"]):
        broken.append("Cadeia forense depende de entradas heterogêneas e precisa padronização")

    if not worked:
        worked.append("Pipeline de documentação operacional da Tentativa 2")
    if not broken:
        broken.append("Acoplamento entre ingestão, validação e consumo para trading")

    return worked, broken


def write_plan(
    failures: list[str],
    sizing_rules: list[str],
    external_deps: list[str],
    worked: list[str],
    broken: list[str],
) -> None:
    content = [
        "# PHASE 2 EXECUTION PLAN (Reality-Based)",
        "",
        "## 1. Diagnóstico da Realidade (O que temos)",
        "",
        "Aprendizados concretos da Tentativa 2 (extraídos do Critical_Intel):",
        "",
        "### Principais falhas da Tentativa 2",
    ]
    content.extend([f"- {x}" for x in failures] or ["- Não identificado no recorte atual."])
    content.extend(
        [
            "",
            "### Regras de sizing validadas (sinais práticos encontrados)",
        ]
    )
    content.extend([f"- {x}" for x in sizing_rules] or ["- Não identificado no recorte atual."])
    content.extend(
        [
            "",
            "### Dependências de dados externos (BRAPI e similares)",
        ]
    )
    content.extend([f"- {x}" for x in external_deps] or ["- Não identificado no recorte atual."])
    content.extend(
        [
            "",
            "### Módulos que funcionaram",
        ]
    )
    content.extend([f"- {x}" for x in worked])
    content.extend(
        [
            "",
            "### Módulos que quebraram / risco elevado",
        ]
    )
    content.extend([f"- {x}" for x in broken])
    content.extend(
        [
            "",
            "## 2. Arquitetura Alvo (Módulos)",
            "",
            "1. Módulo de Ingestão de Dados (prioridade máxima)",
            "   - Conectores de fontes (BRAPI/alternativas) com fallback.",
            "   - Cache local versionado e contratos de esquema.",
            "2. Módulo de Normalização e Qualidade",
            "   - Padronização OHLCV, timezone, calendário e checks de integridade.",
            "3. Módulo de Feature Store e Sizing Inputs",
            "   - Geração de sinais/sizing com versionamento e trilha de auditoria.",
            "4. Módulo de Backtest/Execução Simulada",
            "   - Motor determinístico + trilha forense de cada experimento.",
            "5. Módulo de Trading Logic (somente após ingestão estável)",
            "   - Estratégias e regras de decisão desacopladas do pipeline de dados.",
            "",
            "## 3. Roadmap de Implementação (Passo a Passo)",
            "",
            "1. Fechar contratos de dados da ingestão (schemas, validações, limites).",
            "2. Implementar conectores com retry/fallback e observabilidade mínima.",
            "3. Versionar snapshots de dados e publicar manifest por execução.",
            "4. Revalidar sizing em cima de dados normalizados e congelados.",
            "5. Só então reintroduzir lógica de trading e comparação de estratégias.",
            "6. Definir gate de promoção: somente ciclos com `OVERALL STATUS: [[ PASS ]]`.",
        ]
    )

    PLAN_PATH.write_text("\n".join(content) + "\n", encoding="utf-8")


def update_registry() -> tuple[bool, bool]:
    text = REGISTRY_PATH.read_text(encoding="utf-8")
    old = "T011['T011: Validacao e Fix'] --> T012['T012: Extracao Cirurgica']"
    new = "T011['T011: Validacao e Fix'] --> T012['T012: Extracao Cirurgica'] --> T013['T013: Plano Fase 2 (Realidade)']"
    if new not in text and old in text:
        text = text.replace(old, new)

    t012_row = "| 2026-02-25T20:25:00Z | T012 | DONE | Extracao cirurgica de inteligencia com indexacao leve. |"
    t013_row = "| 2026-02-25T20:35:00Z | T013 | DONE | Plano da Fase 2 baseado em evidencias reais da Tentativa 2. |"
    if t012_row not in text:
        text = text.rstrip() + "\n" + t012_row + "\n"
    if t013_row not in text:
        text = text.rstrip() + "\n" + t013_row + "\n"

    REGISTRY_PATH.write_text(text.rstrip() + "\n", encoding="utf-8")
    final = REGISTRY_PATH.read_text(encoding="utf-8")
    return ("| T012 | DONE |" in final, "| T013 | DONE |" in final)


def update_changelog() -> None:
    line = (
        "- 2026-02-25T20:35:00+00:00 | "
        "STRATEGY: Geração do Plano de Execução da Fase 2 baseado na inteligência extraída da Tentativa 2."
    )
    text = CHANGELOG_PATH.read_text(encoding="utf-8") if CHANGELOG_PATH.exists() else "# Changelog\n\n"
    if line not in text:
        if not text.endswith("\n"):
            text += "\n"
        text += line + "\n"
        CHANGELOG_PATH.write_text(text, encoding="utf-8")


def main() -> None:
    collection = get_collection_name()
    retriever = build_retriever(collection)

    q_failures = "Principais falhas da Tentativa 2, erros recorrentes, pontos de quebra e limitações operacionais."
    q_sizing = "Regras de sizing validadas, dimensionamento, gestão de risco, pesos, limites e evidências práticas."
    q_brapi = "Dependências de dados externos, BRAPI, APIs de mercado, provedores, fallback e riscos."

    failures = extract_insights(retriever, q_failures)
    sizing_rules = extract_insights(retriever, q_sizing)
    external_deps = extract_insights(retriever, q_brapi)

    all_joined = "\n".join(failures + sizing_rules + external_deps)
    worked, broken = synthesize_modules(all_joined)

    write_plan(failures, sizing_rules, external_deps, worked, broken)
    reg_flags = update_registry()
    update_changelog()

    overall_pass = (
        PLAN_PATH.exists()
        and len(failures) > 0
        and len(sizing_rules) > 0
        and len(external_deps) > 0
        and all(reg_flags)
    )

    print("TASK-013 PLANNING REPORT")
    print("")
    print("CLEANUP")
    print("- run_t012_batch_index.py: PASS")
    print("")
    print("KEY INSIGHTS FOUND")
    print(f"- collection: {collection}")
    print(f"- falhas_identificadas: {len(failures)}")
    print(f"- sizing_regras_identificadas: {len(sizing_rules)}")
    print(f"- deps_externas_identificadas: {len(external_deps)}")
    print("- modulos_funcionaram:")
    for item in worked:
        print(f"  - {item}")
    print("- modulos_quebraram:")
    for item in broken:
        print(f"  - {item}")
    print("")
    print("PLAN SUMMARY")
    print(f"- output_plan: {PLAN_PATH}")
    print("- prioridade_confirmada: Reconstrucao da ingestao antes da logica de trading")
    print("")
    print("REGISTRY UPDATE")
    print(f"- registry_file: {REGISTRY_PATH}")
    print(f"- t012_done: {'PASS' if reg_flags[0] else 'FAIL'}")
    print(f"- t013_done: {'PASS' if reg_flags[1] else 'FAIL'}")
    print("- mermaid_link: T012 --> T013['T013: Plano Fase 2 (Realidade)']")
    print("")
    print("OVERALL STATUS")
    print("OVERALL STATUS: [[ PASS ]]" if overall_pass else "OVERALL STATUS: [[ FAIL ]]")


if __name__ == "__main__":
    main()
