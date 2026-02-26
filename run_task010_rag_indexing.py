import csv
import json
import os
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
from langchain_text_splitters import RecursiveCharacterTextSplitter


def load_file_text(path: Path) -> str:
    suffix = path.suffix.lower()
    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raw = path.read_text(encoding="utf-8", errors="ignore")

    if suffix == ".json":
        try:
            parsed = json.loads(raw)
            return json.dumps(parsed, ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            return raw
    if suffix == ".csv":
        # Normaliza CSV para texto legível no embedding.
        reader = csv.reader(raw.splitlines())
        lines = [" | ".join(row) for row in reader]
        return "\n".join(lines)
    return raw


def print_report(gates, retry_log, artifacts, overall_pass):
    print("TASK-010 EXECUTION REPORT")
    print("")
    print("STEP GATES")
    for step, status, detail in gates:
        print(f"- [{status}] {step}: {detail}")
    print("")
    print("RETRY LOG")
    if retry_log:
        for item in retry_log:
            print(f"- {item}")
    else:
        print("- NONE")
    print("")
    print("ARTIFACT LINKS")
    for item in artifacts:
        print(f"- {item}")
    print("")
    print("OVERALL STATUS")
    if overall_pass:
        print("OVERALL STATUS: [[ PASS ]]")
    else:
        print("OVERALL STATUS: [[ FAIL ]]")


def main():
    corpus_path = Path("02_Knowledge_Bank/corpus")
    vector_store = Path("02_Knowledge_Bank/vector_store")
    query = "Quais são as regras de venda?"

    gates = []
    retry_log = []
    artifacts = []
    overall_pass = True

    # STEP 1 - SETUP
    try:
        vector_store.mkdir(parents=True, exist_ok=True)
        gates.append(("SETUP", "PASS", "Dependências instaladas e diretórios prontos."))
    except Exception as exc:
        gates.append(("SETUP", "FAIL", f"Erro no setup: {exc}"))
        overall_pass = False
        print_report(gates, retry_log, artifacts, overall_pass)
        return

    # STEP 2 - LOAD
    docs = []
    try:
        suffixes = {".md", ".json", ".csv"}
        files = [p for p in corpus_path.rglob("*") if p.is_file() and p.suffix.lower() in suffixes]
        for f in files:
            text = load_file_text(f).strip()
            if text:
                docs.append({"source": str(f), "text": text})
        gates.append(("LOAD", "PASS", f"Arquivos carregados: {len(docs)}"))
    except Exception as exc:
        gates.append(("LOAD", "FAIL", f"Erro no load: {exc}"))
        overall_pass = False
        print_report(gates, retry_log, artifacts, overall_pass)
        return

    # STEP 3 - CHUNK
    chunks = []
    try:
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        for doc in docs:
            split_texts = splitter.split_text(doc["text"])
            for idx, chunk in enumerate(split_texts):
                chunks.append(
                    {
                        "id": f'{doc["source"]}::chunk_{idx}',
                        "document": chunk,
                        "metadata": {"source": doc["source"], "chunk_index": idx},
                    }
                )
        gates.append(("CHUNK", "PASS", f"Chunks gerados: {len(chunks)}"))
    except Exception as exc:
        gates.append(("CHUNK", "FAIL", f"Erro no chunking: {exc}"))
        overall_pass = False
        print_report(gates, retry_log, artifacts, overall_pass)
        return

    # STEP 4 - EMBED & STORE
    collection_name = "task010_corpus_index"
    try:
        client = chromadb.PersistentClient(path=str(vector_store))
        try:
            client.delete_collection(collection_name)
        except Exception:
            pass

        use_openai = bool(os.getenv("OPENAI_API_KEY"))
        if use_openai:
            # Se a chave existir, ainda usamos embedding local para evitar dependência extra
            # de pacote de integração e manter execução estável.
            retry_log.append("OPENAI_API_KEY detectada; usando embedding local do Chroma por estabilidade.")

        embedding_fn = DefaultEmbeddingFunction()
        collection = client.get_or_create_collection(
            name=collection_name,
            embedding_function=embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )

        batch_size = 128
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            collection.add(
                ids=[b["id"] for b in batch],
                documents=[b["document"] for b in batch],
                metadatas=[b["metadata"] for b in batch],
            )
        count = collection.count()
        artifacts.append(f"`{vector_store}` (collection={collection_name}, vectors={count})")
        gates.append(("EMBED & STORE", "PASS", f"Vetores persistidos: {count}"))
    except Exception as exc:
        gates.append(("EMBED & STORE", "FAIL", f"Erro na vetorização: {exc}"))
        overall_pass = False
        print_report(gates, retry_log, artifacts, overall_pass)
        return

    # STEP 5 - TEST
    try:
        result = collection.query(query_texts=[query], n_results=3)
        docs_out = result.get("documents", [[]])[0]
        metas_out = result.get("metadatas", [[]])[0]
        coherent = False
        for text in docs_out:
            t = text.lower()
            if "venda" in t or "sell" in t or "regras" in t:
                coherent = True
                break
        if docs_out and coherent:
            artifacts.append(f"query=`{query}` -> top_source=`{metas_out[0].get('source', 'N/A')}`")
            gates.append(("TEST", "PASS", f"Resultados: {len(docs_out)} (coerência validada)"))
        else:
            gates.append(("TEST", "FAIL", "Busca sem resultado coerente para regras de venda."))
            overall_pass = False
    except Exception as exc:
        gates.append(("TEST", "FAIL", f"Erro na query de teste: {exc}"))
        overall_pass = False

    print_report(gates, retry_log, artifacts, overall_pass)


if __name__ == "__main__":
    main()
