#!/usr/bin/env bash
# Corre o Swiss-Company-Enricher usando como entrada o CSV produzido pelo
# scrape_chregister_vs.py (valais_completo.csv), com 5 workers.
#
# Estrutura esperada (a partir da pasta onde este script está):
#   ./valais_completo.csv              <- saída do scrape_chregister_vs.py
#   ./venv/                            <- ambiente virtual já criado
#   ./Swiss-Company-Enricher-main/     <- projeto de enriquecimento
#
# Uso:
#   chmod +x run_enrich_valais.sh
#   ./run_enrich_valais.sh
#
# Seguro interromper (Ctrl+C) e correr outra vez: o cache SQLite
# (output/progress.db) permite retomar sem repetir empresas já enriquecidas.

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

VENV_DIR="venv"
PROJECT_DIR="Swiss-Company-Enricher-main"
INPUT_CSV="$DIR/valais_completo.csv"
OUTPUT_CSV="output/empresas_enriched.csv"
WORKERS=5

if [ ! -f "$INPUT_CSV" ]; then
    echo "Erro: não encontrei $INPUT_CSV (saída do scrape_chregister_vs.py)."
    exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
    echo "Erro: não encontrei o ambiente virtual em ./$VENV_DIR."
    echo "Corra primeiro o setup do Swiss-Company-Enricher (pip install -r requirements.txt)."
    exit 1
fi

echo "==> A ativar o ambiente virtual..."
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

cd "$PROJECT_DIR"

echo "==> A correr o enriquecimento com $WORKERS workers"
echo "    Input:  $INPUT_CSV"
echo "    Output: $PROJECT_DIR/$OUTPUT_CSV"
python3 main.py \
    --input "$INPUT_CSV" \
    --output "$OUTPUT_CSV" \
    --workers "$WORKERS"

echo "==> Concluído. Resultado em: $PROJECT_DIR/$OUTPUT_CSV"
