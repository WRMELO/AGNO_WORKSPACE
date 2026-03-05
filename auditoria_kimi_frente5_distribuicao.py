#!/usr/bin/env python3
"""
Auditoria Kimi K2.5 - Frente 5: Análise de Distribuição e Anomalias
Detecta padrões estatísticos que indiquem erro ou otimismo
"""

import pandas as pd
import numpy as np
import json
from datetime import datetime
from scipy import stats

print("=" * 70)
print("KIMI K2.5 AUDITORIA - FRENTE 5: ANÁLISE DE DISTRIBUIÇÃO")
print("=" * 70)

REPO_PATH = "/home/wilson/AGNO_WORKSPACE"
TRAIN_END = "2022-12-30"
HOLDOUT_START = "2023-01-02"

findings = []

# ============================================================================
# 1. ANÁLISE BR WINNER (C060X)
# ============================================================================
print("\n" + "-" * 70)
print("1. ANÁLISE DISTRIBUIÇÃO BR WINNER")
print("-" * 70)

br_curve = pd.read_parquet(f"{REPO_PATH}/src/data_engine/portfolio/T107_PORTFOLIO_CURVE_DUAL_MODE_EXPANDED_ML_TRIGGER.parquet")
br_curve['date'] = pd.to_datetime(br_curve['date'])

# Separar períodos
br_train = br_curve[br_curve['date'] <= TRAIN_END]
br_holdout = br_curve[br_curve['date'] >= HOLDOUT_START]

# Retornos
br_train_rets = br_train['equity_end_norm'].pct_change().dropna()
br_holdout_rets = br_holdout['equity_end_norm'].pct_change().dropna()

print(f"\nEstatísticas básicas:")
print(f"  TRAIN: mean={br_train_rets.mean():.6f}, std={br_train_rets.std():.6f}")
print(f"  HOLDOUT: mean={br_holdout_rets.mean():.6f}, std={br_holdout_rets.std():.6f}")

# Autocorrelação
ac1_train = br_train_rets.autocorr(lag=1)
ac1_holdout = br_holdout_rets.autocorr(lag=1)
print(f"\nAutocorrelação AC(1):")
print(f"  TRAIN: {ac1_train:.4f}")
print(f"  HOLDOUT: {ac1_holdout:.4f}")

if abs(ac1_holdout) > 0.05:
    findings.append({
        "frente": "5",
        "severidade": "ALTO" if abs(ac1_holdout) > 0.1 else "MEDIO",
        "descricao": f"AC(1) significativo no HOLDOUT: {ac1_holdout:.4f}",
        "evidencia": "AC(1) > |0.05| sugere lookahead ou timing impossível"
    })
    print(f"  >>> FINDING: AC(1) = {ac1_holdout:.4f} (significativo!)")

# Curtose e Skew
from scipy.stats import kurtosis, skew
br_train_kurt = kurtosis(br_train_rets)
br_train_skew = skew(br_train_rets)
br_holdout_kurt = kurtosis(br_holdout_rets)
br_holdout_skew = skew(br_holdout_rets)

print(f"\nCurtose (excesso):")
print(f"  TRAIN: {br_train_kurt:.4f}")
print(f"  HOLDOUT: {br_holdout_kurt:.4f}")
print(f"\nSkewness:")
print(f"  TRAIN: {br_train_skew:.4f}")
print(f"  HOLDOUT: {br_holdout_skew:.4f}")

# KS test entre TRAIN e HOLDOUT
ks_stat, ks_pvalue = stats.ks_2samp(br_train_rets, br_holdout_rets)
print(f"\nKolmogorov-Smirnov test (TRAIN vs HOLDOUT):")
print(f"  KS statistic: {ks_stat:.4f}")
print(f"  p-value: {ks_pvalue:.4f}")

if ks_pvalue < 0.05:
    print(f"  >>> ATENÇÃO: Distribuições significativamente diferentes (p < 0.05)")

