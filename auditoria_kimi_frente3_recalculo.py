#!/usr/bin/env python3
"""
Auditoria Kimi K2.5 - Frente 3: Reprodutibilidade Aritmética
Recalcula métricas financeiras do zero a partir das equity curves
"""

import pandas as pd
import numpy as np
import json
from datetime import datetime

print("=" * 70)
print("KIMI K2.5 AUDITORIA - FRENTE 3: RECÁLCULO ARITMÉTICO")
print("=" * 70)

# ============================================================================
# CONFIGURAÇÕES
# ============================================================================
REPO_PATH = "/home/wilson/AGNO_WORKSPACE"
TRAIN_END = "2022-12-30"
HOLDOUT_START = "2023-01-02"
HOLDOUT_END = "2026-02-26"

# Valores reportados para comparação
REPORTED = {
    "BR_HOLDOUT": {"sharpe": 2.42, "mdd": -0.063, "cagr": 0.311},
    "US_HOLDOUT": {"sharpe": 1.19, "mdd": -0.283, "cagr": 0.355},
}

# ============================================================================
# FUNÇÕES DE CÁLCULO
# ============================================================================

def calc_sharpe(returns, risk_free_rate=0):
    """Sharpe ratio anualizado"""
    excess_returns = returns - risk_free_rate
    if excess_returns.std() == 0:
        return 0
    return excess_returns.mean() / excess_returns.std() * np.sqrt(252)

def calc_mdd(equity_series):
    """Maximum Drawdown"""
    rolling_max = equity_series.cummax()
    drawdown = (equity_series - rolling_max) / rolling_max
    return drawdown.min()

def calc_cagr(equity_series, n_days):
    """Compound Annual Growth Rate"""
    if len(equity_series) < 2 or equity_series.iloc[0] == 0:
        return 0
    total_return = equity_series.iloc[-1] / equity_series.iloc[0]
    return (total_return ** (252 / n_days)) - 1

# ============================================================================
# 1. RECÁLCULO BR WINNER (C060X / T107)
# ============================================================================
print("\n" + "=" * 70)
print("1. RECÁLCULO BR WINNER (C060X via T107)")
print("=" * 70)

# Carregar equity curve BR
br_curve_path = f"{REPO_PATH}/src/data_engine/portfolio/T107_PORTFOLIO_CURVE_DUAL_MODE_EXPANDED_ML_TRIGGER.parquet"
br_curve = pd.read_parquet(br_curve_path)

# Carregar macro data para CDI
macro_path = f"{REPO_PATH}/src/data_engine/ssot/SSOT_MACRO_EXPANDED.parquet"
macro_df = pd.read_parquet(macro_path)

print(f"\n[BR] Equity curve shape: {br_curve.shape}")
print(f"[BR] Colunas: {list(br_curve.columns)}")
print(f"[BR] Date range: {br_curve.index.min()} to {br_curve.index.max()}")

# Verificar colunas disponíveis
if 'date' in br_curve.columns:
    br_curve['date'] = pd.to_datetime(br_curve['date'])
    br_curve.set_index('date', inplace=True)
else:
    br_curve.index = pd.to_datetime(br_curve.index)

# Separar TRAIN e HOLDOUT
br_holdout = br_curve[br_curve.index >= HOLDOUT_START]
br_train = br_curve[br_curve.index <= TRAIN_END]

print(f"[BR] HOLDOUT shape: {br_holdout.shape}")
print(f"[BR] TRAIN shape: {br_train.shape}")

# Calcular retornos - usar equity_end_norm
br_holdout_returns = br_holdout['equity_end_norm'].pct_change().dropna()
br_train_returns = br_train['equity_end_norm'].pct_change().dropna()

# Obter CDI diário
if 'date' in macro_df.columns:
    macro_df['date'] = pd.to_datetime(macro_df['date'])
    macro_df.set_index('date', inplace=True)
else:
    macro_df.index = pd.to_datetime(macro_df.index)

# Fazer merge para alinhar datas
br_holdout_aligned = br_holdout.join(macro_df[['cdi_log_daily']], how='left')
br_train_aligned = br_train.join(macro_df[['cdi_log_daily']], how='left')

# Verificar se cdi_log_daily existe
print(f"\n[BR] CDI disponível no HOLDOUT: {br_holdout_aligned['cdi_log_daily'].notna().sum()} de {len(br_holdout_aligned)}")

