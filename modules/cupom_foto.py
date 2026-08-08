"""Foto do cupom — lança a compra a partir do canhoto, débito ou crédito.

Módulo próprio pelo mesmo motivo do importador de extrato: tem estado que
atravessa vários reruns (a foto, e depois a leitura dela) e regra própria.
A leitura em si mora em `cupom.py`, sem Streamlit; aqui fica só a tela.

O caminho é: tira a foto → o sistema lê → **você confere** → lança.
A conferência não é enfeite. Valor lido errado não dá erro, dá um número
plausível — por isso os campos vêm preenchidos mas editáveis, e a foto fica
lado a lado com eles.

**A leitura vem antes das escolhas de propósito.** Perguntar conta, cartão e
categoria antes da foto faria a pessoa digitar o que a foto já responde, e
ainda por cima jogaria fora o trabalho quando a leitura falhasse. Lendo
primeiro, as escolhas chegam com valor, data e estabelecimento já no lugar.

Leitura ruim **não avança sozinha**: o que ela não conseguiu ler fica vazio ou
como "não identificado", e a tela não deixa passar. Mas também não é beco sem
saída — "✏️ Preencher na mão" segue com a mesma foto anexada, porque quem está
em pé no caixa da loja não pode perder a viagem por causa de um reflexo no
papel.

**Débito e crédito seguem caminhos diferentes**, que é a única parte em que
errar sai caro:

  débito   sai da conta na hora        → lançamento **pago**, sem cartão
  crédito  entra na fatura do cartão   → lançamento **pendente** com cartão,
                                          o dinheiro sai no vencimento

E, como em todo lugar que traz dinheiro de fora para dentro, vale a mesma
regra: **confirma, não duplica.** Se já existe uma conta a pagar do mesmo
valor por perto, a tela oferece dar baixa nela em vez de criar outra.
"""

from datetime import date

import streamlit as st

import cupom
import database as db
import storage
import theme

FORMAS_ROTULO = {
    "credito": "💳 Crédito",
    "debito": "🏦 Débito",
    "pix": "⚡ Pix",
    "dinheiro": "💵 Dinheiro",
    "desconhecido": "❓ Não identificado",
}
# Só o crédito entra na fatura; o resto sai do caixa na hora.
NA_HORA = ("debito", "pix", "dinheiro")

LIDO = "cupom_lido"
FOTO = "cupom_foto"
FALHA = "cupom_falha"


def render(conn, usuario):
    grupo_id = usuario["grupo_id"]

    if not cupom.configurado():
        st.warning(
            "A leitura por foto precisa de uma **chave de API**. O Gemini tem camada "
            "gratuita (cerca de 500 leituras por dia) — pegue em "
            "*aistudio.google.com → Get API key* e cole nos secrets do app:\n\n"
            "```toml\n[gemini]\napi_key = \"AIza...\"\n```\n\n"
            "A Anthropic também serve (`[anthropic] api_key`), custa mais e exige "
            "crédito. Com as duas configuradas, vale o Gemini.\n\n"
            "Enquanto isso, **📷 Foto do Cupom** continua servindo pelo "
            "**✏️ Preencher na mão**, que anexa a foto do mesmo jeito."
        )
        return

    contas = [c for c in db.listar_contas(conn, grupo_id=grupo_id) if c["tipo"] != "cartao"]
    if not contas:
        st.warning("Cadastre uma conta em **⚙️ Configurações → Cadastros** antes de lançar.")
        return

    if st.session_state.get(LIDO):
        _conferir(conn, usuario, contas, grupo_id)
        return

    _capturar()


# ── 1. A foto ────────────────────────────────────────────────────────────

