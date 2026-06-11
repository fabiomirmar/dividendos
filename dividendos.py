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

def exibir_resultado(ticker: str, tipo: str, por_mes: dict, ano: int, qtd: int = 0):
    W_MES   = 11
    W_PGTO  = 10
    W_COM   = 10
    W_TIPO  = 22
    W_VALOR = 12
    W_TOTAL = 12  # extra column when qtd is given

    com_qtd = qtd > 0
    extra_header = f" │ {'Total (R$)':>{W_TOTAL}}" if com_qtd else ""
    extra_sep    = f"┼{'─'*(W_TOTAL+2)}" if com_qtd else ""
    extra_end    = f"┤" if com_qtd else ""

    def _borders(l, mi, mt, r):
        base = (
            f"  {l}{'─'*(W_MES+2)}{mi}{'─'*(W_PGTO+2)}{mi}{'─'*(W_COM+2)}"
            f"{mi}{'─'*(W_TIPO+2)}{mi}{'─'*(W_VALOR+2)}"
        )
        return base + (f"{mt}{'─'*(W_TOTAL+2)}{r}" if com_qtd else f"{r}")

    top  = _borders("┌", "┬", "┬", "┐")
    sep  = _borders("├", "┼", "┼", "┤")
    sep0 = sep
    # inner_w = content width of merged left cell in TOTAL rows
    # = W_MES + W_PGTO + W_COM + W_TIPO + 9 (content) → border = content + 2
    _inner = W_MES + W_PGTO + W_COM + W_TIPO + 11
    bot  = f"  └{'─'*_inner}┴{'─'*(W_VALOR+2)}" + (f"┴{'─'*(W_TOTAL+2)}┘" if com_qtd else "┘")
    totl_inner = _inner
    totl = (
        f"  ├{'─'*totl_inner}┼{'─'*(W_VALOR+2)}"
        + (f"┼{'─'*(W_TOTAL+2)}┤" if com_qtd else "┤")
    )

    def row(mes="", pgto="", com="", tipo_p="", valor="", total=""):
        base = (
            f"  │ {mes:<{W_MES}} │ {pgto:<{W_PGTO}} │ {com:<{W_COM}}"
            f" │ {tipo_p:<{W_TIPO}} │ {valor:>{W_VALOR}}"
        )
        return base + (f" │ {total:>{W_TOTAL}} │" if com_qtd else " │")

    titulo = f"  Proventos de {ticker.upper()} ({tipo}) — {ano}"
    if com_qtd:
        titulo += f"  ·  {qtd:,} cotas"
    print(f"\n{titulo}\n")
    print(top)
    print(row("Mês", "Pagamento", "Data-com", "Tipo",
              "R$/cota" if com_qtd else "Valor (R$)",
              "Total (R$)" if com_qtd else ""))
    print(sep0)

    total_ano      = 0.0
    total_ano_bruto = 0.0
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

        total_mes_bruto = sum(p["valor"] for p in pagamentos)
        total_mes       = total_mes_bruto * qtd if com_qtd else total_mes_bruto
        total_ano_bruto += total_mes_bruto
        total_ano       += total_mes

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
                valor_total = f"{p['valor'] * qtd:.2f}" if com_qtd else ""
                print(row(mes_label, pgto_label, com_label, p["tipo"],
                          f"{p['valor']:.6f}", valor_total))

            if len(itens) > 1:
                sub_bruto = sum(p["valor"] for p in itens)
                sub_total = f"{sub_bruto * qtd:.2f}" if com_qtd else ""
                print(row("", "", "", "Subtotal", f"{sub_bruto:.6f}", sub_total))

        if len(grupos) > 1:
            tm_total = f"{total_mes:.2f}" if com_qtd else f"{total_mes:.6f}"
            print(row("", "", "", "─── Total mês ───",
                      f"{total_mes_bruto:.6f}", tm_total if com_qtd else ""))

    print(totl)
    if com_qtd:
        inner_w = W_MES + W_PGTO + W_COM + W_TIPO + 9
        print(f"  │ {'TOTAL ANO (por cota)':{inner_w}} │ {total_ano_bruto:>{W_VALOR}.6f} │ {'':>{W_TOTAL}} │")
        print(f"  │ {'TOTAL ANO':{inner_w}} │ {'':>{W_VALOR}} │ {total_ano:>{W_TOTAL}.2f} │")
    else:
        print(f"  │ {'TOTAL ANO':{W_MES+W_PGTO+W_COM+W_TIPO+9}} │ {total_ano:>{W_VALOR}.6f} │")
    print(bot)
    print()


# ── Multi-ticker matrix view ───────────────────────────────────────────────────

