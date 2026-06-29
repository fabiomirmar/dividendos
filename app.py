"""
Servidor web para consulta de proventos de ações e FIIs.

Uso:
  python3 app.py                          # sem configuração prévia
  python3 app.py --config carteira.yaml   # com arquivo de configuração
  python3 app.py -c carteira.yaml         # forma abreviada
  python3 app.py -P 8080                  # porta personalizada
  python3 app.py -p $(echo -n 'senha' | base64)   # com proteção por senha

Acesse: http://localhost:5000
"""

import json as _json
import sys
import os
import time
import argparse
import threading
from datetime import date
import base64
import secrets
from functools import wraps
from flask import Flask, render_template, request, jsonify, Response, stream_with_context, session, redirect, url_for

try:
    import yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False

# Allow importing core from the same directory
sys.path.insert(0, os.path.dirname(__file__))
from core import buscar_proventos, agregar_por_mes, total_por_mes, MESES, MESES_CURTOS, INTER_REQ_DELAY
import cache as _cache
from carteira import parse_carteira, qtd_por_mes as _qtd_por_mes, resolver_qtd, qtd_display, tem_posicao_no_ano as _tem_posicao

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), "static"))
app.secret_key = secrets.token_hex(32)

# Ativos pré-carregados do arquivo de configuração
# lista de {ticker, qtd, historico}
app.config["ATIVOS_CONFIG"] = []
app.config["PASSWORD"] = None  # None = sem proteção por senha


