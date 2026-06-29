"""
Cache em disco para os dados de proventos obtidos do Status Invest.

Estrutura do arquivo cache.json:
  {
    "PETR4:2026": {
      "proventos": [...],   # saída bruta de buscar_proventos()
      "tipo": "Ação",
      "fetched_at": "2026-06-29T08:00:00"
    },
    ...
  }
"""

import json
import os
import threading
from datetime import datetime, timedelta

CACHE_FILE = os.path.join(os.path.dirname(__file__), "proventos_cache.json")
CACHE_TTL_HOURS = 24

_lock = threading.Lock()


# ── I/O ────────────────────────────────────────────────────────────────────────

def _load() -> dict:
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data: dict) -> None:
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── Public API ─────────────────────────────────────────────────────────────────

def get_fresh(ticker: str, ano: int):
    """Retorna (proventos, tipo, fetched_at) se o cache existir e for recente, senão None."""
    with _lock:
        data = _load()
        entry = data.get(f"{ticker}:{ano}")
        if not entry:
            return None
        fetched_at = datetime.fromisoformat(entry["fetched_at"])
        if datetime.now() - fetched_at > timedelta(hours=CACHE_TTL_HOURS):
            return None
        return entry["proventos"], entry["tipo"], fetched_at


def get_any(ticker: str, ano: int):
    """Retorna (proventos, tipo, fetched_at) independente da idade, ou None."""
    with _lock:
        data = _load()
        entry = data.get(f"{ticker}:{ano}")
        if not entry:
            return None
        fetched_at = datetime.fromisoformat(entry["fetched_at"])
        return entry["proventos"], entry["tipo"], fetched_at


def put(ticker: str, ano: int, proventos: list, tipo: str) -> None:
    """Grava/atualiza entrada no cache."""
    with _lock:
        data = _load()
        data[f"{ticker}:{ano}"] = {
            "proventos": proventos,
            "tipo": tipo,
            "fetched_at": datetime.now().isoformat(timespec="seconds"),
        }
        _save(data)


def invalidate(ticker: str = None, ano: int = None) -> None:
    """Invalida uma entrada específica (ticker+ano) ou todo o cache (sem args)."""
    with _lock:
        data = _load()
        if ticker is None:
            data = {}
        else:
            data.pop(f"{ticker}:{ano}", None)
        _save(data)


def status() -> dict:
    """Retorna dict {ticker:ano -> {fetched_at, is_fresh, tipo}} para todos os itens."""
    with _lock:
        data = _load()
        now = datetime.now()
        result = {}
        for key, entry in data.items():
            fetched_at = datetime.fromisoformat(entry["fetched_at"])
            result[key] = {
                "fetched_at": entry["fetched_at"],
                "is_fresh": (now - fetched_at) < timedelta(hours=CACHE_TTL_HOURS),
                "tipo": entry.get("tipo", ""),
            }
        return result


def stale_keys() -> list[str]:
    """Retorna lista de chaves 'ticker:ano' com cache expirado."""
    with _lock:
        data = _load()
        now = datetime.now()
        return [
            k for k, v in data.items()
            if (now - datetime.fromisoformat(v["fetched_at"])) > timedelta(hours=CACHE_TTL_HOURS)
        ]
