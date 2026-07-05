#!/usr/bin/env python3
"""
Script para extrair dados do Registro do Comércio do Valais (vs.chregister.ch).

⚠️ IMPORTANTE ANTES DE USAR:
- Verifique os Termos de Uso / robots.txt do site (https://vs.chregister.ch/robots.txt)
  e as condições de reutilização de dados do registro do comércio suíço antes de
  fazer scraping em massa.
- Este site é feito em JSF/PrimeFaces. Cada busca é um POST que precisa reenviar
  um token "javax.faces.ViewState" válido, obtido a partir da página carregada
  antes.
- A busca mostra no máximo 500 resultados por consulta. O modo --auto varre
  TODAS as combinações de 3 caracteres (letras a-z + "&") como consultas
  literais (sem curinga "*", já que o site parece buscar por "contém" mesmo
  sem wildcard). Se algum trio de caracteres ainda bater no limite de 500,
  o script avisa mas não expande automaticamente além de 3 caracteres -
  refine manualmente com --company se precisar.
- A paginação da tabela usa requisições AJAX parciais do PrimeFaces.
- O modo --auto é RESUMÍVEL: grava cada empresa nova no CSV assim que
  encontra e mantém um ficheiro "<out>.progress.txt" com as consultas já
  concluídas. Se você parar o script (Ctrl+C, queda de conexão, etc.) e
  rodar o mesmo comando de novo, ele salta automaticamente o que já foi
  feito e continua de onde parou.

Requisitos (recomendado usar um virtualenv):
    pip install requests beautifulsoup4

Uso:
    python scrape_chregister_vs.py --company "immobilier" --out resultado.csv
    python scrape_chregister_vs.py --auto --out valais_completo.csv
"""

import argparse
import csv
import itertools
import os
import re
import time
import sys
import string
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://vs.chregister.ch"
SEARCH_URL = f"{BASE_URL}/cr-portal/suche/suche.xhtml?amt=VS"
TABLE_ID = "idSucheForm:resultTable"
ROWS_PER_PAGE = 20
FIELDNAMES = ["IDE", "Societe", "Siege", "Nature_juridique"]

# Conjunto de caracteres usado no modo --auto: apenas letras a-z e "&"
# (removidos números, aspas, hífen, parênteses e acentos, que geravam
# combinações redundantes / com pouco valor).
BASE_CHARS = list(string.ascii_lowercase) + ["&"]
QUERY_LENGTH = 3  # combinações literais de 3 caracteres, sem curinga

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-CH,fr;q=0.9,en;q=0.8",
    "Referer": SEARCH_URL,
}

AJAX_HEADERS = {
    **HEADERS,
    "Faces-Request": "partial/ajax",
    "X-Requested-With": "XMLHttpRequest",
}


# --------------------------------------------------------------------------
# Comunicação com o site
# --------------------------------------------------------------------------

