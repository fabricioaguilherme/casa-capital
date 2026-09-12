"""Google Drive: achar a transcrição, ler o texto, copiar templates, salvar PDF."""

from __future__ import annotations

import io
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from . import config, google_clients

MIME_PASTA = "application/vnd.google-apps.folder"
MIME_DOC = "application/vnd.google-apps.document"
MIME_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MIME_PDF = "application/pdf"

# Tipos de arquivo que aceitamos como transcrição.
MIMES_TRANSCRICAO = (MIME_DOC, MIME_DOCX, "text/plain", "text/markdown", "application/rtf")

_ID_EM_LINK = re.compile(r"/(?:folders|d)/([A-Za-z0-9_-]{10,})")


def extrair_id(referencia: str) -> str:
    """Aceita tanto o ID cru quanto o link completo do Drive/Docs."""
    if not referencia:
        return ""
    referencia = referencia.strip()
    achado = _ID_EM_LINK.search(referencia)
    if achado:
        return achado.group(1)
    if referencia.startswith("http"):
        achado = re.search(r"[?&]id=([A-Za-z0-9_-]{10,})", referencia)
        if achado:
            return achado.group(1)
    return referencia


def link_documento(doc_id: str) -> str:
    return f"https://docs.google.com/document/d/{doc_id}/edit"


def link_arquivo(file_id: str) -> str:
    return f"https://drive.google.com/file/d/{file_id}/view"


