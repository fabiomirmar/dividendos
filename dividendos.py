#!/usr/bin/env python3
"""
Consulta proventos (dividendos/JCP/rendimentos) de ações e FIIs via Status Invest.

Uso:
  python3 dividendos.py <TICKER>              — visão detalhada de um ativo
  python3 dividendos.py <TICKER> [TICKER ...] — tabela combinada de múltiplos ativos

Exemplos:
  python3 dividendos.py PETR4
  python3 dividendos.py MXRF11 KNRI11 PETR4
"""

import sys
import json
import html as html_module
import re
import time
import urllib.request
import urllib.error
from datetime import date
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
RETRY_DELAY  = 3  # seconds between retries

MESES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
]

MESES_CURTOS = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
                "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


def _fetch_html(url: str) -> str | None:
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
                print(f"  Timeout (tentativa {attempt}/{MAX_RETRIES}), aguardando {RETRY_DELAY}s...", flush=True)
                time.sleep(RETRY_DELAY)
            else:
                raise TimeoutError(
                    f"o servidor não respondeu após {MAX_RETRIES} tentativas ({TIMEOUT_SECS}s cada)"
                )
    return None


def _extrair_proventos(html: str) -> list | None:
    """Extrai o JSON de proventos do campo <input id='results'> embutido no HTML."""
    m = re.search(r'id="results"[^>]*value="([^"]+)"', html)
    if not m:
        return None
    raw = html_module.unescape(m.group(1))
    return json.loads(raw)


def buscar_proventos(ticker: str) -> tuple[list, str]:
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
        html = _fetch_html(url)
        if html is None:
            continue
        proventos = _extrair_proventos(html)
        if proventos is not None:
            return proventos, tipo

    raise ValueError(f"ticker '{ticker}' não encontrado no Status Invest")


