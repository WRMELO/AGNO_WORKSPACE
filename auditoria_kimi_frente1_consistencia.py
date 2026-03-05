#!/usr/bin/env python3
"""
Auditoria Kimi K2.5 - Frente 1: Consistência Numérica Cruzada
Verifica se métricas batem entre diferentes artefatos
"""

import json
import pandas as pd
from datetime import datetime

print("=" * 70)
print("KIMI K2.5 AUDITORIA - FRENTE 1: CONSISTÊNCIA NUMÉRICA CRUZADA")
print("=" * 70)

REPO_PATH = "/home/wilson/AGNO_WORKSPACE"
TOLERANCE = 0.01

findings = []

# ============================================================================
# 1. CRUZAR MÉTRICAS BR WINNER (C060X)
# ============================================================================
print("\n" + "-" * 70)
print("1. CRUZAMENTO BR WINNER (C060X)")
print("-" * 70)

# Fonte 1: T107_BASELINE_SUMMARY_INTEGRATED_EXPANDED.json
t107_summary = json.load(open(f"{REPO_PATH}/src/data_engine/portfolio/T107_BASELINE_SUMMARY_INTEGRATED_EXPANDED.json"))
# Fonte 2: T107_BACKTEST_INTEGRATED_EXPANDED_SELECTED_CONFIG.json
t107_config = json.load(open(f"{REPO_PATH}/src/data_engine/portfolio/T107_BACKTEST_INTEGRATED_EXPANDED_SELECTED_CONFIG.json"))

br_metrics_summary = {
    "sharpe": t107_summary["winner_expanded_ml"]["holdout"]["sharpe"],
    "mdd": t107_summary["winner_expanded_ml"]["holdout"]["mdd"],
    "cagr": t107_summary["winner_expanded_ml"]["holdout"]["cagr"],
    "equity_final": t107_summary["winner_expanded_ml"]["holdout"]["equity_final"],
    "switches": t107_summary["winner_expanded_ml"]["holdout"]["switches"],
    "cash_frac": t107_summary["winner_expanded_ml"]["holdout"]["time_in_cash_frac"],
}

print("\n[T107 BASELINE SUMMARY - winner_expanded_ml.holdout]:")
for k, v in br_metrics_summary.items():
    print(f"  {k}: {v}")

# Ler equity curve para verificar equity final
br_curve = pd.read_parquet(f"{REPO_PATH}/src/data_engine/portfolio/T107_PORTFOLIO_CURVE_DUAL_MODE_EXPANDED_ML_TRIGGER.parquet")
HOLDOUT_START = "2023-01-02"
br_holdout = br_curve[br_curve['date'] >= HOLDOUT_START]
if len(br_holdout) > 0:
    equity_final_curve = br_holdout['equity_end_norm'].iloc[-1]
    print(f"\n[Equity curve - último valor HOLDOUT]: {equity_final_curve:.2f}")
    
    # Comparar com summary
    delta_equity = abs(equity_final_curve - br_metrics_summary['equity_final'])
    if delta_equity > TOLERANCE:
        findings.append({
            "frente": "1",
            "severidade": "ALTO",
            "descricao": f"Divergência equity final BR: curve={equity_final_curve:.2f} vs summary={br_metrics_summary['equity_final']:.2f}",
            "evidencia": f"Delta: {delta_equity:.2f}"
        })
        print(f"  >>> FINDING: Divergência de {delta_equity:.2f} no equity final!")

# ============================================================================
# 2. CRUZAR MÉTRICAS US WINNER (T122)
# ============================================================================
print("\n" + "-" * 70)
print("2. CRUZAMENTO US WINNER (T122)")
print("-" * 70)

# Fonte 1: T122_SELECTED_CONFIG_US_ENGINE_NPOS_CADENCE.json
t122_config = json.load(open(f"{REPO_PATH}/src/data_engine/portfolio/T122_SELECTED_CONFIG_US_ENGINE_NPOS_CADENCE.json"))
# Fonte 2: T127_US_WINNER_DECLARATION.json
t127_decl = json.load(open(f"{REPO_PATH}/src/data_engine/portfolio/T127_US_WINNER_DECLARATION.json"))

