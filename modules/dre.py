from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dateutil.relativedelta import relativedelta

import database as db
import theme

VISOES = {
    "Tudo (competência)": None,
    "Só realizado (pagos)": "pago",
    "Só previsto (pendentes)": "pendente",
}


def render(conn, usuario):
    col1, col2, col3 = st.columns([1.3, 1.9, 1])
    with col1:
        meses_atras = st.slider("Meses para analisar", 1, 24, 6)
    with col2:
        visao = st.radio("Visão", list(VISOES.keys()), horizontal=True, key="dre_visao")
    with col3:
        futuros = st.checkbox(
            "Meses futuros", value=False, key="dre_futuros",
            help="Inclui lançamentos pendentes de meses à frente (ex.: recorrências já geradas).",
        )

    hoje = date.today()
    data_inicio = hoje.replace(day=1) - relativedelta(months=meses_atras - 1)
    fim_mes_atual = hoje.replace(day=1) + relativedelta(months=1) - timedelta(days=1)

    lancamentos = db.listar_lancamentos(
        conn,
        data_inicio=data_inicio.isoformat(),
        data_fim=None if futuros else fim_mes_atual.isoformat(),
        status=VISOES[visao],
    )

    if not lancamentos:
        st.info("Nenhum lançamento para essa combinação de período e visão.")
        return

    df = pd.DataFrame([dict(l) for l in lancamentos])
    df["data"] = pd.to_datetime(df["data"])
    df["mes"] = df["data"].dt.strftime("%Y-%m")

    resumo_mensal = df.groupby(["mes", "tipo"])["valor"].sum().unstack(fill_value=0)
    for col in ("entrada", "saida"):
        if col not in resumo_mensal.columns:
            resumo_mensal[col] = 0.0
    resumo_mensal["resultado"] = resumo_mensal["entrada"] - resumo_mensal["saida"]

    with st.container(border=True):
        meses = resumo_mensal.index.tolist()
        entradas_m = resumo_mensal["entrada"].tolist()
        saidas_m = resumo_mensal["saida"].tolist()
        saldo_m = resumo_mensal["resultado"].tolist()

        # Rótulos compactos (R$ 3,2 mil) evitam colisão; o valor exato fica no hover.
        # Com muitos meses, o rótulo da linha de saldo sai e fica só no hover.
        mostrar_texto_saldo = len(meses) <= 9

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=meses, y=entradas_m, name="Receitas", marker_color=theme.GREEN,
            text=[theme.moeda_curta(v) if v else "" for v in entradas_m],
            textposition="outside", cliponaxis=False,
            textfont=dict(size=11, color=theme.GREEN_DARK),
            hovertext=[theme.moeda(v) for v in entradas_m],
            hovertemplate="Receitas %{x}: %{hovertext}<extra></extra>",
        ))
        fig.add_trace(go.Bar(
            x=meses, y=saidas_m, name="Despesas", marker_color=theme.RED,
            text=[theme.moeda_curta(v) if v else "" for v in saidas_m],
            textposition="outside", cliponaxis=False,
            textfont=dict(size=11, color=theme.RED),
            hovertext=[theme.moeda(v) for v in saidas_m],
            hovertemplate="Despesas %{x}: %{hovertext}<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=meses, y=saldo_m, name="Saldo",
            mode="lines+markers+text" if mostrar_texto_saldo else "lines+markers",
            line=dict(color=theme.BLUE, width=3),
            marker=dict(size=9, color=theme.BLUE),
            text=[theme.moeda_curta(v) for v in saldo_m] if mostrar_texto_saldo else None,
            textposition="top center",
            textfont=dict(size=11, color=theme.BLUE),
            cliponaxis=False,
            hovertext=[theme.moeda(v) for v in saldo_m],
            hovertemplate="Saldo %{x}: %{hovertext}<extra></extra>",
        ))
        theme.apply_layout(fig)
        fig.update_layout(
            barmode="group", bargap=0.3, height=420,
            yaxis_title="R$", xaxis_title="Mês",
            margin=dict(l=8, r=8, t=48, b=8),
        )
        st.plotly_chart(fig, use_container_width=True)

    m1, m2, m3 = st.columns(3)
    total_entradas = df[df["tipo"] == "entrada"]["valor"].sum()
    total_saidas = df[df["tipo"] == "saida"]["valor"].sum()
    m1.metric("Total receitas", f"{theme.moeda(total_entradas)}")
    m2.metric("Total despesas", f"{theme.moeda(total_saidas)}")
    m3.metric("Resultado do período", f"{theme.moeda(total_entradas - total_saidas)}")

    st.markdown("##### Despesas por categoria")
    despesas = df[df["tipo"] == "saida"]
    if not despesas.empty:
        with st.container(border=True):
            por_categoria = despesas.groupby("nome_categoria")["valor"].sum().sort_values(ascending=False)
            fig2 = px.pie(
                values=por_categoria.values, names=por_categoria.index, hole=0.6,
                color_discrete_sequence=theme.CHART_SEQUENCE,
            )
            theme.apply_layout(fig2)
            st.plotly_chart(fig2, use_container_width=True)

    st.markdown("##### Resultado mês a mês")
    st.dataframe(
        resumo_mensal.rename(columns={"entrada": "Receitas", "saida": "Despesas", "resultado": "Resultado"}),
        use_container_width=True,
    )
