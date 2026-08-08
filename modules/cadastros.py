"""Cadastros — o único lugar onde se cria coisa.

As telas do dia a dia (Fluxo de Caixa, Cartão, A Pagar) só operam o que já
existe. Antes, conta e cartão podiam ser criados em dois lugares diferentes,
e a porta de Contas criava um cartão pela metade — com fechamento, vencimento
e limite chutados.
"""

import streamlit as st

import database as db
import theme

LABEL_TIPO_CONTA = {
    "banco": "🏦 Conta bancária",
    "carteira": "👛 Carteira / Dinheiro",
    "cartao": "💳 Cartão de crédito",
}

# Cartão não entra: ele nasce na seção própria, que pergunta fechamento,
# vencimento e limite. Os três tipos são fixos porque o sistema trata cartão
# de um jeito diferente (fatura, parcelas) — não é rótulo, é comportamento.
TIPOS_CONTA = ["banco", "carteira"]

SECOES = ["🏦  Contas", "💳  Cartões", "🏷️  Categorias", "💰  Formas de pagamento"]


def render(conn, usuario):
    secao = st.radio(
        "Cadastro", SECOES, horizontal=True, key="cadastros_secao",
        label_visibility="collapsed",
    )
    st.divider()
    render_secao(conn, usuario, secao)


def render_secao(conn, usuario, secao):
    grupo_id = usuario["grupo_id"]
    if "Contas" in secao:
        _contas(conn, grupo_id)
    elif "Cartões" in secao:
        _cartoes(conn, grupo_id)
    elif "Categorias" in secao:
        _categorias(conn, grupo_id)
    elif "Formas" in secao:
        _formas_pagamento(conn, grupo_id)


# ── Contas ───────────────────────────────────────────────────────────────

def _contas(conn, grupo_id):
    st.markdown("#### ➕ Nova conta")
    st.caption("Onde o seu dinheiro fica. Cartão de crédito é na seção ao lado.")

    with st.form("cad_nova_conta", clear_on_submit=True):
        c1, c2, c3 = st.columns([2, 2, 1.5], vertical_alignment="bottom")
        nome = c1.text_input("Nome", placeholder="Ex: Banco do Brasil, Carteira")
        tipo = c2.selectbox("Tipo", TIPOS_CONTA, format_func=lambda t: LABEL_TIPO_CONTA[t])
        saldo = c3.number_input("Saldo inicial (R$)", step=100.0, format="%.2f")
        criar = st.form_submit_button("Cadastrar conta", use_container_width=True)

    if criar:
        if not nome.strip():
            st.error("Informe o nome da conta.")
        else:
            db.criar_conta(conn, nome.strip(), tipo, saldo, grupo_id=grupo_id)
            st.success(f"Conta '{nome.strip()}' criada.")
            st.rerun()

    contas = [c for c in db.listar_contas(conn, apenas_ativas=False, grupo_id=grupo_id)
              if c["tipo"] != "cartao"]
    st.divider()
    st.markdown("#### Contas cadastradas")

    if not contas:
        st.info("Nenhuma conta ainda. Sem pelo menos uma, não dá para lançar no Fluxo de Caixa.")
        return

    for c in contas:
        qtd = db.contar_lancamentos_conta(conn, c["id"])
        saldo_atual = db.saldo_atual_conta(conn, c["id"])
        with st.container(border=True):
            cab1, cab2 = st.columns([3, 2])
            cab1.markdown(
                f"**{LABEL_TIPO_CONTA[c['tipo']]} · {theme.esc(c['nome'])}**  \n"
                f"<span style='color:{theme.TEXT_MUTED};font-size:0.82rem;'>"
                f"{qtd} lançamento(s)</span>",
                unsafe_allow_html=True,
            )
            cab2.markdown(
                f"<div style='text-align:right;font-size:1.1rem;font-weight:700;"
                f"color:{theme.DEEP_GREEN};'>{theme.moeda(saldo_atual)}</div>",
                unsafe_allow_html=True,
            )

            if st.checkbox("✏️ Editar / excluir", key=f"cad_conta_edit_{c['id']}"):
                with st.form(f"cad_conta_form_{c['id']}"):
                    e1, e2, e3 = st.columns([2, 2, 1.5], vertical_alignment="bottom")
                    novo_nome = e1.text_input("Nome", value=c["nome"], key=f"cad_cn_{c['id']}")
                    novo_tipo = e2.selectbox(
                        "Tipo", TIPOS_CONTA, index=TIPOS_CONTA.index(c["tipo"]),
                        format_func=lambda t: LABEL_TIPO_CONTA[t], key=f"cad_ct_{c['id']}",
                    )
                    novo_saldo = e3.number_input(
                        "Saldo inicial (R$)", value=float(c["saldo_inicial"]),
                        step=100.0, format="%.2f", key=f"cad_cs_{c['id']}",
                    )
                    salvar = st.form_submit_button("Salvar alterações", use_container_width=True)

                if salvar:
                    if not novo_nome.strip():
                        st.error("O nome não pode ficar vazio.")
                    else:
                        db.atualizar_conta(conn, c["id"], novo_nome.strip(), novo_tipo, novo_saldo)
                        st.success("Conta atualizada.")
                        st.rerun()

                _excluir_conta(conn, c, qtd)


