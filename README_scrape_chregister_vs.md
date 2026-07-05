# scrape_chregister_vs.py — Extrator do Registo do Comércio do Valais

Script que extrai empresas registadas no Registo do Comércio do cantão do Valais,
a partir do portal oficial [vs.chregister.ch](https://vs.chregister.ch), e gera um
CSV com as colunas `IDE, Societe, Siege, Nature_juridique` — exatamente o formato
usado pelo [Swiss Company Enricher](./README.md) para depois preencher email,
telefone e website de cada empresa.

## ⚠️ Antes de usar

- Confirme os [Termos de Uso](https://vs.chregister.ch) e o
  [`robots.txt`](https://vs.chregister.ch/robots.txt) do site, e as condições de
  reutilização de dados do registo do comércio suíço, antes de fazer scraping em
  massa (especialmente no modo `--auto`, que percorre o site inteiro).
- Isto não é uma API oficial — é scraping de um formulário web (JSF/PrimeFaces).
  Se o site mudar de estrutura, o script pode parar de funcionar até ser ajustado.
- Corra a um ritmo razoável (`--delay`, por defeito 1.2s). Ritmos agressivos
  aumentam o risco de bloqueios temporários (HTTP 403) — o script já tem
  retry/backoff automático para isso, mas não é motivo para forçar a velocidade.

## Instalação

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install requests beautifulsoup4
```

## Como funciona (resumo técnico)

O portal do registo é uma aplicação JSF/PrimeFaces: cada pesquisa é um POST que
precisa de reenviar um token `javax.faces.ViewState` válido, obtido a partir da
página carregada antes. A paginação da tabela de resultados usa pedidos AJAX
parciais próprios do PrimeFaces (respostas em XML, não HTML normal). O script
trata de tudo isto automaticamente: carrega a página, extrai o token, envia a
pesquisa, e percorre as páginas seguintes até ao fim ou ao limite de 500
resultados por consulta imposto pelo próprio site.

## Modos de utilização

### 1. Pesquisa simples (`--company`)

Procura um termo literal no campo "Société" e guarda tudo num CSV novo (substitui
o ficheiro de saída se já existir):

```bash
python3 scrape_chregister_vs.py --company "immobilier" --out imobiliarias.csv
```

Útil para testar rapidamente ou para extrair só um subconjunto de empresas.

### 2. Varrimento completo (`--auto`)

Percorre **todas as combinações de 3 caracteres** (letras `a-z` + `&`) como
consultas literais — na prática, uma forma de cobrir todo o registo, já que o
site não oferece um "listar tudo". Os resultados são **acrescentados** ao CSV de
saída à medida que são encontrados (não substitui o ficheiro):

```bash
python3 scrape_chregister_vs.py --auto --out valais_completo.csv
```

**É resumível.** Se interromper (Ctrl+C, queda de ligação, etc.) e correr o
mesmo comando outra vez, o script:
- lê o CSV de saída existente para saber que UIDs (`IDE`) já tem;
- lê `<out>.progress.txt` para saber que combinações de 3 letras já concluiu;
- salta tudo o que já está feito e continua exatamente de onde parou.

Isto significa que **pode correr isto ao longo de vários dias**, em sessões
curtas, sem perder trabalho e sem duplicar empresas no CSV final (a deduplicação
é feita pelo UID/`IDE`).

**Tempo estimado:** com 27 caracteres possíveis (`a-z` + `&`) elevado a 3,
há 19.683 combinações a testar. Com o delay por defeito (1.2s) e assumindo a
maioria das combinações com só 1 página de resultados, conte com **pelo menos
6-8 horas** de corrida contínua para cobrir tudo — mais, se muitas combinações
tiverem várias páginas de resultados (empresas comuns geram mais tráfego de
paginação).

## Opções

| Opção | Default | Descrição |
|---|---|---|
| `--company TERMO` | — | Pesquisa simples por um termo (usar em vez de `--auto`) |
| `--auto` | — | Varre todas as combinações de 3 caracteres |
| `--out FICHEIRO.csv` | `chregister_vs.csv` | CSV de saída |
| `--delay SEGUNDOS` | `1.2` | Espera entre pedidos HTTP |
| `--max-pages N` | `30` | Máximo de páginas por consulta (20 linhas/página) |
| `--debug` | desligado | Grava respostas AJAX brutas em `debug_page_*` para diagnóstico |

## Limitação conhecida: tampo de 500 resultados

O site só mostra até 500 resultados por consulta. Para combinações de 3
caracteres muito comuns que ultrapassem esse limite, o script **avisa no
terminal** (`[aviso] limite de 500 atingido...`) mas não expande automaticamente
a consulta para mais caracteres — ficaria com uma parte das empresas desse trio
em falta. Se vir esse aviso para alguma combinação, refine manualmente com
`--company` usando um termo mais específico (ex: 4 letras em vez de 3) para
capturar o que faltou.

## Ficheiros de saída

- **`<out>.csv`**: uma linha por empresa, colunas `IDE, Societe, Siege,
  Nature_juridique`. Sem duplicados (deduplicação por `IDE`).
- **`<out>.csv.progress.txt`** (só no modo `--auto`): lista de combinações de 3
  caracteres já concluídas — permite retomar. Pode apagar este ficheiro se
  quiser forçar uma nova varredura completa do zero.
- **`debug_page_*.xml` / `debug_page_*_empty.txt` / `debug_page_*_raw.txt`**
  (só com `--debug`, ou automaticamente quando uma página devolve uma resposta
  inesperada/vazia): úteis para perceber se o site mudou de estrutura.

## A seguir: enriquecimento de contactos

O CSV gerado aqui (`IDE, Societe, Siege, Nature_juridique`) é exatamente o
formato de entrada esperado pelo
[Swiss Company Enricher](./README.md) — o passo seguinte para tentar
preencher email, telefone e website de cada empresa encontrada.