def get_session_and_form(session):
    """Carrega a página inicial e extrai o ViewState + nonce necessários pro POST."""
    resp = session.get(SEARCH_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    view_state_input = soup.find("input", {"name": "javax.faces.ViewState"})
    nonce_input = soup.find("input", {"name": "primefaces.nonce"})

    if not view_state_input:
        raise RuntimeError("Não encontrei o campo javax.faces.ViewState na página inicial.")

    view_state = view_state_input.get("value", "")
    nonce = nonce_input.get("value", "") if nonce_input else ""
    return soup, view_state, nonce


def build_search_payload(company_query, view_state, nonce):
    """Monta o corpo do POST equivalente a preencher 'Société' e clicar em 'Chercher'."""
    return {
        "idSucheForm": "idSucheForm",
        "idSucheForm:idFirma": company_query,
        "idSucheForm:idPerson": "",
        "idSucheForm:panel_active": "-1",
        "idSucheForm:j_idt169": "idSucheForm:j_idt169",  # botão "Chercher"
        "javax.faces.ViewState": view_state,
        "primefaces.nonce": nonce,
    }


def build_pagination_payload(company_query, view_state, first, rows=ROWS_PER_PAGE):
    """Monta o corpo do POST AJAX parcial que o PrimeFaces envia ao trocar de página."""
    return {
        "idSucheForm": "idSucheForm",
        "idSucheForm:idFirma": company_query,
        "idSucheForm:idPerson": "",
        "idSucheForm:panel_active": "-1",
        f"{TABLE_ID}_pagination": "true",
        f"{TABLE_ID}_first": str(first),
        f"{TABLE_ID}_rows": str(rows),
        f"{TABLE_ID}_skipChildren": "true",
        f"{TABLE_ID}_encodeFeature": "true",
        "javax.faces.partial.ajax": "true",
        "javax.faces.source": TABLE_ID,
        "javax.faces.partial.execute": TABLE_ID,
        "javax.faces.partial.render": TABLE_ID,
        "javax.faces.ViewState": view_state,
    }


def parse_results(html):
    """Extrai as linhas da tabela de resultados: IDE, Société, Siège, Nature juridique.

    Funciona tanto na página completa quanto no fragmento AJAX de paginação
    (que traz só as <tr data-ri="..."> soltas, sem <tbody> em volta).
    Sempre devolve (rows, warning).
    """
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    trs = soup.find_all("tr", attrs={"data-ri": True})

    if not trs:
        msg = soup.find("div", class_="ui-message")
        warning = msg.get_text(strip=True) if msg else "sem resultados (verifique se a busca tem no mínimo 3 caracteres)"
        return rows, warning

    for tr in trs:
        cells = tr.find_all("td")
        if len(cells) < 4:
            continue
        rows.append({
            "IDE": cells[0].get_text(strip=True),
            "Societe": cells[1].get_text(strip=True),
            "Siege": cells[2].get_text(strip=True),
            "Nature_juridique": cells[3].get_text(strip=True),
        })

    footer = soup.find("div", class_="ui-datatable-footer")
    warning = footer.get_text(strip=True) if footer else ""
    return rows, warning


def parse_partial_response(xml_text):
    """Extrai o HTML da tabela e o novo ViewState de uma resposta AJAX parcial do PrimeFaces."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None, None

    table_html = None
    new_view_state = None
    for update in root.iter("update"):
        uid = update.get("id", "")
        if "resultTable" in uid:
            table_html = update.text or ""
        elif "ViewState" in uid:
            new_view_state = (update.text or "").strip()
    return table_html, new_view_state


def extract_view_state(html):
    soup = BeautifulSoup(html, "html.parser")
    vs = soup.find("input", {"name": "javax.faces.ViewState"})
    return vs.get("value", "") if vs else None


def parse_total(warning):
    """Extrai o número total de resultados a partir do texto do rodapé da tabela."""
    m = re.search(r"trouv[ée]es?\s*:\s*(\d+)", warning or "", flags=re.IGNORECASE)
    return int(m.group(1)) if m else None


def search_first_page(session, query, delay=1.5, max_retries=3):
    """Faz a busca inicial (POST completo, equivalente a clicar em 'Chercher').

    Devolve (rows, warning, view_state_atual).
    """
    wait = delay
    for attempt in range(1, max_retries + 1):
        resp = None
        try:
            _, view_state, nonce = get_session_and_form(session)
            payload = build_search_payload(query, view_state, nonce)

            resp = session.post(SEARCH_URL, data=payload, headers=HEADERS, timeout=30)
            resp.raise_for_status()

            rows, warning = parse_results(resp.text)
            new_view_state = extract_view_state(resp.text) or view_state
            time.sleep(delay)
            return rows, warning, new_view_state

        except requests.exceptions.HTTPError:
            if resp is not None and resp.status_code == 403 and attempt < max_retries:
                backoff = wait * (2 ** (attempt - 1)) + 5
                print(f"  [403] bloqueio temporário em '{query}', tentativa {attempt}/{max_retries}, "
                      f"esperando {backoff:.0f}s...")
                time.sleep(backoff)
                continue
            raise


def fetch_page(session, query, view_state, first, delay=1.5, max_retries=3, debug=False):
    """Busca uma página adicional (2ª em diante) via requisição AJAX parcial.

    Devolve (rows, novo_view_state) ou (None, view_state) se não conseguir.
    """
    wait = delay
    for attempt in range(1, max_retries + 1):
        resp = None
        try:
            payload = build_pagination_payload(query, view_state, first)
            resp = session.post(SEARCH_URL, data=payload, headers=AJAX_HEADERS, timeout=30)
            resp.raise_for_status()

            if debug:
                with open(f"debug_page_first{first}.xml", "w", encoding="utf-8") as f:
                    f.write(resp.text)

            table_html, new_view_state = parse_partial_response(resp.text)
            if table_html is None:
                fname = f"debug_page_first{first}_raw.txt"
                with open(fname, "w", encoding="utf-8") as f:
                    f.write(f"STATUS: {resp.status_code}\n")
                    f.write(f"CONTENT-TYPE: {resp.headers.get('Content-Type')}\n")
                    f.write("---BODY---\n")
                    f.write(resp.text)
                print(f"  [aviso] resposta inesperada na página first={first} "
                      f"(status={resp.status_code}). Salvei em {fname} para diagnóstico.")
                return None, view_state

            rows, _ = parse_results(table_html)

            if not rows:
                fname = f"debug_page_first{first}_empty.txt"
                with open(fname, "w", encoding="utf-8") as f:
                    f.write(f"STATUS: {resp.status_code}\n")
                    f.write("---RAW BODY (resposta AJAX completa)---\n")
                    f.write(resp.text)
                    f.write("\n\n---HTML EXTRAIDO DO UPDATE resultTable---\n")
                    f.write(table_html or "(vazio)")
                print(f"  [aviso] página first={first}: resposta parcial recebida mas 0 linhas extraídas. "
                      f"Salvei em {fname} para diagnóstico.")

            time.sleep(delay)
            return rows, (new_view_state or view_state)

        except requests.exceptions.HTTPError:
            if resp is not None and resp.status_code == 403 and attempt < max_retries:
                backoff = wait * (2 ** (attempt - 1)) + 5
                print(f"  [403] bloqueio temporário na página first={first}, tentativa {attempt}/{max_retries}, "
                      f"esperando {backoff:.0f}s...")
                time.sleep(backoff)
                continue
            raise
    return None, view_state


def search_all_pages(session, query, delay=1.5, max_retries=3, max_pages=30, debug=False):
    """Faz a busca e percorre todas as páginas de resultado (até max_pages ou o fim)."""
    rows, warning, view_state = search_first_page(session, query, delay=delay, max_retries=max_retries)
    all_rows = list(rows)

    total = parse_total(warning)
    if total:
        total = min(total, 500)

    page = 1
    while True:
        if total is not None and len(all_rows) >= total:
            break
        if len(all_rows) < page * ROWS_PER_PAGE:
            break
        if page >= max_pages:
            print(f"  [aviso] atingiu max_pages={max_pages} para '{query}', parando (pode haver mais dados).")
            break

        first = page * ROWS_PER_PAGE
        next_rows, view_state = fetch_page(
            session, query, view_state, first, delay=delay, max_retries=max_retries, debug=debug
        )
        if not next_rows:
            break

        all_rows.extend(next_rows)
        page += 1

    return all_rows, warning


# --------------------------------------------------------------------------
# Persistência (CSV + progresso resumível)
# --------------------------------------------------------------------------

def dedupe(records):
    seen = set()
    unique = []
    for r in records:
        key = r["IDE"]
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


def save_csv(records, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(records)


def append_rows_csv(path, rows):
    """Acrescenta linhas ao CSV, escrevendo cabeçalho só se o arquivo for novo/vazio."""
    if not rows:
        return
    write_header = (not os.path.exists(path)) or os.path.getsize(path) == 0
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if write_header:
            writer.writeheader()
        writer.writerows(rows)


def load_seen_ides_from_csv(path):
    """Lê o CSV existente (se houver) e devolve o conjunto de IDEs já coletados."""
    seen = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("IDE"):
                    seen.add(row["IDE"])
    return seen


def load_progress(path):
    """Lê o ficheiro de progresso (se houver) e devolve o conjunto de consultas já feitas."""
    done = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    done.add(line)
    return done


def mark_progress(path, query):
    with open(path, "a", encoding="utf-8") as f:
        f.write(query + "\n")


def generate_all_queries():
    """Gera todas as combinações de QUERY_LENGTH caracteres a partir de BASE_CHARS,
    em ordem determinística (necessário para o resume funcionar de forma consistente).
    """
    for combo in itertools.product(BASE_CHARS, repeat=QUERY_LENGTH):
        yield "".join(combo)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def run_auto(session, args):
    progress_path = args.out + ".progress.txt"

    seen_ides = load_seen_ides_from_csv(args.out)
    done_queries = load_progress(progress_path)

    total_queries = len(BASE_CHARS) ** QUERY_LENGTH
    print(f"Modo --auto: {total_queries} combinações de {QUERY_LENGTH} caracteres a percorrer "
          f"(alfabeto: {''.join(BASE_CHARS)}).")
    if done_queries:
        print(f"Retomando execução anterior: {len(done_queries)} consultas já concluídas, "
              f"{len(seen_ides)} empresas já salvas em {args.out}.")

    count = 0
    for query in generate_all_queries():
        count += 1
        if query in done_queries:
            continue

        try:
            rows, warning = search_all_pages(
                session, query, delay=args.delay, max_pages=args.max_pages, debug=args.debug
            )
        except Exception as e:
            print(f"[ERRO] busca '{query}': {e} -- será tentada de novo na próxima execução.")
            continue  # não marca progresso: será refeita se o script rodar de novo

        new_rows = [r for r in rows if r["IDE"] not in seen_ides]
        for r in new_rows:
            seen_ides.add(r["IDE"])

        append_rows_csv(args.out, new_rows)      # grava no ficheiro a cada novo resultado
        mark_progress(progress_path, query)       # marca esta consulta como concluída
        done_queries.add(query)

        cap_note = ""
        if len(rows) >= 500:
            cap_note = "  [aviso] limite de 500 atingido - pode haver empresas não capturadas para este trio de letras."

        print(f"[{count}/{total_queries}] '{query}': {len(rows)} linhas | {len(new_rows)} novas "
              f"(acumulado: {len(seen_ides)}){cap_note}")

    print(f"\nConcluído. Total de empresas únicas em {args.out}: {len(seen_ides)}")


def run_company(session, args):
    try:
        rows, warning = search_all_pages(
            session, args.company, delay=args.delay, max_pages=args.max_pages, debug=args.debug
        )
    except Exception as e:
        print(f"[ERRO] busca '{args.company}': {e}")
        rows, warning = [], ""

    print(f"'{args.company}': {len(rows)} linhas no total" + (f" | {warning}" if warning else ""))
    unique_rows = dedupe(rows)
    save_csv(unique_rows, args.out)
    print(f"\nTotal (sem duplicados): {len(unique_rows)} registros salvos em {args.out}")


def main():
    parser = argparse.ArgumentParser(description="Scraper do registro do comércio VS (Suíça)")
    parser.add_argument("--company", help="Busca simples por um termo literal no campo 'Société'")
    parser.add_argument(
        "--auto",
        action="store_true",
        help=f"Varre TODAS as combinações de {QUERY_LENGTH} caracteres (a-z + '&') como consultas "
             f"literais. Resumível: pode interromper (Ctrl+C) e rodar o mesmo comando de novo "
             f"para continuar de onde parou.",
    )
    parser.add_argument("--out", default="chregister_vs.csv", help="Arquivo CSV de saída")
    parser.add_argument("--delay", type=float, default=1.2, help="Segundos de espera entre requisições")
    parser.add_argument("--max-pages", type=int, default=30, help="Máximo de páginas por busca (20 linhas/página)")
    parser.add_argument("--debug", action="store_true", help="Salva respostas AJAX brutas em arquivos debug_page_*")
    args = parser.parse_args()

    if not args.company and not args.auto:
        print("Use --company \"termo\" ou --auto. Veja --help.")
        sys.exit(1)

    session = requests.Session()

    if args.auto:
        run_auto(session, args)
    else:
        run_company(session, args)


if __name__ == "__main__":
    main()