# Recalcular Sharpe BR HOLDOUT
br_sharpe_no_rf = calc_sharpe(br_holdout_returns, risk_free_rate=0)
br_sharpe_with_rf = None
if 'cdi_log_daily' in br_holdout_aligned.columns and br_holdout_aligned['cdi_log_daily'].notna().any():
    cdi_returns = br_holdout_aligned['cdi_log_daily'].dropna()
    # Alinear retornos com CDI
    common_dates = br_holdout_returns.index.intersection(cdi_returns.index)
    if len(common_dates) > 0:
        br_returns_aligned = br_holdout_returns.loc[common_dates]
        cdi_aligned = cdi_returns.loc[common_dates]
        br_sharpe_with_rf = calc_sharpe(br_returns_aligned, risk_free_rate=cdi_aligned)

br_mdd = calc_mdd(br_holdout['equity_end_norm'])
br_cagr = calc_cagr(br_holdout['equity_end_norm'], len(br_holdout))

# Contar switches de regime (transições cash/market)
if 'state_cash' in br_holdout.columns:
    br_switches = ((br_holdout['state_cash'].diff().abs() == 1).sum()) // 2  # Cada transição completa conta como 1
    br_cash_frac = br_holdout['state_cash'].mean()
else:
    br_switches = "N/A - coluna state_cash não encontrada"
    br_cash_frac = "N/A"

print(f"\n[BR HOLDOUT RECALCULADO]")
print(f"  Sharpe (sem rf): {br_sharpe_no_rf:.4f}")
if br_sharpe_with_rf is not None:
    print(f"  Sharpe (com CDI): {br_sharpe_with_rf:.4f}")
else:
    print(f"  Sharpe (com CDI): N/A - CDI não disponível")
print(f"  MDD: {br_mdd:.4f} ({br_mdd*100:.2f}%)")
print(f"  CAGR: {br_cagr:.4f} ({br_cagr*100:.2f}%)")
print(f"  Switches: {br_switches}")
print(f"  % Cash: {br_cash_frac if isinstance(br_cash_frac, str) else f'{br_cash_frac*100:.1f}%'}")

print(f"\n[BR HOLDOUT REPORTADO]")
print(f"  Sharpe: {REPORTED['BR_HOLDOUT']['sharpe']:.2f}")
print(f"  MDD: {REPORTED['BR_HOLDOUT']['mdd']*100:.1f}%")
print(f"  CAGR: {REPORTED['BR_HOLDOUT']['cagr']*100:.1f}%")

# ============================================================================
# 2. RECÁLCULO US WINNER (T122)
# ============================================================================
print("\n" + "=" * 70)
print("2. RECÁLCULO US WINNER (T122)")
print("=" * 70)

# Carregar equity curve US
us_curve_path = f"{REPO_PATH}/src/data_engine/portfolio/T122_US_ENGINE_WINNER_CURVE_DAILY.parquet"
us_curve = pd.read_parquet(us_curve_path)

print(f"\n[US] Equity curve shape: {us_curve.shape}")
print(f"[US] Colunas: {list(us_curve.columns)}")

if 'date' in us_curve.columns:
    us_curve['date'] = pd.to_datetime(us_curve['date'])
    us_curve.set_index('date', inplace=True)
else:
    us_curve.index = pd.to_datetime(us_curve.index)

# Separar TRAIN e HOLDOUT
us_holdout = us_curve[us_curve.index >= HOLDOUT_START]
us_train = us_curve[us_curve.index <= TRAIN_END]

print(f"[US] HOLDOUT shape: {us_holdout.shape}")
print(f"[US] Date range HOLDOUT: {us_holdout.index.min()} to {us_holdout.index.max()}")

# Calcular retornos - verificar coluna equity
print(f"[US] Colunas disponíveis: {list(us_holdout.columns)}")
us_equity_col = 'equity_strategy' if 'equity_strategy' in us_holdout.columns else ('equity' if 'equity' in us_holdout.columns else 'equity_end_norm')
us_holdout_returns = us_holdout[us_equity_col].pct_change().dropna()

# Obter Fed Funds - tentar macro SSOT ou usar ret_cash_1d do próprio US curve
if 'ret_cash_1d' in us_holdout.columns:
    print("[US] Usando ret_cash_1d (Fed Funds) do próprio equity curve")
    rf_returns = us_curve.set_index('date')['ret_cash_1d'] if 'date' in us_curve.columns else us_curve['ret_cash_1d']
    rf_returns.index = pd.to_datetime(rf_returns.index)
