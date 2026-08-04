from datetime import date, timedelta

import streamlit as st

import database as db
import theme

_br_data = theme.data_br


def _formulario_nova(conn, usuario, tipo, rotulo_acao):
    """Formulário sempre visível para cadastrar uma conta a pagar/receber (lançamento pendente)."""
    contas = [c for c in db.listar_contas(conn, grupo_id=usuario["grupo_id"]) if c["tipo"] != "cartao"]
    if not contas:
        st.warning(
            "Cadastre uma conta bancária ou carteira na aba **🏦 Contas** para poder lançar."
        )
        return

    tipo_categoria = "despesa" if tipo == "saida" else "receita"
    categorias = db.listar_categorias(conn, tipo=tipo_categoria)

    rotulo_forma = "Forma de pagamento" if tipo == "saida" else "Forma de recebimento"

    st.markdown(f"#### ➕ Nova conta {rotulo_acao}")
    with st.container(border=True):
        with st.form(f"nova_cpr_{tipo}", clear_on_submit=True):
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1:
                descricao = st.text_input(
                    "Descrição",
                    placeholder="Ex: Aluguel" if tipo == "saida" else "Ex: Salário",
                    key=f"cpr_desc_{tipo}",
                )
            with c2:
                valor = st.number_input(
                    "Valor (R$)", min_value=0.0, step=10.0, format="%.2f", key=f"cpr_val_{tipo}"
                )
            with c3:
                vencimento = st.date_input(
                    "Vencimento", value=date.today(), key=f"cpr_venc_{tipo}"
                )

            c4, c5, c6, c7 = st.columns([1.1, 1.1, 1.1, 0.7])
            with c4:
                conta = st.selectbox(
                    "Conta", contas, format_func=lambda c: c["nome"], key=f"cpr_conta_{tipo}"
                )
            with c5:
                categoria = st.selectbox(
                    "Categoria", categorias,
                    format_func=lambda c: f"{c['icone']} {c['nome']}", key=f"cpr_cat_{tipo}",
                )
            with c6:
                forma = st.selectbox(
                    rotulo_forma, ["—"] + db.FORMAS_PAGAMENTO, key=f"cpr_forma_{tipo}",
                )
            with c7:
                repetir = st.number_input(
                    "Repetir (meses)", min_value=1, max_value=60, value=1,
                    help="1 = só este mês", key=f"cpr_rep_{tipo}",
                )
            enviar = st.form_submit_button(
                f"Cadastrar conta {rotulo_acao}", use_container_width=True
            )

        if enviar:
            if not descricao.strip():
                st.error("Informe a descrição.")
            elif valor <= 0:
                st.error("Informe um valor maior que zero.")
            else:
                db.criar_lancamento(
                    conn, vencimento.isoformat(), conta["id"], categoria["id"],
                    descricao.strip(), valor, tipo, "pendente", usuario["id"],
                    recorrente=(repetir > 1), repeticoes=int(repetir),
                    forma_pagamento=None if forma == "—" else forma,
                    grupo_id=usuario["grupo_id"],
                )
                st.success(
                    f"Cadastrado: {descricao.strip()}"
                    + (f" — {int(repetir)} meses" if repetir > 1 else "")
                )
                st.rerun()


def _lista_pendentes(conn, usuario, tipo, titulo, vazio_msg):
    hoje = date.today()
    grupo_id = usuario["grupo_id"]

    # Totais consideram TUDO em aberto, não só a janela do filtro
    todos = db.listar_lancamentos(
        conn, status="pendente", tipo=tipo, apenas_sem_cartao=True, grupo_id=grupo_id,
    )
    atrasados = [i for i in todos if i["data"] < hoje.isoformat()]

    st.markdown("#### Em aberto")
    m1, m2, m3 = st.columns(3)
    m1.metric("Total em aberto", theme.moeda(sum(i["valor"] for i in todos)))
    m2.metric(
        "Vencidas", theme.moeda(sum(i["valor"] for i in atrasados)),
        delta=f"{len(atrasados)} conta(s)" if atrasados else None,
        delta_color="inverse",
    )
    m3.metric("Lançamentos", f"{len(todos)}")

    if not todos:
        st.info(vazio_msg)
        return

    st.write("")
    col1, col2 = st.columns([1, 2])
    with col1:
        so_vencidas = st.checkbox("Só vencidas / hoje", key=f"venc_{tipo}")
    with col2:
        horizonte = st.slider(
            "Mostrar vencimentos até (dias)", 7, 365, 90, step=7, key=f"hor_{tipo}"
        )

    data_fim = hoje if so_vencidas else hoje + timedelta(days=horizonte)
    itens = [i for i in todos if i["data"] <= data_fim.isoformat()]

    if not itens:
        proximo = min(todos, key=lambda i: i["data"])
        st.info(
            f"Nada vence nesse período. O próximo vencimento é "
            f"**{theme.data_br(proximo['data'])}** — aumente o filtro acima para vê-lo."
        )
        return

    if len(itens) < len(todos):
        st.caption(f"Mostrando {len(itens)} de {len(todos)} lançamentos em aberto.")

    acao = "Recebido" if tipo == "entrada" else "Pago"
    for i in itens:
        atrasado = i["data"] < hoje.isoformat()
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([3, 1.6, 1.8, 1.4])
            detalhe = f"{i['nome_categoria']} · {i['nome_conta']}"
            if i.get("forma_pagamento"):
                detalhe += f" · {i['forma_pagamento']}"
            c1.markdown(
                f"**{i['icone_categoria']} {theme.esc(i['descricao'])}**  \n"
                f"<span style='color:{theme.TEXT_MUTED};font-size:0.8rem;'>{theme.esc(detalhe)}</span>",
                unsafe_allow_html=True,
            )
            c2.markdown(f"**{theme.moeda(i['valor'])}**")
            if atrasado:
                c3.markdown(
                    f"<span style='color:{theme.RED};font-weight:600;'>"
                    f"⚠️ Venceu {_br_data(i['data'])}</span>",
                    unsafe_allow_html=True,
                )
            else:
                c3.markdown(
                    f"<span style='color:{theme.TEXT_MUTED};'>Vence {_br_data(i['data'])}</span>",
                    unsafe_allow_html=True,
                )
            with c4:
                if st.button(acao, key=f"cp_{tipo}_{i['id']}", use_container_width=True, type="primary"):
                    db.marcar_status(conn, i["id"], "pago")
                    st.rerun()
                if st.button("Excluir", key=f"cpdel_{tipo}_{i['id']}", use_container_width=True):
                    db.deletar_lancamento(conn, i["id"])
                    st.rerun()


def render_a_pagar(conn, usuario):
    _formulario_nova(conn, usuario, "saida", "a pagar")
    st.divider()
    _lista_pendentes(conn, usuario, "saida", "📤 Contas a Pagar", "Nenhuma conta a pagar pendente no período.")


def render_a_receber(conn, usuario):
    _formulario_nova(conn, usuario, "entrada", "a receber")
    st.divider()
    _lista_pendentes(conn, usuario, "entrada", "📥 Contas a Receber", "Nenhuma conta a receber pendente no período.")
