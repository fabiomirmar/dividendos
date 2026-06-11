# dividendos

Consulta proventos (dividendos, JCP, rendimentos) de ações e FIIs brasileiros para o ano corrente, com dados obtidos via scraping do [Status Invest](https://statusinvest.com.br).

## Funcionalidades

- Detecta automaticamente se o ticker é uma **ação** ou **FII**
- **Ticker único** → visão detalhada mês a mês, com tipo do provento, data-com e data de pagamento
- **Múltiplos tickers** → tabela combinada com meses no eixo horizontal e total anual por ativo
- Retries automáticos em caso de timeout do servidor
- Sem dependências externas — apenas a biblioteca padrão do Python 3

## Requisitos

- Python 3.10 ou superior

## Uso

```bash
# Visão detalhada de um único ativo
python3 dividendos.py PETR4

# Tabela combinada de múltiplos ativos
python3 dividendos.py MXRF11 KNRI11 PETR4

# Ajuda
python3 dividendos.py --help
```

## Exemplos de saída

### Ticker único (`PETR4`)

```
  Proventos de PETR4 (Ação) — 2026

  ┌─────────────┬────────────┬────────────┬────────────────────────┬──────────────┐
  │ Mês         │ Pagamento  │ Data-com   │ Tipo                   │   Valor (R$) │
  ├─────────────┼────────────┼────────────┼────────────────────────┼──────────────┤
  │ Janeiro     │ —          │            │                        │              │
  ├─────────────┼────────────┼────────────┼────────────────────────┼──────────────┤
  │ Fevereiro   │ 20/02/2026 │ 22/12/2025 │ JCP                    │     0.471604 │
  │             │            │            │ Rend. Tributado        │     0.008921 │
  │             │            │            │ Subtotal               │     0.480525 │
  ├─────────────┼────────────┼────────────┼────────────────────────┼──────────────┤
  │ Março       │ 20/03/2026 │ 22/12/2025 │ Dividendo              │     0.296421 │
  │             │            │            │ JCP                    │     0.175797 │
  │             │            │            │ Rend. Tributado        │     0.008955 │
  │             │            │            │ Subtotal               │     0.481173 │
  ├─────────────┴────────────┴────────────┴────────────────────────┼──────────────┤
  │ TOTAL ANO                                                      │     2.318540 │
  └────────────────────────────────────────────────────────────────┴──────────────┘
```

### Múltiplos tickers

```
  Proventos combinados — 2026  (R$)

  ┌──────────────┬─────────┬─────────┬─────────┬─────────┬─────────┬─────────┬─────────┬─────────┬─────────┬─────────┬─────────┬─────────┬───────────┐
  │ Ticker       │   Jan   │   Fev   │   Mar   │   Abr   │   Mai   │   Jun   │   Jul   │   Ago   │   Set   │   Out   │   Nov   │   Dez   │     Total │
  ├──────────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼───────────┤
  │ MXRF11 (FII) │    0.10 │    0.10 │    0.10 │    0.10 │    0.10 │    0.10 │       — │       — │       — │       — │       — │       — │      0.59 │
  │ KNRI11 (FII) │    1.25 │    0.88 │    1.10 │    1.10 │    1.10 │    1.10 │       — │       — │       — │       — │       — │       — │      6.53 │
  │ PETR4 (Ação) │       — │    0.48 │    0.48 │       — │    0.33 │    0.33 │       — │    0.35 │    0.35 │       — │       — │       — │      2.32 │
  ├──────────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼───────────┤
  │ TOTAL        │    1.35 │    1.46 │    1.68 │    1.20 │    1.53 │    1.53 │       — │    0.35 │    0.35 │       — │       — │       — │      9.44 │
  └──────────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴───────────┘
```

## Notas

- Os dados refletem o **ano corrente** com base na data de pagamento dos proventos.
- Meses futuros mostram proventos já anunciados mas ainda não pagos.
- A fonte dos dados é o site Status Invest. O script pode parar de funcionar caso o site altere sua estrutura HTML.
- Este projeto realiza scraping de uso pessoal. Respeite os [termos de uso](https://statusinvest.com.br) do site.

## Licença

MIT
