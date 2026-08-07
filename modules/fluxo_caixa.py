"""Fluxo de Caixa — quanto tenho, quanto entra, quanto sai, e como termino.

Quatro visões que respondem perguntas diferentes:

  Saldo atual  onde o dinheiro está parado hoje
  Previsto     o que já está marcado para entrar e sair
  Projeção     como o saldo termina, e em que dia ele fura o zero
  Lançamentos  a lista, e o lançamento avulso (exceção — ver abaixo)

O caminho normal de registrar conta é **A Pagar / A Receber**. O formulário
daqui existe só para o que já aconteceu e não estava previsto: o troco do
mercado, o dinheiro que apareceu. Por isso ele vive fechado, atrás de um
clique, e avisa qual é o caminho certo.
"""

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import database as db
import theme
from modules import anexos

VISOES = ["📊  Saldo atual", "📅  Previsto", "📈  Projeção", "📋  Lançamentos"]

JANELAS = [(7, "7 dias"), (30, "30 dias"), (90, "90 dias")]

GRANULARIDADES = {"Diário": "diario", "Semanal": "semanal", "Mensal": "mensal"}


def render(conn, usuario):
    grupo_id = usuario["grupo_id"]
    contas = [c for c in db.listar_contas(conn, grupo_id=grupo_id) if c["tipo"] != "cartao"]

    if not contas:
        st.warning(
            "Cadastre pelo menos uma conta bancária ou carteira em **⚙️ Cadastros** "
            "antes de usar o fluxo de caixa."
        )
        return

    visao = st.radio("Visão", VISOES, horizontal=True, key="fc_visao",
                     label_visibility="collapsed")
    st.divider()

    if visao == VISOES[0]:
        _saldo_atual(conn, grupo_id)
    elif visao == VISOES[1]:
        _previsto(conn, grupo_id, contas)
    elif visao == VISOES[2]:
        _projecao(conn, grupo_id, contas)
    else:
        _lancamentos(conn, usuario, contas)


# ── Saldo atual ──────────────────────────────────────────────────────────

def _saldo_atual(conn, grupo_id):
    n = db.saldo_por_natureza(conn, grupo_id=grupo_id)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("👛 Caixa", theme.moeda(n["caixa"]), help="Dinheiro em espécie e carteiras.")
    c2.metric("🏦 Bancos", theme.moeda(n["bancos"]), help="Contas correntes e poupanças.")
    c3.metric("📈 Aplicações", theme.moeda(n["aplicacoes"]),
              help="Investimentos. Não entram no disponível porque nem sempre dá para resgatar hoje.")
    c4.metric("💰 Disponível hoje", theme.moeda(n["disponivel"]),
              help="Caixa + Bancos. É com isto que você paga as contas desta semana.")

    st.caption(
        f"Patrimônio líquido em dinheiro: **{theme.moeda(n['total'])}** "
        "(disponível + aplicações). Cartão de crédito não aparece aqui — ele é dívida, "
        "não é onde o dinheiro está."
    )

    st.divider()
    st.markdown("##### Por conta")
    for conta in n["contas"]:
        rotulo = "👛" if conta["tipo"] == "carteira" else "🏦"
        with st.container(border=True):
            e, d = st.columns([3, 2])
            e.markdown(f"{rotulo} **{theme.esc(conta['nome'])}**")
            cor = theme.DEEP_GREEN if conta["saldo"] >= 0 else theme.RED
            d.markdown(
                f"<div style='text-align:right;font-weight:700;color:{cor};'>"
                f"{theme.moeda(conta['saldo'])}</div>",
                unsafe_allow_html=True,
            )


# ── Previsto ─────────────────────────────────────────────────────────────

