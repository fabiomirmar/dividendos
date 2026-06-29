# dividendos

Consulta proventos (dividendos, JCP, rendimentos) de ações e FIIs brasileiros para o ano corrente, com dados obtidos via scraping do [Status Invest](https://statusinvest.com.br).

## Funcionalidades

- Detecta automaticamente se o ticker é uma **ação** ou **FII**
- **Ticker único** → visão detalhada mês a mês, com tipo do provento, data-com e data de pagamento
- **Múltiplos tickers** → tabela combinada com meses no eixo horizontal e total anual por ativo
- **Quantidade de cotas** → informe `TICKER:COTAS` para multiplicar os proventos pela quantidade e ver o total em reais
- Retries automáticos em caso de timeout do servidor
- Sem dependências externas para o CLI — apenas a biblioteca padrão do Python 3
- A aplicação web requer [Flask](https://flask.palletsprojects.com/) (`pip install flask`)

## Requisitos

- Python 3.10 ou superior
- Flask 3.0+ (apenas para a aplicação web: `pip install -r requirements.txt`)

## Uso

```bash
# Visão detalhada de um único ativo
python3 dividendos.py PETR4

# Visão detalhada com quantidade de cotas
python3 dividendos.py PETR4:200

# Tabela combinada de múltiplos ativos
python3 dividendos.py MXRF11 KNRI11 PETR4

# Tabela combinada com quantidades de cotas
python3 dividendos.py MXRF11:500 KNRI11:100 PETR4:200

# Mix: alguns com quantidade, outros sem
python3 dividendos.py MXRF11:500 KNRI11 PETR4:200

# Carregar tickers direto de um arquivo de configuração YAML
python3 dividendos.py -c carteira.yaml

# Ajuda
python3 dividendos.py --help
```

## Exemplos de saída

### Ticker único sem cotas (`PETR4`)

```
  Proventos de PETR4 (Ação) — 2026

  ┌─────────────┬────────────┬────────────┬────────────────────────┬──────────────┐
  │ Mês         │ Pagamento  │ Data-com   │ Tipo                   │   Valor (R$) │
  ├─────────────┼────────────┼────────────┼────────────────────────┼──────────────┤
  │ Fevereiro   │ 20/02/2026 │ 22/12/2025 │ JCP                    │     0.471604 │
  │             │            │            │ Rend. Tributado        │     0.008921 │
  │             │            │            │ Subtotal               │     0.480525 │
  ├─────────────┼────────────┼────────────┼────────────────────────┼──────────────┤
  │ Março       │ 20/03/2026 │ 22/12/2025 │ Dividendo              │     0.296421 │
  │             │            │            │ JCP                    │     0.175797 │
  │             │            │            │ Rend. Tributado        │     0.008955 │
  │             │            │            │ Subtotal               │     0.481173 │
  ├────────────────────────────────────────────────────────────────┼──────────────┤
  │ TOTAL ANO                                                      │     2.318540 │
  └────────────────────────────────────────────────────────────────┴──────────────┘
```

### Ticker único com cotas (`PETR4:200`)

```
  Proventos de PETR4 (Ação) — 2026  ·  200 cotas

  ┌─────────────┬────────────┬────────────┬────────────────────────┬──────────────┬──────────────┐
  │ Mês         │ Pagamento  │ Data-com   │ Tipo                   │      R$/cota │   Total (R$) │
  ├─────────────┼────────────┼────────────┼────────────────────────┼──────────────┼──────────────┤
  │ Fevereiro   │ 20/02/2026 │ 22/12/2025 │ JCP                    │     0.471604 │        94.32 │
  │             │            │            │ Rend. Tributado        │     0.008921 │         1.78 │
  │             │            │            │ Subtotal               │     0.480525 │        96.10 │
  ├─────────────┼────────────┼────────────┼────────────────────────┼──────────────┼──────────────┤
  │ Março       │ 20/03/2026 │ 22/12/2025 │ Dividendo              │     0.296421 │        59.28 │
  │             │            │            │ JCP                    │     0.175797 │        35.16 │
  │             │            │            │ Rend. Tributado        │     0.008955 │         1.79 │
  │             │            │            │ Subtotal               │     0.481173 │        96.23 │
  ├────────────────────────────────────────────────────────────────┼──────────────┼──────────────┤
  │ TOTAL ANO (por cota)                                           │     2.318540 │              │
  │ TOTAL ANO                                                      │              │       463.71 │
  └────────────────────────────────────────────────────────────────┴──────────────┴──────────────┘
```

### Múltiplos tickers com cotas

```
  Proventos combinados (valores em R$ considerando as cotas informadas) — 2026  (R$)

  ┌───────────────────┬──────────┬──────────┬──────────┬──────────┬──────────┬──────────┬──────────┬──────────┬──────────┬──────────┬──────────┬──────────┬────────────┐
  │ Ticker            │   Jan    │   Fev    │   Mar    │   Abr    │   Mai    │   Jun    │   Jul    │   Ago    │   Set    │   Out    │   Nov    │   Dez    │      Total │
  ├───────────────────┼──────────┼──────────┼──────────┼──────────┼──────────┼──────────┼──────────┼──────────┼──────────┼──────────┼──────────┼──────────┼────────────┤
  │ MXRF11 (FII) ×500 │    50.00 │    50.00 │    50.00 │    47.50 │    50.00 │    50.00 │        — │        — │        — │        — │        — │        — │     297.50 │
  │ KNRI11 (FII) ×100 │   125.00 │    88.00 │   110.00 │   110.00 │   110.00 │   110.00 │        — │        — │        — │        — │        — │        — │     653.00 │
  │ PETR4 (Ação) ×200 │        — │    96.10 │    96.23 │        — │    65.92 │    65.25 │        — │    70.10 │    70.10 │        — │        — │        — │     463.71 │
  ├───────────────────┼──────────┼──────────┼──────────┼──────────┼──────────┼──────────┼──────────┼──────────┼──────────┼──────────┼──────────┼──────────┼────────────┤
  │ TOTAL             │   175.00 │   234.10 │   256.23 │   157.50 │   225.92 │   225.25 │        — │    70.10 │    70.10 │        — │        — │        — │    1414.21 │
  └───────────────────┴──────────┴──────────┴──────────┴──────────┴──────────┴──────────┴──────────┴──────────┴──────────┴──────────┴──────────┴──────────┴────────────┘
```

## Aplicação Web

O projeto inclui também uma interface web que oferece as mesmas funcionalidades do CLI.

### Requisitos adicionais

```bash
pip install -r requirements.txt
```

### Iniciar o servidor

```bash
# Sem configuração prévia (adicione os tickers via web)
python3 app.py

# Com arquivo de configuração (tickers pré-carregados na interface)
python3 app.py --config carteira.yaml
python3 app.py -c carteira.yaml

# Porta alternativa (flag -P maiúsculo)
python3 app.py -c carteira.yaml -P 8080

# Com proteção por senha (Base64)
python3 app.py -p $(echo -n 'minhasenha' | base64)

# Combinando todas as opções
python3 app.py -c carteira.yaml -P 8080 -p $(echo -n 'minhasenha' | base64)
```

### Proteção por senha

Use a flag `-p`/`--password` para proteger o acesso ao site com uma senha. O valor deve estar codificado em Base64:

```bash
# Gerar o Base64 da sua senha
echo -n 'minhasenha' | base64
# → bWluaGFzZW5oYQ==

python3 app.py -p bWluaGFzZW5oYQ==
```

Sem a flag, o site é acessível sem autenticação.

### Instalação como app no Android (PWA)

A aplicação web é uma **Progressive Web App (PWA)** e pode ser instalada no Android como se fosse um aplicativo nativo:

1. Abra o site no **Chrome** no celular
2. Toque no menu ⋮ → **"Instalar app"** (ou aguarde o banner automático)
3. O app aparecerá na tela inicial com o ícone 💰, sem barra de endereço

> **Requisito:** o Chrome exige HTTPS para mostrar o prompt de instalação. Em rede local, use um túnel como [Tailscale](https://tailscale.com) ou [ngrok](https://ngrok.com).

### Arquivo de configuração (`carteira.yaml`)

Crie um arquivo YAML baseado no exemplo `carteira.example.yaml`:

```yaml
ativos:
  - ticker: PETR4
    qtd: 200        # quantidade de ações/cotas (opcional)

  - ticker: MXRF11
    qtd: 500

  - ticker: VALE3   # sem quantidade: exibe apenas R$/cota

  - ticker: KNRI11
    qtd: 150
```

Ao iniciar com `--config`, os ativos aparecem pré-carregados na interface (marcados com um ponto roxo). Você ainda pode adicionar ou remover tickers manualmente via web.

### Funcionalidades da interface web

- Adicione tickers um a um com quantidade opcional (chips removíveis)
- Selecione o ano de consulta
- **Ticker único** → tabela detalhada mês a mês
- **Múltiplos tickers** → tabela combinada (matriz) com totais mensais
- Mensagens de erro para tickers inválidos
- Responsivo para desktop e mobile

## Notas

- Os dados refletem o **ano corrente** com base na data de pagamento dos proventos.
- Meses futuros mostram proventos já anunciados mas ainda não pagos.
- A fonte dos dados é o site Status Invest. O script pode parar de funcionar caso o site altere sua estrutura HTML.
- Este projeto realiza scraping de uso pessoal. Respeite os [termos de uso](https://statusinvest.com.br) do site.

## Licença

MIT
