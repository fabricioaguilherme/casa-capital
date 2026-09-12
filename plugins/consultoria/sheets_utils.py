"""Planilha de cadastro de clientes: leitura dos dados e escrita de status."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from . import config, google_clients
from .texto_utils import melhor_match, normalizar


@dataclass
class Cliente:
    nome: str
    linha: int  # 1-based, como a planilha mostra
    pasta_drive: str = ""
    email: str = ""
    tipo: str = ""
    resumo_gerado: str = ""
    email_enviado: str = ""
    bruto: Dict[str, str] = field(default_factory=dict)


def _aba() -> str:
    cfg = config.obter()
    if cfg.planilha_aba:
        return cfg.planilha_aba
    metadados = (
        google_clients.sheets()
        .spreadsheets()
        .get(spreadsheetId=cfg.planilha_id, fields="sheets.properties.title")
        .execute()
    )
    abas = metadados.get("sheets", [])
    if not abas:
        raise RuntimeError("A planilha de cadastro não tem nenhuma aba.")
    return abas[0]["properties"]["title"]


def _intervalo(aba: str) -> str:
    return f"'{aba}'!A1:ZZ"


def _ler_grade() -> Tuple[str, List[List[str]]]:
    cfg = config.obter()
    aba = _aba()
    resposta = (
        google_clients.sheets()
        .spreadsheets()
        .values()
        .get(spreadsheetId=cfg.planilha_id, range=_intervalo(aba))
        .execute()
    )
    return aba, resposta.get("values", [])


def _indice_colunas(cabecalho: List[str]) -> Dict[str, int]:
    """Mapeia cada coluna lógica para a posição dela na planilha, comparando os
    rótulos de forma tolerante (sem acento, sem caixa)."""
    cfg = config.obter()
    posicoes = {normalizar(rotulo): i for i, rotulo in enumerate(cabecalho)}
    indices: Dict[str, int] = {}
    for chave, rotulo in cfg.colunas.items():
        posicao = posicoes.get(normalizar(rotulo))
        if posicao is not None:
            indices[chave] = posicao
    return indices


def _celula(linha: List[str], indice: Optional[int]) -> str:
    if indice is None or indice >= len(linha):
        return ""
    return (linha[indice] or "").strip()


def listar_clientes() -> List[Cliente]:
    aba, grade = _ler_grade()
    if not grade:
        return []
    cabecalho = grade[0]
    indices = _indice_colunas(cabecalho)
    if "nome" not in indices:
        raise RuntimeError(
            f"A planilha não tem a coluna de nome ({config.obter().colunas['nome']!r}). "
            "Ajuste planilha.colunas no config.local.yaml."
        )

    clientes: List[Cliente] = []
    for deslocamento, linha in enumerate(grade[1:], start=2):
        nome = _celula(linha, indices.get("nome"))
        if not nome:
            continue
        clientes.append(
            Cliente(
                nome=nome,
                linha=deslocamento,
                pasta_drive=_celula(linha, indices.get("pasta_drive")),
                email=_celula(linha, indices.get("email")),
                tipo=_celula(linha, indices.get("tipo")),
                resumo_gerado=_celula(linha, indices.get("resumo_gerado")),
                email_enviado=_celula(linha, indices.get("email_enviado")),
                bruto={
                    rotulo: _celula(linha, i)
                    for i, rotulo in enumerate(cabecalho)
                    if rotulo
                },
            )
        )
    return clientes


def encontrar_por_nome_de_arquivo(nome_arquivo: str) -> Optional[Cliente]:
    """Identifica o cliente pelo nome do arquivo da transcrição (match parcial)."""
    clientes = listar_clientes()
    escolhido = melhor_match(nome_arquivo, [(c.nome, c) for c in clientes])
    return escolhido[1] if escolhido else None


def encontrar_por_nome(nome: str) -> Optional[Cliente]:
    """Busca pelo nome informado no Telegram (também tolerante a nome parcial)."""
    clientes = listar_clientes()
    alvo = normalizar(nome)
    for cliente in clientes:
        if normalizar(cliente.nome) == alvo:
            return cliente
    escolhido = melhor_match(nome, [(c.nome, c) for c in clientes])
    if escolhido:
        return escolhido[1]
    for cliente in clientes:
        if alvo and alvo in normalizar(cliente.nome):
            return cliente
    return None


def _letra_coluna(indice: int) -> str:
    """0 -> A, 26 -> AA."""
    letras = ""
    indice += 1
    while indice:
        indice, resto = divmod(indice - 1, 26)
        letras = chr(65 + resto) + letras
    return letras


def escrever_status(cliente: Cliente, coluna_logica: str, valor: str) -> Dict[str, Any]:
    """Escreve na coluna de status, achando a linha pelo nome do cliente."""
    cfg = config.obter()
    aba, grade = _ler_grade()
    if not grade:
        return {"ok": False, "motivo": "planilha vazia"}

    indices = _indice_colunas(grade[0])
    indice = indices.get(coluna_logica)
    rotulo = cfg.colunas.get(coluna_logica, coluna_logica)
    if indice is None:
        return {
            "ok": False,
            "motivo": f"a planilha não tem a coluna {rotulo!r} — crie a coluna ou ajuste planilha.colunas",
        }

    # Reconfirma a linha pelo nome: a planilha pode ter mudado desde a leitura.
    linha = cliente.linha
    indice_nome = indices.get("nome")
    if indice_nome is not None:
        alvo = normalizar(cliente.nome)
        for numero, valores in enumerate(grade[1:], start=2):
            if normalizar(_celula(valores, indice_nome)) == alvo:
                linha = numero
                break

    celula = f"'{aba}'!{_letra_coluna(indice)}{linha}"
    google_clients.sheets().spreadsheets().values().update(
        spreadsheetId=cfg.planilha_id,
        range=celula,
        valueInputOption="USER_ENTERED",
        body={"values": [[valor]]},
    ).execute()
    return {"ok": True, "celula": celula, "valor": valor}


def marcar_resumo_gerado(cliente: Cliente) -> Dict[str, Any]:
    return escrever_status(cliente, "resumo_gerado", config.VALOR_RESUMO_GERADO)


def marcar_email_enviado(cliente: Cliente) -> Dict[str, Any]:
    return escrever_status(cliente, "email_enviado", config.VALOR_EMAIL_ENVIADO)