def _capturar():
    st.markdown(
        "Tire a foto do **cupom ou do canhoto da maquininha**. O sistema lê o "
        "valor, a data e o estabelecimento — e você confere antes de lançar."
    )
    quem = {"gemini": "Gemini", "anthropic": "Claude"}.get(cupom.provedor(), "—")
    st.caption(f"Leitura por {quem}.")

    # Duas portas de propósito: no celular a câmera é o caminho natural, no
    # computador a foto já está no arquivo. `st.camera_input` abre a câmera
    # traseira do próprio navegador, sem aplicativo nenhum.
    aba_camera, aba_arquivo = st.tabs(["📷  Tirar foto", "📁  Enviar arquivo"])

    imagem = nome = None
    with aba_camera:
        tirada = st.camera_input("Cupom", key="cupom_camera", label_visibility="collapsed")
        if tirada:
            imagem, nome = tirada.getvalue(), "cupom.jpg"
    with aba_arquivo:
        enviada = st.file_uploader("Foto do cupom", type=["jpg", "jpeg", "png", "webp"],
                                   key="cupom_arquivo")
        if enviada:
            imagem, nome = enviada.getvalue(), enviada.name

    if not imagem:
        return

    try:
        storage.validar(nome, imagem)
    except storage.ArquivoRecusado as erro:
        st.error(str(erro))
        return

    c_ler, c_mao = st.columns([2, 1])
    if c_ler.button("🔍 Ler este cupom", type="primary", use_container_width=True):
        with st.spinner("Lendo a foto…"):
            try:
                lido = cupom.ler(imagem, nome)
            except cupom.CupomIlegivel as erro:
                st.session_state[FALHA] = (str(erro), True)   # a foto
                lido = None
            except cupom.LeituraIndisponivel as erro:
                st.session_state[FALHA] = (str(erro), False)  # a configuração
                lido = None
            except Exception as erro:  # imprevisto
                st.session_state[FALHA] = (cupom.explicar_falha(erro), False)
                lido = None

        st.session_state[FOTO] = {"dados": imagem, "nome": nome}
        if lido:
            st.session_state.pop(FALHA, None)
            st.session_state[LIDO] = lido
        st.rerun()

    # Escapatória: foto ruim não pode custar a viagem inteira. A pessoa está
    # no caixa da loja com o comprovante na mão — melhor digitar quatro campos
    # do que sair sem lançar e esquecer depois.
    if c_mao.button("✏️ Preencher na mão", use_container_width=True):
        st.session_state[FOTO] = {"dados": imagem, "nome": nome}
        st.session_state[LIDO] = _em_branco()
        st.session_state.pop(FALHA, None)
        st.rerun()

    if st.session_state.get(FALHA):
        mensagem, da_foto = st.session_state[FALHA]
        # Mandar tirar outra foto quando o problema é a chave da API faz a
        # pessoa fotografar cinco vezes até desistir. Cada erro, seu conselho.
        conselho = ("Tente uma foto mais nítida — ou use **✏️ Preencher na mão**, "
                    "que guarda esta mesma foto como comprovante."
                    if da_foto else
                    "**Isto não é problema da foto.** Enquanto não for resolvido, "
                    "use **✏️ Preencher na mão** — a foto fica anexada do mesmo jeito.")
        st.error(f"{mensagem}\n\n{conselho}")


def _em_branco():
    """Leitura vazia: os campos aparecem para preencher, a foto vai junto."""
    return {"valor": 0.0, "data": None, "estabelecimento": "", "forma": "desconhecido",
            "parcelas": 1, "observacao": None, "confianca": "manual"}


# ── 2. A conferência ─────────────────────────────────────────────────────

