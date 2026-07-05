# Scrape Chregister VS

Ferramentas para extrair empresas registadas no Registo do Comércio do cantão
do Valais (Suíça) e enriquecer esses dados com website, email e telefone
encontrados publicamente na internet.

O projeto tem dois passos, que podem ser corridos em conjunto ou separados:

```
scrape_chregister_vs.py                    Swiss-Company-Enricher-main/
(vs.chregister.ch)                         (pesquisa web + scraping de contactos)
        │                                              │
        ▼                                              ▼
  valais_completo.csv   ─────────────────────►  empresas_enriched.csv
  (IDE, Societe,                                (+ Website, Email, Telefone,
   Siege, Nature_juridique)                       Facebook, Instagram, LinkedIn...)
```

## ⚠️ Antes de usar

- Isto faz scraping de sites públicos (o registo oficial do comércio e
  motores de busca gratuitos). Não é uso de nenhuma API oficial. Confirme os
  Termos de Uso e `robots.txt` dos sites envolvidos antes de correr em massa.
- Os resultados do enriquecimento (email/telefone/website) vêm de pesquisa e
  scraping automáticos — trate-os como um ponto de partida, não como dados
  100% fiáveis. Nem todas as empresas têm presença online.
- Se pretende usar os contactos encontrados para marketing, verifique as
  regras aplicáveis de comunicação comercial não solicitada na Suíça (LCD/UWG)
  e proteção de dados (nLPD) antes de enviar campanhas em massa.

## Estrutura do repositório

```
.
├── scrape_chregister_vs.py           # Extrator do Registo do Comércio (vs.chregister.ch)
├── run_scrape_completo.sh            # Prepara venv + corre o varrimento completo
├── README_scrape_chregister_vs.md    # Documentação do extrator
│
├── Swiss-Company-Enricher-main/      # Enriquecimento (website/email/telefone)
│   ├── main.py
│   ├── config.py
│   ├── company_enricher/
│   └── README.md                     # Documentação do enriquecimento
├── run_enrich_valais.sh              # Corre o enriquecimento sobre valais_completo.csv
│
├── run_pipeline_completo.sh          # Corre os dois passos acima, por ordem
└── README_run_pipeline_completo.md   # Documentação do pipeline completo
```

## Início rápido

Correr tudo, do zero, num único comando:

```bash
chmod +x run_pipeline_completo.sh run_scrape_completo.sh run_enrich_valais.sh
./run_pipeline_completo.sh
```

Isto:
1. Cria o ambiente virtual Python e instala as dependências necessárias.
2. Varre o Registo do Comércio do Valais → `valais_completo.csv`.
3. Enriquece cada empresa com website/email/telefone → `Swiss-Company-Enricher-main/output/empresas_enriched.csv`.

**Tempo total estimado: ~1 a 1,5 dias** de execução contínua (isto é scraping
gratuito, não uma API paga — ver documentação de cada passo para detalhes).
Pode interromper com Ctrl+C a qualquer momento; todos os passos retomam
automaticamente de onde ficaram.

## Correr os passos individualmente

Só o varrimento do registo:
```bash
./run_scrape_completo.sh
```

Só o enriquecimento (assumindo que já tem `valais_completo.csv`):
```bash
./run_enrich_valais.sh
```

Ver `README_scrape_chregister_vs.md` e `Swiss-Company-Enricher-main/README.md`
para opções avançadas (filtros, número de workers, backends de pesquisa, etc.).

## Formato dos dados

**`valais_completo.csv`** (saída do passo 1 / entrada do passo 2):

| IDE | Societe | Siege | Nature_juridique |
|---|---|---|---|
| CHE-409.337.525 | A.A.A. Speed Serrurerie Urgence, Kombas | Port-Valais | Entreprise individuelle |

**`empresas_enriched.csv`** (saída final, passo 2): as mesmas colunas acima
mais `Website, Email, Telefone, Codigo_postal, Cidade_detectada, Facebook,
Instagram, LinkedIn, Paginas_analisadas`.

## Licença

Todos os direitos reservados. Este repositório não inclui uma licença de
código aberto — ver ficheiro de licença (ou a ausência dele) para detalhes.
