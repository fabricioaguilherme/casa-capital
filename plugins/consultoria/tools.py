"""Handlers das ferramentas do plugin de consultoria.

Cada handler segue o contrato do Hermes: ``handler(args: dict, **kwargs) -> str``,
sempre devolvendo uma string JSON e nunca levantando exceção.
"""

from __future__ import annotations

import json
import logging
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from . import (
    config,
    docs_utils,
    drive_utils,
    email_utils,
    gpt_summarizer,
    sheets_utils,
    state,
    texto_utils,
)

logger = logging.getLogger(__name__)

PALAVRA_SEBRAE = "sebrae"
PALAVRA_CONSULTORIA = "consultoria"


def _json(dados: Dict[str, Any]) -> str:
    return json.dumps(dados, ensure_ascii=False)


def _erro(mensagem: str, **extra: Any) -> str:
    dados = {"ok": False, "erro": mensagem}
    dados.update(extra)
    return _json(dados)


def _protegido(funcao):
    """Converte qualquer exceção em JSON de erro — o Hermes nunca deve estourar."""

    def dentro(args: Dict[str, Any], **kwargs: Any) -> str:
        try:
            return funcao(args or {}, **kwargs)
        except Exception as excecao:  # noqa: BLE001 — contrato do Hermes
            logger.error("consultoria.%s falhou: %s", funcao.__name__, excecao)
            logger.debug("%s", traceback.format_exc())
            return _erro(f"{type(excecao).__name__}: {excecao}")

    dentro.__name__ = funcao.__name__
    dentro.__doc__ = funcao.__doc__
    return dentro


def _normalizar_palavra(bruto: str) -> str:
    limpo = texto_utils.normalizar(bruto or "")
    if PALAVRA_SEBRAE in limpo:
        return PALAVRA_SEBRAE
    if PALAVRA_CONSULTORIA in limpo:
        return PALAVRA_CONSULTORIA
    return ""


def _checar_configuracao() -> Optional[str]:
    pendencias = config.obter().faltando()
    if pendencias:
        return _erro(
            "O plugin de consultoria ainda não está configurado.",
            faltando=pendencias,
            como_resolver=(
                "Preencha esses campos em ~/.hermes/plugins/consultoria/config.local.yaml "
                "(modelo em config.example.yaml) e peça de novo."
            ),
        )
    return None


def _localizar_transcricao(referencia: str, cliente: str) -> Tuple[Optional[Dict[str, Any]], str]:
    """Acha a transcrição: por ID/link informado, por cliente, ou a mais recente."""
    cfg = config.obter()
    if referencia:
        possivel_id = drive_utils.extrair_id(referencia)
        # Um ID do Drive não tem espaço nem ponto; se tiver, é nome de arquivo.
        if possivel_id and " " not in possivel_id and len(possivel_id) >= 20:
            try:
                return drive_utils.metadados(possivel_id), "arquivo informado"
            except Exception:
                logger.debug("referência %r não é um ID válido, tentando por nome", referencia)
        arquivo = drive_utils.transcricao_mais_recente(cfg.pasta_transcricoes_id, referencia)
        if arquivo:
            return arquivo, "arquivo pelo nome informado"

    if cliente:
        arquivo = drive_utils.transcricao_mais_recente(cfg.pasta_transcricoes_id, cliente)
        if arquivo:
            return arquivo, "transcrição mais recente do cliente"

    return drive_utils.transcricao_mais_recente(cfg.pasta_transcricoes_id), "transcrição mais recente da pasta"


def _pasta_do_cliente(cliente: sheets_utils.Cliente) -> Tuple[str, str]:
    """Pasta onde salvar os documentos; cria dentro da raiz se o cadastro não trouxer."""
    if cliente.pasta_drive:
        return drive_utils.extrair_id(cliente.pasta_drive), ""
    cfg = config.obter()
    if cfg.pasta_raiz_clientes_id:
        pasta = drive_utils.garantir_pasta(cliente.nome, cfg.pasta_raiz_clientes_id)
        return pasta, f"O cadastro de {cliente.nome} não tinha pasta; usei/criei uma na raiz de clientes."
    return "", (
        f"O cadastro de {cliente.nome} não tem pasta no Drive e não há pasta raiz configurada — "
        "os documentos foram criados na raiz do Drive da Service Account."
    )


def _valores_automaticos(nome_cliente: str, data_reuniao: str) -> Dict[str, str]:
    return {
        "CLIENTE": nome_cliente,
        "DATA_REUNIAO": data_reuniao,
        "DATA_HOJE": datetime.now().strftime("%d/%m/%Y"),
    }


def _nome_documento(modelo: str, nome_cliente: str) -> str:
    hoje = datetime.now().strftime("%Y-%m-%d")
    try:
        return modelo.format(cliente=nome_cliente, data=hoje)
    except (KeyError, IndexError, ValueError):
        return f"{nome_cliente} - Resumo - {hoje}"