def _login_required(f):
    """Decorator: redireciona para login se senha estiver configurada e usuário não autenticado."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if app.config["PASSWORD"] and not session.get("autenticado"):
            if request.is_json or request.headers.get("Accept") == "text/event-stream":
                return jsonify({"erro": "Não autorizado"}), 401
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return decorated


def _carregar_config(caminho: str) -> list[dict]:
    """Lê arquivo YAML (formato antigo ou novo) e retorna lista de {ticker, qtd, historico}."""
    if not _YAML_AVAILABLE:
        print("AVISO: pyyaml não está instalado. Execute: pip install pyyaml")
        return []
    with open(caminho, encoding="utf-8") as f:
        dados = yaml.safe_load(f)
    return parse_carteira(dados)


def _processar_ticker(ticker: str, qtd_map: dict | int, ano: int, force_refresh: bool = False) -> dict:
    """
    Busca e processa proventos de um ticker. Usa cache salvo em disco.

    qtd_map pode ser:
      - int: quantidade fixa para todos os meses
      - dict {mes: qty}: quantidade variável por mês (carry-forward já resolvido)
    """
    from_cache = False
    fetched_at = None

    cached = None if force_refresh else _cache.get_fresh(ticker, ano)
    if cached:
        proventos, tipo, fetched_at = cached
        from_cache = True
    else:
        proventos, tipo = buscar_proventos(ticker)
        _cache.put(ticker, ano, proventos, tipo)
        fetched_at = None  # acabou de buscar

    por_mes_detalhe = agregar_por_mes(proventos, ano)
    por_mes_total   = total_por_mes(por_mes_detalhe)

    # Normaliza qtd_map: sempre {mes: qty} para uso uniforme
    if isinstance(qtd_map, dict):
        qtd_mes = qtd_map          # já resolvido por mês
        qtd_fixo = None            # indica quantidade variável
    else:
        qtd_fixo = int(qtd_map or 0)
        qtd_mes = {m: qtd_fixo for m in range(1, 13)}

    meses_data = []
    total_ano_reais = 0.0
    por_mes_reais = {}   # {mes: R$ já calculado com qtd do mês}

    for m in range(1, 13):
        pagamentos = por_mes_detalhe.get(m, [])
        grupos = {}
        for p in pagamentos:
            grupos.setdefault(p["data_pagamento"], []).append(p)

        qtd = qtd_mes.get(m, 0)
        total_mes_bruto = sum(p["valor"] for p in pagamentos)
        total_mes_reais = round(total_mes_bruto * qtd, 2) if qtd else None
        if total_mes_reais:
            total_ano_reais += total_mes_reais
            por_mes_reais[m] = total_mes_reais

        meses_data.append({
            "mes":        m,
            "nome":       MESES[m - 1],
            "qtd":        qtd,
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
            "total_reais": total_mes_reais,
        })

    total_ano_bruto = sum(por_mes_total.values())
    return {
        "ticker":          ticker.upper(),
        "tipo":            tipo,
        "qtd":             qtd_fixo,   # None quando variável
        "qtd_variavel":    qtd_fixo is None and any(qtd_mes.values()),
        "ano":             ano,
        "meses":           meses_data,
        "total_ano_bruto": round(total_ano_bruto, 6),
        "total_ano_reais": round(total_ano_reais, 2) if total_ano_reais else None,
        "por_mes_total":   {m: round(v, 6) for m, v in por_mes_total.items()},
        "por_mes_reais":   por_mes_reais,   # {mes: R$} pré-calculado
        "from_cache":      from_cache,
        "fetched_at":      fetched_at.isoformat(timespec="seconds") if fetched_at else None,
    }


@app.route("/login", methods=["GET", "POST"])
def login():
    erro = None
    if request.method == "POST":
        senha = request.form.get("senha", "")
        if senha == app.config["PASSWORD"]:
            session["autenticado"] = True
            return redirect(request.args.get("next") or url_for("index"))
        erro = "Senha incorreta."
    return render_template("login.html", erro=erro)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@_login_required
def index():
    return render_template("index.html", ano=date.today().year,
                           has_password=bool(app.config["PASSWORD"]))


@app.route("/api/config")
@_login_required
def api_config():
    """Retorna os ativos pré-carregados. Para o novo formato, inclui qtd resolvida para hoje."""
    ano_hoje = date.today().year
    mes_hoje = date.today().month
    ativos_resp = []
    for a in app.config["ATIVOS_CONFIG"]:
        if a.get("historico"):
            qtd_atual = resolver_qtd(a["historico"], ano_hoje, mes_hoje)
        else:
            qtd_atual = a.get("qtd", 0)
        ativos_resp.append({
            "ticker":    a["ticker"],
            "qtd":       qtd_atual,
            "variavel":  a.get("historico") is not None,
        })
    carteira_variavel = all(a.get("historico") is not None for a in app.config["ATIVOS_CONFIG"]) \
        if app.config["ATIVOS_CONFIG"] else False
    return jsonify({"ativos": ativos_resp, "carteira_variavel": carteira_variavel})


@app.route("/api/proventos", methods=["POST"])
@_login_required
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
@_login_required
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
    force_refresh = bool(body.get("force_refresh", False))

    # Índice de historico por ticker (para o novo formato de carteira)
    _historico_idx = {
        a["ticker"]: a["historico"]
        for a in app.config["ATIVOS_CONFIG"]
        if a.get("historico")
    }

    def _sse(payload: dict) -> str:
        return f"data: {_json.dumps(payload, ensure_ascii=False)}\n\n"

    def generate():
        # Pré-resolve qtd_map por ticker e filtra posições zeradas no ano
        ativos_filtrados = []
        for a in ativos:
            ticker = a.get("ticker", "").strip().upper()
            if not ticker:
                continue
            qtd = int(a.get("qtd") or 0)
            historico = _historico_idx.get(ticker)
            if historico and qtd == 0:
                qtd_map = _qtd_por_mes(historico, ano)
                if not _tem_posicao(historico, ano):
                    continue   # sem posição neste ano — omite
            else:
                qtd_map = qtd
            ativos_filtrados.append((ticker, qtd_map))

        total = len(ativos_filtrados)
        for idx, (ticker, qtd_map) in enumerate(ativos_filtrados, 1):

            # Delay apenas quando vai buscar do Status Invest
            cached_check = _cache.get_fresh(ticker, ano) if not force_refresh else None
            if idx > 1 and not cached_check:
                time.sleep(INTER_REQ_DELAY)

            yield _sse({"type": "progress", "ticker": ticker, "index": idx, "total": total})

            try:
                dados = _processar_ticker(ticker, qtd_map, ano, force_refresh=force_refresh)
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


@app.route("/api/cache/status")
@_login_required
def api_cache_status():
    """Retorna informações sobre o cache atual."""
    return jsonify(_cache.status())


@app.route("/api/cache/invalidate", methods=["POST"])
@_login_required
def api_cache_invalidate():
    """
    Invalida entradas do cache.
    Body (opcional): {"tickers": ["PETR4", "MXRF11"], "ano": 2026}
    Sem body: invalida todo o cache.
    """
    body    = request.get_json(force=True) or {}
    tickers = body.get("tickers")
    ano     = int(body.get("ano", date.today().year))
    if tickers:
        for t in tickers:
            _cache.invalidate(t.strip().upper(), ano)
        return jsonify({"invalidated": tickers})
    _cache.invalidate()
    return jsonify({"invalidated": "all"})


# ── Background daily refresh ───────────────────────────────────────────────────

def _bg_refresh():
    """Verifica a cada hora se há entradas expiradas e as atualiza em background."""
    ano = date.today().year
    stale = _cache.stale_keys()
    if stale:
        print(f"[cache] Atualizando {len(stale)} entrada(s) expirada(s)...")
        for key in stale:
            ticker, ano_str = key.split(":", 1)
            try:
                proventos, tipo = buscar_proventos(ticker)
                _cache.put(ticker, int(ano_str), proventos, tipo)
                print(f"[cache] {ticker}:{ano_str} atualizado.")
                time.sleep(INTER_REQ_DELAY)
            except Exception as e:
                print(f"[cache] Erro ao atualizar {ticker}: {e}")
    # Reagenda para daqui a 1 hora
    t = threading.Timer(3600, _bg_refresh)
    t.daemon = True
    t.start()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Servidor web de consulta de proventos de ações e FIIs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemplos:\n"
            "  python3 app.py\n"
            "  python3 app.py --config carteira.yaml\n"
            "  python3 app.py -c carteira.yaml -P 8080\n"
            "  python3 app.py -p $(echo -n 'minhasenha' | base64)\n"
        ),
    )
    parser.add_argument(
        "-c", "--config",
        metavar="ARQUIVO",
        help="Arquivo YAML com lista predefinida de ativos (tickers e cotas).",
    )
    parser.add_argument(
        "-P", "--port",
        type=int,
        default=int(os.environ.get("PORT", 5000)),
        metavar="PORTA",
        help="Porta do servidor (padrão: 5000).",
    )
    parser.add_argument(
        "-p", "--password",
        metavar="BASE64",
        help="Senha em Base64 para proteger o acesso ao site.",
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

    if args.password:
        try:
            senha_decoded = base64.b64decode(args.password).decode("utf-8")
            app.config["PASSWORD"] = senha_decoded
            print("Proteção por senha ativada.")
        except Exception:
            print("ERRO: --password deve estar em formato Base64 válido.")
            print("  Exemplo: python3 app.py -p $(echo -n 'minhasenha' | base64)")
            sys.exit(1)

    print(f"Iniciando servidor em http://localhost:{args.port}")
    _bg_refresh()   # inicia o loop de refresh automático (daemon thread)
    app.run(host="0.0.0.0", port=args.port, debug=False, threaded=True)
