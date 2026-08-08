"""Importar extrato bancário (OFX) com conciliação.

Módulo isolado de propósito: ele não é operação do dia a dia, tem estado
próprio (o arquivo carregado atravessa vários reruns) e regra própria (casar
em vez de criar). Misturar isso ao Fluxo de Caixa deixaria as duas coisas
difíceis de mexer.

A regra que orienta tudo aqui: **o extrato confirma, não duplica.**

  linha bate com um pendente        → marca como pago
  linha é pagamento de fatura       → dá as compras daquela fatura por pagas
  linha não bate com nada           → aí sim vira lançamento novo

A leitura do arquivo mora em `ofx.py`; as consultas, em `database.py`. Aqui
fica só a tela e a decisão do usuário.
"""

import streamlit as st

import database as db
import ofx
import theme

CASAR = "Casar (marcar como pago)"
CASAR_FATURA = "Casar fatura do cartão"
CRIAR = "Criar lançamento novo"
IGNORAR = "Ignorar"


def render(conn, usuario):
    grupo_id = usuario["grupo_id"]
    contas = [c for c in db.listar_contas(conn, grupo_id=grupo_id) if c["tipo"] != "cartao"]

    if not contas:
        st.warning("Cadastre uma conta bancária em **⚙️ Cadastros** antes de importar.")
        return

    st.markdown(
        "Suba o arquivo **OFX** que o seu banco exporta (procure por *exportar para "
        "o gerenciador financeiro* ou *OFX* no aplicativo). O sistema compara com o "
        "que você já lançou e propõe o que fazer com cada linha — nada é gravado "
        "sem você confirmar."
    )

    arquivo = st.file_uploader("Arquivo OFX", type=["ofx"], key="imp_arquivo")
    if not arquivo:
        st.caption(
            "Dois arquivos diferentes servem aqui: o **extrato da conta**, que traz o "
            "pagamento da fatura numa linha só, e a **fatura do cartão**, que traz cada "
            "compra. O sistema reconhece qual é."
        )
        return

    bruto = arquivo.getvalue()
    try:
        transacoes = ofx.ler(bruto)
    except Exception as erro:  # arquivo corrompido ou formato inesperado
        st.error(f"Não consegui ler este arquivo: {erro}")
        return

    # O invólucro do OFX diz se é conta ou cartão. Importar fatura como conta
    # debitaria tudo na data da compra e duplicaria com o pagamento que vem no
    # extrato do banco — por isso a origem é confirmada antes de qualquer coisa.
    parece_cartao = ofx.e_de_cartao(bruto)
    cartoes = db.listar_cartoes(conn, grupo_id=grupo_id)

    origens = ["🏦 Extrato de conta", "💳 Fatura de cartão"]
    padrao = 1 if (parece_cartao and cartoes) else 0
    origem = st.radio("Origem do arquivo", origens, index=padrao,
                      horizontal=True, key="imp_origem")
    de_cartao = origem == origens[1]

    if parece_cartao and not de_cartao:
        st.warning(
            "Este arquivo **parece ser fatura de cartão**. Importado como extrato de "
            "conta, as compras sairiam do saldo na data da compra e depois "
            "duplicariam com o pagamento da fatura."
        )

    cartao = None
    if de_cartao:
        if not cartoes:
            st.warning("Cadastre o cartão em **⚙️ Configurações → Cadastros** antes de "
                       "importar a fatura dele.")
            return
        c1, c2 = st.columns(2)
        with c1:
            cartao = st.selectbox("Cartão", cartoes,
                                  format_func=lambda c: c["nome_conta"], key="imp_cartao")
        with c2:
            conta = st.selectbox("Conta que paga a fatura", contas,
                                 format_func=lambda c: c["nome"], key="imp_conta_fatura")
        st.caption(
            "As compras entram **pendentes**, com o cartão vinculado: elas saem do saldo "
            "no vencimento da fatura, não na data da compra."
        )
    else:
        conta = st.selectbox("Conta deste extrato", contas,
                             format_func=lambda c: c["nome"], key="imp_conta")

    if not transacoes:
        st.warning(
            "Não encontrei transações neste arquivo. Confira se ele é mesmo um "
            "extrato OFX — alguns bancos exportam um OFX de *investimentos*, "
            "que tem outro formato."
        )
        return

    _resumo_arquivo(transacoes)

    ja_importadas = db.fitids_ja_importados(
        conn, [t["fitid"] for t in transacoes], grupo_id=grupo_id)
    novas = [t for t in transacoes if not t["fitid"] or t["fitid"] not in ja_importadas]

    if ja_importadas:
        st.info(
            f"**{len(ja_importadas)} transação(ões) já tinham sido importadas** e ficaram "
            "de fora. Pode subir o mesmo extrato quantas vezes quiser."
        )

    if not novas:
        st.success("Tudo deste extrato já está no sistema. Nada a fazer.")
        return

    st.divider()
    st.markdown(f"##### {len(novas)} transação(ões) para revisar")
    _revisar(conn, usuario, novas, conta, grupo_id, cartao)


def _resumo_arquivo(transacoes):
    entradas, saidas, inicio, fim = ofx.resumo(transacoes)
    m1, m2, m3 = st.columns(3)
    m1.metric("Período", f"{theme.data_br(inicio.isoformat())} a {theme.data_br(fim.isoformat())}")
    m2.metric("Entradas", theme.moeda(entradas))
    m3.metric("Saídas", theme.moeda(saidas))