def _produzir_documento(
    template: config.TemplateConfig,
    *,
    transcricao: str,
    nome_cliente: str,
    data_reuniao: str,
    pasta_id: str,
    estilo: str,
) -> Dict[str, Any]:
    """Gera + revisa o conteúdo e devolve o Google Doc preenchido."""
    areas = docs_utils.areas_do_template(template.doc_id)
    resumo = gpt_summarizer.gerar_resumo(
        transcricao,
        areas,
        cliente=nome_cliente,
        data_reuniao=data_reuniao,
        descricoes=template.areas,
        instrucoes_extra=template.instrucoes,
        estilo=estilo,
    )
    resumo = gpt_summarizer.revisar_resumo(resumo, transcricao, cliente=nome_cliente)

    valores = dict(resumo)
    valores.update(_valores_automaticos(nome_cliente, data_reuniao))
    documento = docs_utils.gerar_documento(
        template.doc_id, _nome_documento(template.nome_arquivo, nome_cliente), pasta_id, valores
    )
    documento["areas"] = areas
    documento["resumo"] = resumo
    return documento


@_protegido
def gerar_resumo(args: Dict[str, Any], **_kwargs: Any) -> str:
    """Passos 3 a 10 do fluxo: acha a transcrição, confere o cadastro, gera,
    revisa, preenche os templates e marca a planilha."""
    problema = _checar_configuracao()
    if problema:
        return problema

    cfg = config.obter()
    palavra = _normalizar_palavra(args.get("palavra_chave", ""))
    if not palavra:
        return _erro(
            "Não reconheci a palavra-chave. Use 'Sebrae' (gera os dois documentos) ou "
            "'Consultoria' (gera só o resumo detalhado)."
        )

    nome_informado = (args.get("cliente") or "").strip()
    arquivo, origem = _localizar_transcricao((args.get("arquivo") or "").strip(), nome_informado)
    if not arquivo:
        return _erro(
            "Não encontrei nenhuma transcrição na pasta do Drive.",
            pasta=cfg.pasta_transcricoes_id,
            dica="Confirme se o arquivo foi salvo na pasta de transcrições e se a Service Account tem acesso.",
        )

    # Passo 4: identifica o cliente pelo nome do arquivo e confere o cadastro.
    cliente = sheets_utils.encontrar_por_nome_de_arquivo(arquivo["name"])
    if cliente is None and nome_informado:
        cliente = sheets_utils.encontrar_por_nome(nome_informado)
    if cliente is None:
        return _erro(
            f"Não consegui identificar o cliente a partir do arquivo {arquivo['name']!r}.",
            dica=(
                "Confirme se o nome do cliente aparece no nome do arquivo e se ele está cadastrado "
                "na planilha, ou me diga o nome do cliente."
            ),
        )

    tipo_cadastrado = _normalizar_palavra(cliente.tipo)
    conflito = ""
    if tipo_cadastrado and tipo_cadastrado != palavra:
        conflito = (
            f"ATENÇÃO: você mandou '{palavra.capitalize()}', mas o cadastro de {cliente.nome} diz "
            f"'{cliente.tipo}'. Segui pela palavra-chave que você mandou — confira o cadastro depois."
        )
    elif not tipo_cadastrado and cliente.tipo:
        conflito = (
            f"A coluna Tipo de {cliente.nome} está preenchida com {cliente.tipo!r}, que não é nem "
            "'Sebrae' nem 'Consultoria'. Segui pela palavra-chave que você mandou."
        )
    elif not cliente.tipo:
        conflito = f"O cadastro de {cliente.nome} está sem a coluna Tipo preenchida — não deu para conferir."

    transcricao = drive_utils.ler_texto(arquivo)
    if not transcricao.strip():
        return _erro(f"A transcrição {arquivo['name']!r} está vazia ou não deu para ler o texto.")

    data_reuniao = drive_utils.data_da_reuniao(arquivo)
    pasta_id, aviso_pasta = _pasta_do_cliente(cliente)

    documentos: Dict[str, Any] = {}
    detalhado = _produzir_documento(
        cfg.template_detalhado,
        transcricao=transcricao,
        nome_cliente=cliente.nome,
        data_reuniao=data_reuniao,
        pasta_id=pasta_id,
        estilo="detalhado",
    )
    documentos["detalhado"] = detalhado

    avisos: List[str] = [a for a in (conflito, aviso_pasta) if a]

    # "Sebrae" gera também o documento curto (template do Sebrae).
    if palavra == PALAVRA_SEBRAE:
        if cfg.template_curto.doc_id:
            documentos["curto"] = _produzir_documento(
                cfg.template_curto,
                transcricao=transcricao,
                nome_cliente=cliente.nome,
                data_reuniao=data_reuniao,
                pasta_id=pasta_id,
                estilo="curto",
            )
        else:
            avisos.append(
                "O template curto (Sebrae) ainda não está configurado (templates.curto.doc_id), "
                "então gerei só o resumo detalhado."
            )

    # Passo 9: status na planilha.
    status = sheets_utils.marcar_resumo_gerado(cliente)
    if not status.get("ok"):
        avisos.append(f"Não consegui marcar 'Resumo Gerado' na planilha: {status.get('motivo')}")

    sobraram = docs_utils.marcadores_nao_preenchidos(detalhado["id"])
    if sobraram:
        avisos.append(
            "Sobraram marcadores sem conteúdo no documento detalhado: "
            + ", ".join("{{" + m + "}}" for m in sobraram)
        )

    state.salvar(
        {
            "cliente": cliente.nome,
            "email": cliente.email,
            "linha": cliente.linha,
            "pasta_id": pasta_id,
            "palavra_chave": palavra,
            "arquivo_transcricao": {"id": arquivo["id"], "name": arquivo["name"]},
            "transcricao": transcricao,
            "data_reuniao": data_reuniao,
            "template_detalhado_id": cfg.template_detalhado.doc_id,
            "doc_detalhado_id": detalhado["id"],
            "doc_detalhado_nome": detalhado["nome"],
            "doc_detalhado_link": detalhado["link"],
            "resumo_detalhado": detalhado["resumo"],
            "doc_curto_link": documentos.get("curto", {}).get("link", ""),
            "aprovado": False,
        }
    )

    resposta = {
        "ok": True,
        "cliente": cliente.nome,
        "palavra_chave": palavra,
        "tipo_no_cadastro": cliente.tipo,
        "transcricao_usada": arquivo["name"],
        "como_encontrei": origem,
        "data_reuniao": data_reuniao,
        "link_resumo_detalhado": detalhado["link"],
        "documentos_gerados": (
            ["detalhado", "curto"] if "curto" in documentos else ["detalhado"]
        ),
        "planilha_resumo_gerado": status.get("ok", False),
        "avisos": avisos,
        "proximo_passo": (
            "Mande o link do resumo detalhado para o consultor revisar e avise que ele pode "
            "responder 'ok' para enviar ao cliente, ou mandar o que quer corrigir."
        ),
    }
    if "curto" in documentos:
        resposta["link_resumo_curto"] = documentos["curto"]["link"]
    return _json(resposta)


