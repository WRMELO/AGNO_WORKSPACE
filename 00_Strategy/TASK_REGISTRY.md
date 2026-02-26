# AGNO PROJECT - TASK REGISTRY (CORE STATE)

| ID | Task Name | Phase | Status | Key Artifacts / Logs | Timestamp |
| --- | --- | --- | --- | --- | --- |
| T001 | Bootstrap | Setup | DONE | Bootstrap legado concluido. | 2026-02-25T14:45:00Z |
| T002 | Infra Audit | Audit | DONE | Auditoria de integridade aprovada. | 2026-02-25T17:38:28Z |
| T003 | Ingestao Legado | Ingestion | DONE | `00_Strategy/Task_History/T003/report.md` | 2026-02-25T18:15:42Z |
| T007 | Mapeamento Corpus de Negocio | Ingestion | DONE | Evidencia em `changelog` (mapeamento Bolsa/Carteira). | 2026-02-25T18:55:46Z |
| T010 | Indexacao Vetorial | RAG | DONE | Evidencia em `changelog` (`RAG: Indexação vetorial concluída`). | 2026-02-25T18:45:00Z |
| T012 | Extracao Cirurgica | Recovery | DONE | Extracao cirurgica e indexacao leve (`Critical_Intel_VectorStore`). | 2026-02-25T20:25:00Z |
| T013 | Plano Fase 2 - Realidade | Strategy | DONE | `00_Strategy/PHASE2_EXECUTION_PLAN.md` | 2026-02-25T20:35:00Z |
| T014 | Data Engine Skeleton (Ports & Adapters) | 2 - Operations | DONE | `src/data_engine/ports/market_data_port.py`, `scripts/t014_verify_skeleton.py` | 2026-02-25T18:05:00-03:00 |
| T015 | BRAPI Adapter | 2 - Operations | DONE | `src/data_engine/adapters/brapi_adapter.py`, `scripts/t015_test_connection.py`; token encontrado em `/home/wilson/CEP_NA_BOLSA/planning/secrets/brapi_token.txt` e validado com PETR4 | 2026-02-26T09:00:00-03:00 |
| T016 | Key Persist (.env) | 2 - Operations | DONE | Persistencia de `BRAPI_API_KEY` em `.env` sem sobrescrever conteudo existente; validado com `load_dotenv` | 2026-02-26T08:55:00-03:00 |
| T017 | Legacy Markdown Bundle | 2 - Operations | DONE | `scripts/t017_bundle_legacy.py`; bundle criado em `00_Strategy/00_Legacy_Imports/LEGACY_BUNDLE.md` com filtro estrito `.md` | 2026-02-26T09:10:00-03:00 |
| T018 | BRAPI Full Extraction | 2 - Operations | DONE | `BrapiAdapter` com OHLCV bruto + `events_data` via `dividendsData` (`cashDividends/stockDividends/subscriptions`) e fundamentos; ver `scripts/t018_verify_full.py` | 2026-02-26T12:00:00-03:00 |
| T019 | SSOT S001 Hunt | 2 - Operations | DONE | `scripts/t019_find_s001_targeted.py`; S001 lógico ingerido para `src/data_engine/ssot/SSOT_UNIVERSE_RAW_S001.parquet` a partir de `universe_candidates.parquet` (1690 linhas) | 2026-02-26T15:00:00-03:00 |
| T020 | Universe Sanity (S001) | 2 - Operations | DONE | T020 (Redo V2): expansão de sufixos para `3,4,5,6,11,31-35,39`; normalização `.SA`/`F`; `SSOT_UNIVERSE_S001_CLEAN.parquet` regenerado e rejeitos auditados | 2026-02-26T16:30:00-03:00 |
| T021 | Market Data Backfill | 2 - Operations | DONE | T021 (Fix): pruning de 109 tickers 404, criação de `SSOT_UNIVERSE_BLACKLIST.csv` e `SSOT_UNIVERSE_OPERATIONAL.parquet` (697), consolidação do `SSOT_MARKET_DATA_RAW.parquet` e `SSOT_FUNDAMENTALS.parquet`. | 2026-02-26T17:30:00-03:00 |
| T022 | Macro SSOT Builder | 2 - Operations | DONE | T022 V2: calendário mestre estrito via BRAPI `^BVSP`; alinhamento CDI (BCB série 12) + SP500 (Yahoo), retornos log e `SSOT_MACRO.parquet` (2025 linhas, sem NaN). | 2026-02-26T20:30:00-03:00 |
| T023 | Canonical Builder (SPC Constants) | 2 - Operations | DONE | T023 Heuristic Final: `scripts/t023_build_canonical_base_heuristic.py` com auto-correção Min-Distortion em eventos de split/inplit; VIVT3 ajustado automaticamente (audit em `data/market_data/heuristic_adjustments_t023.csv`) + forense/hunt legado. | 2026-02-27T12:00:00-03:00 |
| V001 | Visual Verification (Split-Only) | 2 - Operations | DONE | V001 Final Check: `scripts/v001_heuristic_output_check.py`; plots em `data/verification_plots/heuristic_final/` validando `close_raw` vs `close_operational` (VIVT3 divergente, MGLU3/PETR4 sobrepostos). | 2026-02-27T13:00:00-03:00 |
| T099 | Phase 1 Knowledge Dump | 2 - Operations (Closing Data Phase) | DONE | T099: Consolidated Phase 1 Knowledge (Heuristics, Physics, and SPC Math) into documentation. | 2026-02-27T14:00:00-03:00 |