def _conferir(conn, usuario, contas, grupo_id):
    lido = st.session_state[LIDO]
    foto = st.session_state.get(FOTO, {})
    grupo = usuario["grupo_id"]

    esq, dir_ = st.columns([1, 2])
    with esq:
        if foto.get("dados"):
            st.image(foto["dados"], use_container_width=True)
        if st.button("↩︎ Outra foto", use_container_width=True):
            _limpar()
            st.rerun()

    with dir_:
        if lido["confianca"] == "manual":
            st.info("Preencha os campos abaixo. A foto fica anexada como comprovante.")
        elif lido["confianca"] == "baixa":
            st.warning("A foto ficou difícil de ler. **Confira todos os campos.**")
        if lido["observacao"]:
            st.caption(f"No comprovante: {theme.esc(lido['observacao'])}")

        c1, c2 = st.columns([2, 1])
        descricao = c1.text_input("Descrição", value=lido["estabelecimento"],
                                  key="cupom_desc")
        valor = c2.number_input("Valor (R$)", value=float(lido["valor"]),
                                min_value=0.0, step=1.0, format="%.2f", key="cupom_valor")

        c3, c4 = st.columns(2)
        data_compra = c3.date_input("Data da compra", value=lido["data"] or date.today(),
                                    key="cupom_data")
        forma = c4.selectbox(
            "Forma de pagamento", list(FORMAS_ROTULO),
            index=list(FORMAS_ROTULO).index(lido["forma"]),
            format_func=lambda f: FORMAS_ROTULO[f], key="cupom_forma",
        )

        if forma == "desconhecido":
            st.warning(
                ("Escolha se foi **débito ou crédito** acima."
                 if lido["confianca"] == "manual" else
                 "O canhoto não disse se foi **débito ou crédito** — escolha acima.")
                + " No débito o dinheiro sai hoje; no crédito, só no vencimento da fatura."
            )
            return

        cartao = _destino(conn, contas, forma, grupo, lido)
        if forma == "credito" and cartao is None:
            return

        categorias = db.listar_categorias(conn, tipo="despesa", grupo_id=grupo)
        c5, c6 = st.columns(2)
        categoria = c5.selectbox("Categoria", categorias,
                                 format_func=lambda c: f"{c['icone']} {c['nome']}",
                                 key="cupom_cat")
        parcelas = c6.number_input("Parcelas", min_value=1, max_value=48,
                                   value=lido["parcelas"] if forma == "credito" else 1,
                                   disabled=forma != "credito", key="cupom_parcelas")

        conta = st.session_state.get("cupom_conta_escolhida")
        _salvar(conn, usuario, grupo, {
            "descricao": descricao, "valor": valor, "data": data_compra,
            "forma": forma, "cartao": cartao, "conta": conta,
            "categoria": categoria, "parcelas": int(parcelas), "foto": foto,
        })


def _destino(conn, contas, forma, grupo_id, lido):
    """Onde a compra bate: no cartão (crédito) ou direto na conta (o resto)."""
    if forma == "credito":
        cartoes = db.listar_cartoes(conn, grupo_id=grupo_id)
        if not cartoes:
            st.warning("Cadastre o cartão em **⚙️ Configurações → Cadastros** para "
                       "lançar compras no crédito.")
            return None
        cartao = st.selectbox("Cartão", cartoes,
                              format_func=lambda c: c["nome_conta"], key="cupom_cartao")
        conta = st.selectbox("Conta que paga a fatura", contas,
                             format_func=lambda c: c["nome"], key="cupom_conta")
        st.session_state["cupom_conta_escolhida"] = conta
        _, vencimento = db.ciclo_fatura(
            st.session_state["cupom_data"].isoformat(),
            cartao["dia_fechamento"], cartao["dia_vencimento"])
        st.caption(
            f"A despesa conta em **{theme.data_br(st.session_state['cupom_data'].isoformat())}**, "
            f"mas o dinheiro sai em **{theme.data_br(vencimento.isoformat())}**, "
            "no vencimento da fatura."
        )
        return cartao

    conta = st.selectbox("Conta", contas, format_func=lambda c: c["nome"], key="cupom_conta")
    st.session_state["cupom_conta_escolhida"] = conta
    st.caption("O dinheiro sai da conta na data da compra.")
    return None


# ── 3. O lançamento ──────────────────────────────────────────────────────

