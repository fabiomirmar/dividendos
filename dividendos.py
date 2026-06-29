#!/usr/bin/env python3
"""
Consulta proventos (dividendos/JCP/rendimentos) de ações e FIIs via Status Invest.

Uso:
  python3 dividendos.py <TICKER>              — visão detalhada de um ativo
  python3 dividendos.py <TICKER> [TICKER ...] — tabela combinada de múltiplos ativos
  python3 dividendos.py -c carteira.yaml      — carrega tickers do arquivo de configuração

Exemplos:
  python3 dividendos.py PETR4
  python3 dividendos.py MXRF11 KNRI11 PETR4
  python3 dividendos.py -c carteira.yaml
"""

import sys
import argparse
from datetime import date
from collections import defaultdict

from core import (
    buscar_proventos,
    agregar_por_mes,
    total_por_mes,
    MESES,
    MESES_CURTOS,
)


# ── Single-ticker detailed view ───────────────────────────────────────────────

def exibir_resultado(ticker: str, tipo: str, por_mes: dict, ano: int,
                     qtd: int | dict = 0):
    """
    qtd pode ser:
      - int: quantidade fixa para todos os meses
      - dict {mes: qty}: quantidade variável por mês
    """
    W_MES   = 11
    W_PGTO  = 10
    W_COM   = 10
    W_TIPO  = 22
    W_VALOR = 12
    W_TOTAL = 12  # extra column when qtd is given

    qtd_variavel = isinstance(qtd, dict)
    def _qtd(mes: int) -> int:
        return qtd.get(mes, 0) if qtd_variavel else int(qtd)

    com_qtd = qtd_variavel or int(qtd) > 0
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
        titulo += "  ·  quantidade variável" if qtd_variavel else f"  ·  {qtd:,} cotas"
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
        qtd_m = _qtd(mes)

        if not pagamentos:
            print(row(nome_mes, "—"))
            continue

        grupos: dict[str, list] = {}
        for p in pagamentos:
            grupos.setdefault(p["data_pagamento"], []).append(p)

        total_mes_bruto = sum(p["valor"] for p in pagamentos)
        total_mes       = total_mes_bruto * qtd_m if (com_qtd and qtd_m) else total_mes_bruto
        total_ano_bruto += total_mes_bruto
        if com_qtd and qtd_m:
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
                valor_total = f"{p['valor'] * qtd_m:.2f}" if (com_qtd and qtd_m) else ("×0" if com_qtd else "")
                print(row(mes_label, pgto_label, com_label, p["tipo"],
                          f"{p['valor']:.6f}", valor_total))

            if len(itens) > 1:
                sub_bruto = sum(p["valor"] for p in itens)
                sub_total = f"{sub_bruto * qtd_m:.2f}" if (com_qtd and qtd_m) else ""
                print(row("", "", "", "Subtotal", f"{sub_bruto:.6f}", sub_total))

        if len(grupos) > 1:
            tm_total = f"{total_mes:.2f}" if (com_qtd and qtd_m) else f"{total_mes_bruto:.6f}"
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
    qtds: dict[str, dict | int],   # dict[mes,qty] ou int por ticker
    ano: int,
):
    """
    dados:  {ticker: {mes: total_valor_por_cota}}
    tipos:  {ticker: 'FII' | 'Ação'}
    qtds:   {ticker: int | dict{mes:qty}}
    Exibe tabela com tickers nas linhas e meses nas colunas.
    Inclui subtotais por grupo (FIIs / Ações) quando ambos estão presentes.
    """
    def _qtd_m(ticker, mes):
        q = qtds.get(ticker, 0)
        return q.get(mes, 0) if isinstance(q, dict) else int(q)

    tickers = list(dados.keys())
    com_qtd = any(
        any(_qtd_m(t, m) > 0 for m in range(1, 13))
        for t in tickers
    )

    def _label(t):
        q = qtds.get(t, 0)
        if isinstance(q, dict):
            valores = [v for v in q.values() if v > 0]
            suffix = f" ×var" if valores else ""
        else:
            suffix = f" ×{q:,}" if q > 0 else ""
        return f"{t} ({tipos.get(t, '')}){suffix}"

    labels = {t: _label(t) for t in tickers}
    W_TICK = max(16, max(len(l) for l in labels.values()))
    W_M    = 8 if com_qtd else 7
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
    bot  = sep_line("└", "┴", "┴", "┘")

    def row(label, mes_vals: list[str], total: str, bold: bool = False) -> str:
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

    # Agrupar tickers por tipo, preservando a ordem original dentro de cada grupo
    fiis  = [t for t in tickers if tipos.get(t) == "FII"]
    acoes = [t for t in tickers if tipos.get(t) != "FII"]
    grupos = []
    if fiis:  grupos.append(("Sub-total FIIs",  fiis))
    if acoes: grupos.append(("Sub-total Ações", acoes))
    multi_grupo = len(grupos) > 1

    total_ano_geral = 0.0
    totais_mes: dict[int, float] = defaultdict(float)
    primeiro_grupo = True

    for label_subtotal, grupo_tickers in grupos:
        if not primeiro_grupo:
            print(sep)
        primeiro_grupo = False

        subtotal_mes: dict[int, float] = defaultdict(float)
        subtotal_ano = 0.0

        for ticker in grupo_tickers:
            por_mes = dados[ticker]
            vals = []
            total_ticker = 0.0
            for m in range(1, 13):
                v   = por_mes.get(m)
                qtd_m = _qtd_m(ticker, m)
                val = (v * qtd_m if qtd_m > 0 else v) if v is not None else None
                totais_mes[m]    += val or 0.0
                subtotal_mes[m]  += val or 0.0
                total_ticker     += val or 0.0
                vals.append(_fmt(v, qtd_m))
            total_ano_geral += total_ticker
            subtotal_ano    += total_ticker
            print(row(labels[ticker], vals, f"{total_ticker:.2f}"))

        if multi_grupo:
            print(sep)
            sub_vals = ["—" if subtotal_mes.get(m, 0) == 0 else f"{subtotal_mes[m]:.2f}" for m in range(1, 13)]
            print(row(f"{label_subtotal}", sub_vals, f"{subtotal_ano:.2f}"))

    print(sep)
    total_vals = ["—" if totais_mes.get(m, 0) == 0 else f"{totais_mes[m]:.2f}" for m in range(1, 13)]
    print(row(f"{'TOTAL':<{W_TICK}}", total_vals, f"{total_ano_geral:.2f}"))
    print(bot)
    print()