@_protegido
def ajustar_resumo(args: Dict[str, Any], **_kwargs: Any) -> str:
    """Passo 11 (ramo de correção): aplica o feedback e regera o documento."""
    problema = _checar_configuracao()
    if problema:
        return problema

    feedback = (args.get("feedback") or "").strip()
    if not feedback:
        return _erro("Preciso do texto do que deve ser corrigido no resumo.")
    if texto_utils.e_aprovacao(feedback):
        return _erro(
            "Isso parece uma aprovação, não uma correção — use a ferramenta aprovar_e_enviar."
        )

    sessao = state.recuperar((args.get("cliente") or "").strip())
    if not sessao:
        return _erro(
            "Não tenho nenhum resumo em revisão para ajustar. Gere o resumo primeiro com a "
            "palavra-chave (Sebrae ou Consultoria)."
        )

    cfg = config.obter()
    nome_cliente = sessao["cliente"]
    resumo = gpt_summarizer.ajustar_resumo(
        sessao.get("resumo_detalhado", {}),
        feedback,
        sessao.get("transcricao", ""),
        cliente=nome_cliente,
    )

    # O documento anterior já teve os marcadores substituídos, então a versão
    # nova sai de uma cópia limpa do template; a antiga vai para a lixeira.
    valores = dict(resumo)
    valores.update(_valores_automaticos(nome_cliente, sessao.get("data_reuniao", "")))
    template_id = sessao.get("template_detalhado_id") or cfg.template_detalhado.doc_id
    documento = docs_utils.gerar_documento(
        template_id,
        sessao.get("doc_detalhado_nome") or _nome_documento(cfg.template_detalhado.nome_arquivo, nome_cliente),
        sessao.get("pasta_id", ""),
        valores,
    )

    avisos: List[str] = []
    antigo = sessao.get("doc_detalhado_id")
    if antigo and antigo != documento["id"]:
        try:
            drive_utils.mover_para_lixeira(antigo)
        except Exception as excecao:  # noqa: BLE001 — versão antiga na lixeira é acessório
            avisos.append(f"Não consegui descartar a versão anterior do documento: {excecao}")

    sessao.update(
        {
            "resumo_detalhado": resumo,
            "doc_detalhado_id": documento["id"],
            "doc_detalhado_link": documento["link"],
            "doc_detalhado_nome": documento["nome"],
            "aprovado": False,
        }
    )
    state.salvar(sessao)

    return _json(
        {
            "ok": True,
            "cliente": nome_cliente,
            "feedback_aplicado": feedback,
            "link_resumo_detalhado": documento["link"],
            "avisos": avisos,
            "proximo_passo": (
                "Mande o link atualizado para o consultor revisar de novo: ele responde 'ok' "
                "para enviar ao cliente, ou manda outra correção."
            ),
        }
    )