def agregar_por_mes(proventos: list, ano: int) -> dict:
    """
    Agrupa proventos pelo mês da data de pagamento (pd) para o ano informado.
    Retorna dict[mes] = lista de pagamentos ordenados por data de pagamento.
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


# ── Single-ticker detailed view ───────────────────────────────────────────────

def exibir_resultado(ticker: str, tipo: str, por_mes: dict, ano: int):
    W_MES   = 11
    W_PGTO  = 10
    W_COM   = 10
    W_TIPO  = 22
    W_VALOR = 12

    sep  = f"  ├{'─'*(W_MES+2)}┼{'─'*(W_PGTO+2)}┼{'─'*(W_COM+2)}┼{'─'*(W_TIPO+2)}┼{'─'*(W_VALOR+2)}┤"
    sep0 = f"  ├{'─'*(W_MES+2)}┼{'─'*(W_PGTO+2)}┼{'─'*(W_COM+2)}┼{'─'*(W_TIPO+2)}┼{'─'*(W_VALOR+2)}┤"
    top  = f"  ┌{'─'*(W_MES+2)}┬{'─'*(W_PGTO+2)}┬{'─'*(W_COM+2)}┬{'─'*(W_TIPO+2)}┬{'─'*(W_VALOR+2)}┐"
    bot  = f"  └{'─'*(W_MES+W_PGTO+W_COM+W_TIPO+11)}┴{'─'*(W_VALOR+2)}┘"
    totl = f"  ├{'─'*(W_MES+2)}┴{'─'*(W_PGTO+2)}┴{'─'*(W_COM+2)}┴{'─'*(W_TIPO+2)}┼{'─'*(W_VALOR+2)}┤"

    def row(mes="", pgto="", com="", tipo_p="", valor=""):
        return (
            f"  │ {mes:<{W_MES}} │ {pgto:<{W_PGTO}} │ {com:<{W_COM}} │ {tipo_p:<{W_TIPO}} │ {valor:>{W_VALOR}} │"
        )

    print(f"\n  Proventos de {ticker.upper()} ({tipo}) — {ano}\n")
    print(top)
    print(row("Mês", "Pagamento", "Data-com", "Tipo", "Valor (R$)"))
    print(sep0)

    total_ano = 0.0
    first_month = True

    for mes in range(1, 13):
        if not first_month:
            print(sep)
        first_month = False

        pagamentos = por_mes.get(mes, [])
        nome_mes = MESES[mes - 1]

        if not pagamentos:
            print(row(nome_mes, "—"))
            continue

        grupos: dict[str, list] = {}
        for p in pagamentos:
            grupos.setdefault(p["data_pagamento"], []).append(p)

        total_mes = sum(p["valor"] for p in pagamentos)
        total_ano += total_mes

        mes_impresso = False
        primeiro_grupo = True

        for pgto_data, itens in grupos.items():
            if not primeiro_grupo:
                print(row())
            primeiro_grupo = False

            for i, p in enumerate(itens):
                mes_label  = nome_mes if not mes_impresso else ""
                pgto_label = pgto_data if i == 0 else ""
                com_label  = p["data_com"] if i == 0 else ""
                mes_impresso = True
                print(row(mes_label, pgto_label, com_label, p["tipo"], f"{p['valor']:.6f}"))

            if len(itens) > 1:
                subtotal = sum(p["valor"] for p in itens)
                print(row("", "", "", "Subtotal", f"{subtotal:.6f}"))

        if len(grupos) > 1:
            print(row("", "", "", "─── Total mês ───", f"{total_mes:.6f}"))

    print(totl)
    print(f"  │ {'TOTAL ANO':{W_MES+W_PGTO+W_COM+W_TIPO+9}} │ {total_ano:>{W_VALOR}.6f} │")
    print(bot)
    print()


# ── Multi-ticker matrix view ───────────────────────────────────────────────────

def exibir_matriz(
    dados: dict[str, dict[int, float]],
    tipos: dict[str, str],
    ano: int,
):
    """
    dados:  {ticker: {mes: total_valor}}
    tipos:  {ticker: 'FII' | 'Ação'}
    Exibe tabela com tickers nas linhas e meses nas colunas.
    """
    tickers = list(dados.keys())
    labels  = {t: f"{t} ({tipos.get(t, '')})" for t in tickers}
    W_TICK = max(8, max(len(l) for l in labels.values()))
    W_M    = 7   # each month column
    W_T    = 9   # annual total column

    def _fmt(v: float | None) -> str:
        return f"{v:.2f}" if v else "—"

    def sep_line(left, mid_m, mid_t, right):
        return (
            f"  {left}{'─'*(W_TICK+2)}"
            + (f"{mid_m}{'─'*(W_M+2)}" * 12)
            + f"{mid_t}{'─'*(W_T+2)}{right}"
        )

    top  = sep_line("┌", "┬", "┬", "┐")
    sep  = sep_line("├", "┼", "┼", "┤")
    sep2 = sep_line("├", "┼", "┼", "┤")  # before TOTAL row
    bot  = sep_line("└", "┴", "┴", "┘")

    def row(ticker, mes_vals: list[str], total: str) -> str:
        cells = "".join(f" │ {v:>{W_M}}" for v in mes_vals)
        return f"  │ {ticker:<{W_TICK}} │{cells[3:]} │ {total:>{W_T}} │"

    # Header
    print(f"\n  Proventos combinados — {ano}  (R$)\n")
    print(top)

    header_meses = [f"{m:^{W_M}}" for m in MESES_CURTOS]
    print(f"  │ {'Ticker':<{W_TICK}} │ " + " │ ".join(header_meses) + f" │ {'Total':>{W_T}} │")
    print(sep)

    # One row per ticker
    total_ano_geral = 0.0
    totais_mes: dict[int, float] = defaultdict(float)

    for ticker in tickers:
        por_mes = dados[ticker]
        total_ticker = sum(por_mes.values())
        total_ano_geral += total_ticker
        vals = []
        for m in range(1, 13):
            v = por_mes.get(m)
            totais_mes[m] += v or 0.0
            vals.append(_fmt(v))
        tipo = tipos.get(ticker, "")
        label = labels[ticker]
        print(f"  │ {label:<{W_TICK}} │ " + " │ ".join(f"{v:>{W_M}}" for v in vals) + f" │ {total_ticker:>{W_T}.2f} │")

    # Total row
    print(sep2)
    total_vals = [_fmt(totais_mes.get(m)) for m in range(1, 13)]
    merged_label = f"{'TOTAL':<{W_TICK}}"
    # The sep2 merges the 12 month columns into one visual block, so we keep the same row format
    print(f"  │ {merged_label} │ " + " │ ".join(f"{v:>{W_M}}" for v in total_vals) + f" │ {total_ano_geral:>{W_T}.2f} │")
    print(bot)
    print()


# ── Entry point ────────────────────────────────────────────────────────────────

HELP = """\
uso: dividendos.py [-h] TICKER [TICKER ...]