def _previsto(conn, grupo_id, contas):
    conta_id = _filtro_conta(conn, contas, chave="fc_prev_conta")

    st.markdown("##### O que já está marcado para acontecer")
    colunas = st.columns(3)
    for coluna, (dias, rotulo) in zip(colunas, JANELAS):
        entradas, saidas = db.previsto_ate(conn, dias, grupo_id=grupo_id, conta_id=conta_id)
        with coluna:
            with st.container(border=True):
                st.markdown(f"**Próximos {rotulo}**")
                st.markdown(
                    f"<span style='color:{theme.GREEN};font-weight:700;'>"
                    f"+ {theme.moeda(entradas)}</span><br>"
                    f"<span style='color:{theme.RED};font-weight:700;'>"
                    f"− {theme.moeda(saidas)}</span>",
                    unsafe_allow_html=True,
                )
                liquido = entradas - saidas
                cor = theme.DEEP_GREEN if liquido >= 0 else theme.RED
                st.markdown(
                    f"<div style='border-top:1px solid {theme.BORDER};margin-top:6px;"
                    f"padding-top:6px;font-weight:700;color:{cor};'>"
                    f"{theme.moeda(liquido)}</div>",
                    unsafe_allow_html=True,
                )

    st.caption(
        "Conta vencida e ainda não paga entra desde a primeira janela — ela continua "
        "sendo dinheiro que vai sair."
    )

    st.divider()
    dias = st.select_slider(
        "Detalhar por categoria em", options=[d for d, _ in JANELAS],
        value=30, format_func=lambda d: f"{d} dias", key="fc_prev_dias",
    )

    esq, dir_ = st.columns(2)
    for coluna, tipo, titulo, cor in (
        (esq, "saida", "📤 Saídas previstas", theme.RED),
        (dir_, "entrada", "📥 Entradas previstas", theme.GREEN),
    ):
        with coluna:
            st.markdown(f"##### {titulo}")
            linhas = db.previsto_por_categoria(conn, dias, tipo, grupo_id=grupo_id,
                                               conta_id=conta_id)
            if not linhas:
                st.caption("Nada previsto nesta janela.")
                continue
            total = sum(l["total"] for l in linhas)
            for l in linhas:
                fatia = (l["total"] / total * 100) if total else 0
                with st.container(border=True):
                    a, b = st.columns([3, 2])
                    a.markdown(
                        f"{l['icone']} **{theme.esc(l['nome'])}**  \n"
                        f"<span style='color:{theme.TEXT_MUTED};font-size:0.78rem;'>"
                        f"{l['quantidade']} lançamento(s) · {fatia:.0f}% do total</span>",
                        unsafe_allow_html=True,
                    )
                    b.markdown(
                        f"<div style='text-align:right;font-weight:700;color:{cor};'>"
                        f"{theme.moeda(l['total'])}</div>",
                        unsafe_allow_html=True,
                    )


# ── Projeção ─────────────────────────────────────────────────────────────

def _projecao(conn, grupo_id, contas):
    c1, c2, c3 = st.columns([1.4, 1.4, 2])
    with c1:
        dias = st.select_slider(
            "Horizonte", options=[30, 60, 90, 180, 365], value=90,
            format_func=lambda d: f"{d} dias", key="fc_proj_dias",
        )
    with c2:
        rotulo = st.radio("Agrupar por", list(GRANULARIDADES), horizontal=True,
                          key="fc_proj_gran")
    with c3:
        conta_id = _filtro_conta(conn, contas, chave="fc_proj_conta")

    pontos = db.projecao_saldo(conn, dias, grupo_id=grupo_id, conta_id=conta_id)
    agrupados = db.agrupar_projecao(pontos, GRANULARIDADES[rotulo])

    saldo_hoje = pontos[0][1]
    saldo_fim = pontos[-1][1]
    negativos = [(d, s) for d, s, _, _ in pontos if s < 0]

    m1, m2, m3 = st.columns(3)
    m1.metric("Saldo hoje", theme.moeda(saldo_hoje))
    m2.metric(f"Saldo em {dias} dias", theme.moeda(saldo_fim),
              delta=theme.moeda(saldo_fim - saldo_hoje))
    m3.metric("Menor saldo do período", theme.moeda(min(s for _, s, _, _ in pontos)))

    if negativos:
        dia, valor = negativos[0]
        st.error(
            f"**O saldo fica negativo em {theme.data_br(dia.isoformat())}** "
            f"({theme.moeda(valor)}). Daqui até lá dá para antecipar recebimento, "
            "adiar alguma saída ou resgatar aplicação."
        )
    else:
        st.success(f"O saldo não fica negativo nos próximos {dias} dias.")

    df = pd.DataFrame(
        [(d, s, e, sa) for d, s, e, sa in agrupados],
        columns=["data", "saldo", "entradas", "saidas"],
    )

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["data"], y=df["saldo"], name="Saldo projetado",
        mode="lines+markers", line=dict(color=theme.BLUE, width=3),
        marker=dict(size=6, color=theme.BLUE),
        hovertext=[theme.moeda(v) for v in df["saldo"]],
        hovertemplate="%{x|%d/%m/%Y}: %{hovertext}<extra></extra>",
    ))
    fig.add_hline(y=0, line_dash="dot", line_color=theme.RED, opacity=0.6)
    theme.apply_layout(fig)
    fig.update_layout(height=380, yaxis_title="R$", xaxis_title="",
                      margin=dict(l=8, r=8, t=40, b=8))
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("##### Movimento por período")
    tabela = df.copy()
    tabela["data"] = tabela["data"].apply(lambda d: theme.data_br(d.isoformat()))
    tabela = tabela.rename(columns={
        "data": "Data", "saldo": "Saldo ao fim",
        "entradas": "Entradas", "saidas": "Saídas",
    })
    st.dataframe(tabela, use_container_width=True, hide_index=True)