def _salvar(conn, usuario, grupo_id, dados):
    cartao_id = dados["cartao"]["id"] if dados["cartao"] else None
    transacao = {"data": dados["data"], "valor": dados["valor"],
                 "tipo": "saida", "descricao": dados["descricao"], "fitid": None}

    # Confirma, não duplica: a compra pode já estar cadastrada em A Pagar.
    candidatos = db.candidatos_conciliacao(
        conn, transacao, grupo_id=grupo_id,
        conta_id=dados["conta"]["id"] if dados["conta"] else None,
        cartao_id=cartao_id)

    escolhido = None
    if candidatos:
        st.divider()
        st.info(f"**Já existe {len(candidatos)} lançamento pendente** com este valor "
                "por perto. Dar baixa nele evita lançar a mesma compra duas vezes.")
        escolhido = st.selectbox(
            "Lançamento correspondente", [None] + candidatos, key="cupom_candidato",
            format_func=lambda l: ("— criar um lançamento novo —" if l is None else
                                   f"{l['icone_categoria']} {l['descricao']} · "
                                   f"{theme.data_br(l['data'])} · {theme.moeda(l['valor'])}"),
        )

    if not st.button("Lançar", type="primary", use_container_width=True, key="cupom_lancar"):
        return

    # A trava fica aqui, e não no campo: no modo manual ele nasce zerado, e um
    # mínimo no widget só faria o número aparecer preenchido com 0,01.
    if dados["valor"] <= 0:
        st.error("Informe o valor da compra.")
        return
    if not dados["descricao"].strip():
        st.error("Informe a descrição — é o que você vai reconhecer na lista depois.")
        return

    if escolhido:
        db.conciliar_lancamento(conn, escolhido["id"], None,
                                data_extrato=dados["data"].isoformat())
        ids = [escolhido["id"]]
        recado = "Lançamento existente marcado como pago."
    else:
        # Crédito nasce pendente para o ciclo de fatura valer; o resto já saiu.
        status = "pendente" if cartao_id else "pago"
        db.criar_lancamento(
            conn, dados["data"].isoformat(),
            dados["conta"]["id"], dados["categoria"]["id"], dados["descricao"],
            dados["valor"], "saida", status, usuario["id"],
            cartao_id=cartao_id, parcelas=dados["parcelas"],
            forma_pagamento=FORMAS_ROTULO[dados["forma"]].split(" ", 1)[1],
            grupo_id=grupo_id,
        )
        ids = _ultimos_ids(conn, grupo_id, dados["parcelas"])
        recado = ("Compra lançada no cartão — sai do caixa no vencimento."
                  if cartao_id else "Compra lançada, já paga.")

    _guardar_foto(conn, usuario, grupo_id, dados["foto"], ids[:1])
    _limpar()
    st.success(recado + " A foto ficou anexada como comprovante.")
    st.rerun()


def _ultimos_ids(conn, grupo_id, quantos):
    """Os lançamentos recém-criados, do primeiro para o último.

    Compra parcelada vira N lançamentos. A ordem importa: o comprovante é da
    compra, então ele pertence à parcela 1 — invertido, ele acabaria preso na
    última, que vence daqui a meses.
    """
    linhas = conn.execute(
        "SELECT id FROM lancamentos WHERE grupo_id = ? ORDER BY id DESC LIMIT ?",
        (grupo_id, quantos),
    ).fetchall()
    return [l["id"] for l in reversed(linhas)]


def _guardar_foto(conn, usuario, grupo_id, foto, ids):
    """A foto vira anexo do lançamento — é o comprovante dele."""
    if not foto.get("dados") or not ids:
        return
    try:
        armazenamento = storage.obter()
        chave = armazenamento.salvar(foto["dados"], foto["nome"])
        db.criar_anexo(
            conn, "lancamento", ids[0], foto["nome"], chave, armazenamento.nome,
            cupom.mime_de(foto["nome"]), len(foto["dados"]),
            storage.hash_conteudo(foto["dados"]), usuario["id"], grupo_id=grupo_id,
        )
    except Exception as erro:  # anexo é acessório: não derruba o lançamento
        st.warning(f"O lançamento foi salvo, mas a foto não: {erro}")


def _limpar():
    for chave in (LIDO, FOTO, FALHA, "cupom_conta_escolhida"):
        st.session_state.pop(chave, None)
