"""Descrições das ferramentas que o modelo do Hermes lê para decidir quando chamar."""

from __future__ import annotations

GERAR_RESUMO = {
    "name": "gerar_resumo",
    "description": (
        "Gera o(s) resumo(s) de uma reunião de consultoria a partir da transcrição mais recente "
        "no Google Drive. CHAME esta ferramenta quando o consultor mandar apenas a palavra-chave "
        "'Sebrae' ou 'Consultoria' (sozinha ou em uma frase curta), sem precisar de mais nenhum "
        "dado: a ferramenta acha sozinha a transcrição mais recente, identifica o cliente pelo "
        "nome do arquivo, confere o cadastro na planilha e preenche os templates.\n"
        "- 'Sebrae' gera DOIS documentos (resumo curto do template Sebrae + resumo detalhado do cliente).\n"
        "- 'Consultoria' gera APENAS o resumo detalhado do cliente.\n"
        "Depois de executar, mostre ao consultor o link do resumo detalhado, repasse os avisos "
        "(principalmente conflito entre a palavra-chave e a coluna Tipo do cadastro) e diga que "
        "ele pode responder 'ok' para enviar ao cliente ou mandar o que quer corrigir."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "palavra_chave": {
                "type": "string",
                "enum": ["Sebrae", "Consultoria"],
                "description": (
                    "A palavra-chave que o consultor mandou. 'Sebrae' = gera os dois documentos; "
                    "'Consultoria' = gera só o resumo detalhado."
                ),
            },
            "cliente": {
                "type": "string",
                "description": (
                    "Opcional. Nome do cliente, só quando o consultor citar um cliente específico. "
                    "Sem isso, a ferramenta usa a transcrição mais recente da pasta."
                ),
            },
            "arquivo": {
                "type": "string",
                "description": (
                    "Opcional. Nome, ID ou link da transcrição no Drive, quando o consultor "
                    "apontar um arquivo específico em vez do mais recente."
                ),
            },
        },
        "required": ["palavra_chave"],
    },
}

AJUSTAR_RESUMO = {
    "name": "ajustar_resumo",
    "description": (
        "Aplica uma correção do consultor no resumo detalhado que está em revisão e devolve o "
        "link atualizado do Google Doc. CHAME esta ferramenta quando, DEPOIS de ter mandado o "
        "link de um resumo para revisão, o consultor responder com qualquer texto que não seja "
        "uma aprovação — por exemplo 'tira a parte do financeiro', 'o faturamento é 80 mil, não "
        "60', 'ficou muito longo'. Passe o texto dele inteiro em 'feedback'. Depois de executar, "
        "mande o link atualizado e diga que ele pode aprovar com 'ok' ou pedir outra correção."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "feedback": {
                "type": "string",
                "description": "O pedido de correção do consultor, com as palavras dele.",
            },
            "cliente": {
                "type": "string",
                "description": (
                    "Opcional. Nome do cliente, se o consultor citar um. Sem isso, a ferramenta "
                    "ajusta o último resumo em revisão."
                ),
            },
        },
        "required": ["feedback"],
    },
}

APROVAR_E_ENVIAR = {
    "name": "aprovar_e_enviar",
    "description": (
        "Fecha o ciclo: exporta o resumo detalhado aprovado em PDF, salva na pasta do cliente no "
        "Drive, envia por e-mail para o endereço cadastrado do cliente e marca 'Enviado' na "
        "planilha. CHAME esta ferramenta quando, DEPOIS de ter mandado o link de um resumo para "
        "revisão, o consultor aprovar — 'ok', 'okay', 'aprovado', 'pode enviar', 'manda', "
        "'confirmado', 'sim' e variações. Nunca chame antes de ter gerado um resumo. Depois de "
        "executar, confirme o envio e repasse o lembrete de avisar o cliente pelo WhatsApp."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "cliente": {
                "type": "string",
                "description": (
                    "Opcional. Nome do cliente, se o consultor citar um. Sem isso, envia o último "
                    "resumo que estava em revisão."
                ),
            }
        },
        "required": [],
    },
}

STATUS_CONSULTORIA = {
    "name": "status_consultoria",
    "description": (
        "Mostra o estado do plugin de consultoria: o que ainda falta configurar (IDs de pasta, "
        "planilha, templates, chave da OpenAI, e-mail) e qual resumo está em revisão no momento. "
        "Use quando o consultor perguntar se está tudo configurado, o que falta, ou em que pé "
        "está o resumo — e também para explicar um erro de configuração."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "cliente": {
                "type": "string",
                "description": "Opcional. Nome do cliente cuja sessão de revisão se quer consultar.",
            }
        },
        "required": [],
    },
}
