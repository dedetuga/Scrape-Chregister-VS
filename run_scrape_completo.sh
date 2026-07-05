#!/usr/bin/env bash
# Prepara o ambiente virtual e corre o varrimento completo (--auto) do
# registo do comércio do Valais, gravando o resultado em valais_completo.csv.
#
# Uso:
#   chmod +x run_scrape_completo.sh
#   ./run_scrape_completo.sh
#
# É seguro interromper com Ctrl+C e correr outra vez: o script retoma
# automaticamente de onde ficou (ver README_scrape_chregister_vs.md).

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

VENV_DIR="venv"
OUT_CSV="valais_completo.csv"

if [ ! -d "$VENV_DIR" ]; then
    echo "==> A criar o ambiente virtual em ./$VENV_DIR ..."
    python3 -m venv "$VENV_DIR"
fi

echo "==> A ativar o ambiente virtual..."
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "==> A instalar/atualizar dependências..."
pip install --upgrade pip --quiet
pip install requests beautifulsoup4 --quiet

echo "==> A iniciar o varrimento completo (--auto) -> $OUT_CSV"
echo "    (pode interromper com Ctrl+C e correr este script outra vez para retomar)"
python3 scrape_chregister_vs.py --auto --out "$OUT_CSV"

echo "==> Concluído. Resultado em: $OUT_CSV"
