"""
Módulo para parsing e resolução de quantidade de cotas por mês/ano.

Suporta dois formatos de YAML:

Formato antigo (lista de ativos com quantidade fixa):
  ativos:
    - ticker: PETR4
      qtd: 200

Novo formato (quantidade variável por mês/ano, carry-forward):
  PETR4:
    2025:
      dec: 1600
    2026:
      jan: 2770

No novo formato, cada entrada define a quantidade a partir daquele mês
até a próxima alteração (carry-forward). Qtd 0 = zerou a posição.
"""

MONTH_ABBR = ['jan', 'feb', 'mar', 'apr', 'may', 'jun',
               'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
MONTH_IDX  = {m: i + 1 for i, m in enumerate(MONTH_ABBR)}


def _is_novo_formato(dados: dict) -> bool:
    return 'ativos' not in dados


def parse_carteira(dados: dict) -> list[dict]:
    """
    Aceita ambos os formatos e retorna lista de:
      {
        'ticker':    str,
        'qtd':       int | None,   # None = quantidade variável
        'historico': dict | None,  # {(ano, mes_idx): qty}
      }
    """
    if not _is_novo_formato(dados):
        result = []
        for item in dados.get('ativos', []):
            ticker = str(item.get('ticker', '')).strip().upper()
            if ticker:
                result.append({
                    'ticker':    ticker,
                    'qtd':       int(item.get('qtd') or 0),
                    'historico': None,
                })
        return result

    result = []
    for ticker, anos in dados.items():
        if not isinstance(anos, dict):
            continue
        ticker = str(ticker).strip().upper()
        historico = {}
        for ano, meses in anos.items():
            if not isinstance(meses, dict):
                continue
            for mes_abbr, qty in meses.items():
                mes_idx = MONTH_IDX.get(str(mes_abbr).strip().lower())
                if mes_idx is not None:
                    historico[(int(ano), mes_idx)] = int(qty)
        result.append({
            'ticker':    ticker,
            'qtd':       None,        # variável
            'historico': historico,
        })
    return result


def resolver_qtd(historico: dict, ano: int, mes: int) -> int:
    """
    Retorna a quantidade efetiva para (ano, mes) usando carry-forward:
    pega a entrada mais recente com (y, m) <= (ano, mes).
    Retorna 0 se não houver nenhuma entrada anterior.
    """
    result = 0
    for (y, m), qty in sorted(historico.items()):
        if (y, m) <= (ano, mes):
            result = qty
        else:
            break
    return result


def qtd_por_mes(historico: dict, ano: int) -> dict:
    """Retorna {1..12: qty} resolvido para o ano consultado."""
    return {m: resolver_qtd(historico, ano, m) for m in range(1, 13)}


def qtd_display(historico: dict, ano: int) -> int | None:
    """
    Retorna a quantidade mais recente até dezembro do ano consultado,
    para exibição como referência. None se o histórico estiver vazio.
    """
    qtds = qtd_por_mes(historico, ano)
    valores = [v for v in qtds.values() if v > 0]
    return valores[-1] if valores else None


def tem_posicao_no_ano(historico: dict, ano: int) -> bool:
    """Retorna True se o ativo tem pelo menos um mês com quantidade > 0 no ano."""
    return any(v > 0 for v in qtd_por_mes(historico, ano).values())