def listar_transcricoes(pasta_id: str, limite: int = 25) -> List[Dict[str, Any]]:
    """Arquivos da pasta de transcrições, do mais recente para o mais antigo."""
    consulta = f"'{pasta_id}' in parents and trashed = false and mimeType != '{MIME_PASTA}'"
    resposta = (
        google_clients.drive()
        .files()
        .list(
            q=consulta,
            orderBy="modifiedTime desc",
            pageSize=limite,
            fields="files(id, name, mimeType, modifiedTime, createdTime)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        .execute()
    )
    arquivos = resposta.get("files", [])
    return [a for a in arquivos if a.get("mimeType") in MIMES_TRANSCRICAO]


def transcricao_mais_recente(
    pasta_id: str = "", filtro_nome: str = ""
) -> Optional[Dict[str, Any]]:
    """A transcrição mais recente da pasta; com ``filtro_nome``, a mais recente
    cujo nome casa com aquele cliente."""
    from .texto_utils import pontuacao_match

    pasta_id = pasta_id or config.obter().pasta_transcricoes_id
    arquivos = listar_transcricoes(pasta_id)
    if not arquivos:
        return None
    if not filtro_nome:
        return arquivos[0]
    for arquivo in arquivos:  # já ordenados por data desc
        if pontuacao_match(filtro_nome, arquivo["name"]) >= 0.45:
            return arquivo
    return None


def metadados(file_id: str) -> Dict[str, Any]:
    return (
        google_clients.drive()
        .files()
        .get(
            fileId=file_id,
            fields="id, name, mimeType, modifiedTime, createdTime, parents",
            supportsAllDrives=True,
        )
        .execute()
    )


def _baixar(file_id: str) -> bytes:
    from googleapiclient.http import MediaIoBaseDownload

    pedido = google_clients.drive().files().get_media(fileId=file_id, supportsAllDrives=True)
    buffer = io.BytesIO()
    download = MediaIoBaseDownload(buffer, pedido)
    concluido = False
    while not concluido:
        _, concluido = download.next_chunk()
    return buffer.getvalue()


def _exportar(file_id: str, mime: str) -> bytes:
    from googleapiclient.http import MediaIoBaseDownload

    pedido = google_clients.drive().files().export_media(fileId=file_id, mimeType=mime)
    buffer = io.BytesIO()
    download = MediaIoBaseDownload(buffer, pedido)
    concluido = False
    while not concluido:
        _, concluido = download.next_chunk()
    return buffer.getvalue()


def _texto_de_docx(conteudo: bytes) -> str:
    """Extrai o texto de um .docx sem depender de biblioteca externa."""
    import xml.etree.ElementTree as ET
    import zipfile

    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with zipfile.ZipFile(io.BytesIO(conteudo)) as pacote:
        xml = pacote.read("word/document.xml")
    raiz = ET.fromstring(xml)
    paragrafos = []
    for paragrafo in raiz.iter(f"{{{ns['w']}}}p"):
        pedacos = [no.text or "" for no in paragrafo.iter(f"{{{ns['w']}}}t")]
        paragrafos.append("".join(pedacos))
    return "\n".join(paragrafos).strip()


def ler_texto(arquivo: Dict[str, Any]) -> str:
    """Texto da transcrição, seja ela Google Doc, .docx ou texto puro."""
    mime = arquivo.get("mimeType", "")
    file_id = arquivo["id"]
    if mime == MIME_DOC:
        return _exportar(file_id, "text/plain").decode("utf-8", errors="replace").strip()
    conteudo = _baixar(file_id)
    if mime == MIME_DOCX:
        return _texto_de_docx(conteudo)
    return conteudo.decode("utf-8", errors="replace").strip()


def copiar_template(template_id: str, nome: str, pasta_destino_id: str) -> str:
    """Duplica um template dentro da pasta do cliente e devolve o ID da cópia."""
    corpo: Dict[str, Any] = {"name": nome}
    if pasta_destino_id:
        corpo["parents"] = [pasta_destino_id]
    copia = (
        google_clients.drive()
        .files()
        .copy(fileId=template_id, body=corpo, fields="id", supportsAllDrives=True)
        .execute()
    )
    return copia["id"]


def exportar_pdf(doc_id: str) -> bytes:
    return _exportar(doc_id, MIME_PDF)


def salvar_pdf(conteudo: bytes, nome: str, pasta_destino_id: str) -> Dict[str, str]:
    """Sobe o PDF na pasta do cliente (substitui um de mesmo nome, se existir)."""
    from googleapiclient.http import MediaIoBaseUpload

    if not nome.lower().endswith(".pdf"):
        nome = f"{nome}.pdf"
    midia = MediaIoBaseUpload(io.BytesIO(conteudo), mimetype=MIME_PDF, resumable=False)
    drive = google_clients.drive()

    existente = _procurar_por_nome(nome, pasta_destino_id)
    if existente:
        arquivo = (
            drive.files()
            .update(fileId=existente, media_body=midia, fields="id, name", supportsAllDrives=True)
            .execute()
        )
    else:
        corpo: Dict[str, Any] = {"name": nome}
        if pasta_destino_id:
            corpo["parents"] = [pasta_destino_id]
        arquivo = (
            drive.files()
            .create(body=corpo, media_body=midia, fields="id, name", supportsAllDrives=True)
            .execute()
        )
    return {"id": arquivo["id"], "nome": arquivo.get("name", nome), "link": link_arquivo(arquivo["id"])}


def _procurar_por_nome(nome: str, pasta_id: str) -> str:
    if not pasta_id:
        return ""
    seguro = nome.replace("'", "\\'")
    resposta = (
        google_clients.drive()
        .files()
        .list(
            q=f"name = '{seguro}' and '{pasta_id}' in parents and trashed = false",
            pageSize=1,
            fields="files(id)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        .execute()
    )
    arquivos = resposta.get("files", [])
    return arquivos[0]["id"] if arquivos else ""


def mover_para_lixeira(file_id: str) -> None:
    """Descarta uma versão antiga do resumo sem apagar de vez."""
    google_clients.drive().files().update(
        fileId=file_id, body={"trashed": True}, supportsAllDrives=True
    ).execute()


def garantir_pasta(nome: str, pasta_pai_id: str) -> str:
    """Pasta do cliente dentro da raiz — usada quando o cadastro não traz uma."""
    seguro = nome.replace("'", "\\'")
    resposta = (
        google_clients.drive()
        .files()
        .list(
            q=(
                f"name = '{seguro}' and mimeType = '{MIME_PASTA}' "
                f"and '{pasta_pai_id}' in parents and trashed = false"
            ),
            pageSize=1,
            fields="files(id)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        .execute()
    )
    arquivos = resposta.get("files", [])
    if arquivos:
        return arquivos[0]["id"]
    pasta = (
        google_clients.drive()
        .files()
        .create(
            body={"name": nome, "mimeType": MIME_PASTA, "parents": [pasta_pai_id]},
            fields="id",
            supportsAllDrives=True,
        )
        .execute()
    )
    return pasta["id"]


def data_da_reuniao(arquivo: Dict[str, Any]) -> str:
    """Data da reunião: a que estiver no nome do arquivo; senão, a do arquivo."""
    nome = arquivo.get("name", "")
    achado = re.search(r"(20\d{2})[-_./](\d{1,2})[-_./](\d{1,2})", nome)
    if achado:
        ano, mes, dia = achado.groups()
        return f"{int(dia):02d}/{int(mes):02d}/{ano}"
    achado = re.search(r"(\d{1,2})[-_./](\d{1,2})[-_./](20\d{2})", nome)
    if achado:
        dia, mes, ano = achado.groups()
        return f"{int(dia):02d}/{int(mes):02d}/{ano}"
    bruto = arquivo.get("createdTime") or arquivo.get("modifiedTime") or ""
    if bruto:
        try:
            quando = datetime.fromisoformat(bruto.replace("Z", "+00:00"))
            return quando.astimezone(timezone.utc).strftime("%d/%m/%Y")
        except ValueError:
            pass
    return datetime.now().strftime("%d/%m/%Y")
