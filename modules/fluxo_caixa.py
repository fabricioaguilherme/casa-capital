from datetime import date

import streamlit as st

import database as db
import theme
from modules import anexos


def render(conn, usuario):
    contas = db.listar_contas(conn)
    contas_nao_cartao = [c for c in contas if c["tipo"] != "cartao"]
    categorias = db.listar_categorias(conn)

    if not contas_nao_cartao:
        st.warning(
            "Cadastre pelo menos uma conta bancária ou carteira na aba **🏦 Contas** "
            "antes de lançar movimentações."
        )
        return

    st.markdown("#### ➕ Novo lançamento")
    with st.container(border=True):
        tipo = st.radio(
            "Tipo", ["saida", "entrada"],
            format_func=lambda x: "Saída (despesa)" if x == "saida" else "Entrada (receita)",
            horizontal=True, key="fc_tipo_novo",
        )
        tipo_categoria = "despesa" if tipo == "saida" else "receita"
        cats_filtradas = [c for c in categorias if c["tipo"] == tipo_categoria]

        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            descricao = st.text_input("Descrição", key="fc_descricao", placeholder="Ex: Supermercado")
        with c2:
            valor = st.number_input("Valor (R$)", min_value=0.0, step=10.0, format="%.2f", key="fc_valor")
        with c3:
            data_lanc = st.date_input("Data", value=date.today(), key="fc_data")

        c4, c5, c6, c7 = st.columns(4)
        with c4:
            conta = st.selectbox("Conta", contas_nao_cartao, format_func=lambda c: c["nome"], key="fc_conta_novo")
        with c5:
            categoria = st.selectbox("Categoria", cats_filtradas, format_func=lambda c: f"{c['icone']} {c['nome']}", key="fc_categoria")
        with c6:
            rotulo_forma = "Forma de pagamento" if tipo == "saida" else "Forma de recebimento"
            forma = st.selectbox(rotulo_forma, ["—"] + db.FORMAS_PAGAMENTO, key="fc_forma")
        with c7:
            status = st.selectbox("Status", ["pago", "pendente"], format_func=lambda s: "Pago/Recebido" if s == "pago" else "Pendente", key="fc_status")

        c8, c9, _ = st.columns([1.1, 1.2, 1.7])
        with c8:
            recorrente = st.checkbox("Repetir todo mês", key="fc_recorrente")
        with c9:
            repeticoes = st.number_input("Quantas vezes (incluindo esta)", min_value=2, max_value=60, value=12, key="fc_repeticoes") if recorrente else 1

        if st.button("Salvar lançamento", use_container_width=True, key="fc_salvar", type="primary"):
            if not descricao.strip():
                st.error("Informe a descrição.")
            elif valor <= 0:
                st.error("Informe um valor maior que zero.")
            else:
                db.criar_lancamento(
                    conn, data_lanc.isoformat(), conta["id"], categoria["id"], descricao.strip(),
                    valor, tipo, status, usuario["id"],
                    recorrente=recorrente, repeticoes=int(repeticoes) if recorrente else 1,
                    forma_pagamento=None if forma == "—" else forma,
                )
                st.success("Lançamento salvo.")
                st.rerun()

    st.divider()

    col1, col2, col3 = st.columns(3)
    with col1:
        data_inicio = st.date_input("De", value=date.today().replace(day=1), key="fc_inicio")
    with col2:
        data_fim = st.date_input("Até", value=date.today(), key="fc_fim")
    with col3:
        # filtro por id (nomes de conta podem se repetir, ex.: banco e cartão homônimos)
        opcoes = [("Todas", None)] + [(c["nome"], c["id"]) for c in contas_nao_cartao]
        filtro = st.selectbox("Conta", opcoes, format_func=lambda o: o[0], key="fc_conta")
    conta_id = filtro[1]

    lancamentos = db.listar_lancamentos(
        conn, data_inicio=data_inicio.isoformat(), data_fim=data_fim.isoformat(),
        conta_id=conta_id, apenas_sem_cartao=True,
    )

    if not lancamentos:
        st.info("Nenhum lançamento no período selecionado.")
        return

    entradas = sum(l["valor"] for l in lancamentos if l["tipo"] == "entrada")
    saidas = sum(l["valor"] for l in lancamentos if l["tipo"] == "saida")

    m1, m2, m3 = st.columns(3)
    m1.metric("Entradas", f"{theme.moeda(entradas)}")
    m2.metric("Saídas", f"{theme.moeda(saidas)}")
    m3.metric("Saldo do período", f"{theme.moeda(entradas - saidas)}")

    st.markdown("##### Lançamentos")
    qtd_anexos = db.contar_anexos(conn, "lancamento", [l["id"] for l in lancamentos])
    for l in lancamentos:
        sinal = "+" if l["tipo"] == "entrada" else "-"
        cor = theme.GREEN if l["tipo"] == "entrada" else theme.RED
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([3, 1.6, 1.8, 1.6])
            detalhe = f"{l['nome_categoria']} · {l['nome_conta']}"
            if l.get("forma_pagamento"):
                detalhe += f" · {l['forma_pagamento']}"
            c1.markdown(
                f"**{l['icone_categoria']} {theme.esc(l['descricao'])}**  \n"
                f"<span style='color:{theme.TEXT_MUTED};font-size:0.8rem;'>{theme.esc(detalhe)}</span>",
                unsafe_allow_html=True,
            )
            c2.markdown(
                f"<span style='color:{cor};font-weight:700;'>{sinal} {theme.moeda(l['valor'])}</span>",
                unsafe_allow_html=True,
            )
            c3.markdown(
                f"<span style='color:{theme.TEXT_MUTED};'>{theme.data_br(l['data'])}<br>"
                f"{'✅ Pago' if l['status'] == 'pago' else '⏳ Pendente'}</span>",
                unsafe_allow_html=True,
            )
            with c4:
                if l["status"] == "pendente":
                    if st.button("Marcar pago", key=f"pg_{l['id']}", use_container_width=True):
                        db.marcar_status(conn, l["id"], "pago")
                        st.rerun()
                if st.button("Excluir", key=f"del_{l['id']}", use_container_width=True):
                    db.deletar_lancamento(conn, l["id"], apenas_futuras=False)
                    st.rerun()
                if l["recorrencia_id"] and st.button(
                    "Excluir futuras", key=f"delf_{l['id']}", use_container_width=True
                ):
                    db.deletar_lancamento(conn, l["id"], apenas_futuras=True)
                    st.rerun()

            anexos.alternar(
                conn, usuario, "lancamento", l["id"],
                quantidade=qtd_anexos.get(l["id"], 0),
            )
