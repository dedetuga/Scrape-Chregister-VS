#!/usr/bin/env bash
# Corre o pipeline completo, por ordem:
#   1) run_scrape_completo.sh  -> gera valais_completo.csv (registo do comércio)
#   2) run_enrich_valais.sh    -> enriquece esse CSV com website/email/telefone
#
# Uso:
#   chmod +x run_pipeline_completo.sh
#   ./run_pipeline_completo.sh
#
# Se o passo 1 for interrompido (Ctrl+C) e voltar a correr este script, ele
# retoma sozinho de onde ficou (ambos os scripts já são resumíveis). Se o
# passo 1 falhar (código de saída != 0), o passo 2 NÃO arranca, para não
# enriquecer um CSV incompleto/corrompido.

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

SCRAPE_SCRIPT="./run_scrape_completo.sh"
ENRICH_SCRIPT="./run_enrich_valais.sh"

for script in "$SCRAPE_SCRIPT" "$ENRICH_SCRIPT"; do
    if [ ! -f "$script" ]; then
        echo "Erro: não encontrei $script nesta pasta."
        exit 1
    fi
done

echo "############################################################"
echo "# PASSO 1/2 — Varrimento do registo do comércio (Valais)"
echo "############################################################"
"$SCRAPE_SCRIPT"

echo
echo "############################################################"
echo "# PASSO 2/2 — Enriquecimento de contactos (website/email/tel)"
echo "############################################################"
"$ENRICH_SCRIPT"

echo
echo "==> Pipeline completo. Resultado final em:"
echo "    Swiss-Company-Enricher-main/output/empresas_enriched.csv"
