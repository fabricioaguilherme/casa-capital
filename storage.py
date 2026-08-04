"""Camada de armazenamento de arquivos.

Regra de ouro: o arquivo NUNCA vai para dentro do banco — só a ficha dele.
O banco guarda nome, chave, tamanho e hash; o binário mora aqui.

Trocar de local para nuvem (S3, Cloudflare R2, Supabase Storage) no futuro
significa escrever uma classe nova com os mesmos 5 métodos e mudar
BACKEND_PADRAO. Nada mais no aplicativo precisa saber onde o arquivo está.
"""

import hashlib
import os
import re
import unicodedata
import uuid
from datetime import date

BASE = os.path.dirname(os.path.abspath(__file__))
PASTA_ANEXOS = os.path.join(BASE, "anexos")


def disco_efemero():
    """True quando o disco é apagado a cada reinício (Streamlit Community Cloud).

    Lá o app roda a partir de /mount/src e hiberna após 12h sem uso; ao acordar,
    a pasta de anexos volta vazia. As fichas continuam no banco e a tela mostra
    "Arquivo ausente" — o dado não corrompe, mas o arquivo se perde. Enquanto
    não houver um bucket de verdade (ver esqueleto de ArmazenamentoS3 no fim
    deste arquivo), a tela de anexos avisa antes de o usuário confiar no upload.
    """
    return BASE.startswith("/mount/src")

TAMANHO_MAX_MB = 15
EXTENSOES_PERMITIDAS = {
    # imagens (foto de recibo, canhoto, comprovante)
    ".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif",
    # documentos
    ".pdf", ".txt", ".csv", ".xlsx", ".xls", ".docx", ".doc", ".ofx",
}
EXTENSOES_IMAGEM = {".jpg", ".jpeg", ".png", ".webp"}

BACKEND_PADRAO = "local"


class ArquivoRecusado(Exception):
    """Arquivo não passou na validação (extensão, tamanho ou vazio)."""


def _slug(texto, limite=60):
    """Nome legível e seguro: sem acento, sem caractere especial, sem barra."""
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    texto = re.sub(r"[^A-Za-z0-9._-]+", "-", texto).strip("-.")
    return (texto[:limite] or "arquivo").lower()


def validar(nome_original, dados):
    """Levanta ArquivoRecusado se o arquivo não puder ser guardado."""
    if not dados:
        raise ArquivoRecusado("Arquivo vazio.")

    tamanho_mb = len(dados) / (1024 * 1024)
    if tamanho_mb > TAMANHO_MAX_MB:
        raise ArquivoRecusado(
            f"Arquivo de {tamanho_mb:.1f} MB excede o limite de {TAMANHO_MAX_MB} MB."
        )

    ext = os.path.splitext(nome_original)[1].lower()
    if ext not in EXTENSOES_PERMITIDAS:
        permitidas = ", ".join(sorted(e.lstrip(".") for e in EXTENSOES_PERMITIDAS))
        rotulo = ext or "sem extensão"
        raise ArquivoRecusado(f"Tipo '{rotulo}' não aceito. Permitidos: {permitidas}.")

    return ext


def hash_conteudo(dados):
    return hashlib.sha256(dados).hexdigest()


class ArmazenamentoLocal:
    """Guarda os arquivos em disco, organizados por ano/mês."""

    nome = "local"

    def __init__(self, raiz=PASTA_ANEXOS):
        self.raiz = raiz

    def gerar_chave(self, nome_original):
        """Chave = ano/mes/uuid-nome-seguro.ext — sem colisão e sem path traversal."""
        ext = os.path.splitext(nome_original)[1].lower()
        base = _slug(os.path.splitext(os.path.basename(nome_original))[0])
        hoje = date.today()
        return f"{hoje:%Y/%m}/{uuid.uuid4().hex[:12]}-{base}{ext}"

    def _caminho(self, chave):
        # normaliza e garante que a chave não escapa da pasta raiz
        destino = os.path.normpath(os.path.join(self.raiz, chave))
        if not destino.startswith(os.path.normpath(self.raiz) + os.sep):
            raise ArquivoRecusado("Caminho de arquivo inválido.")
        return destino

    def salvar(self, dados, nome_original):
        chave = self.gerar_chave(nome_original)
        destino = self._caminho(chave)
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        with open(destino, "wb") as f:
            f.write(dados)
        return chave

    def ler(self, chave):
        destino = self._caminho(chave)
        if not os.path.exists(destino):
            return None
        with open(destino, "rb") as f:
            return f.read()

    def excluir(self, chave):
        destino = self._caminho(chave)
        if os.path.exists(destino):
            os.remove(destino)
            return True
        return False

    def existe(self, chave):
        return os.path.exists(self._caminho(chave))


# ── Futuro: implementar a mesma interface para nuvem ─────────────────────
# class ArmazenamentoS3:
#     nome = "s3"
#     def gerar_chave(self, nome_original): ...
#     def salvar(self, dados, nome_original): ...   # put_object
#     def ler(self, chave): ...                      # get_object
#     def excluir(self, chave): ...                  # delete_object
#     def existe(self, chave): ...
#     def url_assinada(self, chave, segundos=300): ...

_BACKENDS = {"local": ArmazenamentoLocal()}


def obter(nome=None):
    """Devolve o backend de armazenamento (padrão: local)."""
    return _BACKENDS[nome or BACKEND_PADRAO]


def e_imagem(nome_original):
    return os.path.splitext(nome_original)[1].lower() in EXTENSOES_IMAGEM


def tamanho_legivel(bytes_):
    if bytes_ < 1024:
        return f"{bytes_} B"
    if bytes_ < 1024 * 1024:
        return f"{bytes_ / 1024:.0f} KB"
    return f"{bytes_ / (1024 * 1024):.1f} MB"
