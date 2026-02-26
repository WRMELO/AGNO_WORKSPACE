# Report - SSOT Reference Refresh V1 (S003)

- status_final: PASS_FINAL

## PASS_OPERACIONAL
- value: True
- criterion: 5 Parquets canônicos materializados + política de janela 2018..2026 validada para BVSP/CDI/SP500.

## PASS_RACIOCINIO
- value: True
- como foi feito: descoberta de fontes internas/locais/external raw, canonização determinística em Parquet no deliverables_root, preservando raws quando necessário.
- como foi decidido: Ações/BDRs alinhados por interseção com universo promovido; CDI via SGS 4389 para estender 2026 com comparação de consistência contra SSOT interno; SP500 aproveitado de fonte canônica já gerada na Tentativa 2; BVSP via SSOT de CEP_NA_BOLSA com cópia rastreável.

## FOUND vs MISSING
- FOUND:
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/ssot_reference_refresh_v1/ssot_ref_acoes.parquet` rows=854 min_date=None max_date=None sha256=40668fb4d58a5ab242dd982a394a41b51dae95892f11706dc768521869930b1f
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/ssot_reference_refresh_v1/ssot_ref_bdrs.parquet` rows=840 min_date=None max_date=None sha256=d0c3415574560d5d9ebb22767f7775c378a52c50f1169a076652458c1078cfeb
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/ssot_reference_refresh_v1/bvsp_daily.parquet` rows=2011 min_date=2018-01-02 00:00:00 max_date=2026-02-04 00:00:00 sha256=9cd2d229bae1a57bd2468215b0a39e8b72f40ed5c9cd0e369365dfe5866ff2d9
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/ssot_reference_refresh_v1/cdi_daily.parquet` rows=2043 min_date=2018-01-02 00:00:00 max_date=2026-02-19 00:00:00 sha256=175d432bd852152deaf80247d4736cf75f86e53972ab4e099efc79b560ee2b04
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/ssot_reference_refresh_v1/sp500_daily.parquet` rows=2045 min_date=2018-01-02 00:00:00 max_date=2026-02-20 00:00:00 sha256=f9840468b7d015ede3ac3f681f49b5c56dee60e7eae70adcac03abb92e53d4bf
- MISSING:
  - none

## Janela Temporal (política)
- start_floor: 2018-01-01
- end_definition: max_date real disponível em 2026
- violations: none

## Evidências
- `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/ssot_reference_refresh_v1/evidence/discovery_inputs.json`
- `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/ssot_reference_refresh_v1/evidence/acoes_bdrs_alignment_counts.csv`
- `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/ssot_reference_refresh_v1/evidence/cdi_overlap_comparison_internal_vs_sgs4389.json`
- `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/ssot_reference_refresh_v1/evidence/head20_cdi_daily.csv`
- `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/ssot_reference_refresh_v1/evidence/head20_sp500_daily.csv`
- `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/ssot_reference_refresh_v1/evidence/head20_bvsp_daily.csv`

## Regras
- Sem inferência sem evidência; Parquet canônico; ssot_snapshot read-only.
