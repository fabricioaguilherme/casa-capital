from datetime import date

import streamlit as st

import database as db
import theme


def render(conn, usuario):
    grupo_id = usuario["grupo_id"]
    cartoes = db.listar_cartoes(conn, grupo_id=grupo_id)

    st.markdown("#### ➕ Cadastrar cartão")
    with st.container(border=True):
        with st.form("novo_cartao", clear_on_submit=True):
            nome = st.text_input("Nome do cartão", placeholder="Ex: Nubank, Inter")
            col1, col2, col3 = st.columns(3)
            with col1:
                dia_fechamento = st.number_input("Dia de fechamento", min_value=1, max_value=31, value=25)
            with col2:
                dia_vencimento = st.number_input("Dia de vencimento", min_value=1, max_value=31, value=5)
            with col3:
                limite = st.number_input("Limite (R$)", min_value=0.0, step=100.0, format="%.2f")
            criar = st.form_submit_button("Cadastrar cartão", use_container_width=True)
        if criar:
            if not nome.strip():
                st.error("Informe o nome do cartão.")
            else:
                db.criar_cartao(conn, nome.strip(), int(dia_fechamento), int(dia_vencimento), limite, grupo_id=grupo_id)
                st.success(f"Cartão '{nome.strip()}' cadastrado.")
                st.rerun()

    if not cartoes:
        st.info("Nenhum cartão cadastrado ainda. Use o formulário acima.")
        return

    contas_debito = [c for c in db.listar_contas(conn, grupo_id=grupo_id) if c["tipo"] != "cartao"]
    categorias_despesa = db.listar_categorias(conn, tipo="despesa")

    st.divider()
    st.markdown("#### 🛒 Lançar compra no cartão")
    if not contas_debito:
        st.warning(
            "Cadastre uma conta bancária ou carteira na aba **🏦 Contas** para indicar "
            "quem paga a fatura."
        )
    else:
        with st.container(border=True):
            with st.form("compra_cartao", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    cartao = st.selectbox("Cartão", cartoes, format_func=lambda c: c["nome_conta"])
                    descricao = st.text_input("Descrição da compra", placeholder="Ex: Notebook")
                    valor_total = st.number_input("Valor total (R$)", min_value=0.0, step=10.0, format="%.2f")
                with col2:
                    categoria = st.selectbox("Categoria", categorias_despesa, format_func=lambda c: f"{c['icone']} {c['nome']}")
                    parcelas = st.number_input("Parcelas", min_value=1, max_value=48, value=1)
                    data_compra = st.date_input("Data da compra", value=date.today())
                conta_debito = st.selectbox(
                    "Conta que vai pagar a fatura", contas_debito, format_func=lambda c: c["nome"],
                )
                enviar = st.form_submit_button("Salvar compra", use_container_width=True)

            if enviar:
                if not descricao.strip():
                    st.error("Informe a descrição da compra.")
                elif valor_total <= 0:
                    st.error("Informe um valor maior que zero.")
                else:
                    valor_parcela = round(valor_total / parcelas, 2)
                    db.criar_lancamento(
                        conn, data_compra.isoformat(), conta_debito["id"], categoria["id"],
                        descricao.strip(), valor_parcela, "saida", "pendente", usuario["id"],
                        cartao_id=cartao["id"], parcelas=int(parcelas),
                        forma_pagamento="Cartão de crédito",
                        grupo_id=grupo_id,
                    )
                    st.success(
                        f"Compra lançada em {int(parcelas)}x de {theme.moeda(valor_parcela)}."
                    )
                    st.rerun()

    st.divider()
    st.markdown("##### Fatura por mês")
    col1, col2, col3 = st.columns(3)
    with col1:
        cartao_sel = st.selectbox("Cartão", cartoes, format_func=lambda c: c["nome_conta"], key="fatura_cartao")
    with col2:
        mes = st.selectbox("Mês", list(range(1, 13)), index=date.today().month - 1, key="fatura_mes")
    with col3:
        ano = st.number_input("Ano", min_value=2020, max_value=2100, value=date.today().year, key="fatura_ano")

    itens = db.fatura_cartao(conn, cartao_sel["id"], mes, int(ano))
    if not itens:
        st.info("Sem lançamentos nesse mês para este cartão.")
        return

    total = sum(i["valor"] for i in itens)
    st.metric(f"Total da fatura {mes:02d}/{ano}", f"{theme.moeda(total)}")
    for i in itens:
        c1, c2 = st.columns([4, 1])
        c1.write(f"{i['descricao']} — {i['data']}")
        c2.write(f"{theme.moeda(i['valor'])}")
