from datetime import date, timedelta

import plotly.express as px
import streamlit as st

import database as db
import theme


def render(conn, usuario):
    grupo_id = usuario["grupo_id"]
    saldos = db.saldos_por_conta(conn, grupo_id=grupo_id)
    contas_nao_cartao = [c for c in saldos if c["tipo"] != "cartao"]

    if not contas_nao_cartao:
        st.warning(
            "**Comece por aqui:** você ainda não tem uma conta bancária ou carteira cadastrada. "
            "Abra a aba **🏦 Contas** para cadastrar — sem isso não é possível lançar movimentações."
        )

    hoje = date.today()

    # ── Janela de projeção ───────────────────────────────────────────────
    sel, _ = st.columns([1.1, 4.9])
    with sel:
        dias = int(st.number_input(
            "Ver próximos (dias)", min_value=1, max_value=365, value=30, step=1,
            key="dash_dias", help="Quantos dias à frente considerar em A pagar, A receber e Saldo projetado.",
        ))
    limite = hoje + timedelta(days=dias)
    ate = limite.strftime("%d/%m")

    # ── Projeção de caixa ────────────────────────────────────────────────
    saldo_total = sum(c["saldo"] for c in contas_nao_cartao)
    a_pagar = db.listar_lancamentos(
        conn, status="pendente", tipo="saida",
        apenas_sem_cartao=True, data_fim=limite.isoformat(), grupo_id=grupo_id,
    )
    a_receber = db.listar_lancamentos(
        conn, status="pendente", tipo="entrada",
        apenas_sem_cartao=True, data_fim=limite.isoformat(), grupo_id=grupo_id,
    )
    total_pagar = sum(l["valor"] for l in a_pagar)
    total_receber = sum(l["valor"] for l in a_receber)
    saldo_projetado = saldo_total - total_pagar + total_receber

    kpis = [
        ("💵", "Saldo em contas", saldo_total, "Disponível hoje",
         theme.RED if saldo_total < 0 else theme.TEXT),
        ("📤", f"A pagar · {dias} dias", total_pagar,
         f"{len(a_pagar)} lançamento(s) até {ate}",
         theme.RED if total_pagar > 0 else theme.TEXT),
        ("📥", f"A receber · {dias} dias", total_receber,
         f"{len(a_receber)} lançamento(s) até {ate}",
         theme.GREEN_DARK if total_receber > 0 else theme.TEXT),
        ("🎯", "Saldo projetado", saldo_projetado,
         f"Saldo − a pagar + a receber, em {ate}",
         theme.RED if saldo_projetado < 0 else theme.GREEN_DARK),
    ]
    cols = st.columns(4)
    for col, (icone, label, valor, nota, cor) in zip(cols, kpis):
        col.markdown(
            f"""<div class="kpi">
            <div class="kpi-topo">
              <div class="kpi-icone">{icone}</div>
              <div class="kpi-label">{label}</div>
            </div>
            <div class="kpi-valor" style="color:{cor};">{theme.moeda(valor)}</div>
            <div class="kpi-nota">{nota}</div>
            </div>""",
            unsafe_allow_html=True,
        )

    # ── Linha secundária: visão patrimonial ──────────────────────────────
    total_investido = sum(i["valor_atual"] for i in db.listar_investimentos(conn, grupo_id=grupo_id))
    patrimonio = db.patrimonio_liquido(conn, saldo_contas=saldo_total, investido=total_investido, grupo_id=grupo_id)
    inicio_mes = hoje.replace(day=1)
    lancamentos_mes = db.listar_lancamentos(
        conn, data_inicio=inicio_mes.isoformat(), data_fim=hoje.isoformat(), grupo_id=grupo_id,
    )
    entradas_mes = sum(l["valor"] for l in lancamentos_mes if l["tipo"] == "entrada")
    saidas_mes = sum(l["valor"] for l in lancamentos_mes if l["tipo"] == "saida")
    resultado_mes = entradas_mes - saidas_mes

    st.write("")
    linha2 = [
        ("💹", "Investido", total_investido, theme.TEXT),
        ("🏦", "Patrimônio líquido", patrimonio,
         theme.RED if patrimonio < 0 else theme.TEXT),
        ("📅", "Resultado do mês", resultado_mes,
         theme.RED if resultado_mes < 0 else theme.TEXT),
    ]
    cols2 = st.columns(3)
    for col, (icone, label, valor, cor) in zip(cols2, linha2):
        col.markdown(
            f"""<div class="kpi" style="padding:0.75rem 1rem;">
            <div class="kpi-label" style="margin-bottom:0.15rem;">{icone} {label}</div>
            <div style="font-size:1.1rem;font-weight:700;color:{cor};white-space:nowrap;">{theme.moeda(valor)}</div>
            </div>""",
            unsafe_allow_html=True,
        )

    # ── Saldo por conta ──────────────────────────────────────────────────
    if contas_nao_cartao:
        st.write("")
        st.markdown(
            f'<div style="font-size:0.78rem;font-weight:700;letter-spacing:0.08em;'
            f'text-transform:uppercase;color:{theme.TEXT_SUAVE};margin-bottom:0.4rem;">'
            f'Saldo por conta</div>',
            unsafe_allow_html=True,
        )
        cols3 = st.columns(4)
        for i, c in enumerate(contas_nao_cartao[:4]):
            cor = theme.RED if c["saldo"] < 0 else theme.TEXT
            cols3[i].markdown(
                f"""<div class="kpi" style="padding:0.75rem 1rem;">
                <div class="kpi-label" style="margin-bottom:0.15rem;">{theme.esc(c['nome'])}</div>
                <div style="font-size:1.1rem;font-weight:700;color:{cor};white-space:nowrap;">{theme.moeda(c['saldo'])}</div>
                </div>""",
                unsafe_allow_html=True,
            )

    # ── Gráfico do mês + vencimentos da janela ───────────────────────────
    st.write("")
    col1, col2 = st.columns([3, 2])

    with col1:
        with st.container(border=True):
            st.markdown("##### Receitas x Despesas (mês atual)")
            if entradas_mes or saidas_mes:
                nomes = ["Receitas", "Despesas"]
                fig = px.pie(
                    values=[entradas_mes, saidas_mes], names=nomes, color=nomes,
                    hole=0.62, color_discrete_map={"Receitas": theme.GREEN, "Despesas": theme.RED},
                )
                theme.apply_layout(fig)
                fig.update_layout(height=280, showlegend=True)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Sem lançamentos neste mês ainda.")

    with col2:
        with st.container(border=True):
            st.markdown(f"##### Próximos vencimentos ({dias} dias)")
            proximos = sorted(a_pagar + a_receber, key=lambda l: l["data"])
            if not proximos:
                st.info(f"Nada vencendo nos próximos {dias} dias.")
            else:
                for l in proximos[:8]:
                    sinal = "+" if l["tipo"] == "entrada" else "-"
                    cor = theme.GREEN if l["tipo"] == "entrada" else theme.RED
                    st.markdown(
                        f"""<div style="display:flex;justify-content:space-between;align-items:center;
                        padding:0.5rem 0;border-bottom:1px solid {theme.BORDER};">
                        <div>
                          <div style="font-size:0.88rem;">{theme.esc(l['descricao'])}</div>
                          <div style="font-size:0.72rem;color:{theme.TEXT_SUAVE};">{theme.data_br(l['data'])[:5]}</div>
                        </div>
                        <span style="color:{cor};font-weight:600;font-size:0.9rem;">{sinal} {theme.moeda(l['valor'])}</span>
                        </div>""",
                        unsafe_allow_html=True,
                    )
                if len(proximos) > 8:
                    st.caption(f"+ {len(proximos) - 8} outros na janela de {dias} dias.")
