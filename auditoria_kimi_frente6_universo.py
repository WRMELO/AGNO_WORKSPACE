#!/usr/bin/env python3
"""
Auditoria Kimi K2.5 - Frente 6: Validação de Universo e Seleção
Verifica survivorship bias e viés de seleção
"""

import pandas as pd
import json
from datetime import datetime

print("=" * 70)
print("KIMI K2.5 AUDITORIA - FRENTE 6: VALIDAÇÃO DE UNIVERSO")
print("=" * 70)

REPO_PATH = "/home/wilson/AGNO_WORKSPACE"
findings = []

# ============================================================================
# 1. VERIFICAR UNIVERSO BR
# ============================================================================
print("\n" + "-" * 70)
print("1. UNIVERSO BR (663 tickers)")
print("-" * 70)

br_universe = pd.read_parquet(f"{REPO_PATH}/src/data_engine/ssot/SSOT_UNIVERSE_OPERATIONAL.parquet")
print(f"\nShape do universo BR: {br_universe.shape}")
print(f"Colunas: {list(br_universe.columns)}")
print(f"\nAmostra de tickers:")
print(br_universe.head(10).to_string())

# Contar tickers únicos
n_tickers_br = br_universe['ticker'].nunique() if 'ticker' in br_universe.columns else "N/A"
print(f"\nNúmero de tickers únicos: {n_tickers_br}")

# Verificar se há tickers deslistados (teriam datas de fim)
if 'data_fim' in br_universe.columns or 'end_date' in br_universe.columns:
    print("\n>>> Coluna de data fim encontrada — possível rastreamento de deslistamentos")
else:
    print("\n>>> AVISO: Não encontrada coluna de data fim — não é possível verificar deslistamentos diretamente")

# ============================================================================
# 2. VERIFICAR UNIVERSO US (S&P 500)
# ============================================================================
print("\n" + "-" * 70)
print("2. UNIVERSO US (S&P 500)")
print("-" * 70)

# Procurar snapshot do S&P 500
import os
sp500_files = []
for root, dirs, files in os.walk(f"{REPO_PATH}/outputs"):
    for file in files:
        if 'sp500' in file.lower() and file.endswith('.csv'):
            sp500_files.append(os.path.join(root, file))

print(f"\nArquivos S&P 500 encontrados:")
for f in sp500_files[:5]:
    print(f"  {f}")

# Ler o snapshot se existir
if sp500_files:
    sp500_snapshot = pd.read_csv(sp500_files[0])
    print(f"\nSnapshot S&P 500 shape: {sp500_snapshot.shape}")
    print(f"Colunas: {list(sp500_snapshot.columns)}")
    print(f"\nPrimeiras linhas:")
    print(sp500_snapshot.head().to_string())
    
    # Verificar se há data no arquivo
    if 'date' in sp500_snapshot.columns:
        print(f"\nData do snapshot: {sp500_snapshot['date'].iloc[0]}")
    
    # Verificar se há composição histórica vs atual
    print(f"\n>>> ATENÇÃO: Se este snapshot é de 2026, mas o backtest começa em 2018,")
    print(f"    então estamos usando composição futura = SURVIVORSHIP BIAS CRITICO")

# Ler universe US
us_universe = pd.read_parquet(f"{REPO_PATH}/src/data_engine/ssot/SSOT_US_UNIVERSE_OPERATIONAL.parquet")
print(f"\nShape do universo US: {us_universe.shape}")
print(f"Colunas: {list(us_universe.columns)}")
n_tickers_us = us_universe['ticker'].nunique() if 'ticker' in us_universe.columns else us_universe.shape[0]
print(f"Número de tickers únicos: {n_tickers_us}")

# ============================================================================
# 3. VERIFICAR SCRIPT DE INGESTÃO US
# ============================================================================
print("\n" + "-" * 70)
print("3. ANÁLISE DO SCRIPT DE INGESTÃO S&P 500 (T084)")
print("-" * 70)

# Ler o script para verificar como obtém o universo
t084_path = f"{REPO_PATH}/scripts/t084_ingest_sp500_brapi_us_market_data.py"
with open(t084_path, 'r') as f:
    t084_content = f.read()

# Procurar por referências ao snapshot
if 'sp500_current_symbols_snapshot.csv' in t084_content:
    print("\n>>> FINDING CRITICO: Script T084 usa 'sp500_current_symbols_snapshot.csv'")
    print("    Isso significa que o universo é baseado na composição ATUAL do S&P 500,")
    print("    não na composição histórica de 2018.")
    print("    = SURVIVORSHIP BIAS: empresas que saíram do índice não estão incluídas.")
    findings.append({
        "frente": "6",
        "severidade": "CRITICO",
        "descricao": "Universo US baseado em sp500_current_symbols_snapshot.csv = composição futura",
        "evidencia": "t084_ingest_sp500_brapi_us_market_data.py linha com sp500_current_symbols_snapshot.csv"
    })

if 'brapi' in t084_content.lower():
    print("\n>>> US data sourced from BRAPI (Brazilian API) — verificar se dados históricos")
    print("    incluem tickers deslistados")

# ============================================================================
# 4. RESUMO
# ============================================================================
print("\n" + "=" * 70)
print("RESUMO FRENTE 6")
print("=" * 70)

if findings:
    print(f"\nEncontrados {len(findings)} findings:")
    for f in findings:
        print(f"  [{f['severidade']}] {f['descricao']}")
        print(f"    Evidência: {f['evidencia']}")
else:
    print("\nNenhum finding de universo detectado (requer investigação manual adicional)")

with open(f"{REPO_PATH}/auditoria_kimi_frente6_resultados.json", 'w') as f:
    json.dump({
        "findings": findings,
        "universes": {
            "BR": {"n_tickers": int(n_tickers_br) if isinstance(n_tickers_br, (int, float)) else str(n_tickers_br)},
            "US": {"n_tickers": int(n_tickers_us) if isinstance(n_tickers_us, (int, float)) else str(n_tickers_us)}
        },
        "timestamp": datetime.now().isoformat()
    }, f, indent=2)

print(f"\nResultados salvos em: {REPO_PATH}/auditoria_kimi_frente6_resultados.json")