def _filtro_conta(conn, contas, chave):
    opcoes = [("Todas as contas", None)] + [(c["nome"], c["id"]) for c in contas]
    escolha = st.selectbox("Conta", opcoes, format_func=lambda o: o[0], key=chave)
    return escolha[1]


# ── Lançamentos ──────────────────────────────────────────────────────────

def _lancamentos(conn, usuario, contas):
    grupo_id = usuario["grupo_id"]

    st.info(
        "**O caminho normal é 📤 A Pagar / 📥 A Receber.** Lançar por aqui é para o que "
        "já aconteceu e não estava previsto — o troco do mercado, um dinheiro que "
        "apareceu. Contas que se repetem, registre lá, e elas aparecem na projeção."
    )
    if st.checkbox("➕ Lançar movimentação avulsa", key="fc_abrir_avulso"):
        _formulario_avulso(conn, usuario, contas)

    st.divider()

    col1, col2, col3 = st.columns(3)
    with col1:
        data_inicio = st.date_input("De", value=date.today().replace(day=1), key="fc_inicio")
    with col2:
        data_fim = st.date_input("Até", value=date.today(), key="fc_fim")
    with col3:
        conta_id = _filtro_conta(conn, contas, chave="fc_conta")

    lancamentos = db.listar_lancamentos(
        conn, data_inicio=data_inicio.isoformat(), data_fim=data_fim.isoformat(),
        conta_id=conta_id, apenas_sem_cartao=True, grupo_id=grupo_id,
    )

    if not lancamentos:
        st.info("Nenhum lançamento no período selecionado.")
        return

    entradas = sum(l["valor"] for l in lancamentos if l["tipo"] == "entrada")
    saidas = sum(l["valor"] for l in lancamentos if l["tipo"] == "saida")

    m1, m2, m3 = st.columns(3)
    m1.metric("Entradas", theme.moeda(entradas))
    m2.metric("Saídas", theme.moeda(saidas))
    m3.metric("Saldo do período", theme.moeda(entradas - saidas))

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


def _formulario_avulso(conn, usuario, contas):
    grupo_id = usuario["grupo_id"]
    categorias = db.listar_categorias(conn, grupo_id=grupo_id)

    with st.container(border=True):
        tipo = st.radio(
            "Tipo", ["saida", "entrada"],
            format_func=lambda x: "Saída (despesa)" if x == "saida" else "Entrada (receita)",
            horizontal=True, key="fc_tipo_novo",
        )
        tipo_categoria = "despesa" if tipo == "saida" else "receita"
        cats_filtradas = [c for c in categorias if c["tipo"] == tipo_categoria]

        c1, c2, c3 = st.columns([2, 1, 1])
        descricao = c1.text_input("Descrição", key="fc_descricao", placeholder="Ex: Supermercado")
        valor = c2.number_input("Valor (R$)", min_value=0.0, step=10.0, format="%.2f", key="fc_valor")
        data_lanc = c3.date_input("Data", value=date.today(), key="fc_data")

        c4, c5, c6, c7 = st.columns(4)
        conta = c4.selectbox("Conta", contas, format_func=lambda c: c["nome"], key="fc_conta_novo")
        categoria = c5.selectbox("Categoria", cats_filtradas,
                                 format_func=lambda c: f"{c['icone']} {c['nome']}", key="fc_categoria")
        rotulo_forma = "Forma de pagamento" if tipo == "saida" else "Forma de recebimento"
        forma = c6.selectbox(rotulo_forma, ["—"] + db.nomes_formas_pagamento(conn, grupo_id=grupo_id),
                             key="fc_forma")
        status = c7.selectbox("Status", ["pago", "pendente"],
                              format_func=lambda s: "Pago/Recebido" if s == "pago" else "Pendente",
                              key="fc_status")

        if st.button("Salvar lançamento", use_container_width=True, key="fc_salvar", type="primary"):
            if not descricao.strip():
                st.error("Informe a descrição.")
            elif valor <= 0:
                st.error("Informe um valor maior que zero.")
            else:
                db.criar_lancamento(
                    conn, data_lanc.isoformat(), conta["id"], categoria["id"], descricao.strip(),
                    valor, tipo, status, usuario["id"],
                    forma_pagamento=None if forma == "—" else forma,
                    grupo_id=grupo_id,
                )
                st.success("Lançamento salvo.")
                st.rerun()
