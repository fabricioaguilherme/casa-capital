import plotly.express as px
import streamlit as st

import database as db
import theme

TIPOS_INVESTIMENTO = ["Renda Fixa", "Ações", "Fundos Imobiliários", "Fundos", "Cripto", "Previdência", "Outro"]


def render(conn, usuario):
    grupo_id = usuario["grupo_id"]
    st.markdown("#### ➕ Adicionar investimento")
    with st.container(border=True):
        with st.form("novo_investimento", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                nome = st.text_input("Nome", placeholder="Ex: Tesouro Selic, XPML11, Bitcoin")
                tipo = st.selectbox("Tipo", TIPOS_INVESTIMENTO)
            with col2:
                valor_aportado = st.number_input("Valor total aportado (R$)", min_value=0.0, step=100.0, format="%.2f")
                valor_atual = st.number_input("Valor atual da posição (R$)", min_value=0.0, step=100.0, format="%.2f")
            criar = st.form_submit_button("Salvar investimento", use_container_width=True)
        if criar:
            if not nome.strip():
                st.error("Informe o nome do investimento.")
            else:
                db.criar_investimento(conn, nome.strip(), tipo, valor_aportado, valor_atual, usuario["id"], grupo_id=grupo_id)
                st.success("Investimento adicionado.")
                st.rerun()

    investimentos = db.listar_investimentos(conn, grupo_id=grupo_id)
    if not investimentos:
        st.info("Nenhum investimento cadastrado ainda. Use o formulário acima.")
        return

    st.divider()

    total_aportado = sum(i["valor_aportado"] for i in investimentos)
    total_atual = sum(i["valor_atual"] for i in investimentos)
    rentabilidade = ((total_atual - total_aportado) / total_aportado * 100) if total_aportado else 0

    m1, m2, m3 = st.columns(3)
    m1.metric("Total aportado", f"{theme.moeda(total_aportado)}")
    m2.metric("Valor atual da carteira", f"{theme.moeda(total_atual)}")
    m3.metric("Rentabilidade", f"{rentabilidade:+.1f}%")

    col1, col2 = st.columns([3, 2])
    with col1:
        st.markdown("##### Sua carteira")
        for i in investimentos:
            ganho = i["valor_atual"] - i["valor_aportado"]
            pct = (ganho / i["valor_aportado"] * 100) if i["valor_aportado"] else 0
            cor = theme.GREEN if ganho >= 0 else theme.RED
            with st.container(border=True):
                st.markdown(
                    f"**{theme.esc(i['nome'])}**  \n"
                    f"<span style='color:{theme.TEXT_MUTED};font-size:0.8rem;'>{i['tipo']} · "
                    f"aportado {theme.moeda(i['valor_aportado'])}</span>  "
                    f"<span style='color:{cor};font-weight:700;'>{pct:+.1f}%</span>",
                    unsafe_allow_html=True,
                )
                c1, c2, c3 = st.columns([2, 1, 1])
                novo_valor = c1.number_input(
                    "Valor atual (R$)", value=float(i["valor_atual"]),
                    step=100.0, format="%.2f", key=f"inv_{i['id']}",
                )
                if c2.button("Atualizar", key=f"upd_inv_{i['id']}", use_container_width=True):
                    db.atualizar_investimento(conn, i["id"], novo_valor)
                    st.rerun()
                if c3.button("Excluir", key=f"del_inv_{i['id']}", use_container_width=True):
                    db.deletar_investimento(conn, i["id"])
                    st.rerun()
    with col2:
        with st.container(border=True):
            st.markdown("##### Alocação por tipo")
            por_tipo = {}
            for i in investimentos:
                por_tipo[i["tipo"]] = por_tipo.get(i["tipo"], 0) + i["valor_atual"]
            fig = px.pie(
                values=list(por_tipo.values()), names=list(por_tipo.keys()), hole=0.62,
                color_discrete_sequence=theme.CHART_SEQUENCE,
            )
            theme.apply_layout(fig)
            st.plotly_chart(fig, use_container_width=True)
