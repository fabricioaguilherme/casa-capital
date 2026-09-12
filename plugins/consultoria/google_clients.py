"""Clientes autenticados das APIs do Google (Service Account)."""

from __future__ import annotations

import threading
from typing import Any

from . import config

_lock = threading.Lock()
_servicos: dict[str, Any] = {}


def _credenciais():
    from google.oauth2 import service_account

    cfg = config.obter()
    if cfg.service_account_info:
        return service_account.Credentials.from_service_account_info(
            cfg.service_account_info, scopes=config.ESCOPOS_GOOGLE
        )
    if cfg.service_account_file:
        return service_account.Credentials.from_service_account_file(
            cfg.service_account_file, scopes=config.ESCOPOS_GOOGLE
        )
    raise RuntimeError(
        "Service Account do Google não configurada — preencha google.service_account_file "
        "no config.local.yaml ou GOOGLE_SERVICE_ACCOUNT_JSON no ambiente."
    )


def _servico(nome: str, versao: str):
    chave = f"{nome}:{versao}"
    servico = _servicos.get(chave)
    if servico is None:
        with _lock:
            servico = _servicos.get(chave)
            if servico is None:
                from googleapiclient.discovery import build

                servico = build(nome, versao, credentials=_credenciais(), cache_discovery=False)
                _servicos[chave] = servico
    return servico


def drive():
    return _servico("drive", "v3")


def docs():
    return _servico("docs", "v1")


def sheets():
    return _servico("sheets", "v4")


def limpar_cache() -> None:
    with _lock:
        _servicos.clear()
