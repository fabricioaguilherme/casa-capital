"""Google Docs: descobrir os marcadores do template e preencher as cópias."""

from __future__ import annotations

import re
from typing import Dict, List

from . import config, drive_utils, google_clients

MARCADOR = re.compile(r"\{\{\s*([A-Za-z0-9_ÀÁÂÃÉÊÍÓÔÕÚÇ_-]+?)\s*\}\}")


def texto_do_documento(doc_id: str) -> str:
    """Texto corrido do documento, incluindo tabelas e cabeçalhos."""
    documento = google_clients.docs().documents().get(documentId=doc_id).execute()
    pedacos: List[str] = []

    def caminhar(elementos) -> None:
        for elemento in elementos or []:
            if "paragraph" in elemento:
                for item in elemento["paragraph"].get("elements", []):
                    conteudo = item.get("textRun", {}).get("content")
                    if conteudo:
                        pedacos.append(conteudo)
            elif "table" in elemento:
                for linha in elemento["table"].get("tableRows", []):
                    for celula in linha.get("tableCells", []):
                        caminhar(celula.get("content"))
            elif "tableOfContents" in elemento:
                caminhar(elemento["tableOfContents"].get("content"))

    caminhar(documento.get("body", {}).get("content"))
    for secao in list(documento.get("headers", {}).values()) + list(
        documento.get("footers", {}).values()
    ):
        caminhar(secao.get("content"))
    return "".join(pedacos)


def descobrir_marcadores(doc_id: str) -> List[str]:
    """Lê o template e devolve os marcadores ``{{AREA}}`` na ordem em que aparecem.

    É assim que o plugin aprende as áreas do template sem elas estarem
    escritas no código: basta escrever os marcadores no Google Doc.
    """
    vistos: List[str] = []
    for achado in MARCADOR.finditer(texto_do_documento(doc_id)):
        marcador = achado.group(1).strip().upper()
        if marcador not in vistos:
            vistos.append(marcador)
    return vistos


def areas_do_template(doc_id: str) -> List[str]:
    """Só as áreas que o GPT precisa escrever (sem CLIENTE/DATA_*)."""
    automaticos = set(config.MARCADORES_AUTOMATICOS)
    return [m for m in descobrir_marcadores(doc_id) if m not in automaticos]


def preencher(doc_id: str, valores: Dict[str, str]) -> int:
    """Substitui ``{{CHAVE}}`` pelo texto correspondente. Devolve quantas
    substituições foram enviadas."""
    pedidos = []
    for chave, valor in valores.items():
        pedidos.append(
            {
                "replaceAllText": {
                    "containsText": {"text": "{{" + chave + "}}", "matchCase": False},
                    "replaceText": valor or "",
                }
            }
        )
        # Tolera o marcador escrito com espaços: {{ CHAVE }}
        pedidos.append(
            {
                "replaceAllText": {
                    "containsText": {"text": "{{ " + chave + " }}", "matchCase": False},
                    "replaceText": valor or "",
                }
            }
        )
    if not pedidos:
        return 0
    google_clients.docs().documents().batchUpdate(
        documentId=doc_id, body={"requests": pedidos}
    ).execute()
    return len(pedidos)


def gerar_documento(
    template_id: str, nome: str, pasta_destino_id: str, valores: Dict[str, str]
) -> Dict[str, str]:
    """Copia o template, preenche os marcadores e devolve id/nome/link."""
    copia_id = drive_utils.copiar_template(template_id, nome, pasta_destino_id)
    preencher(copia_id, valores)
    return {"id": copia_id, "nome": nome, "link": drive_utils.link_documento(copia_id)}


def marcadores_nao_preenchidos(doc_id: str) -> List[str]:
    """Marcadores que sobraram no documento gerado — sinal de área sem conteúdo."""
    return descobrir_marcadores(doc_id)
