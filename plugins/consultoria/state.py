"""Estado entre as ferramentas.

``gerar_resumo`` guarda o que ``ajustar_resumo`` e ``aprovar_e_enviar``
precisam (transcrição, resumo aprovado até agora, documento gerado), para que
o consultor só precise responder "ok" ou mandar a correção no Telegram.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

CHAVE = "sessoes"
# O estado do Hermes tem cota (10 MB); guardamos poucas sessões e transcrições
# aparadas para nunca chegar perto dela.
MAXIMO_SESSOES = 10
MAXIMO_TRANSCRICAO = 150_000

_lock = threading.Lock()
_estado_hermes: Any = None  # ctx.state, quando o plugin é carregado pelo Hermes


def usar_estado_do_hermes(estado: Any) -> None:
    """Chamado em register(ctx) para usar o armazenamento durável do Hermes."""
    global _estado_hermes
    _estado_hermes = estado


def _caminho_arquivo() -> Path:
    base = os.getenv("CONSULTORIA_STATE_DIR") or (
        Path.home() / ".hermes" / "plugins" / "consultoria" / "state"
    )
    caminho = Path(base)
    caminho.mkdir(parents=True, exist_ok=True)
    return caminho / "sessoes.json"


def _ler() -> List[Dict[str, Any]]:
    if _estado_hermes is not None:
        try:
            return list(_estado_hermes.get(CHAVE, []) or [])
        except Exception:
            pass
    arquivo = _caminho_arquivo()
    if not arquivo.is_file():
        return []
    try:
        with arquivo.open("r", encoding="utf-8") as fonte:
            return list(json.load(fonte) or [])
    except (OSError, ValueError):
        return []


def _gravar(sessoes: List[Dict[str, Any]]) -> None:
    sessoes = sessoes[-MAXIMO_SESSOES:]
    if _estado_hermes is not None:
        try:
            _estado_hermes.set(CHAVE, sessoes)
            return
        except Exception:
            pass
    arquivo = _caminho_arquivo()
    # Escrita atômica: nunca deixa um JSON pela metade se o processo cair.
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=str(arquivo.parent), delete=False
    ) as temporario:
        json.dump(sessoes, temporario, ensure_ascii=False)
        provisorio = temporario.name
    os.replace(provisorio, arquivo)


def salvar(sessao: Dict[str, Any]) -> Dict[str, Any]:
    """Grava (ou atualiza) a sessão daquele cliente e a devolve."""
    sessao = dict(sessao)
    sessao["atualizado_em"] = time.time()
    transcricao = sessao.get("transcricao") or ""
    if len(transcricao) > MAXIMO_TRANSCRICAO:
        sessao["transcricao"] = transcricao[:MAXIMO_TRANSCRICAO]
    chave = (sessao.get("cliente") or "").strip().lower()
    with _lock:
        sessoes = [s for s in _ler() if (s.get("cliente") or "").strip().lower() != chave]
        sessoes.append(sessao)
        _gravar(sessoes)
    return sessao


def recuperar(cliente: str = "") -> Optional[Dict[str, Any]]:
    """Sessão do cliente informado; sem nome, a última sessão trabalhada."""
    sessoes = _ler()
    if not sessoes:
        return None
    if not cliente:
        return max(sessoes, key=lambda s: s.get("atualizado_em", 0))

    from .texto_utils import melhor_match, normalizar

    alvo = normalizar(cliente)
    for sessao in sorted(sessoes, key=lambda s: s.get("atualizado_em", 0), reverse=True):
        if normalizar(sessao.get("cliente", "")) == alvo:
            return sessao
    escolhido = melhor_match(cliente, [(s.get("cliente", ""), s) for s in sessoes])
    return escolhido[1] if escolhido else None


def limpar() -> None:
    with _lock:
        _gravar([])