elif 'fed_funds_rate' in macro_df.columns or 'cash_log_daily_us' in macro_df.columns:
    rf_col = 'cash_log_daily_us' if 'cash_log_daily_us' in macro_df.columns else 'fed_funds_rate'
    print(f"[US] Usando risk-free do macro: {rf_col}")
    rf_returns = macro_df[rf_col].dropna()
else:
    print("[US] AVISO: Risk-free rate não encontrado")
    rf_returns = None

# Recalcular Sharpe US HOLDOUT
us_sharpe_no_rf = calc_sharpe(us_holdout_returns, risk_free_rate=0)
us_sharpe_with_rf = None

if rf_returns is not None:
    common_dates_us = us_holdout_returns.index.intersection(rf_returns.index)
    if len(common_dates_us) > 0:
        us_returns_aligned = us_holdout_returns.loc[common_dates_us]
        rf_aligned = rf_returns.loc[common_dates_us]
        us_sharpe_with_rf = calc_sharpe(us_returns_aligned, risk_free_rate=rf_aligned)

us_mdd = calc_mdd(us_holdout[us_equity_col])
us_cagr = calc_cagr(us_holdout[us_equity_col], len(us_holdout))

# Contar switches
if 'state_cash' in us_holdout.columns:
    us_switches = ((us_holdout['state_cash'].diff().abs() == 1).sum()) // 2
    us_cash_frac = us_holdout['state_cash'].mean()
else:
    us_switches = "N/A"
    us_cash_frac = "N/A"

print(f"\n[US HOLDOUT RECALCULADO]")
print(f"  Sharpe (sem rf): {us_sharpe_no_rf:.4f}")
if us_sharpe_with_rf is not None:
    print(f"  Sharpe (com Fed Funds): {us_sharpe_with_rf:.4f}")
else:
    print(f"  Sharpe (com Fed Funds): N/A")
print(f"  MDD: {us_mdd:.4f} ({us_mdd*100:.2f}%)")
print(f"  CAGR: {us_cagr:.4f} ({us_cagr*100:.2f}%)")
print(f"  Switches: {us_switches}")
print(f"  % Cash: {us_cash_frac if isinstance(us_cash_frac, str) else f'{us_cash_frac*100:.1f}%'}")

print(f"\n[US HOLDOUT REPORTADO]")
print(f"  Sharpe: {REPORTED['US_HOLDOUT']['sharpe']:.2f}")
print(f"  MDD: {REPORTED['US_HOLDOUT']['mdd']*100:.1f}%")
print(f"  CAGR: {REPORTED['US_HOLDOUT']['cagr']*100:.1f}%")

# ============================================================================
# 3. ANÁLISE DE DIVERGÊNCIAS
# ============================================================================
print("\n" + "=" * 70)
print("3. ANÁLISE DE DIVERGÊNCIAS")
print("=" * 70)

print("\n[BR HOLDOUT - COMPARAÇÃO]")
print(f"  Sharpe reportado:    {REPORTED['BR_HOLDOUT']['sharpe']:.4f}")
print(f"  Sharpe recalc (s/rf): {br_sharpe_no_rf:.4f}")
if br_sharpe_with_rf is not None:
    delta_sharpe_br = br_sharpe_with_rf - REPORTED['BR_HOLDOUT']['sharpe']
    print(f"  Sharpe recalc (c/rf): {br_sharpe_with_rf:.4f} (delta: {delta_sharpe_br:+.4f})")
print(f"  MDD reportado:       {REPORTED['BR_HOLDOUT']['mdd']:.4f}")
print(f"  MDD recalc:          {br_mdd:.4f} (delta: {br_mdd - REPORTED['BR_HOLDOUT']['mdd']:+.4f})")
print(f"  CAGR reportado:      {REPORTED['BR_HOLDOUT']['cagr']:.4f}")
print(f"  CAGR recalc:         {br_cagr:.4f} (delta: {br_cagr - REPORTED['BR_HOLDOUT']['cagr']:+.4f})")

print("\n[US HOLDOUT - COMPARAÇÃO]")
print(f"  Sharpe reportado:    {REPORTED['US_HOLDOUT']['sharpe']:.4f}")
print(f"  Sharpe recalc (s/rf): {us_sharpe_no_rf:.4f}")
if us_sharpe_with_rf is not None:
    delta_sharpe_us = us_sharpe_with_rf - REPORTED['US_HOLDOUT']['sharpe']
    print(f"  Sharpe recalc (c/rf): {us_sharpe_with_rf:.4f} (delta: {delta_sharpe_us:+.4f})")
