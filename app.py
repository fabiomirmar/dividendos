"""
Servidor web para consulta de proventos de ações e FIIs.

Uso:
  python3 app.py                          # sem configuração prévia
  python3 app.py --config carteira.yaml   # com arquivo de configuração
  python3 app.py -c carteira.yaml         # forma abreviada

Acesse: http://localhost:5000
"""

import json as _json
import sys
import os
import time
import argparse
from datetime import date
from flask import Flask, render_template, request, jsonify, Response, stream_with_context

try:
    import yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False

# Allow importing core from the same directory
sys.path.insert(0, os.path.dirname(__file__))
from core import buscar_proventos, agregar_por_mes, total_por_mes, MESES, MESES_CURTOS, INTER_REQ_DELAY

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), "static"))

# Ativos pré-carregados do arquivo de configuração (lista de {ticker, qtd})
app.config["ATIVOS_CONFIG"] = []


def _carregar_config(caminho: str) -> list[dict]:
    """Lê um arquivo YAML de configuração e retorna lista de {ticker, qtd}."""
    if not _YAML_AVAILABLE:
        print("AVISO: pyyaml não está instalado. Execute: pip install pyyaml")
        return []
    with open(caminho, encoding="utf-8") as f:
        dados = yaml.safe_load(f)
    ativos = []
    for item in dados.get("ativos", []):
        ticker = str(item.get("ticker", "")).strip().upper()
        if not ticker:
            continue
        qtd = int(item.get("qtd") or 0)
        ativos.append({"ticker": ticker, "qtd": qtd})
    return ativos


def _processar_ticker(ticker: str, qtd: int, ano: int) -> dict:
    """Busca e processa proventos de um ticker. Retorna um dict com os dados."""
    proventos, tipo = buscar_proventos(ticker)
    por_mes_detalhe = agregar_por_mes(proventos, ano)
    por_mes_total   = total_por_mes(por_mes_detalhe)

    meses_data = []
    for m in range(1, 13):
        pagamentos = por_mes_detalhe.get(m, [])
        grupos = {}
        for p in pagamentos:
            grupos.setdefault(p["data_pagamento"], []).append(p)

        total_mes_bruto = sum(p["valor"] for p in pagamentos)
        meses_data.append({
            "mes":        m,
            "nome":       MESES[m - 1],
            "grupos":     [
                {
                    "data_pagamento": pgto,
                    "data_com":       itens[0]["data_com"],
                    "itens": [
                        {
                            "tipo":  i["tipo"],
                            "valor": i["valor"],
                            "total": round(i["valor"] * qtd, 2) if qtd else None,
                        }
                        for i in itens
                    ],
                    "subtotal":       round(sum(i["valor"] for i in itens), 6),
                    "subtotal_total": round(sum(i["valor"] for i in itens) * qtd, 2) if qtd else None,
                }
                for pgto, itens in grupos.items()
            ],
            "total_bruto": round(total_mes_bruto, 6),
            "total_reais": round(total_mes_bruto * qtd, 2) if qtd else None,
        })

    total_ano_bruto = sum(por_mes_total.values())
    return {
        "ticker":          ticker.upper(),
        "tipo":            tipo,
        "qtd":             qtd,
        "ano":             ano,
        "meses":           meses_data,
        "total_ano_bruto": round(total_ano_bruto, 6),
        "total_ano_reais": round(total_ano_bruto * qtd, 2) if qtd else None,
        "por_mes_total":   {m: round(v, 6) for m, v in por_mes_total.items()},
    }


@app.route("/")
def index():
    return render_template("index.html", ano=date.today().year)


@app.route("/api/config")
def api_config():
    """Retorna os ativos pré-carregados do arquivo de configuração."""
    return jsonify({"ativos": app.config["ATIVOS_CONFIG"]})