def _revisar(conn, usuario, transacoes, conta, grupo_id, cartao=None):
    categorias = db.listar_categorias(conn, grupo_id=grupo_id)
    cartao_id = cartao["id"] if cartao else None
    decisoes = {}

    for i, t in enumerate(transacoes):
        chave = t["fitid"] or f"linha{i}"
        # Vindo da fatura, procura entre as compras daquele cartão: é o que
        # evita duplicar o que já foi lançado na mão.
        candidatos = db.candidatos_conciliacao(
            conn, t, grupo_id=grupo_id, conta_id=conta["id"], cartao_id=cartao_id)
        # Baixa de fatura só faz sentido no extrato da conta.
        faturas = [] if cartao else db.faturas_para_conciliar(conn, t, grupo_id=grupo_id)

        # A sugestão vai na ordem do risco: casar não cria nada, criar cria.
        opcoes = []
        if faturas:
            opcoes.append(CASAR_FATURA)
        if candidatos:
            opcoes.append(CASAR)
        opcoes += [CRIAR, IGNORAR]

        with st.container(border=True):
            cab, val = st.columns([3.5, 1.5])
            cor = theme.GREEN if t["tipo"] == "entrada" else theme.RED
            sinal = "+" if t["tipo"] == "entrada" else "−"
            cab.markdown(
                f"**{theme.esc(t['descricao'])}**  \n"
                f"<span style='color:{theme.TEXT_MUTED};font-size:0.8rem;'>"
                f"{theme.data_br(t['data'].isoformat())}</span>",
                unsafe_allow_html=True,
            )
            val.markdown(
                f"<div style='text-align:right;font-weight:700;color:{cor};'>"
                f"{sinal} {theme.moeda_md(t['valor'])}</div>",
                unsafe_allow_html=True,
            )

            acao = st.radio("O que fazer", opcoes, horizontal=True,
                            key=f"imp_acao_{chave}", label_visibility="collapsed")

            decisao = {"transacao": t, "acao": acao}

            if acao == CASAR_FATURA:
                escolha = st.selectbox(
                    "Fatura", faturas, key=f"imp_fat_{chave}",
                    format_func=lambda f: (
                        f"💳 {f['cartao']} · vence {theme.data_br(f['vencimento'].isoformat())} "
                        f"· {theme.moeda(f['total'])} ({len(f['lancamento_ids'])} compras)"
                    ),
                )
                decisao["fatura"] = escolha
                st.caption(
                    "As compras desta fatura ficam como pagas. Nenhum lançamento novo "
                    "é criado — elas já estão no sistema."
                )

            elif acao == CASAR:
                escolha = st.selectbox(
                    "Lançamento correspondente", candidatos, key=f"imp_cand_{chave}",
                    format_func=lambda l: (
                        f"{l['icone_categoria']} {l['descricao']} · "
                        f"{theme.data_br(l['data'])} · {theme.moeda(l['valor'])}"
                    ),
                )
                decisao["candidato"] = escolha

            elif acao == CRIAR:
                tipo_cat = "receita" if t["tipo"] == "entrada" else "despesa"
                elegiveis = [c for c in categorias if c["tipo"] == tipo_cat]
                decisao["categoria"] = st.selectbox(
                    "Categoria", elegiveis, key=f"imp_cat_{chave}",
                    format_func=lambda c: f"{c['icone']} {c['nome']}",
                )

            decisoes[chave] = decisao

    st.divider()
    resumo = _contar(decisoes)
    st.markdown(
        f"**{resumo[CASAR]} para casar · {resumo[CASAR_FATURA]} fatura(s) · "
        f"{resumo[CRIAR]} novo(s) · {resumo[IGNORAR]} ignorado(s)**"
    )

    if st.button("Importar", type="primary", use_container_width=True, key="imp_confirmar"):
        _aplicar(conn, usuario, decisoes, conta, grupo_id, cartao_id)


def _contar(decisoes):
    contagem = {CASAR: 0, CASAR_FATURA: 0, CRIAR: 0, IGNORAR: 0}
    for d in decisoes.values():
        contagem[d["acao"]] += 1
    return contagem


def _aplicar(conn, usuario, decisoes, conta, grupo_id, cartao_id=None):
    casados = faturas = criados = 0

    for decisao in decisoes.values():
        t = decisao["transacao"]
        acao = decisao["acao"]

        if acao == CASAR and decisao.get("candidato"):
            db.conciliar_lancamento(conn, decisao["candidato"]["id"], t["fitid"],
                                    data_extrato=t["data"].isoformat())
            casados += 1

        elif acao == CASAR_FATURA and decisao.get("fatura"):
            db.conciliar_fatura(conn, decisao["fatura"]["lancamento_ids"], t["fitid"])
            faturas += 1

        elif acao == CRIAR and decisao.get("categoria"):
            db.criar_do_extrato(conn, t, conta["id"], decisao["categoria"]["id"],
                                usuario["id"], grupo_id=grupo_id, cartao_id=cartao_id)
            criados += 1

    partes = []
    if casados:
        partes.append(f"{casados} conciliado(s)")
    if faturas:
        partes.append(f"{faturas} fatura(s) baixada(s)")
    if criados:
        partes.append(f"{criados} lançamento(s) novo(s)")

    st.success("Importado: " + (", ".join(partes) if partes else "nada a fazer") + ".")
    st.rerun()