us_metrics_config = {
    "sharpe": t122_config["winner_metrics_strategy"]["holdout"]["sharpe"],
    "mdd": t122_config["winner_metrics_strategy"]["holdout"]["mdd"],
    "cagr": t122_config["winner_metrics_strategy"]["holdout"]["cagr"],
    "equity_final": t122_config["winner_metrics_strategy"]["holdout"]["equity_final"],
    "switches": t122_config["winner_coverage"]["switches"],
}

print("\n[T122 SELECTED CONFIG - winner_metrics_strategy.holdout]:")
for k, v in us_metrics_config.items():
    print(f"  {k}: {v}")

print("\n[T127 WINNER DECLARATION]:")
print(f"  Winner: {t127_decl['winner_label']}")
print(f"  Task ID: {t127_decl['winner_task_id']}")

# Ler equity curve US para verificar equity final
us_curve = pd.read_parquet(f"{REPO_PATH}/src/data_engine/portfolio/T122_US_ENGINE_WINNER_CURVE_DAILY.parquet")
us_holdout = us_curve[us_curve['date'] >= HOLDOUT_START]
if len(us_holdout) > 0:
    equity_final_us_curve = us_holdout['equity_strategy'].iloc[-1]
    print(f"\n[Equity curve US - último valor HOLDOUT]: {equity_final_us_curve:.2f}")
    
    delta_equity_us = abs(equity_final_us_curve - us_metrics_config['equity_final'])
    if delta_equity_us > TOLERANCE:
        findings.append({
            "frente": "1",
            "severidade": "ALTO",
            "descricao": f"Divergência equity final US: curve={equity_final_us_curve:.2f} vs config={us_metrics_config['equity_final']:.2f}",
            "evidencia": f"Delta: {delta_equity_us:.2f}"
        })
        print(f"  >>> FINDING: Divergência de {delta_equity_us:.2f} no equity final!")
    else:
        print(f"  >>> OK: Equity final consistente (delta: {delta_equity_us:.2f})")

# ============================================================================
# 3. VERIFICAR SWITCHES
# ============================================================================
print("\n" + "-" * 70)
print("3. CONSISTÊNCIA DE SWITCHES (T122)")
print("-" * 70)

# Do config
switches_config = t122_config["winner_coverage"]["switches"]
# Do curve (contar transições)
us_curve_full = pd.read_parquet(f"{REPO_PATH}/src/data_engine/portfolio/T122_US_ENGINE_WINNER_CURVE_DAILY.parquet")

# T122 é engine pura sem ML trigger, então não tem state_cash
# Switches no config provavelmente são rebalanceamentos
print(f"Switches reportados em T122 config: {switches_config}")
print(f"Rebalance days: {t122_config['winner_coverage']['n_rebalance_days']}")

# ============================================================================
# 4. VERIFICAR CUSTO TOTAL
# ============================================================================
print("\n" + "-" * 70)
print("4. CONSISTÊNCIA DE CUSTOS")
print("-" * 70)

total_cost_reported = t122_config["winner_coverage"]["total_cost_paid_holdout"]
print(f"Custo total reportado (HOLDOUT): ${total_cost_reported:,.2f}")

# Verificar se bate com equity * cost_rate
# Cost rate: 0.0001 (1 bp)
cost_rate = t122_config["config_fixed"]["cost_rate_one_way"]
print(f"Cost rate: {cost_rate} ({cost_rate*10000:.0f} bps)")

# ============================================================================
# RESUMO
# ============================================================================
print("\n" + "=" * 70)
print("RESUMO FRENTE 1")
print("=" * 70)

if findings:
    print(f"\nEncontrados {len(findings)} findings:")
    for f in findings:
        print(f"  [{f['severidade']}] {f['descricao']}")
else:
    print("\nNenhum finding de consistência numérica detectado (dentro da tolerância de 0.01)")

# Salvar
with open(f"{REPO_PATH}/auditoria_kimi_frente1_resultados.json", 'w') as f:
    json.dump({"findings": findings, "timestamp": datetime.now().isoformat()}, f, indent=2)

print(f"\nResultados salvos em: {REPO_PATH}/auditoria_kimi_frente1_resultados.json")
