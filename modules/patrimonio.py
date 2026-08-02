import plotly.express as px
import streamlit as st

import database as db
import theme

CATEGORIAS_ATIVO = ["Imóvel", "Veículo", "Reserva de Emergência", "Outro Bem"]
CATEGORIAS_PASSIVO = ["Financiamento", "Empréstimo", "Cartão (dívida)", "Outra Dívida"]


def render(conn, usuario):
    st.markdown("#### ➕ Adicionar bem ou dívida")
    with st.container(border=True):
        tipo = st.radio("Tipo", ["ativo", "passivo"], format_func=lambda t: "Ativo (bem)" if t == "ativo" else "Passivo (dívida)", horizontal=True, key="pat_tipo")
        opcoes = CATEGORIAS_ATIVO if tipo == "ativo" else CATEGORIAS_PASSIVO

        col1, col2 = st.columns(2)
        with col1:
            nome = st.text_input("Nome", placeholder="Ex: Apartamento Centro, Financiamento do carro", key="pat_nome")
        with col2:
            categoria = st.selectbox("Categoria", opcoes, key="pat_categoria")
            valor = st.number_input("Valor atual (R$)", min_value=0.0, step=1000.0, format="%.2f", key="pat_valor")
        if st.button("Salvar item", use_container_width=True, key="pat_salvar", type="primary"):
            if not nome.strip():
                st.error("Informe o nome do item.")
            else:
                db.criar_patrimonio_item(conn, nome.strip(), tipo, categoria, valor, usuario["id"])
                st.success("Item adicionado.")
                st.rerun()

    itens = db.listar_patrimonio(conn)
    ativos = [i for i in itens if i["tipo"] == "ativo"]
    passivos = [i for i in itens if i["tipo"] == "passivo"]

    total_ativos = sum(i["valor_atual"] for i in ativos)
    total_passivos = sum(i["valor_atual"] for i in passivos)
    saldo_contas = db.saldo_total(conn)
    total_investido = sum(i["valor_atual"] for i in db.listar_investimentos(conn))
    patrimonio_liquido = total_ativos + total_investido + saldo_contas - total_passivos

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Bens", f"{theme.moeda(total_ativos)}")
    m2.metric("Dívidas", f"{theme.moeda(total_passivos)}")
    m3.metric("Saldo em contas + investimentos", f"{theme.moeda(saldo_contas + total_investido)}")
    m4.metric("Patrimônio líquido", f"{theme.moeda(patrimonio_liquido)}")

    def _lista_itens(lista, prefixo, titulo):
        st.markdown(f"##### {titulo}")
        if not lista:
            st.caption("Nada cadastrado nesta categoria.")
            return
        for i in lista:
            with st.container(border=True):
                st.markdown(
                    f"**{theme.esc(i['nome'])}**  \n"
                    f"<span style='color:{theme.TEXT_MUTED};font-size:0.8rem;'>"
                    f"{i['categoria']} · atualizado em {i['data_atualizacao']}</span>",
                    unsafe_allow_html=True,
                )
                c1, c2, c3 = st.columns([2, 1, 1])
                novo_valor = c1.number_input(
                    "Valor atual (R$)", value=float(i["valor_atual"]),
                    step=1000.0, format="%.2f", key=f"{prefixo}_{i['id']}",
                )
                if c2.button("Atualizar", key=f"upd_{prefixo}_{i['id']}", use_container_width=True):
                    db.atualizar_patrimonio_item(conn, i["id"], novo_valor)
                    st.rerun()
                if c3.button("Excluir", key=f"del_{prefixo}_{i['id']}", use_container_width=True):
                    db.deletar_patrimonio_item(conn, i["id"])
                    st.rerun()

    if ativos or passivos:
        col1, col2 = st.columns(2)
        with col1:
            _lista_itens(ativos, "at", "Bens (ativos)")
        with col2:
            _lista_itens(passivos, "ps", "Dívidas (passivos)")

        with st.container(border=True):
            st.markdown("##### Composição do patrimônio bruto")
            composicao = {"Contas + Investimentos": saldo_contas + total_investido}
            for i in ativos:
                composicao[i["nome"]] = i["valor_atual"]
            fig = px.pie(
                values=list(composicao.values()), names=list(composicao.keys()), hole=0.62,
                color_discrete_sequence=theme.CHART_SEQUENCE,
            )
            theme.apply_layout(fig)
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Nenhum bem ou dívida cadastrado ainda.")
