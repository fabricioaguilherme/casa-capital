"""Geração, revisão e ajuste dos resumos com a OpenAI (GPT)."""

from __future__ import annotations

import json
import threading
from typing import Dict, List, Optional

from . import config

# Transcrições muito longas são cortadas pelo meio, preservando começo e fim
# (abertura da reunião e encaminhamentos finais são as partes mais densas).
LIMITE_CARACTERES = 120_000

_lock = threading.Lock()
_cliente = None


def _openai():
    global _cliente
    if _cliente is None:
        with _lock:
            if _cliente is None:
                from openai import OpenAI

                cfg = config.obter()
                if not cfg.openai_api_key:
                    raise RuntimeError(
                        "OPENAI_API_KEY não configurada — preencha openai.api_key no "
                        "config.local.yaml ou exporte OPENAI_API_KEY."
                    )
                _cliente = OpenAI(api_key=cfg.openai_api_key)
    return _cliente


def _encurtar(transcricao: str) -> str:
    if len(transcricao) <= LIMITE_CARACTERES:
        return transcricao
    metade = LIMITE_CARACTERES // 2
    return (
        transcricao[:metade]
        + "\n\n[... trecho do meio da transcrição omitido por tamanho ...]\n\n"
        + transcricao[-metade:]
    )


def _instrucao_de_falantes() -> str:
    nome = config.obter().consultor_nome.strip()
    if nome:
        identificacao = (
            f"O consultor é {nome}. Se a transcrição trouxer rótulos de quem fala, todas as "
            f"falas atribuídas a {nome} (ou a variações desse nome) são do consultor, e todas "
            "as demais são do cliente ou de um segundo participante."
        )
    else:
        identificacao = (
            "A transcrição pode ou não trazer rótulos de quem fala, e o nome do consultor "
            "pode não estar configurado."
        )
    return (
        f"{identificacao} Se não houver separação confiável de falantes, infira pelo conteúdo: "
        "quem faz perguntas de diagnóstico, conduz a conversa e dá orientação estratégica é o "
        "CONSULTOR; quem descreve a operação do negócio, relata números e problemas e recebe as "
        "orientações é o CLIENTE. Um segundo consultor eventualmente presente também conduz e "
        "orienta — trate-o como consultor, não como cliente. O resumo é sobre o negócio do "
        "cliente e sobre as orientações dadas; nunca narre a reunião como diálogo."
    )


def _descricao_das_areas(areas: List[str], descricoes: Dict[str, str]) -> str:
    linhas = []
    for area in areas:
        detalhe = (descricoes or {}).get(area, "").strip()
        linhas.append(f'- "{area}"{": " + detalhe if detalhe else ""}')
    return "\n".join(linhas)