def _excluir_conta(conn, conta, qtd_lancamentos):
    st.markdown("---")
    if qtd_lancamentos:
        st.caption(
            f"Esta conta tem {qtd_lancamentos} lançamento(s). Excluir apaga "
            "esses lançamentos junto — não há como desfazer."
        )
        confirmado = st.checkbox(
            "Confirmo que quero excluir a conta e seus lançamentos",
            key=f"cad_conf_{conta['id']}",
        )
    else:
        confirmado = True

    if st.button("Excluir conta", key=f"cad_del_{conta['id']}", disabled=not confirmado):
        db.deletar_conta(conn, conta["id"], apagar_lancamentos=True)
        st.success(f"Conta '{conta['nome']}' excluída.")
        st.rerun()


# ── Cartões ──────────────────────────────────────────────────────────────

def _cartoes(conn, grupo_id):
    st.markdown("#### ➕ Novo cartão")
    st.caption("As compras e faturas ficam na tela 💳 Cartão.")

    with st.form("cad_novo_cartao", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns([2, 1.2, 1.2, 1.4], vertical_alignment="bottom")
        nome = c1.text_input("Nome do cartão", placeholder="Ex: Nubank, Inter")
        fechamento = c2.number_input("Dia de fechamento", min_value=1, max_value=31, value=25)
        vencimento = c3.number_input("Dia de vencimento", min_value=1, max_value=31, value=5)
        limite = c4.number_input("Limite (R$)", min_value=0.0, step=100.0, format="%.2f")
        criar = st.form_submit_button("Cadastrar cartão", use_container_width=True)

    if criar:
        if not nome.strip():
            st.error("Informe o nome do cartão.")
        else:
            db.criar_cartao(conn, nome.strip(), int(fechamento), int(vencimento),
                            limite, grupo_id=grupo_id)
            st.success(f"Cartão '{nome.strip()}' criado.")
            st.rerun()

    cartoes = db.listar_cartoes(conn, grupo_id=grupo_id)
    st.divider()
    st.markdown("#### Cartões cadastrados")

    if not cartoes:
        st.info("Nenhum cartão cadastrado ainda.")
        return

    for cart in cartoes:
        compras = db.contar_lancamentos_cartao(conn, cart["id"])
        with st.container(border=True):
            st.markdown(
                f"**💳 {theme.esc(cart['nome_conta'])}**  \n"
                f"<span style='color:{theme.TEXT_MUTED};font-size:0.82rem;'>"
                f"fecha dia {cart['dia_fechamento']} · vence dia {cart['dia_vencimento']} · "
                f"limite {theme.moeda(cart['limite'])} · {compras} compra(s)</span>",
                unsafe_allow_html=True,
            )

            if st.checkbox("✏️ Editar / excluir", key=f"cad_cart_edit_{cart['id']}"):
                with st.form(f"cad_cart_form_{cart['id']}"):
                    e1, e2, e3, e4 = st.columns([2, 1.2, 1.2, 1.4], vertical_alignment="bottom")
                    novo_nome = e1.text_input("Nome", value=cart["nome_conta"], key=f"cad_kn_{cart['id']}")
                    novo_fech = e2.number_input(
                        "Dia de fechamento", min_value=1, max_value=31,
                        value=int(cart["dia_fechamento"]), key=f"cad_kf_{cart['id']}")
                    novo_venc = e3.number_input(
                        "Dia de vencimento", min_value=1, max_value=31,
                        value=int(cart["dia_vencimento"]), key=f"cad_kv_{cart['id']}")
                    novo_lim = e4.number_input(
                        "Limite (R$)", min_value=0.0, value=float(cart["limite"]),
                        step=100.0, format="%.2f", key=f"cad_kl_{cart['id']}")
                    salvar = st.form_submit_button("Salvar alterações", use_container_width=True)

                if salvar:
                    if not novo_nome.strip():
                        st.error("O nome não pode ficar vazio.")
                    else:
                        db.atualizar_cartao(conn, cart["id"], novo_nome.strip(),
                                            int(novo_fech), int(novo_venc), novo_lim, grupo_id)
                        st.success("Cartão atualizado.")
                        st.rerun()

                st.markdown("---")
                if compras:
                    st.caption(
                        f"Este cartão tem {compras} compra(s) lançada(s). Excluir apaga "
                        "essas compras e o histórico de faturas junto."
                    )
                    confirmado = st.checkbox(
                        "Confirmo que quero excluir o cartão e suas compras",
                        key=f"cad_kconf_{cart['id']}",
                    )
                else:
                    confirmado = True

                if st.button("Excluir cartão", key=f"cad_kdel_{cart['id']}",
                             disabled=not confirmado):
                    ok, motivo = db.deletar_cartao(conn, cart["id"], grupo_id,
                                                   apagar_lancamentos=True)
                    if ok:
                        st.success(f"Cartão '{cart['nome_conta']}' excluído.")
                        st.rerun()
                    else:
                        st.error(motivo)


# ── Categorias ───────────────────────────────────────────────────────────

def _categorias(conn, grupo_id):
    st.markdown("#### ➕ Nova categoria")
    st.caption("Serve para agrupar os lançamentos na análise por categoria e nos gráficos.")

    with st.form("cad_nova_categoria", clear_on_submit=True):
        c1, c2, c3 = st.columns([2.5, 1.5, 1], vertical_alignment="bottom")
        nome = c1.text_input("Nome", placeholder="Ex: Pet, Viagem, Escola")
        tipo = c2.selectbox("Tipo", ["despesa", "receita"],
                            format_func=lambda t: "📤 Despesa" if t == "despesa" else "📥 Receita")
        icone = c3.text_input("Ícone", value="💰", max_chars=4)
        criar = st.form_submit_button("Cadastrar categoria", use_container_width=True)

    if criar:
        if not nome.strip():
            st.error("Informe o nome da categoria.")
        else:
            db.criar_categoria(conn, nome.strip(), tipo, icone.strip() or "💰", grupo_id=grupo_id)
            st.success(f"Categoria '{nome.strip()}' criada.")
            st.rerun()

    st.divider()
    for rotulo, tipo in (("📥 Receitas", "receita"), ("📤 Despesas", "despesa")):
        categorias = db.listar_categorias(conn, tipo=tipo, grupo_id=grupo_id)
        st.markdown(f"#### {rotulo}")
        if not categorias:
            st.caption("Nenhuma nesta lista.")
            continue
        for cat in categorias:
            de_fabrica = cat["grupo_id"] is None
            usos = db.contar_lancamentos_categoria(conn, cat["id"])
            with st.container(border=True):
                c1, c2 = st.columns([3.5, 1.6], vertical_alignment="center")
                c1.markdown(f"{cat['icone']} **{theme.esc(cat['nome'])}**")
                c2.markdown(
                    f"<span style='color:{theme.TEXT_MUTED};font-size:0.8rem;'>"
                    f"{'de fábrica · ' if de_fabrica else ''}{usos} uso(s)</span>",
                    unsafe_allow_html=True,
                )

                # Item de fábrica é igual para todas as famílias: renomear aqui
                # mudaria a categoria de todo mundo.
                if de_fabrica:
                    continue

                if st.checkbox("✏️ Editar / excluir", key=f"cad_cat_edit_{cat['id']}"):
                    with st.form(f"cad_cat_form_{cat['id']}"):
                        e1, e2 = st.columns([3, 1], vertical_alignment="bottom")
                        novo_nome = e1.text_input("Nome", value=cat["nome"],
                                                  key=f"cad_gn_{cat['id']}")
                        novo_icone = e2.text_input("Ícone", value=cat["icone"],
                                                   max_chars=4, key=f"cad_gi_{cat['id']}")
                        salvar = st.form_submit_button("Salvar alterações",
                                                       use_container_width=True)
                    if salvar:
                        if not novo_nome.strip():
                            st.error("O nome não pode ficar vazio.")
                        else:
                            db.atualizar_categoria(conn, cat["id"], novo_nome.strip(),
                                                   novo_icone.strip() or "💰", grupo_id)
                            st.success("Categoria atualizada.")
                            st.rerun()

                    if st.button("Excluir categoria", key=f"cad_delcat_{cat['id']}"):
                        ok, motivo = db.deletar_categoria(conn, cat["id"], grupo_id)
                        if ok:
                            st.success("Categoria excluída.")
                            st.rerun()
                        else:
                            st.error(motivo)


# ── Formas de pagamento ──────────────────────────────────────────────────

def _formas_pagamento(conn, grupo_id):
    st.markdown("#### ➕ Nova forma de pagamento")
    st.caption("Aparece na lista ao registrar um pagamento ou recebimento.")

    with st.form("cad_nova_forma", clear_on_submit=True):
        c1, c2 = st.columns([3, 1.4], vertical_alignment="bottom")
        nome = c1.text_input("Nome", placeholder="Ex: Vale-refeição, PicPay")
        criar = c2.form_submit_button("Cadastrar", use_container_width=True)

    if criar:
        if not nome.strip():
            st.error("Informe o nome.")
        else:
            db.criar_forma_pagamento(conn, nome.strip(), grupo_id)
            st.success(f"'{nome.strip()}' cadastrada.")
            st.rerun()

    st.divider()
    st.markdown("#### Formas cadastradas")
    for forma in db.listar_formas_pagamento(conn, grupo_id=grupo_id):
        de_fabrica = forma["grupo_id"] is None
        with st.container(border=True):
            st.markdown(
                f"**{theme.esc(forma['nome'])}**"
                + (f" <span style='color:{theme.TEXT_MUTED};font-size:0.8rem;'>"
                   "· de fábrica</span>" if de_fabrica else ""),
                unsafe_allow_html=True,
            )
            if de_fabrica:
                continue

            if st.checkbox("✏️ Editar / excluir", key=f"cad_forma_edit_{forma['id']}"):
                with st.form(f"cad_forma_form_{forma['id']}"):
                    f1, f2 = st.columns([3, 1.4], vertical_alignment="bottom")
                    novo_nome = f1.text_input("Nome", value=forma["nome"],
                                              key=f"cad_fn_{forma['id']}")
                    salvar = f2.form_submit_button("Salvar", use_container_width=True)
                if salvar:
                    if not novo_nome.strip():
                        st.error("O nome não pode ficar vazio.")
                    else:
                        db.atualizar_forma_pagamento(conn, forma["id"],
                                                     novo_nome.strip(), grupo_id)
                        st.success("Atualizada.")
                        st.rerun()

                if st.button("Excluir", key=f"cad_delforma_{forma['id']}"):
                    ok, motivo = db.deletar_forma_pagamento(conn, forma["id"], grupo_id)
                    if ok:
                        st.success("Excluída.")
                        st.rerun()
                    else:
                        st.error(motivo)
