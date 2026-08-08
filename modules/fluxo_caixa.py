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

from dateutil.relativedelta import relativedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import database as db
import theme
from modules import anexos

VISOES = ["📊  Saldo atual", "📉  Realizado", "📅  Previsto", "📈  Projeção", "📋  Lançamentos"]

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
        _realizado(conn, grupo_id, contas)
    elif visao == VISOES[2]:
        _previsto(conn, grupo_id, contas)
    elif visao == VISOES[3]:
        _projecao(conn, grupo_id, contas)
    else:
        _lancamentos(conn, usuario, contas)


# ── Realizado (o passado) ────────────────────────────────────────────────

def _realizado(conn, grupo_id, contas):
    hoje = date.today()
    c1, c2, c3 = st.columns([1.2, 1.2, 2], vertical_alignment="bottom")
    with c1:
        inicio = st.date_input("De", value=hoje - relativedelta(months=6), key="fc_real_ini")
    with c2:
        fim = st.date_input("Até", value=hoje, key="fc_real_fim")
    with c3:
        conta_id = _filtro_conta(conn, contas, chave="fc_real_conta")

    if inicio > fim:
        st.error("A data inicial está depois da final.")
        return

    entradas, saidas = db.realizado_resumo(
        conn, inicio.isoformat(), fim.isoformat(), grupo_id=grupo_id, conta_id=conta_id)
    meses = db.realizado_por_mes(
        conn, inicio.isoformat(), fim.isoformat(), grupo_id=grupo_id, conta_id=conta_id)

    if not meses:
        st.info("Nenhum lançamento pago neste período. Só entra aqui o que foi de fato "
                "pago ou recebido — o que está pendente aparece em Previsto.")
        return

    resultado = entradas - saidas
    qtd_meses = len(meses)
    positivos = sum(1 for m in meses if m["resultado"] > 0)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Entradas", theme.moeda(entradas))
    m2.metric("Saídas", theme.moeda(saidas))
    m3.metric("Resultado", theme.moeda(resultado),
              delta=f"{(resultado / entradas * 100) if entradas else 0:.0f}% do que entrou")
    m4.metric("Média por mês", theme.moeda(resultado / qtd_meses),
              help=f"{positivos} de {qtd_meses} meses fecharam no positivo.")

    if resultado < 0:
        st.warning(
            f"No período você gastou **{theme.moeda_md(abs(resultado))} a mais** do que "
            "entrou. A diferença saiu do saldo que já existia."
        )

    # Barras de entrada e saída com a linha do resultado por cima: é onde se
    # enxerga o mês que destoou.
    rotulos = [f"{m['mes'][5:]}/{m['mes'][2:4]}" for m in meses]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=rotulos, y=[m["entradas"] for m in meses], name="Entradas",
                         marker_color=theme.GREEN))
    fig.add_trace(go.Bar(x=rotulos, y=[m["saidas"] for m in meses], name="Saídas",
                         marker_color=theme.RED))
    fig.add_trace(go.Scatter(x=rotulos, y=[m["resultado"] for m in meses], name="Resultado",
                             mode="lines+markers", line=dict(color=theme.BLUE, width=3),
                             marker=dict(size=8, color=theme.BLUE)))
    fig.add_hline(y=0, line_dash="dot", line_color=theme.TEXT_SUAVE, opacity=0.5)
    theme.apply_layout(fig)
    fig.update_layout(barmode="group", bargap=0.3, height=360, yaxis_title="R$",
                      margin=dict(l=8, r=8, t=44, b=8))
    st.plotly_chart(fig, use_container_width=True)

    esq, dir_ = st.columns(2)
    for coluna, tipo, titulo, cor in (
        (esq, "saida", "📤 Para onde foi", theme.RED),
        (dir_, "entrada", "📥 De onde veio", theme.GREEN),
    ):
        with coluna:
            st.markdown(f"##### {titulo}")
            linhas = db.realizado_por_categoria(
                conn, inicio.isoformat(), fim.isoformat(), tipo,
                grupo_id=grupo_id, conta_id=conta_id)
            if not linhas:
                st.caption("Nada neste período.")
                continue
            st.markdown(_lista_categorias(linhas, cor, qtd_meses), unsafe_allow_html=True)


