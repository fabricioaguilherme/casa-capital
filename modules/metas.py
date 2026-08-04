from datetime import date

import streamlit as st

import database as db
import theme


def render(conn, usuario):
    grupo_id = usuario["grupo_id"]
    st.markdown("#### ➕ Nova meta")
    with st.container(border=True):
        with st.form("nova_meta", clear_on_submit=True):
            nome = st.text_input("Nome da meta", placeholder="Ex: Reserva de emergência, Viagem")
            col1, col2 = st.columns(2)
            with col1:
                valor_alvo = st.number_input("Valor alvo (R$)", min_value=0.0, step=100.0, format="%.2f")
            with col2:
                data_alvo = st.date_input(
                    "Data alvo", value=date.today().replace(year=date.today().year + 1)
                )
            criar = st.form_submit_button("Criar meta", use_container_width=True)
        if criar:
            if not nome.strip():
                st.error("Informe o nome da meta.")
            elif valor_alvo <= 0:
                st.error("Informe um valor alvo maior que zero.")
            else:
                db.criar_meta(conn, nome.strip(), valor_alvo, data_alvo.isoformat(), usuario["id"], grupo_id=grupo_id)
                st.success("Meta criada.")
                st.rerun()

    metas = db.listar_metas(conn, grupo_id=grupo_id)
    if not metas:
        st.info("Nenhuma meta cadastrada ainda. Use o formulário acima.")
        return

    st.divider()
    st.markdown("#### Suas metas")

    for m in metas:
        progresso = min(m["valor_atual"] / m["valor_alvo"], 1.0) if m["valor_alvo"] else 0
        falta = max(m["valor_alvo"] - m["valor_atual"], 0)
        with st.container(border=True):
            st.markdown(
                f"**{theme.esc(m['nome'])}**  \n"
                f"<span style='color:{theme.TEXT_MUTED};font-size:0.85rem;'>"
                f"{theme.moeda(m['valor_atual'])} de {theme.moeda(m['valor_alvo'])} "
                f"· faltam {theme.moeda(falta)} · até {m['data_alvo']}</span>",
                unsafe_allow_html=True,
            )
            st.progress(progresso, text=f"{progresso * 100:.0f}%")
            col1, col2, col3 = st.columns([2, 1, 1])
            novo_valor = col1.number_input(
                "Valor acumulado (R$)", value=float(m["valor_atual"]),
                step=100.0, format="%.2f", key=f"meta_{m['id']}",
            )
            if col2.button("Atualizar", key=f"upd_meta_{m['id']}", use_container_width=True):
                db.atualizar_meta_progresso(conn, m["id"], novo_valor)
                st.rerun()
            if col3.button("Excluir", key=f"del_meta_{m['id']}", use_container_width=True):
                db.deletar_meta(conn, m["id"])
                st.rerun()
