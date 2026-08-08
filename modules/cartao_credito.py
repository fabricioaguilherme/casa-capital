from datetime import date

import streamlit as st

import database as db
import theme


def render(conn, usuario):
    grupo_id = usuario["grupo_id"]
    cartoes = db.listar_cartoes(conn, grupo_id=grupo_id)

    # O cadastro do cartão mora em ⚙️ Cadastros. Aqui é só operação: compras e
    # faturas. Ter dois formulários criando cartão foi o que confundiu antes.
    if not cartoes:
        st.info("Nenhum cartão cadastrado ainda. Cadastre em **⚙️ Cadastros → 💳 Cartões**.")
        return

    contas_debito = [c for c in db.listar_contas(conn, grupo_id=grupo_id) if c["tipo"] != "cartao"]
    categorias_despesa = db.listar_categorias(conn, tipo="despesa", grupo_id=grupo_id)

    st.markdown("#### 🛒 Lançar compra no cartão")
    if not contas_debito:
        st.warning(
            "Cadastre uma conta bancária ou carteira em **⚙️ Cadastros** para indicar "
            "quem paga a fatura."
        )
    else:
        with st.container(border=True):
            with st.form("compra_cartao", clear_on_submit=True):
                c1, c2, c3 = st.columns([2, 1, 1])
                with c1:
                    descricao = st.text_input("Descrição", placeholder="Ex: Notebook",
                                              key="cc_desc")
                with c2:
                    valor_total = st.number_input("Valor total (R$)", min_value=0.0, step=10.0,
                                                  format="%.2f", key="cc_valor")
                with c3:
                    data_compra = st.date_input("Data da compra", value=date.today(),
                                                key="cc_data")

                c4, c5, c6, c7 = st.columns([1.1, 1.1, 1.1, 0.7])
                with c4:
                    cartao = st.selectbox("Cartão", cartoes,
                                          format_func=lambda c: c["nome_conta"], key="cc_cartao")
                with c5:
                    categoria = st.selectbox("Categoria", categorias_despesa,
                                             format_func=lambda c: f"{c['icone']} {c['nome']}",
                                             key="cc_cat")
                with c6:
                    conta_debito = st.selectbox("Conta que paga a fatura", contas_debito,
                                                format_func=lambda c: c["nome"], key="cc_conta")
                with c7:
                    parcelas = st.number_input("Parcelas", min_value=1, max_value=48, value=1,
                                               help="1 = à vista", key="cc_parcelas")
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
                    _, vencimento = db.ciclo_fatura(
                        data_compra.isoformat(),
                        cartao["dia_fechamento"], cartao["dia_vencimento"],
                    )
                    resumo = (f"{int(parcelas)}x de {theme.moeda(valor_parcela)}"
                              if parcelas > 1 else theme.moeda(valor_parcela))
                    st.success(
                        f"Compra lançada: {resumo}. "
                        f"Entra na fatura que vence em {theme.data_br(vencimento.isoformat())}."
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
