"""Envio do PDF ao cliente por SMTP do Gmail (senha de app)."""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr
from typing import Dict

from . import config


def _formatar(texto: str, cliente: str) -> str:
    try:
        return texto.format(cliente=cliente)
    except (KeyError, IndexError, ValueError):
        # Chave desconhecida no template do usuário não pode derrubar o envio.
        return texto


def enviar_resumo(
    destinatario: str, cliente: str, pdf: bytes, nome_arquivo: str
) -> Dict[str, object]:
    """Manda o PDF do resumo para o e-mail cadastrado do cliente."""
    cfg = config.obter()
    pendencias = cfg.faltando_envio()
    if pendencias:
        return {"ok": False, "erro": "configuração de e-mail incompleta", "faltando": pendencias}
    if not destinatario:
        return {"ok": False, "erro": "o cadastro do cliente não tem e-mail preenchido"}

    if not nome_arquivo.lower().endswith(".pdf"):
        nome_arquivo = f"{nome_arquivo}.pdf"

    mensagem = EmailMessage()
    mensagem["Subject"] = _formatar(cfg.email_assunto, cliente)
    mensagem["From"] = (
        formataddr((cfg.email_nome_remetente, cfg.email_remetente))
        if cfg.email_nome_remetente
        else cfg.email_remetente
    )
    mensagem["To"] = destinatario
    mensagem.set_content(_formatar(cfg.email_corpo, cliente))
    mensagem.add_attachment(
        pdf, maintype="application", subtype="pdf", filename=nome_arquivo
    )

    contexto = ssl.create_default_context()
    if cfg.smtp_port == 465:
        with smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_port, context=contexto, timeout=60) as smtp:
            smtp.login(cfg.email_remetente, cfg.email_senha_app)
            smtp.send_message(mensagem)
    else:
        with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=60) as smtp:
            smtp.ehlo()
            smtp.starttls(context=contexto)
            smtp.ehlo()
            smtp.login(cfg.email_remetente, cfg.email_senha_app)
            smtp.send_message(mensagem)

    return {"ok": True, "destinatario": destinatario, "anexo": nome_arquivo}