print(f"  MDD reportado:       {REPORTED['US_HOLDOUT']['mdd']:.4f}")
print(f"  MDD recalc:          {us_mdd:.4f} (delta: {us_mdd - REPORTED['US_HOLDOUT']['mdd']:+.4f})")
print(f"  CAGR reportado:      {REPORTED['US_HOLDOUT']['cagr']:.4f}")
print(f"  CAGR recalc:         {us_cagr:.4f} (delta: {us_cagr - REPORTED['US_HOLDOUT']['cagr']:+.4f})")

# ============================================================================
# 4. VERIFICAÇÃO DE MÉTODO DE SHARPE
# ============================================================================
print("\n" + "=" * 70)
print("4. VERIFICAÇÃO DO MÉTODO DE CÁLCULO DO SHARPE")
print("=" * 70)

print("\n" + "-" * 70)
print("HIPÓTESE: O Sharpe reportado NÃO desconta risk-free rate")
print("-" * 70)

if br_sharpe_with_rf is not None:
    br_diff_rf = abs(br_sharpe_no_rf - REPORTED['BR_HOLDOUT']['sharpe'])
    br_diff_with_rf = abs(br_sharpe_with_rf - REPORTED['BR_HOLDOUT']['sharpe'])
    print(f"\n[BR] Divergência Sharpe (sem rf):   {br_diff_rf:.4f}")
    print(f"[BR] Divergência Sharpe (com rf):  {br_diff_with_rf:.4f}")
    if br_diff_rf < br_diff_with_rf:
        print("  >>> VEREDICTO: O Sharpe reportado provavelmente NÃO desconta CDI")
    else:
        print("  >>> VEREDICTO: O Sharpe reportado provavelmente DESCONTA CDI")

if us_sharpe_with_rf is not None:
    us_diff_rf = abs(us_sharpe_no_rf - REPORTED['US_HOLDOUT']['sharpe'])
    us_diff_with_rf = abs(us_sharpe_with_rf - REPORTED['US_HOLDOUT']['sharpe'])
    print(f"\n[US] Divergência Sharpe (sem rf):   {us_diff_rf:.4f}")
    print(f"[US] Divergência Sharpe (com rf):  {us_diff_with_rf:.4f}")
    if us_diff_rf < us_diff_with_rf:
        print("  >>> VEREDICTO: O Sharpe reportado provavelmente NÃO desconta Fed Funds")
    else:
        print("  >>> VEREDICTO: O Sharpe reportado provavelmente DESCONTA Fed Funds")

print("\n" + "=" * 70)
print("FIM DO RECÁLCULO")
print("=" * 70)

# Salvar resultados para relatório final
results = {
    "timestamp": datetime.now().isoformat(),
    "BR": {
        "reported": REPORTED['BR_HOLDOUT'],
        "recalculated_no_rf": {
            "sharpe": float(br_sharpe_no_rf),
            "mdd": float(br_mdd),
            "cagr": float(br_cagr),
        },
        "recalculated_with_rf": {
            "sharpe": float(br_sharpe_with_rf) if br_sharpe_with_rf else None,
        } if br_sharpe_with_rf else None,
        "switches": int(br_switches) if isinstance(br_switches, (int, np.integer)) else br_switches,
        "cash_frac": float(br_cash_frac) if isinstance(br_cash_frac, (int, float, np.floating, np.integer)) else br_cash_frac,
    },
    "US": {
        "reported": REPORTED['US_HOLDOUT'],
        "recalculated_no_rf": {
            "sharpe": float(us_sharpe_no_rf),
            "mdd": float(us_mdd),
            "cagr": float(us_cagr),
        },
        "recalculated_with_rf": {
            "sharpe": float(us_sharpe_with_rf) if us_sharpe_with_rf else None,
        } if us_sharpe_with_rf else None,
        "switches": int(us_switches) if isinstance(us_switches, (int, np.integer)) else us_switches,
        "cash_frac": float(us_cash_frac) if isinstance(us_cash_frac, (int, float, np.floating, np.integer)) else us_cash_frac,
    }
}

output_path = f"{REPO_PATH}/auditoria_kimi_frente3_resultados.json"
with open(output_path, 'w') as f:
    json.dump(results, f, indent=2)

print(f"\nResultados salvos em: {output_path}")
