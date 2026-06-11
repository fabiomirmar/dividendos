"""
Servidor web para consulta de proventos de ações e FIIs.
Uso: python3 app.py
Acesse: http://localhost:5000
"""

import sys
import os
from datetime import date
from flask import Flask, render_template, request, jsonify

# Allow importing core from the same directory
sys.path.insert(0, os.path.dirname(__file__))
from core import buscar_proventos, agregar_por_mes, total_por_mes, MESES, MESES_CURTOS

app = Flask(__name__)


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
        "por_mes_total":   {m: round(v, 2) for m, v in por_mes_total.items()},
    }


@app.route("/")
def index():
    return render_template("index.html", ano=date.today().year)


@app.route("/api/proventos", methods=["POST"])
def api_proventos():
    body = request.get_json(force=True)
    ativos = body.get("ativos", [])   # [{ticker, qtd}]
    ano    = int(body.get("ano", date.today().year))

    if not ativos:
        return jsonify({"erro": "Nenhum ativo informado."}), 400

    resultados = []
    erros      = []

    for a in ativos:
        ticker = a.get("ticker", "").strip().upper()
        qtd    = int(a.get("qtd") or 0)
        if not ticker:
            continue
        try:
            dados = _processar_ticker(ticker, qtd, ano)
            resultados.append(dados)
        except ValueError as e:
            erros.append({"ticker": ticker, "erro": str(e)})
        except TimeoutError as e:
            erros.append({"ticker": ticker, "erro": str(e)})

    return jsonify({
        "ano":        ano,
        "meses_curtos": MESES_CURTOS,
        "resultados": resultados,
        "erros":      erros,
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Iniciando servidor em http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
