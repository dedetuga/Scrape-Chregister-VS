#!/usr/bin/env python3
"""Diagnóstico isolado: testa cada backend do ddgs, um de cada vez, sem o pipeline todo."""

import sys
from ddgs import DDGS

print(f"Python: {sys.version}")
try:
    import ddgs
    print(f"ddgs version: {ddgs.__version__ if hasattr(ddgs, '__version__') else '?'}")
except Exception as e:
    print(f"Erro a importar ddgs: {e}")

for backend in ["duckduckgo", "brave", "yahoo", "yandex", "mojeek", "startpage"]:
    print(f"\n--- Testando backend: {backend} ---")
    try:
        with DDGS(timeout=10) as ddgs_client:
            results = ddgs_client.text("Migros Suisse", max_results=3, backend=backend)
            print(f"OK: {len(results)} resultados")
            for r in results[:2]:
                print(f"  - {r.get('href') or r.get('url')}")
    except Exception as e:
        print(f"FALHOU: {type(e).__name__}: {e}")
