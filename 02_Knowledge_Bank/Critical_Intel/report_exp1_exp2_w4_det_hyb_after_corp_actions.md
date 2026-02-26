# report_exp1_exp2_w4_det_hyb_after_corp_actions

- overall: `PASS`
- generated_at_utc: `2026-02-24T19:48:45.996229+00:00`

## Confirmação das pré-condições (paths + hashes)
- `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/state/s006_operational_base_global/ACTIVE_S006_POINTER.json` :: `a2e49aa9c52d807ea780c029676e6bcd726b9c1b069310b753734ef43eec288a`
- `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/data/ssot/corporate_actions/corporate_actions_ssot_v2.parquet` :: `53684890aa4a661823abecc88f4cc2b56bd40a1e35791ec6441d1656a080bc62`
- `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/data/ssot/corporate_actions/manifest_v2.json` :: `ed87a34a2621372e93997e342cb4d61f4487bf3670df6f3e15b19c863bbc0a48`
- `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/state/s006_operational_base_global/20260224/S006_CANONICAL_BASE_WITH_CORP_ACTIONS_V2/manifest.json` :: `35392bed72a1587e7f16e168ce9859d0b88d95bf16e089e400796a0da84d1586`
- `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/state/s007_ruleflags_global/20260224/S007_FROM_S006_CORP_ACTIONS_V2/manifest.json` :: `d749c74e8b306315a74a11c4dac0a79541a1e47cf0d6168eac92607616895bce`
- `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/state/s008_candidates_global/20260224/S008_FROM_S007_CORP_ACTIONS_V2/manifest.json` :: `8e36fe6f497e2a8cd804aeca626e3f55cc9a9dd208f9bc6cc479aa612dfb0dff`

## Trecho inserido no checklist (append-only)
```markdown
## Atualização 2026-02-24 — Corporate Actions V2 e supersedência canônica

- Ativação da base canônica: `S006_CANONICAL_BASE_WITH_CORP_ACTIONS_V2` em `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/state/s006_operational_base_global/20260224/S006_CANONICAL_BASE_WITH_CORP_ACTIONS_V2/base_operacional_canonica.parquet` (hash do manifest: `35392bed72a1587e7f16e168ce9859d0b88d95bf16e089e400796a0da84d1586`).
- SSOT corporate actions V2: `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/data/ssot/corporate_actions/corporate_actions_ssot_v2.parquet` (hash do `manifest_v2.json`: `ed87a34a2621372e93997e342cb4d61f4487bf3670df6f3e15b19c863bbc0a48`).
- Cadeia reexecutada: `S007_FROM_S006_CORP_ACTIONS_V2` (`/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/state/s007_ruleflags_global/20260224/S007_FROM_S006_CORP_ACTIONS_V2/s007_ruleflags.parquet`, hash do manifest: `d749c74e8b306315a74a11c4dac0a79541a1e47cf0d6168eac92607616895bce`) e `S008_FROM_S007_CORP_ACTIONS_V2` (`/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/state/s008_candidates_global/20260224/S008_FROM_S007_CORP_ACTIONS_V2/s008_candidates.parquet`, hash do manifest: `8e36fe6f497e2a8cd804aeca626e3f55cc9a9dd208f9bc6cc479aa612dfb0dff`).
- Motivo: correção de tratamento de corporate actions (caso `VIVT3` abril/2025), eliminação de duplo ajuste e remoção do outlier extremo na validação S4.
- Registro de erro de orientação (CTO): instrução anterior pressupôs duas variantes de `EXP_1`; no estado canônico atual `EXP_1` é única. Próximas instruções devem validar mapeamento de experimento antes de exigir matriz de variantes.
```

## Inventário das execuções
- EXP1_UNIQUE_W4: `PASS`
  - file: `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/experimentos/on_flight/20260224/EXP1_EXP2_W4_DET_HYB_AFTER_CORP_ACTIONS_V1/runs/EXP1_UNIQUE_W4/equity_curves.parquet`
  - hash: `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/experimentos/on_flight/20260224/EXP1_EXP2_W4_DET_HYB_AFTER_CORP_ACTIONS_V1/runs/EXP1_UNIQUE_W4/equity_curves.parquet` => `8222ab39220c4fec6e73007fac47f31221d696b3bbcfea0f6e2b0cd02dc2c23e`
- EXP1_HYBRID_W4_NA: `N/A`
- EXP2_DETERMINISTIC_W4: `PASS`
  - file: `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/experimentos/on_flight/20260224/EXP1_EXP2_W4_DET_HYB_AFTER_CORP_ACTIONS_V1/runs/EXP2_DETERMINISTIC_W4/equity_curves.parquet`
  - hash: `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/experimentos/on_flight/20260224/EXP1_EXP2_W4_DET_HYB_AFTER_CORP_ACTIONS_V1/runs/EXP2_DETERMINISTIC_W4/equity_curves.parquet` => `dbbe67afdc3c33718b7f2444a5339681916ed721557b4e1ea329db236fdbdf70`
- EXP2_HYBRID_W4: `PASS`
  - file: `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/experimentos/on_flight/20260224/EXP1_EXP2_W4_DET_HYB_AFTER_CORP_ACTIONS_V1/runs/EXP2_HYBRID_W4/equity_curves.parquet`
  - hash: `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/experimentos/on_flight/20260224/EXP1_EXP2_W4_DET_HYB_AFTER_CORP_ACTIONS_V1/runs/EXP2_HYBRID_W4/equity_curves.parquet` => `009b4820e05fffa160f00ad23245b163b0a7f65ecf0bf072e45cf13f4200e980`

- Plotly HTML: `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/experimentos/on_flight/20260224/EXP1_EXP2_W4_DET_HYB_AFTER_CORP_ACTIONS_V1/plots/base1_exp1_exp2_w4_det_hyb_plus_benchmarks.html`

## Checagem numérica simples (abril/2025)
- EXP1_unique: max_abs_daily_return_apr2025=0.000525, days_gt_15pct_abs=0
- EXP2_deterministic_w4: max_abs_daily_return_apr2025=0.007319, days_gt_15pct_abs=0
- EXP2_hybrid_w4: max_abs_daily_return_apr2025=0.036485, days_gt_15pct_abs=0

## Registro de erro do CTO
- O CTO orientou duas variantes para EXP_1, mas o runner canônico de EXP_1 é de política única; EXP1_HYBRID_W4 foi registrado como N/A para reforçar validação prévia de mapeamento de variantes.