def _lista_categorias(linhas, cor, meses=1):
    """Lista compacta de categoria → total, com a média mensal ao lado."""
    total = sum(l["total"] for l in linhas)
    blocos = [
        f"<div style='display:flex;align-items:center;gap:8px;padding:7px 10px;"
        f"border-bottom:1px solid {theme.BORDER};'>"
        f"<span>{l['icone']}</span>"
        f"<span style='flex:1;font-weight:600;'>{theme.esc(l['nome'])}"
        f"<span style='color:{theme.TEXT_MUTED};font-weight:400;font-size:0.75rem;'> · "
        f"{(l['total'] / total * 100) if total else 0:.0f}%"
        + (f" · {theme.moeda_md(l['total'] / meses)}/mês" if meses > 1 else "")
        + "</span></span>"
        f"<span style='font-weight:700;color:{cor};white-space:nowrap;'>"
        f"{theme.moeda_md(l['total'])}</span></div>"
        for l in linhas
    ]
    rodape = (
        f"<div style='display:flex;padding:8px 10px;font-weight:700;'>"
        f"<span style='flex:1;'>Total</span>"
        f"<span style='color:{cor};'>{theme.moeda_md(total)}</span></div>"
    )
    return (
        f"<div style='background:{theme.CARD};border:1px solid {theme.BORDER};"
        f"border-radius:12px;overflow:hidden;'>" + "".join(blocos) + rodape + "</div>"
    )


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
        f"Patrimônio líquido em dinheiro: **{theme.moeda_md(n['total'])}** "
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
                f"{theme.moeda_md(conta['saldo'])}</div>",
                unsafe_allow_html=True,
            )


# ── Previsto ─────────────────────────────────────────────────────────────

def _previsto(conn, grupo_id, contas):
    # Filtro e horizonte na mesma linha: o detalhe por categoria é o que
    # interessa, e ele precisa caber na tela sem rolagem.
    c_conta, c_dias = st.columns([2, 3], vertical_alignment="bottom")
    with c_conta:
        conta_id = _filtro_conta(conn, contas, chave="fc_prev_conta")
    with c_dias:
        dias = st.select_slider(
            "Horizonte", options=list(range(7, 91, 7)), value=30,
            format_func=lambda d: f"{d} dias", key="fc_prev_dias",
        )

    resumo = []
    for janela, rotulo in JANELAS:
        entradas, saidas = db.previsto_ate(conn, janela, grupo_id=grupo_id, conta_id=conta_id)
        liquido = entradas - saidas
        cor = theme.DEEP_GREEN if liquido >= 0 else theme.RED
        resumo.append(
            f"<div style='flex:1;padding:0 10px;border-left:3px solid {cor};'>"
            f"<div style='font-size:0.72rem;color:{theme.TEXT_MUTED};font-weight:600;'>"
            f"PRÓXIMOS {rotulo.upper()}</div>"
            f"<div style='font-weight:700;font-size:1.05rem;color:{cor};'>"
            f"{theme.moeda_md(liquido)}</div>"
            f"<div style='font-size:0.74rem;color:{theme.TEXT_MUTED};'>"
            f"<span style='color:{theme.GREEN};'>+{theme.moeda_md(entradas)}</span> · "
            f"<span style='color:{theme.RED};'>−{theme.moeda_md(saidas)}</span></div></div>"
        )

    st.markdown(
        "<div style='display:flex;gap:6px;margin:2px 0 10px;'>" + "".join(resumo) + "</div>",
        unsafe_allow_html=True,
    )

    esq, dir_ = st.columns(2)
    for coluna, tipo, titulo, cor in (
        (esq, "saida", f"📤 Saídas previstas · {dias} dias", theme.RED),
        (dir_, "entrada", f"📥 Entradas previstas · {dias} dias", theme.GREEN),
    ):
        with coluna:
            st.markdown(f"##### {titulo}")
            linhas = db.previsto_por_categoria(conn, dias, tipo, grupo_id=grupo_id,
                                               conta_id=conta_id)
            if not linhas:
                st.caption("Nada previsto nesta janela.")
                continue
            st.markdown(_lista_categorias(linhas, cor), unsafe_allow_html=True)

    st.caption(
        "Conta vencida e ainda não paga entra desde a primeira janela — ela continua "
        "sendo dinheiro que vai sair."
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
            f"({theme.moeda_md(valor)}). Daqui até lá dá para antecipar recebimento, "
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
                f"<span style='color:{cor};font-weight:700;'>{sinal} {theme.moeda_md(l['valor'])}</span>",
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