@_protegido
def aprovar_e_enviar(args: Dict[str, Any], **_kwargs: Any) -> str:
    """Passo 12: exporta o PDF, envia por e-mail ao cliente e marca a planilha."""
    problema = _checar_configuracao()
    if problema:
        return problema

    sessao = state.recuperar((args.get("cliente") or "").strip())
    if not sessao:
        return _erro(
            "Não tenho nenhum resumo aprovado para enviar. Gere o resumo primeiro com a "
            "palavra-chave (Sebrae ou Consultoria)."
        )

    nome_cliente = sessao["cliente"]
    destinatario = (sessao.get("email") or "").strip()
    if not destinatario:
        atual = sheets_utils.encontrar_por_nome(nome_cliente)
        destinatario = (atual.email if atual else "").strip()
    if not destinatario:
        return _erro(
            f"O cadastro de {nome_cliente} não tem e-mail preenchido — não dá para enviar o PDF."
        )

    doc_id = sessao.get("doc_detalhado_id")
    if not doc_id:
        return _erro("Perdi a referência do documento do resumo. Gere o resumo de novo.")

    pdf = drive_utils.exportar_pdf(doc_id)
    nome_pdf = f"{sessao.get('doc_detalhado_nome') or nome_cliente}.pdf"

    avisos: List[str] = []
    arquivo_pdf: Dict[str, str] = {}
    try:
        arquivo_pdf = drive_utils.salvar_pdf(pdf, nome_pdf, sessao.get("pasta_id", ""))
    except Exception as excecao:  # noqa: BLE001 — o e-mail é o que importa
        avisos.append(f"Não consegui salvar o PDF na pasta do cliente: {excecao}")

    envio = email_utils.enviar_resumo(destinatario, nome_cliente, pdf, nome_pdf)
    if not envio.get("ok"):
        return _erro(
            f"Não consegui enviar o e-mail para {destinatario}: {envio.get('erro')}",
            faltando=envio.get("faltando", []),
            pdf_salvo_no_drive=arquivo_pdf.get("link", ""),
        )

    cliente_planilha = sheets_utils.encontrar_por_nome(nome_cliente)
    status: Dict[str, Any] = {"ok": False, "motivo": "cliente não encontrado na planilha"}
    if cliente_planilha:
        status = sheets_utils.marcar_email_enviado(cliente_planilha)
    if not status.get("ok"):
        avisos.append(f"Não consegui marcar 'Email Enviado' na planilha: {status.get('motivo')}")

    sessao.update({"aprovado": True, "pdf_link": arquivo_pdf.get("link", "")})
    state.salvar(sessao)

    return _json(
        {
            "ok": True,
            "cliente": nome_cliente,
            "email_enviado_para": destinatario,
            "pdf": arquivo_pdf.get("link", ""),
            "planilha_email_enviado": status.get("ok", False),
            "avisos": avisos,
            "lembrete_para_o_consultor": (
                f"PDF enviado para {destinatario}. Lembre-se de avisar {nome_cliente} pelo "
                "WhatsApp que o resumo chegou por e-mail."
            ),
        }
    )


@_protegido
def status_consultoria(args: Dict[str, Any], **_kwargs: Any) -> str:
    """Diagnóstico: o que está configurado e qual resumo está em revisão."""
    cfg = config.obter()
    sessao = state.recuperar((args.get("cliente") or "").strip())
    return _json(
        {
            "ok": True,
            "configuracao_faltando": cfg.faltando(),
            "configuracao_envio_faltando": cfg.faltando_envio(),
            "consultor_nome": cfg.consultor_nome or "(não configurado — o GPT vai inferir pelo conteúdo)",
            "modelo_gpt": cfg.openai_model,
            "template_detalhado_configurado": bool(cfg.template_detalhado.doc_id),
            "template_curto_configurado": bool(cfg.template_curto.doc_id),
            "resumo_em_revisao": (
                {
                    "cliente": sessao.get("cliente"),
                    "link": sessao.get("doc_detalhado_link"),
                    "aprovado": sessao.get("aprovado", False),
                    "transcricao": (sessao.get("arquivo_transcricao") or {}).get("name", ""),
                }
                if sessao
                else None
            ),
        }
    )