def exibir_matriz(
    dados: dict[str, dict[int, float]],
    tipos: dict[str, str],
    qtds: dict[str, int],
    ano: int,
):
    """
    dados:  {ticker: {mes: total_valor_por_cota}}
    tipos:  {ticker: 'FII' | 'Ação'}
    qtds:   {ticker: quantidade_de_cotas}  (0 = sem quantidade)
    Exibe tabela com tickers nas linhas e meses nas colunas.
    """
    tickers   = list(dados.keys())
    com_qtd   = any(qtds.get(t, 0) > 0 for t in tickers)

    def _label(t):
        q = qtds.get(t, 0)
        suffix = f" ×{q:,}" if q > 0 else ""
        return f"{t} ({tipos.get(t, '')}){suffix}"

    labels = {t: _label(t) for t in tickers}
    W_TICK = max(8, max(len(l) for l in labels.values()))
    W_M    = 8 if com_qtd else 7   # wider when showing totals
    W_T    = 10 if com_qtd else 9

    def _fmt(v: float | None, qtd: int = 0) -> str:
        if v is None:
            return "—"
        total = v * qtd if qtd > 0 else v
        return f"{total:.2f}"

    def sep_line(left, mid_m, mid_t, right):
        return (
            f"  {left}{'─'*(W_TICK+2)}"
            + (f"{mid_m}{'─'*(W_M+2)}" * 12)
            + f"{mid_t}{'─'*(W_T+2)}{right}"
        )

    top  = sep_line("┌", "┬", "┬", "┐")
    sep  = sep_line("├", "┼", "┼", "┤")
    sep2 = sep_line("├", "┼", "┼", "┤")
    bot  = sep_line("└", "┴", "┴", "┘")

    def row(label, mes_vals: list[str], total: str) -> str:
        cells = " │ ".join(f"{v:>{W_M}}" for v in mes_vals)
        return f"  │ {label:<{W_TICK}} │ {cells} │ {total:>{W_T}} │"

    titulo = "  Proventos combinados"
    if com_qtd:
        titulo += " (valores em R$ considerando as cotas informadas)"
    print(f"\n{titulo} — {ano}  (R$)\n")
    print(top)

    header_meses = [f"{m:^{W_M}}" for m in MESES_CURTOS]
    print(f"  │ {'Ticker':<{W_TICK}} │ " + " │ ".join(header_meses) + f" │ {'Total':>{W_T}} │")
    print(sep)

    total_ano_geral = 0.0
    totais_mes: dict[int, float] = defaultdict(float)

    for ticker in tickers:
        por_mes = dados[ticker]
        qtd = qtds.get(ticker, 0)
        vals = []
        total_ticker = 0.0
        for m in range(1, 13):
            v = por_mes.get(m)
            val = (v * qtd if qtd > 0 else v) if v is not None else None
            totais_mes[m] += val or 0.0
            total_ticker   += val or 0.0
            vals.append(_fmt(v, qtd))
        total_ano_geral += total_ticker
        print(row(labels[ticker], vals, f"{total_ticker:.2f}"))

    print(sep2)
    total_vals = [_fmt(totais_mes.get(m) or None) for m in range(1, 13)]
    # totais_mes has 0.0 for empty months — show "—" for those
    total_vals = ["—" if totais_mes.get(m, 0) == 0 else f"{totais_mes[m]:.2f}" for m in range(1, 13)]
    print(row(f"{'TOTAL':<{W_TICK}}", total_vals, f"{total_ano_geral:.2f}"))
    print(bot)
    print()


# ── Entry point ────────────────────────────────────────────────────────────────

HELP = """\
uso: dividendos.py [-h] TICKER[:COTAS] [TICKER[:COTAS] ...]

Consulta proventos (dividendos, JCP, rendimentos) de ações e FIIs
brasileiros via Status Invest, para o ano corrente.

argumentos posicionais:
  TICKER              código do ativo na B3 (ex: PETR4, MXRF11, KNRI11)
  TICKER:COTAS        ticker com quantidade de cotas; multiplica o valor
                      do provento pelo número de cotas informado

opções:
  -h, --help          exibe esta ajuda e encerra

exemplos:
  # visão detalhada de um único ativo
  python3 dividendos.py PETR4

  # visão detalhada com quantidade de cotas
  python3 dividendos.py PETR4:200

  # tabela combinada sem quantidades
  python3 dividendos.py MXRF11 KNRI11 PETR4

  # tabela combinada com quantidades
  python3 dividendos.py MXRF11:500 KNRI11:100 PETR4:200

  # mix: alguns com quantidade, outros sem
  python3 dividendos.py MXRF11:500 KNRI11 PETR4:200

notas:
  - Ações e FIIs são detectados automaticamente.
  - Tickers inválidos são ignorados na visão combinada.
  - Fonte dos dados: https://statusinvest.com.br
"""


def _parse_arg(arg: str) -> tuple[str, int]:
    """'PETR4:200' → ('PETR4', 200),  'PETR4' → ('PETR4', 0)"""
    if ":" in arg:
        ticker, qtd_str = arg.split(":", 1)
        try:
            qtd = int(qtd_str.replace(".", "").replace(",", ""))
            if qtd <= 0:
                raise ValueError
        except ValueError:
            print(f"  Aviso: quantidade inválida em '{arg}', usando sem quantidade.")
            qtd = 0
        return ticker.strip().upper(), qtd
    return arg.strip().upper(), 0


def main():
    args = sys.argv[1:]

    if not args or any(a in ("-h", "--help") for a in args):
        print(HELP)
        sys.exit(0 if args else 1)

    parsed   = [_parse_arg(a) for a in args]
    tickers  = [t for t, _ in parsed]
    qtds     = {t: q for t, q in parsed}
    ano_atual = date.today().year

    # ── Single ticker: detailed view ──────────────────────────────────────────
    if len(tickers) == 1:
        ticker = tickers[0]
        qtd    = qtds[ticker]
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
        exibir_resultado(ticker, tipo, por_mes, ano_atual, qtd)
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

    exibir_matriz(dados, tipos, qtds, ano_atual)


if __name__ == "__main__":
    main()

