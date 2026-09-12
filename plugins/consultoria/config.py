"""Configuração do plugin de consultoria.

Este módulo NÃO contém segredos — ele apenas carrega o que estiver em:

1. variáveis de ambiente (prioridade máxima);
2. um arquivo YAML local, indicado por ``CONSULTORIA_CONFIG`` ou, por padrão,
   ``~/.hermes/plugins/consultoria/config.local.yaml``.

O arquivo YAML local é o lugar de guardar IDs, e-mails e senha de app; ele não
é versionado (ver ``config.example.yaml`` para o modelo).
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

try:  # PyYAML é opcional: sem ele, só variáveis de ambiente valem
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


CAMINHO_PADRAO = Path.home() / ".hermes" / "plugins" / "consultoria" / "config.local.yaml"

# Marcadores preenchidos pelo próprio plugin — nunca são pedidos ao GPT.
MARCADORES_AUTOMATICOS = ("CLIENTE", "DATA_REUNIAO", "DATA_HOJE")

# Nomes padrão das colunas da planilha de cadastro. Qualquer um pode ser
# trocado em ``planilha.colunas`` no YAML se a planilha usar outro rótulo.
COLUNAS_PADRAO = {
    "nome": "Nome",
    "pasta_drive": "Pasta Drive",
    "email": "Email",
    "tipo": "Tipo",
    "resumo_gerado": "Resumo Gerado",
    "email_enviado": "Email Enviado",
}

VALOR_RESUMO_GERADO = "OK"
VALOR_EMAIL_ENVIADO = "Enviado"

ESCOPOS_GOOGLE = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/spreadsheets",
]


def _por_caminho(dados: Dict[str, Any], caminho: str) -> Any:
    atual: Any = dados
    for parte in caminho.split("."):
        if not isinstance(atual, dict) or parte not in atual:
            return None
        atual = atual[parte]
    return atual


@dataclass
class TemplateConfig:
    """Um dos dois templates (curto/Sebrae ou detalhado/cliente)."""

    doc_id: str = ""
    # Nome do documento gerado; {cliente} e {data} são substituídos.
    nome_arquivo: str = "{cliente} - Resumo - {data}"
    # Descrição opcional de cada área, por marcador: {"DIAGNOSTICO": "o que ..."}.
    # Os marcadores em si são descobertos lendo o próprio template.
    areas: Dict[str, str] = field(default_factory=dict)
    # Instrução extra de estilo para este template (ex.: "seja sucinto, 3 linhas por área").
    instrucoes: str = ""


@dataclass
class Config:
    service_account_file: str = ""
    service_account_info: Optional[Dict[str, Any]] = None

    pasta_transcricoes_id: str = ""
    pasta_raiz_clientes_id: str = ""

    planilha_id: str = ""
    planilha_aba: str = ""
    colunas: Dict[str, str] = field(default_factory=lambda: dict(COLUNAS_PADRAO))

    template_curto: TemplateConfig = field(default_factory=TemplateConfig)
    template_detalhado: TemplateConfig = field(default_factory=TemplateConfig)

    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_model_revisor: str = ""

    consultor_nome: str = ""

    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    email_remetente: str = ""
    email_senha_app: str = ""
    email_nome_remetente: str = ""
    email_assunto: str = "Resumo da nossa consultoria - {cliente}"
    email_corpo: str = (
        "Olá!\n\nSegue em anexo o resumo da nossa reunião de consultoria.\n\n"
        "Qualquer dúvida, é só me chamar.\n\nAbraço."
    )

    @property
    def modelo_revisor(self) -> str:
        return self.openai_model_revisor or self.openai_model

    def faltando(self) -> List[str]:
        """Campos obrigatórios ainda não preenchidos — usado pelas ferramentas
        para avisar o consultor em vez de estourar um erro de API."""
        pendencias = []
        if not (self.service_account_file or self.service_account_info):
            pendencias.append("google.service_account_file (ou GOOGLE_SERVICE_ACCOUNT_JSON)")
        if not self.pasta_transcricoes_id:
            pendencias.append("drive.pasta_transcricoes_id")
        if not self.planilha_id:
            pendencias.append("planilha.id")
        if not self.template_detalhado.doc_id:
            pendencias.append("templates.detalhado.doc_id")
        if not self.openai_api_key:
            pendencias.append("openai.api_key (ou OPENAI_API_KEY)")
        return pendencias

    def faltando_envio(self) -> List[str]:
        pendencias = []
        if not self.email_remetente:
            pendencias.append("email.remetente")
        if not self.email_senha_app:
            pendencias.append("email.senha_app (senha de app do Gmail)")
        return pendencias


def _carregar_yaml() -> Dict[str, Any]:
    caminho = Path(os.getenv("CONSULTORIA_CONFIG") or CAMINHO_PADRAO)
    if not caminho.is_file() or yaml is None:
        return {}
    with caminho.open("r", encoding="utf-8") as arquivo:
        return yaml.safe_load(arquivo) or {}


def _template(dados: Dict[str, Any], chave: str, padrao_nome: str) -> TemplateConfig:
    bruto = _por_caminho(dados, f"templates.{chave}") or {}
    return TemplateConfig(
        doc_id=os.getenv(f"CONSULTORIA_TEMPLATE_{chave.upper()}_ID", "") or bruto.get("doc_id", ""),
        nome_arquivo=bruto.get("nome_arquivo", padrao_nome),
        areas=dict(bruto.get("areas") or {}),
        instrucoes=bruto.get("instrucoes", ""),
    )


def _service_account_info(dados: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    bruto = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "") or ""
    if not bruto:
        bruto_yaml = _por_caminho(dados, "google.service_account_json")
        if isinstance(bruto_yaml, dict):
            return bruto_yaml
        bruto = bruto_yaml or ""
    if not bruto:
        return None
    try:
        return json.loads(bruto)
    except (TypeError, json.JSONDecodeError):
        return None


def _construir() -> Config:
    dados = _carregar_yaml()

    colunas = dict(COLUNAS_PADRAO)
    colunas.update(_por_caminho(dados, "planilha.colunas") or {})

    porta = os.getenv("CONSULTORIA_SMTP_PORT") or _por_caminho(dados, "email.smtp_port") or 587
    try:
        porta = int(porta)
    except (TypeError, ValueError):
        porta = 587

    cfg = Config(
        service_account_file=(
            os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "")
            or _por_caminho(dados, "google.service_account_file")
            or ""
        ),
        service_account_info=_service_account_info(dados),
        pasta_transcricoes_id=(
            os.getenv("CONSULTORIA_PASTA_TRANSCRICOES", "")
            or _por_caminho(dados, "drive.pasta_transcricoes_id")
            or ""
        ),
        pasta_raiz_clientes_id=(
            os.getenv("CONSULTORIA_PASTA_CLIENTES", "")
            or _por_caminho(dados, "drive.pasta_raiz_clientes_id")
            or ""
        ),
        planilha_id=(
            os.getenv("CONSULTORIA_PLANILHA_ID", "") or _por_caminho(dados, "planilha.id") or ""
        ),
        planilha_aba=(
            os.getenv("CONSULTORIA_PLANILHA_ABA", "") or _por_caminho(dados, "planilha.aba") or ""
        ),
        colunas=colunas,
        template_curto=_template(dados, "curto", "{cliente} - Resumo Sebrae - {data}"),
        template_detalhado=_template(dados, "detalhado", "{cliente} - Resumo da Consultoria - {data}"),
        openai_api_key=(
            os.getenv("OPENAI_API_KEY", "") or _por_caminho(dados, "openai.api_key") or ""
        ),
        openai_model=(
            os.getenv("OPENAI_MODEL", "") or _por_caminho(dados, "openai.model") or "gpt-4o"
        ),
        openai_model_revisor=(
            os.getenv("OPENAI_MODEL_REVISOR", "") or _por_caminho(dados, "openai.model_revisor") or ""
        ),
        consultor_nome=(
            os.getenv("CONSULTORIA_CONSULTOR_NOME", "")
            or _por_caminho(dados, "consultor.nome")
            or ""
        ),
        smtp_host=(
            os.getenv("CONSULTORIA_SMTP_HOST", "")
            or _por_caminho(dados, "email.smtp_host")
            or "smtp.gmail.com"
        ),
        smtp_port=porta,
        email_remetente=(
            os.getenv("CONSULTORIA_EMAIL_REMETENTE", "")
            or _por_caminho(dados, "email.remetente")
            or ""
        ),
        email_senha_app=(
            os.getenv("CONSULTORIA_EMAIL_SENHA_APP", "")
            or _por_caminho(dados, "email.senha_app")
            or ""
        ),
        email_nome_remetente=(
            os.getenv("CONSULTORIA_EMAIL_NOME", "") or _por_caminho(dados, "email.nome") or ""
        ),
    )

    assunto = _por_caminho(dados, "email.assunto")
    if assunto:
        cfg.email_assunto = assunto
    corpo = _por_caminho(dados, "email.corpo")
    if corpo:
        cfg.email_corpo = corpo
    return cfg


_cache: Optional[Config] = None
_lock = threading.Lock()


def obter() -> Config:
    """Configuração carregada uma vez por processo."""
    global _cache
    if _cache is None:
        with _lock:
            if _cache is None:
                _cache = _construir()
    return _cache


def recarregar() -> Config:
    """Relê env/YAML — útil depois de editar o config.local.yaml."""
    global _cache
    with _lock:
        _cache = _construir()
    return _cache