# Melhores dias vs rebalanceamento
print(f"\nMelhores dias de retorno (HOLDOUT):")
br_holdout_copy = br_holdout.copy()
br_holdout_copy['ret'] = br_holdout_copy['equity_end_norm'].pct_change()
top5_days = br_holdout_copy.nlargest(5, 'ret')[['date', 'ret', 'ret_strategy']]
print(top5_days.to_string())

# ============================================================================
# 2. ANÁLISE US WINNER (T122)
# ============================================================================
print("\n" + "-" * 70)
print("2. ANÁLISE DISTRIBUIÇÃO US WINNER")
print("-" * 70)

us_curve = pd.read_parquet(f"{REPO_PATH}/src/data_engine/portfolio/T122_US_ENGINE_WINNER_CURVE_DAILY.parquet")
us_curve['date'] = pd.to_datetime(us_curve['date'])

us_train = us_curve[us_curve['date'] <= TRAIN_END]
us_holdout = us_curve[us_curve['date'] >= HOLDOUT_START]

us_train_rets = us_train['equity_strategy'].pct_change().dropna()
us_holdout_rets = us_holdout['equity_strategy'].pct_change().dropna()

print(f"\nEstatísticas básicas:")
print(f"  TRAIN: mean={us_train_rets.mean():.6f}, std={us_train_rets.std():.6f}")
print(f"  HOLDOUT: mean={us_holdout_rets.mean():.6f}, std={us_holdout_rets.std():.6f}")

# Autocorrelação
ac1_train_us = us_train_rets.autocorr(lag=1)
ac1_holdout_us = us_holdout_rets.autocorr(lag=1)
print(f"\nAutocorrelação AC(1):")
print(f"  TRAIN: {ac1_train_us:.4f}")
print(f"  HOLDOUT: {ac1_holdout_us:.4f}")

if abs(ac1_holdout_us) > 0.05:
    findings.append({
        "frente": "5",
        "severidade": "ALTO" if abs(ac1_holdout_us) > 0.1 else "MEDIO",
        "descricao": f"AC(1) significativo no HOLDOUT US: {ac1_holdout_us:.4f}",
        "evidencia": "AC(1) > |0.05| sugere lookahead ou timing impossível"
    })
    print(f"  >>> FINDING: AC(1) = {ac1_holdout_us:.4f} (significativo!)")

# KS test
ks_stat_us, ks_pvalue_us = stats.ks_2samp(us_train_rets, us_holdout_rets)
print(f"\nKolmogorov-Smirnov test (TRAIN vs HOLDOUT US):")
print(f"  KS statistic: {ks_stat_us:.4f}")
print(f"  p-value: {ks_pvalue_us:.4f}")

# ============================================================================
# RESUMO
# ============================================================================
print("\n" + "=" * 70)
print("RESUMO FRENTE 5")
print("=" * 70)

if findings:
    print(f"\nEncontrados {len(findings)} findings:")
    for f in findings:
        print(f"  [{f['severidade']}] {f['descricao']}")
        print(f"    {f['evidencia']}")
else:
    print("\nNenhum finding de distribuição detectado")
    print(f"  BR AC(1): {ac1_holdout:.4f} (limite: 0.05)")
    print(f"  US AC(1): {ac1_holdout_us:.4f} (limite: 0.05)")

with open(f"{REPO_PATH}/auditoria_kimi_frente5_resultados.json", 'w') as f:
    json.dump({
        "findings": findings,
        "stats": {
            "BR": {"ac1_holdout": float(ac1_holdout), "ks_pvalue": float(ks_pvalue)},
            "US": {"ac1_holdout": float(ac1_holdout_us), "ks_pvalue": float(ks_pvalue_us)}
        },
        "timestamp": datetime.now().isoformat()
    }, f, indent=2)

print(f"\nResultados salvos em: {REPO_PATH}/auditoria_kimi_frente5_resultados.json")