# ── Entry point ────────────────────────────────────────────────────────────────


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


def _carregar_config(caminho: str) -> list[dict]:
    """Lê arquivo YAML (formato antigo ou novo) e retorna lista de {ticker, qtd, historico}."""
    try:
        import yaml
    except ImportError:
        print("ERRO: pyyaml não está instalado. Execute: pip install pyyaml")
        sys.exit(1)
    try:
        from carteira import parse_carteira
    except ImportError:
        print("ERRO: módulo carteira.py não encontrado.")
        sys.exit(1)
    with open(caminho, encoding="utf-8") as f:
        dados = yaml.safe_load(f)
    return parse_carteira(dados)


def main():
    parser = argparse.ArgumentParser(
        prog="dividendos.py",
        description="Consulta proventos de ações e FIIs via Status Invest.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "exemplos:\n"
            "  python3 dividendos.py PETR4\n"
            "  python3 dividendos.py PETR4:200\n"
            "  python3 dividendos.py MXRF11:500 KNRI11:100 PETR4:200\n"
            "  python3 dividendos.py -c carteira.yaml\n"
        ),
    )
    parser.add_argument(
        "tickers",
        nargs="*",
        metavar="TICKER[:COTAS]",
        help="Ticker(s) a consultar, com quantidade de cotas opcional (ex: PETR4:200).",
    )
    parser.add_argument(
        "-c", "--config",
        metavar="ARQUIVO",
        help="Arquivo YAML com lista predefinida de ativos (tickers e cotas).",
    )
    parser.add_argument(
        "-a", "--ano",
        type=int,
        default=date.today().year,
        metavar="ANO",
        help=f"Ano a consultar (padrão: {date.today().year}).",
    )
    args = parser.parse_args()

    if not args.tickers and not args.config:
        parser.print_help()
        sys.exit(1)

    ano_atual = args.ano

    # Carregar tickers: do arquivo YAML ou dos argumentos posicionais
    if args.config:
        try:
            ativos = _carregar_config(args.config)
        except FileNotFoundError:
            print(f"ERRO: arquivo não encontrado: {args.config}")
            sys.exit(1)
        except Exception as e:
            print(f"ERRO ao ler configuração: {e}")
            sys.exit(1)
        if not ativos:
            print(f"ERRO: nenhum ativo encontrado em {args.config}")
            sys.exit(1)
    else:
        ativos = [
            {"ticker": t, "qtd": q, "historico": None}
            for t, q in (_parse_arg(a) for a in args.tickers)
        ]

    tickers = [a["ticker"] for a in ativos]

    def _get_qtd_map(ativo: dict) -> dict:
        """Retorna {mes: qty} para o ano consultado."""
        if ativo.get("historico"):
            from carteira import qtd_por_mes
            return qtd_por_mes(ativo["historico"], ano_atual)
        qtd = ativo.get("qtd", 0)
        return {m: qtd for m in range(1, 13)}

    # ── Single ticker: detailed view ──────────────────────────────────────────
    if len(tickers) == 1:
        ativo  = ativos[0]
        ticker = ativo["ticker"]
        qtd_map = _get_qtd_map(ativo)
        if all(v == 0 for v in qtd_map.values()):
            print(f"  {ticker}: posição encerrada em {ano_atual}. Nenhum dado a exibir.")
            return
        print(f"Buscando proventos de {ticker} para {ano_atual} via Status Invest...")
        try:
            proventos, tipo = buscar_proventos(ticker)
        except ValueError as e:
            print(f"  Erro: {e}")
            print("  Verifique se o ticker está correto (ex: PETR4, MXRF11, KNRI11).")
            sys.exit(1)
        except (TimeoutError, RuntimeError) as e:
            print(f"\n  Erro: {e}.\n  O site Status Invest pode estar fora do ar ou com lentidão.")
            sys.exit(1)
        por_mes = agregar_por_mes(proventos, ano_atual)
        exibir_resultado(ticker, tipo, por_mes, ano_atual, qtd_map)
        return

    # ── Multiple tickers: matrix view ─────────────────────────────────────────
    print(f"Buscando proventos de {len(tickers)} ativos para {ano_atual} via Status Invest...\n")
    dados: dict[str, dict[int, float]] = {}
    tipos: dict[str, str] = {}
    qtd_maps: dict[str, dict] = {}
    erros: list[str] = []

    for ativo in ativos:
        ticker = ativo["ticker"]
        qtd_map_candidato = _get_qtd_map(ativo)
        # Omite tickers sem posição no ano consultado (todos os meses = 0)
        if all(v == 0 for v in qtd_map_candidato.values()):
            continue
        print(f"  • {ticker} ... ", end="", flush=True)
        try:
            proventos, tipo = buscar_proventos(ticker)
            por_mes = agregar_por_mes(proventos, ano_atual)
            dados[ticker] = total_por_mes(por_mes)
            tipos[ticker] = tipo
            qtd_maps[ticker] = qtd_map_candidato
            print("OK")
        except ValueError as e:
            print(f"ignorado ({e})")
            erros.append(ticker)
        except (TimeoutError, RuntimeError) as e:
            print(f"ignorado ({e})")
            erros.append(ticker)

    if erros:
        print(f"\n  Atenção: {len(erros)} ativo(s) ignorado(s) por erro: {', '.join(erros)}")

    if not dados:
        print("\n  Nenhum dado disponível para exibir.")
        sys.exit(1)

    exibir_matriz(dados, tipos, qtd_maps, ano_atual)


if __name__ == "__main__":
    main()

