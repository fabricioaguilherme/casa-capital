"""Normalização e casamento de nomes (arquivo de transcrição x cadastro)."""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable, Optional, Tuple

_NAO_ALFANUM = re.compile(r"[^a-z0-9]+")
_PALAVRAS_IGNORADAS = {
    "transcricao", "transcript", "reuniao", "meeting", "consultoria", "sebrae",
    "notes", "notas", "resumo", "gravacao", "audio", "call", "tactiq", "craftnote",
    "google", "meet", "zoom", "docx", "txt", "pdf",
    # Sufixos societários: não distinguem um cliente do outro.
    "ltda", "eireli", "epp", "mei", "sa", "cia", "comercio", "servicos",
}


def normalizar(texto: str) -> str:
    """Minúsculas, sem acento e sem pontuação — base de toda comparação."""
    if not texto:
        return ""
    sem_acento = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return _NAO_ALFANUM.sub(" ", sem_acento.lower()).strip()


def tokens(texto: str) -> list[str]:
    return [t for t in normalizar(texto).split() if t]


def tokens_significativos(texto: str) -> list[str]:
    """Tokens úteis para casar nomes: descarta datas, ruídos e palavras genéricas."""
    uteis = []
    for token in tokens(texto):
        if token.isdigit() or len(token) < 3 or token in _PALAVRAS_IGNORADAS:
            continue
        uteis.append(token)
    return uteis


def pontuacao_match(nome_cadastro: str, nome_arquivo: str) -> float:
    """Quão bem o nome cadastrado aparece no nome do arquivo (0 a 1).

    Match parcial de propósito: o arquivo costuma ser
    ``Transcricao - Padaria do Ze - 2026-03-11.docx`` para o cadastro
    ``Padaria do Zé Ltda``.
    """
    alvo = normalizar(nome_arquivo)
    if not alvo:
        return 0.0

    nome_normalizado = normalizar(nome_cadastro)
    if nome_normalizado and nome_normalizado in alvo:
        # Nome inteiro presente: melhor casamento possível.
        return 1.0

    partes = tokens_significativos(nome_cadastro)
    if not partes:
        return 0.0

    encontrados = [parte for parte in partes if parte in alvo]
    if not encontrados:
        return 0.0

    proporcao = len(encontrados) / len(partes)
    # Nome longo casado só por um token curto vale menos.
    maior = max(len(parte) for parte in encontrados)
    bonus = min(maior / 12.0, 0.25)
    return min(0.95, proporcao * 0.75 + bonus)


def melhor_match(
    nome_arquivo: str, candidatos: Iterable[Tuple[str, object]], minimo: float = 0.45
) -> Optional[Tuple[str, object, float]]:
    """Escolhe o candidato ``(nome, payload)`` que melhor casa com o arquivo."""
    melhor = None
    for nome, payload in candidatos:
        pontos = pontuacao_match(nome, nome_arquivo)
        if pontos >= minimo and (melhor is None or pontos > melhor[2]):
            melhor = (nome, payload, pontos)
    return melhor


_APROVACOES = {
    "ok", "okay", "oka", "aprovado", "aprovada", "aprovo", "pode enviar", "pode mandar",
    "manda", "mandar", "envia", "enviar", "confirmado", "confirmo", "sim", "perfeito",
    "ta otimo", "esta otimo", "beleza", "fechado", "pode seguir", "ok pode enviar",
}


def e_aprovacao(texto: str) -> bool:
    """Reconhece as variações de 'ok' que liberam o envio ao cliente."""
    limpo = normalizar(texto)
    return bool(limpo) and limpo in _APROVACOES