@app.route("/api/proventos", methods=["POST"])
def api_proventos():
    body = request.get_json(force=True)
    ativos = body.get("ativos", [])   # [{ticker, qtd}]
    ano    = int(body.get("ano", date.today().year))

    if not ativos:
        return jsonify({"erro": "Nenhum ativo informado."}), 400

    resultados = []
    erros      = []

    for i, a in enumerate(ativos):
        ticker = a.get("ticker", "").strip().upper()
        qtd    = int(a.get("qtd") or 0)
        if not ticker:
            continue
        # Pequeno delay entre requisições para evitar rate-limit (429)
        if i > 0:
            time.sleep(INTER_REQ_DELAY)
        try:
            dados = _processar_ticker(ticker, qtd, ano)
            resultados.append(dados)
        except (ValueError, TimeoutError, RuntimeError) as e:
            erros.append({"ticker": ticker, "erro": str(e)})

    return jsonify({
        "ano":        ano,
        "meses_curtos": MESES_CURTOS,
        "resultados": resultados,
        "erros":      erros,
    })


@app.route("/api/proventos/stream", methods=["POST"])
def api_proventos_stream():
    """
    Endpoint SSE: processa tickers um a um e emite eventos à medida que avança.
    Eventos emitidos (formato SSE, 'data: <JSON>\\n\\n'):
      {"type": "progress", "ticker": "...", "index": 1, "total": 4}
      {"type": "result",   "data": {...}}
      {"type": "error",    "ticker": "...", "erro": "..."}
      {"type": "done",     "ano": 2026, "meses_curtos": [...]}
    """
    body    = request.get_json(force=True)
    ativos  = body.get("ativos", [])
    ano     = int(body.get("ano", date.today().year))

    def _sse(payload: dict) -> str:
        return f"data: {_json.dumps(payload, ensure_ascii=False)}\n\n"

    def generate():
        total = sum(1 for a in ativos if a.get("ticker", "").strip())
        idx   = 0
        for a in ativos:
            ticker = a.get("ticker", "").strip().upper()
            qtd    = int(a.get("qtd") or 0)
            if not ticker:
                continue
            idx += 1
            if idx > 1:
                time.sleep(INTER_REQ_DELAY)

            yield _sse({"type": "progress", "ticker": ticker, "index": idx, "total": total})

            try:
                dados = _processar_ticker(ticker, qtd, ano)
                yield _sse({"type": "result", "data": dados})
            except (ValueError, TimeoutError, RuntimeError) as e:
                yield _sse({"type": "error", "ticker": ticker, "erro": str(e)})

        yield _sse({"type": "done", "ano": ano, "meses_curtos": MESES_CURTOS})

    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Servidor web de consulta de proventos de ações e FIIs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemplos:\n"
            "  python3 app.py\n"
            "  python3 app.py --config carteira.yaml\n"
            "  python3 app.py -c carteira.yaml -p 8080\n"
        ),
    )
    parser.add_argument(
        "-c", "--config",
        metavar="ARQUIVO",
        help="Arquivo YAML com lista predefinida de ativos (tickers e cotas).",
    )
    parser.add_argument(
        "-p", "--port",
        type=int,
        default=int(os.environ.get("PORT", 5000)),
        metavar="PORTA",
        help="Porta do servidor (padrão: 5000).",
    )
    args = parser.parse_args()

    if args.config:
        try:
            ativos = _carregar_config(args.config)
            app.config["ATIVOS_CONFIG"] = ativos
            print(f"Configuração carregada: {args.config} ({len(ativos)} ativo(s))")
            for a in ativos:
                sufixo = f"  ×{a['qtd']}" if a["qtd"] else ""
                print(f"  • {a['ticker']}{sufixo}")
        except FileNotFoundError:
            print(f"ERRO: arquivo não encontrado: {args.config}")
            sys.exit(1)
        except Exception as e:
            print(f"ERRO ao ler configuração: {e}")
            sys.exit(1)

    print(f"Iniciando servidor em http://localhost:{args.port}")
    app.run(host="0.0.0.0", port=args.port, debug=False, threaded=True)
