#!/usr/bin/env python3
"""
Auditoria Kimi K2.5 - Frente 2: Integridade SHA256
Verifica se hashes batem
"""

import hashlib
import json
import os
from datetime import datetime

print("=" * 70)
print("KIMI K2.5 AUDITORIA - FRENTE 2: INTEGRIDADE SHA256")
print("=" * 70)

REPO_PATH = "/home/wilson/AGNO_WORKSPACE"
findings = []

# Função para calcular SHA256
def compute_sha256(filepath):
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()

# Procurar manifests
manifests = []
for root, dirs, files in os.walk(f"{REPO_PATH}/outputs/governanca"):
    for file in files:
        if file.endswith('_manifest.json'):
            manifests.append(os.path.join(root, file))

print(f"\nManifests encontrados: {len(manifests)}")

# Verificar os principais
key_manifests = [m for m in manifests if any(x in m for x in ['T107', 'T122', 'T128'])]
print(f"Manifests chave (T107, T122, T128): {len(key_manifests)}")

for manifest_path in key_manifests[:3]:  # Verificar os 3 principais
    print(f"\n{'='*60}")
    print(f"Verificando: {os.path.basename(manifest_path)}")
    print(f"{'='*60}")
    
    try:
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        print(f"  Task: {manifest.get('task_id', 'N/A')}")
        print(f"  Status: {manifest.get('overall_status', 'N/A')}")
        
        # Verificar artefatos
        if 'artifacts' in manifest:
            for artifact in manifest['artifacts']:
                filepath = artifact.get('path', '')
                declared_hash = artifact.get('hash', '')
                
                if filepath and os.path.exists(filepath):
                    actual_hash = compute_sha256(filepath)
                    match = actual_hash == declared_hash
                    status = "✓ OK" if match else "✗ DIVERGE"
                    print(f"  {status} {os.path.basename(filepath)}")
                    if not match:
                        findings.append({
                            "frente": "2",
                            "severidade": "CRITICO",
                            "descricao": f"Hash divergente em {filepath}",
                            "evidencia": f"Declarado: {declared_hash[:16]}... | Real: {actual_hash[:16]}..."
                        })
                else:
                    print(f"  ? N/A  {os.path.basename(filepath)} (arquivo não encontrado)")
                    
    except Exception as e:
        print(f"  ERRO ao ler manifest: {e}")

# Resumo
print("\n" + "=" * 70)
print("RESUMO FRENTE 2")
print("=" * 70)

if findings:
    print(f"\nEncontrados {len(findings)} findings:")
    for f in findings:
        print(f"  [{f['severidade']}] {f['descricao']}")
else:
    print(f"\nNenhum hash divergente detectado nos manifests verificados")

with open(f"{REPO_PATH}/auditoria_kimi_frente2_resultados.json", 'w') as f:
    json.dump({
        "findings": findings,
        "manifests_checked": len(key_manifests),
        "timestamp": datetime.now().isoformat()
    }, f, indent=2)

print(f"\nResultados salvos em: {REPO_PATH}/auditoria_kimi_frente2_resultados.json")
