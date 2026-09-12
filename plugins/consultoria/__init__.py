"""Plugin Hermes: resumos de reuniões de consultoria.

Registra três ferramentas que cobrem o fluxo inteiro — gerar os resumos a
partir da transcrição no Drive, ajustar conforme o feedback do consultor no
Telegram e, na aprovação, mandar o PDF por e-mail ao cliente.
"""

from __future__ import annotations

import logging

from . import schemas, state, tools

logger = logging.getLogger(__name__)

TOOLSET = "consultoria"

_FERRAMENTAS = (
    (schemas.GERAR_RESUMO, tools.gerar_resumo, "Gera os resumos da reunião", "📝"),
    (schemas.AJUSTAR_RESUMO, tools.ajustar_resumo, "Ajusta o resumo com o feedback", "✏️"),
    (schemas.APROVAR_E_ENVIAR, tools.aprovar_e_enviar, "Envia o PDF ao cliente", "📨"),
    (schemas.STATUS_CONSULTORIA, tools.status_consultoria, "Estado do plugin de consultoria", "🔎"),
)


def _registrar_log(ctx) -> None:
    """Hook opcional: deixa no log qual ferramenta rodou e se deu certo."""

    def depois(tool_name: str = "", result=None, **_kwargs):
        if tool_name in {esquema["name"] for esquema, *_ in _FERRAMENTAS}:
            sucesso = isinstance(result, str) and '"ok": true' in result.lower()
            logger.info("consultoria: %s -> %s", tool_name, "ok" if sucesso else "erro")
        return None

    try:
        ctx.register_hook("post_tool_call", depois)
    except Exception as excecao:  # noqa: BLE001 — log é acessório, nunca derruba o plugin
        logger.debug("consultoria: hook de log não registrado (%s)", excecao)


def register(ctx) -> None:
    """Ponto de entrada chamado pelo Hermes ao carregar o plugin."""
    try:
        state.usar_estado_do_hermes(ctx.state)
    except Exception as excecao:  # noqa: BLE001 — cai no arquivo local
        logger.debug("consultoria: ctx.state indisponível, usando arquivo local (%s)", excecao)

    for esquema, handler, descricao, emoji in _FERRAMENTAS:
        ctx.register_tool(
            name=esquema["name"],
            toolset=TOOLSET,
            schema=esquema,
            handler=handler,
            description=descricao,
            emoji=emoji,
        )

    _registrar_log(ctx)
    logger.info("consultoria: %d ferramentas registradas", len(_FERRAMENTAS))
