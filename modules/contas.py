import streamlit as st

import database as db
import theme

TIPOS = ["banco", "carteira", "cartao"]
LABEL_TIPO = {
    "banco": "🏦 Conta bancária",
    "carteira": "👛 Carteira / Dinheiro",
    "cartao": "💳 Cartão de crédito",
}


def render(conn, usuario):
    grupo_id = usuario["grupo_id"]
    contas = db.listar_contas(conn, apenas_ativas=False, grupo_id=grupo_id)

    st.markdown("#### ➕ Nova conta")
    with st.form("nova_conta_gestao", clear_on_submit=True):
        col1, col2, col3 = st.columns([2, 2, 1.5])
        with col1:
            nome = st.text_input("Nome", placeholder="Ex: Banco do Brasil, Carteira")
        with col2:
            tipo = st.selectbox("Tipo", TIPOS, format_func=lambda t: LABEL_TIPO[t])
        with col3:
            saldo_inicial = st.number_input("Saldo inicial (R$)", step=100.0, format="%.2f")
        criar = st.form_submit_button("Cadastrar conta", use_container_width=True)

    if criar:
        if not nome.strip():
            st.error("Informe o nome da conta.")
        else:
            if tipo == "cartao":
                db.criar_cartao(conn, nome.strip(), 25, 5, 0.0, grupo_id=grupo_id)
                st.success(
                    f"Cartão '{nome.strip()}' criado. Ajuste fechamento, vencimento e limite na aba Cartão."
                )
            else:
                db.criar_conta(conn, nome.strip(), tipo, saldo_inicial, grupo_id=grupo_id)
                st.success(f"Conta '{nome.strip()}' criada.")
            st.rerun()

    st.divider()

    if not contas:
        st.info("Nenhuma conta cadastrada ainda. Use o formulário acima para começar.")
        return

    st.markdown("#### Contas cadastradas")

    tem_conta_movimentavel = any(c["tipo"] != "cartao" for c in contas)
    if not tem_conta_movimentavel:
        st.warning(
            "Você só tem cartões cadastrados. Cadastre uma conta bancária ou carteira "
            "(ou corrija o tipo abaixo) para poder lançar movimentações no Fluxo de Caixa."
        )

    for c in contas:
        qtd_lanc = db.contar_lancamentos_conta(conn, c["id"])
        saldo = db.saldo_atual_conta(conn, c["id"])
        with st.container(border=True):
            cab1, cab2 = st.columns([3, 2])
            cab1.markdown(
                f"**{LABEL_TIPO[c['tipo']]} · {theme.esc(c['nome'])}**  \n"
                f"<span style='color:{theme.TEXT_MUTED};font-size:0.82rem;'>"
                f"{qtd_lanc} lançamento(s) vinculado(s)</span>",
                unsafe_allow_html=True,
            )
            cab2.markdown(
                f"<div style='text-align:right;font-size:1.1rem;font-weight:700;"
                f"color:{theme.DEEP_GREEN};'>{theme.moeda(saldo)}</div>",
                unsafe_allow_html=True,
            )

            if st.checkbox("✏️ Editar / excluir", key=f"edit_toggle_{c['id']}"):
                with st.form(f"editar_conta_{c['id']}"):
                    e1, e2, e3 = st.columns([2, 2, 1.5])
                    with e1:
                        novo_nome = st.text_input("Nome", value=c["nome"], key=f"nome_{c['id']}")
                    with e2:
                        novo_tipo = st.selectbox(
                            "Tipo", TIPOS, index=TIPOS.index(c["tipo"]),
                            format_func=lambda t: LABEL_TIPO[t], key=f"tipo_{c['id']}",
                        )
                    with e3:
                        novo_saldo = st.number_input(
                            "Saldo inicial (R$)", value=float(c["saldo_inicial"]),
                            step=100.0, format="%.2f", key=f"saldo_{c['id']}",
                        )
                    salvar = st.form_submit_button("Salvar alterações", use_container_width=True)

                if salvar:
                    if not novo_nome.strip():
                        st.error("O nome não pode ficar vazio.")
                    else:
                        db.atualizar_conta(conn, c["id"], novo_nome.strip(), novo_tipo, novo_saldo)
                        st.success("Conta atualizada.")
                        st.rerun()

                st.markdown("---")
                if qtd_lanc > 0:
                    st.caption(
                        f"Esta conta tem {qtd_lanc} lançamento(s). Excluir a conta apaga "
                        "esses lançamentos também — não há como desfazer."
                    )
                    confirmar = st.checkbox(
                        "Confirmo que quero excluir a conta e seus lançamentos",
                        key=f"conf_{c['id']}",
                    )
                else:
                    confirmar = True

                if st.button("Excluir conta", key=f"del_conta_{c['id']}", disabled=not confirmar):
                    db.deletar_conta(conn, c["id"], apagar_lancamentos=True)
                    st.success(f"Conta '{c['nome']}' excluída.")
                    st.rerun()
