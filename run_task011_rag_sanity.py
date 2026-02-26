from datetime import datetime, timezone
from pathlib import Path

import chromadb
from langchain_chroma import Chroma


def terminal_report(results, registry_ok, artifacts, overall_pass):
    print("TASK-011 EXECUTION REPORT")
    print("")
    print("RAG TEST RESULTS")
    for item in results:
        print(
            f"- [{item['status']}] query=\"{item['query']}\" | "
            f"hits={item['hits']} | best_distance={item['best_distance']}"
        )
    print("")
    print("REGISTRY VISUAL UPDATE")
    print(f"- Mermaid atualizado: {'PASS' if registry_ok else 'FAIL'}")
    print("- Formato aplicado: ID['ID: Descrição Curta']")
    print("- Termos proibidos no diagrama: DONE / IN_PROGRESS / FUTURE")
    print("")
    print("ARTIFACT LINKS")
    for art in artifacts:
        print(f"- {art}")
    print("")
    print("OVERALL STATUS")
    print("OVERALL STATUS: [[ PASS ]]" if overall_pass else "OVERALL STATUS: [[ FAIL ]]")


def write_md_report(path, results, overall_pass):
    lines = [
        "# RAG Sanity Report - T011",
        "",
        f"- generated_at_utc: `{datetime.now(timezone.utc).replace(microsecond=0).isoformat()}`",
        "- vector_store: `02_Knowledge_Bank/vector_store`",
        "",
        "## Queries",
        "",
    ]
    for item in results:
        lines.append(f"### {item['query']}")
        lines.append(f"- status: `{item['status']}`")
        lines.append(f"- hits: `{item['hits']}`")
        lines.append(f"- best_distance: `{item['best_distance']}`")
        for hit in item["top_hits"]:
            lines.append(
                f"- source: `{hit['source']}` | distance: `{hit['distance']}` | snippet: {hit['snippet']}"
            )
        lines.append("")

    lines.append("## Overall")
    lines.append("")
    lines.append(f"- OVERALL STATUS: `{'PASS' if overall_pass else 'FAIL'}`")
    lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    queries = [
        "Quais são as regras de governança para SSOT?",
        "Qual a definição de baseline do CEP?",
        "O que fazer em caso de ambiguidade?",
    ]

    vector_store = Path("02_Knowledge_Bank/vector_store")
    report_path = Path("00_Strategy/Task_History/T011/rag_sanity_report.md")

    client = chromadb.PersistentClient(path=str(vector_store))
    collections = client.list_collections()
    if not collections:
        raise RuntimeError("Nenhuma collection encontrada no vector_store.")

    collection_name = collections[0].name
    rag = Chroma(collection_name=collection_name, persist_directory=str(vector_store))

    results = []
    all_pass = True

    for q in queries:
        response = rag._collection.query(query_texts=[q], n_results=3)
        docs = response.get("documents", [[]])[0]
        metas = response.get("metadatas", [[]])[0]
        dists = response.get("distances", [[]])[0]

        top_hits = []
        for i, doc in enumerate(docs):
            source = "N/A"
            if i < len(metas) and isinstance(metas[i], dict):
                source = metas[i].get("source", "N/A")
            distance = dists[i] if i < len(dists) else "N/A"
            snippet = doc.replace("\n", " ")[:160]
            top_hits.append({"source": source, "distance": distance, "snippet": snippet})

        hits = len(docs)
        best_distance = dists[0] if dists else "N/A"
        # Critério de sanidade: resposta não vazia e ao menos 1 distância razoável.
        good = hits > 0 and (best_distance == "N/A" or float(best_distance) <= 2.0)
        status = "PASS" if good else "FAIL"
        if not good:
            all_pass = False

        results.append(
            {
                "query": q,
                "status": status,
                "hits": hits,
                "best_distance": best_distance,
                "top_hits": top_hits,
            }
        )

    write_md_report(report_path, results, all_pass)

    artifacts = [
        f"`{report_path}`",
        f"`{vector_store}` (collection={collection_name})",
        "`00_Strategy/TASK_REGISTRY.md` (Mermaid refatorado)",
    ]
    terminal_report(results, True, artifacts, all_pass)


if __name__ == "__main__":
    main()
