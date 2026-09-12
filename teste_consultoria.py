"""teste_consultoria.py — o fluxo do plugin de consultoria, sem tocar em nenhuma API.

    python3 teste_consultoria.py

Google, OpenAI e SMTP são substituídos por dublês; o que está sob teste é a
regra de negócio: achar o cliente pelo nome do arquivo, o duplo-check da coluna
Tipo (avisa, mas nunca bloqueia), quais documentos cada palavra-chave gera, o
ciclo de correção e o envio final com os dois status na planilha.
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ["CONSULTORIA_STATE_DIR"] = tempfile.mkdtemp(prefix="consultoria-teste-")

from plugins.consultoria import (  # noqa: E402
    config,
    docs_utils,
    drive_utils,
    email_utils,
    gpt_summarizer,
    sheets_utils,
    state,
    texto_utils,
    tools,
)

AREAS = ["DIAGNOSTICO", "ORIENTACOES", "PROXIMOS_PASSOS"]
TRANSCRICAO = "Consultor: como estão as vendas?\nCliente: caíram 20% no trimestre."

registro = {}


def _config_completa():
    cfg = config.Config(
        service_account_file="/tmp/fake.json",
        pasta_transcricoes_id="PASTA_TRANSCRICOES",
        planilha_id="PLANILHA",
        openai_api_key="sk-teste",
        consultor_nome="Fabrício",
        email_remetente="consultor@gmail.com",
        email_senha_app="senha-de-app",
    )
    cfg.template_detalhado = config.TemplateConfig(doc_id="TPL_DETALHADO")
    cfg.template_curto = config.TemplateConfig(doc_id="TPL_CURTO")
    config._cache = cfg
    return cfg


def _cadastro(tipo_padaria="Consultoria"):
    return [
        sheets_utils.Cliente(
            nome="Padaria do Zé Ltda",
            linha=2,
            pasta_drive="PASTA_PADARIA",
            email="ze@padaria.com.br",
            tipo=tipo_padaria,
        ),
        sheets_utils.Cliente(
            nome="Oficina Bom Motor",
            linha=3,
            pasta_drive="PASTA_OFICINA",
            email="contato@bommotor.com.br",
            tipo="Sebrae",
        ),
    ]


def _instalar_dubles(tipo_padaria="Consultoria", arquivo="Tactiq - Padaria do Ze - 2026-03-11.docx"):
    registro.clear()
    registro.update({"status": [], "docs": [], "lixeira": [], "emails": [], "pdfs": []})
    state.limpar()

    drive_utils.transcricao_mais_recente = lambda pasta="", filtro_nome="": {
        "id": "TRANS1",
        "name": arquivo,
        "mimeType": drive_utils.MIME_DOCX,
    }
    drive_utils.ler_texto = lambda _arquivo: TRANSCRICAO
    drive_utils.data_da_reuniao = lambda _arquivo: "11/03/2026"
    drive_utils.mover_para_lixeira = lambda file_id: registro["lixeira"].append(file_id)
    drive_utils.exportar_pdf = lambda doc_id: b"%PDF-fake"
    drive_utils.salvar_pdf = lambda pdf, nome, pasta: (
        registro["pdfs"].append((nome, pasta)) or {"id": "PDF1", "nome": nome, "link": "link-pdf"}
    )

    sheets_utils.listar_clientes = lambda: _cadastro(tipo_padaria)
    sheets_utils.escrever_status = lambda cliente, coluna, valor: (
        registro["status"].append((cliente.nome, coluna, valor)) or {"ok": True, "celula": "X1"}
    )

    docs_utils.areas_do_template = lambda doc_id: list(AREAS)
    docs_utils.marcadores_nao_preenchidos = lambda doc_id: []

    def gerar_documento(template_id, nome, pasta, valores):
        indice = len(registro["docs"]) + 1
        registro["docs"].append({"template": template_id, "nome": nome, "pasta": pasta, "valores": valores})
        return {"id": f"DOC{indice}", "nome": nome, "link": f"https://docs.google.com/document/d/DOC{indice}/edit"}

    docs_utils.gerar_documento = gerar_documento

    gpt_summarizer.gerar_resumo = lambda transcricao, areas, **kw: {a: f"texto de {a}" for a in areas}
    gpt_summarizer.revisar_resumo = lambda resumo, transcricao, **kw: {
        a: t + " (revisado)" for a, t in resumo.items()
    }
    gpt_summarizer.ajustar_resumo = lambda resumo, feedback, transcricao, **kw: {
        a: f"{t} [{feedback}]" for a, t in resumo.items()
    }

    email_utils.enviar_resumo = lambda destinatario, cliente, pdf, nome: (
        registro["emails"].append((destinatario, cliente, nome)) or {"ok": True, "destinatario": destinatario}
    )


def executar():
    falhas = []

    def conferir(titulo, condicao, detalhe=""):
        print(f"   {'ok   ' if condicao else 'ERRADO'} {titulo}")
        if not condicao:
            falhas.append(f"{titulo}{' — ' + detalhe if detalhe else ''}")

    # ── 1. Palavra-chave "Consultoria": só o documento do cliente ───────────
    print("\n1. Palavra-chave 'Consultoria' (cadastro também é Consultoria)")
    _config_completa()
    _instalar_dubles(tipo_padaria="Consultoria")
    resposta = json.loads(tools.gerar_resumo({"palavra_chave": "Consultoria"}))
    conferir("gerou sem erro", resposta.get("ok"), json.dumps(resposta, ensure_ascii=False))
    conferir("identificou o cliente pelo nome do arquivo", resposta.get("cliente") == "Padaria do Zé Ltda")
    conferir("gerou só o detalhado", resposta.get("documentos_gerados") == ["detalhado"])
    conferir("devolveu o link do Google Doc", "docs.google.com" in resposta.get("link_resumo_detalhado", ""))
    conferir("marcou 'Resumo Gerado' na planilha", ("Padaria do Zé Ltda", "resumo_gerado", "OK") in registro["status"])
    conferir("salvou na pasta do cliente", registro["docs"][0]["pasta"] == "PASTA_PADARIA")
    conferir(
        "preencheu os marcadores automáticos",
        registro["docs"][0]["valores"].get("CLIENTE") == "Padaria do Zé Ltda"
        and registro["docs"][0]["valores"].get("DATA_REUNIAO") == "11/03/2026",
    )
    conferir("passou pelo revisor", "(revisado)" in registro["docs"][0]["valores"]["DIAGNOSTICO"])
    conferir("sem aviso de conflito", not resposta.get("avisos"), str(resposta.get("avisos")))

    # ── 2. Palavra-chave "Sebrae": os dois documentos ───────────────────────
    print("\n2. Palavra-chave 'Sebrae' (cadastro Sebrae)")
    _instalar_dubles(tipo_padaria="Sebrae", arquivo="CraftNote 2026-02-01 Oficina Bom Motor.txt")
    resposta = json.loads(tools.gerar_resumo({"palavra_chave": "Sebrae"}))
    conferir("achou a Oficina", resposta.get("cliente") == "Oficina Bom Motor")
    conferir("gerou os dois documentos", resposta.get("documentos_gerados") == ["detalhado", "curto"])
    conferir("devolveu os dois links", bool(resposta.get("link_resumo_curto")) and bool(resposta.get("link_resumo_detalhado")))
    conferir("usou os dois templates", {d["template"] for d in registro["docs"]} == {"TPL_DETALHADO", "TPL_CURTO"})

    # ── 3. Duplo-check: a palavra-chave manda, mas o agente avisa ───────────
    print("\n3. Palavra-chave 'Sebrae' num cliente cadastrado como 'Consultoria'")
    _instalar_dubles(tipo_padaria="Consultoria")
    resposta = json.loads(tools.gerar_resumo({"palavra_chave": "Sebrae"}))
    conferir("gerou assim mesmo (não bloqueou)", resposta.get("ok"))
    conferir("gerou os dois documentos, como pede a palavra-chave", resposta.get("documentos_gerados") == ["detalhado", "curto"])
    avisos = " ".join(resposta.get("avisos", []))
    conferir("avisou do conflito", "ATENÇÃO" in avisos and "Consultoria" in avisos, avisos)

    # ── 4. Ciclo de correção ────────────────────────────────────────────────
    print("\n4. Consultor manda uma correção em vez de 'ok'")
    _instalar_dubles(tipo_padaria="Consultoria")
    primeiro = json.loads(tools.gerar_resumo({"palavra_chave": "Consultoria"}))
    ajuste = json.loads(tools.ajustar_resumo({"feedback": "tira a parte do financeiro"}))
    conferir("ajustou sem erro", ajuste.get("ok"), json.dumps(ajuste, ensure_ascii=False))
    conferir("devolveu link novo", ajuste.get("link_resumo_detalhado") != primeiro.get("link_resumo_detalhado"))
    conferir("descartou a versão anterior", registro["lixeira"] == ["DOC1"], str(registro["lixeira"]))
    conferir("aplicou o feedback no texto", "tira a parte do financeiro" in registro["docs"][-1]["valores"]["DIAGNOSTICO"])
    conferir("manteve o mesmo nome de arquivo", registro["docs"][-1]["nome"] == registro["docs"][0]["nome"])

    # ── 5. Aprovação e envio ────────────────────────────────────────────────
    print("\n5. Consultor responde 'ok'")
    envio = json.loads(tools.aprovar_e_enviar({}))
    conferir("enviou sem erro", envio.get("ok"), json.dumps(envio, ensure_ascii=False))
    conferir("mandou para o e-mail do cadastro", registro["emails"] and registro["emails"][0][0] == "ze@padaria.com.br")
    conferir("salvou o PDF na pasta do cliente", registro["pdfs"] and registro["pdfs"][0][1] == "PASTA_PADARIA")
    conferir("marcou 'Email Enviado'", ("Padaria do Zé Ltda", "email_enviado", "Enviado") in registro["status"])
    conferir("lembrou do WhatsApp", "WhatsApp" in envio.get("lembrete_para_o_consultor", ""))

    # ── 6. Erros previsíveis viram recado, não exceção ──────────────────────
    print("\n6. Situações de erro")
    _instalar_dubles(tipo_padaria="Consultoria")
    resposta = json.loads(tools.gerar_resumo({"palavra_chave": "qualquer outra coisa"}))
    conferir("palavra-chave desconhecida é recusada com explicação", resposta.get("ok") is False and "Sebrae" in resposta.get("erro", ""))

    drive_utils.transcricao_mais_recente = lambda pasta="", filtro_nome="": None
    resposta = json.loads(tools.gerar_resumo({"palavra_chave": "Consultoria"}))
    conferir("pasta sem transcrição avisa em vez de estourar", resposta.get("ok") is False and "transcrição" in resposta.get("erro", ""))

    _instalar_dubles(tipo_padaria="Consultoria")
    resposta = json.loads(tools.ajustar_resumo({"feedback": "ok"}))
    conferir("'ok' não é tratado como correção", resposta.get("ok") is False)

    resposta = json.loads(tools.aprovar_e_enviar({}))
    conferir("aprovar sem resumo gerado avisa", resposta.get("ok") is False)

    config._cache = config.Config()
    resposta = json.loads(tools.gerar_resumo({"palavra_chave": "Consultoria"}))
    conferir(
        "plugin não configurado lista o que falta",
        resposta.get("ok") is False and len(resposta.get("faltando", [])) >= 4,
        json.dumps(resposta, ensure_ascii=False),
    )
    _config_completa()

    # ── 7. Peças isoladas ───────────────────────────────────────────────────
    print("\n7. Regras de apoio")
    conferir("nome parcial casa com o cadastro", texto_utils.pontuacao_match("Padaria do Zé Ltda", "Tactiq - Padaria do Ze.docx") > 0.45)
    conferir("cliente errado não casa", texto_utils.pontuacao_match("Oficina Bom Motor", "Tactiq - Padaria do Ze.docx") == 0.0)
    conferir("'pode enviar' é aprovação", texto_utils.e_aprovacao("Pode enviar"))
    conferir("correção não é aprovação", not texto_utils.e_aprovacao("ok, mas muda o diagnóstico"))
    conferir("marcadores são lidos do template", docs_utils.MARCADOR.findall("DIAGNÓSTICO\n{{DIAGNOSTICO}}\n{{ PROXIMOS_PASSOS }}") == ["DIAGNOSTICO", "PROXIMOS_PASSOS"])
    conferir("coluna 27 vira AA", sheets_utils._letra_coluna(0) == "A" and sheets_utils._letra_coluna(26) == "AA")

    return falhas


if __name__ == "__main__":
    problemas = executar()
    if problemas:
        print("\nFALHOU: " + "; ".join(problemas))
    else:
        print("\nOK — palavra-chave decide os documentos, conflito com o cadastro avisa sem")
        print("     bloquear, correção regera o Doc e a aprovação envia o PDF e marca a planilha.")
    sys.stdout.flush()
    os._exit(1 if problemas else 0)
