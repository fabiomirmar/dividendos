"""
Lógica central de scraping e processamento de proventos.
Compartilhada entre o script CLI (dividendos.py) e o servidor web (app.py).
"""

import json
import html as html_module
import re
import time
import urllib.request
import urllib.error
from collections import defaultdict

BASE_URL_ACAO = "https://statusinvest.com.br/acoes/{ticker}"
BASE_URL_FII  = "https://statusinvest.com.br/fundos-imobiliarios/{ticker}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
}

MAX_RETRIES  = 3
TIMEOUT_SECS = 20
RETRY_DELAY  = 3

MESES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
]

MESES_CURTOS = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
                "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


def _fetch_html(url: str, on_retry=None) -> str | None:
    """
    Faz o download do HTML da URL com retries em caso de timeout.
    on_retry: callback opcional chamado a cada retry com (attempt, max_retries).
    """
    req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECS) as r:
                if r.status == 200:
                    return r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise
        except TimeoutError:
            if attempt < MAX_RETRIES:
                if on_retry:
                    on_retry(attempt, MAX_RETRIES)
                time.sleep(RETRY_DELAY)
            else:
                raise TimeoutError(
                    f"o servidor não respondeu após {MAX_RETRIES} tentativas "
                    f"({TIMEOUT_SECS}s cada)"
                )
    return None


def _extrair_proventos(html: str) -> list | None:
    """Extrai o JSON de proventos do campo <input id='results'> embutido no HTML."""
    m = re.search(r'id="results"[^>]*value="([^"]+)"', html)
    if not m:
        return None
    raw = html_module.unescape(m.group(1))
    return json.loads(raw)


def buscar_proventos(ticker: str, on_retry=None) -> tuple[list, str]:
    """
    Tenta FII primeiro, depois ação.
    Retorna (lista_proventos, tipo) onde tipo é 'FII' ou 'Ação'.
    Levanta ValueError se o ticker não for encontrado.
    Levanta TimeoutError se o servidor não responder.
    """
    ticker_lower = ticker.lower()
    for url, tipo in [
        (BASE_URL_FII.format(ticker=ticker_lower),  "FII"),
        (BASE_URL_ACAO.format(ticker=ticker_lower), "Ação"),
    ]:
        html = _fetch_html(url, on_retry=on_retry)
        if html is None:
            continue
        proventos = _extrair_proventos(html)
        if proventos is not None:
            return proventos, tipo

    raise ValueError(f"ticker '{ticker}' não encontrado no Status Invest")


def agregar_por_mes(proventos: list, ano: int) -> dict:
    """
    Agrupa proventos pelo mês da data de pagamento (pd) para o ano informado.
    Retorna dict[mes (int)] = lista de pagamentos ordenados por data/tipo.
    """
    por_mes = defaultdict(list)

    for item in proventos:
        pd = item.get("pd", "")
        ed = item.get("ed", "")
        if not pd:
            continue
        try:
            _dia, mes, ano_pg = pd.split("/")
            ano_pg = int(ano_pg)
            mes_pg = int(mes)
        except ValueError:
            continue

        if ano_pg != ano:
            continue

        por_mes[mes_pg].append({
            "valor":          item.get("v", 0) or 0,
            "tipo":           item.get("et", "N/A"),
            "data_com":       ed or "N/A",
            "data_pagamento": pd,
        })

    result = {}
    for mes, items in por_mes.items():
        result[mes] = sorted(items, key=lambda x: (x["data_pagamento"], x["tipo"]))
    return result


def total_por_mes(por_mes: dict) -> dict[int, float]:
    """Retorna {mes: soma_valores} a partir de agregar_por_mes."""
    return {m: sum(p["valor"] for p in items) for m, items in por_mes.items()}