Consulta proventos (dividendos, JCP, rendimentos) de ações e FIIs
brasileiros via Status Invest, para o ano corrente.

argumentos posicionais:
  TICKER              código do ativo na B3 (ex: PETR4, MXRF11, KNRI11)
                      um ou mais tickers separados por espaço

opções:
  -h, --help          exibe esta ajuda e encerra

exemplos:
  # visão detalhada de um único ativo (mês a mês com tipo e datas)
  python3 dividendos.py PETR4

  # tabela combinada de múltiplos ativos (meses no eixo horizontal)
  python3 dividendos.py MXRF11 KNRI11 PETR4

  # misturando ações e FIIs
  python3 dividendos.py ITUB4 BBAS3 MXRF11 HGLG11 KNRI11

notas:
  - Acões e FIIs são detectados automaticamente.
  - Tickers inválidos são ignorados na visão combinada.
  - Fonte dos dados: https://statusinvest.com.br
"""


def main():
    args = sys.argv[1:]

    if not args or any(a in ("-h", "--help") for a in args):
        print(HELP)
        sys.exit(0 if args else 1)

    tickers = [t.strip().upper() for t in args]
    ano_atual = date.today().year

    # ── Single ticker: detailed view ──────────────────────────────────────────
    if len(tickers) == 1:
        ticker = tickers[0]
        print(f"Buscando proventos de {ticker} para {ano_atual} via Status Invest...")
        try:
            proventos, tipo = buscar_proventos(ticker)
        except ValueError as e:
            print(f"  Erro: {e}")
            print("  Verifique se o ticker está correto (ex: PETR4, MXRF11, KNRI11).")
            sys.exit(1)
        except TimeoutError as e:
            print(f"\n  Erro: {e}.\n  O site Status Invest pode estar fora do ar ou com lentidão.")
            sys.exit(1)
        por_mes = agregar_por_mes(proventos, ano_atual)
        exibir_resultado(ticker, tipo, por_mes, ano_atual)
        return

    # ── Multiple tickers: matrix view ─────────────────────────────────────────
    print(f"Buscando proventos de {len(tickers)} ativos para {ano_atual} via Status Invest...\n")
    dados: dict[str, dict[int, float]] = {}
    tipos: dict[str, str] = {}
    erros: list[str] = []

    for ticker in tickers:
        print(f"  • {ticker} ... ", end="", flush=True)
        try:
            proventos, tipo = buscar_proventos(ticker)
            por_mes = agregar_por_mes(proventos, ano_atual)
            dados[ticker] = {m: sum(p["valor"] for p in items) for m, items in por_mes.items()}
            tipos[ticker] = tipo
            print("OK")
        except ValueError as e:
            print(f"ignorado ({e})")
            erros.append(ticker)
        except TimeoutError as e:
            print(f"ignorado ({e})")
            erros.append(ticker)

    if erros:
        print(f"\n  Atenção: {len(erros)} ativo(s) ignorado(s) por erro: {', '.join(erros)}")

    if not dados:
        print("\n  Nenhum dado disponível para exibir.")
        sys.exit(1)

    exibir_matriz(dados, tipos, ano_atual)


if __name__ == "__main__":
    main()