def _chamar_json(mensagens: List[Dict[str, str]], modelo: str) -> Dict[str, str]:
    resposta = _openai().chat.completions.create(
        model=modelo,
        messages=mensagens,
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    conteudo = resposta.choices[0].message.content or "{}"
    dados = json.loads(conteudo)
    if not isinstance(dados, dict):
        raise ValueError("A resposta do GPT não veio como objeto JSON.")
    return {str(k).strip().upper(): ("" if v is None else str(v)).strip() for k, v in dados.items()}


def _normalizar_saida(bruto: Dict[str, str], areas: List[str]) -> Dict[str, str]:
    """Garante uma chave para cada área do template, na ordem do template."""
    return {area: bruto.get(area, "").strip() for area in areas}


def gerar_resumo(
    transcricao: str,
    areas: List[str],
    *,
    cliente: str = "",
    data_reuniao: str = "",
    descricoes: Optional[Dict[str, str]] = None,
    instrucoes_extra: str = "",
    estilo: str = "detalhado",
) -> Dict[str, str]:
    """Escreve o conteúdo de cada área do template a partir da transcrição."""
    if not areas:
        raise ValueError(
            "O template não tem nenhum marcador {{AREA}}. Escreva os marcadores no Google Doc "
            "do template (ex.: {{DIAGNOSTICO}}) para o agente saber quais áreas preencher."
        )

    if estilo == "curto":
        tamanho = (
            "Cada área deve ter de 2 a 5 linhas, objetivas, em tópicos curtos quando fizer sentido."
        )
    else:
        tamanho = (
            "Cada área deve ser desenvolvida: 1 a 3 parágrafos (ou uma lista de itens quando a "
            "área pedir), com o detalhe necessário para o cliente reler daqui a um mês e entender."
        )

    sistema = (
        "Você é um consultor empresarial sênior escrevendo o resumo de uma reunião de "
        "consultoria a partir da transcrição. Escreva em português do Brasil, em tom "
        "profissional, direto e respeitoso, na terceira pessoa ou em voz institucional.\n\n"
        f"{_instrucao_de_falantes()}\n\n"
        "REGRAS INEGOCIÁVEIS:\n"
        "- Use exclusivamente o que está na transcrição. Nunca invente números, nomes, prazos, "
        "diagnósticos ou recomendações que não tenham sido ditos.\n"
        "- Se uma área do template não tiver respaldo na transcrição, escreva exatamente: "
        "'Não abordado nesta reunião.'\n"
        "- Não escreva marcadores como {{AREA}} no texto, não repita o título da área dentro do "
        "conteúdo e não use formatação markdown de título.\n"
        f"- {tamanho}"
    )

    usuario = (
        f"Cliente: {cliente or 'não informado'}\n"
        f"Data da reunião: {data_reuniao or 'não informada'}\n\n"
        "Preencha as áreas abaixo. Responda em JSON, com uma chave por área, exatamente com "
        "estes nomes de chave, e o valor sendo o texto pronto para ser colado no documento:\n"
        f"{_descricao_das_areas(areas, descricoes or {})}\n"
        f"{instrucoes_extra}\n\n"
        "TRANSCRIÇÃO:\n"
        f"{_encurtar(transcricao)}"
    )

    bruto = _chamar_json(
        [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
        config.obter().openai_model,
    )
    return _normalizar_saida(bruto, areas)


def revisar_resumo(
    resumo: Dict[str, str], transcricao: str, *, cliente: str = ""
) -> Dict[str, str]:
    """Segunda passada de IA: gramática, clareza, tom e coerência entre as áreas."""
    areas = list(resumo.keys())
    sistema = (
        "Você é um revisor editorial de documentos de consultoria. Recebe um resumo já escrito "
        "e a transcrição que o originou. Sua função é corrigir gramática, ortografia e "
        "pontuação, melhorar a clareza e o tom profissional, e garantir coerência entre as "
        "áreas (sem contradições e sem repetir a mesma informação em áreas diferentes).\n\n"
        "REGRAS INEGOCIÁVEIS:\n"
        "- Não acrescente nenhuma informação que não esteja na transcrição.\n"
        "- Não remova informação correta que já esteja no resumo.\n"
        "- Mantenha exatamente as mesmas chaves de área que recebeu.\n"
        "- Preserve 'Não abordado nesta reunião.' onde já estiver."
    )
    usuario = (
        f"Cliente: {cliente or 'não informado'}\n\n"
        "RESUMO A REVISAR (JSON):\n"
        f"{json.dumps(resumo, ensure_ascii=False, indent=2)}\n\n"
        "TRANSCRIÇÃO DE REFERÊNCIA (use apenas para conferir fatos):\n"
        f"{_encurtar(transcricao)}\n\n"
        "Responda o JSON revisado, com as mesmas chaves."
    )
    bruto = _chamar_json(
        [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
        config.obter().modelo_revisor,
    )
    revisado = _normalizar_saida(bruto, areas)
    # Se o revisor esvaziar uma área, mantém a versão anterior.
    return {area: (revisado.get(area) or resumo.get(area, "")) for area in areas}


def ajustar_resumo(
    resumo: Dict[str, str], feedback: str, transcricao: str, *, cliente: str = ""
) -> Dict[str, str]:
    """Reescreve o resumo aplicando o feedback do consultor."""
    areas = list(resumo.keys())
    sistema = (
        "Você é o revisor de um documento de consultoria. Recebe o resumo atual, a transcrição "
        "original e um pedido de correção feito pelo próprio consultor que conduziu a reunião. "
        "Aplique o pedido fielmente.\n\n"
        "REGRAS INEGOCIÁVEIS:\n"
        "- O pedido do consultor manda: se ele corrigir um fato, a correção dele vale sobre a "
        "transcrição.\n"
        "- Fora o que o pedido determina, não invente informação que não esteja na transcrição.\n"
        "- Altere apenas as áreas afetadas pelo pedido; devolva as demais exatamente como estão.\n"
        "- Mantenha exatamente as mesmas chaves de área que recebeu."
    )
    usuario = (
        f"Cliente: {cliente or 'não informado'}\n\n"
        "PEDIDO DO CONSULTOR:\n"
        f"{feedback.strip()}\n\n"
        "RESUMO ATUAL (JSON):\n"
        f"{json.dumps(resumo, ensure_ascii=False, indent=2)}\n\n"
        "TRANSCRIÇÃO DE REFERÊNCIA:\n"
        f"{_encurtar(transcricao)}\n\n"
        "Responda o JSON ajustado, com as mesmas chaves."
    )
    bruto = _chamar_json(
        [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
        config.obter().modelo_revisor,
    )
    ajustado = _normalizar_saida(bruto, areas)
    return {area: (ajustado.get(area) or resumo.get(area, "")) for area in areas}
