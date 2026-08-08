"""Fluxo de Caixa — quanto tenho, como foi, o que vem, e como termino.

Quatro visões que respondem perguntas diferentes:

  Saldo atual          onde o dinheiro está parado hoje
  Previsto × Realizado como os meses se comportaram e o que ainda está marcado,
                       no mesmo gráfico ou separados, com o que mostrar à escolha
  Projeção             como o saldo termina, e em que dia ele fura o zero
  Lançamentos          a lista, e o lançamento avulso (exceção — ver abaixo)

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
from modules import anexos, importar

VISOES = ["📊  Saldo atual", "📉  Previsto × Realizado", "📈  Projeção",
          "📋  Lançamentos", "📥  Importar extrato"]

AGRUPAMENTOS = {"Mensal": "mensal", "Semanal": "semanal", "Diário": "diario"}

SERIES = ["Entradas", "Saídas", "Resultado"]
DETALHES = ["Por categoria", "Tabela mensal"]

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
        _previsto_realizado(conn, grupo_id, contas)
    elif visao == VISOES[2]:
        _projecao(conn, grupo_id, contas)
    elif visao == VISOES[3]:
        _lancamentos(conn, usuario, contas)
    else:
        # Importar extrato é operação de caixa, não configuração — por isso
        # entra aqui. O módulo segue separado; só a porta de entrada é esta.
        importar.render(conn, usuario)


# ── Previsto × Realizado ─────────────────────────────────────────────────

def _previsto_realizado(conn, grupo_id, contas):
    """Passado e futuro na mesma tela, porque a pergunta é a mesma: como está
    indo. O que já aconteceu vem de `pago`; o que ainda vai, de `pendente`."""
    hoje = date.today()

    # Tudo numa faixa só. Os filtros são meio de chegar ao gráfico, não o
    # assunto da tela: cada linha que eles ocupam empurra a análise para baixo
    # da dobra. Por isso seleção em vez de botão de rádio (rádio com três
    # opções quebra em duas linhas na coluna estreita) e botão de alternância
    # em vez de multiseleção (as etiquetas da multiseleção empilham).
    c1, c2, c3, c4, c5 = st.columns([1.1, 1.1, 1.7, 1.2, 1.2], vertical_alignment="bottom")
    with c1:
        inicio = st.date_input("De", value=hoje - relativedelta(months=5), key="fc_pr_ini")
    with c2:
        fim = st.date_input("Até", value=hoje + relativedelta(months=3), key="fc_pr_fim")
    with c3:
        conta_id = _filtro_conta(conn, contas, chave="fc_pr_conta")
    with c4:
        # Mensal enxerga a tendência; diário serve para investigar um mês que
        # destoou. Por isso mensal é o padrão.
        periodo = st.selectbox("Agrupar por", list(AGRUPAMENTOS), key="fc_pr_periodo")
    with c5:
        modo = st.selectbox("Gráfico", ["Unificado", "Separado"], key="fc_pr_modo")

    c6, c7 = st.columns([1.6, 1.2], vertical_alignment="bottom")
    with c6:
        series = st.segmented_control("Mostrar no gráfico", SERIES, default=SERIES,
                                      selection_mode="multi", key="fc_pr_series") or []
    with c7:
        detalhes = st.segmented_control("Detalhar", DETALHES, default=["Por categoria"],
                                        selection_mode="multi", key="fc_pr_detalhes") or []

    if inicio > fim:
        st.error("A data inicial está depois da final.")
        return

    serie = db.serie_periodo(conn, inicio.isoformat(), fim.isoformat(),
                             AGRUPAMENTOS[periodo], grupo_id=grupo_id, conta_id=conta_id)
    if not serie:
        st.info("Nenhum lançamento neste período.")
        return

    st.caption(
        "Por **competência**: a compra no cartão conta no mês em que foi feita, "
        "não no mês em que a fatura é paga. Para ver o dinheiro saindo da conta, "
        "use a visão 📈 Projeção."
    )
    _cabecalho_pr(serie, periodo)
    _grafico_pr(serie, modo, series)

    if "Por categoria" in detalhes:
        _categorias_pr(conn, grupo_id, conta_id, inicio, fim, hoje, len(serie))
    if "Tabela mensal" in detalhes:
        _tabela_pr(serie)


def _cabecalho_pr(serie, periodo):
    real_e = sum(m["entradas_reais"] for m in serie)
    real_s = sum(m["saidas_reais"] for m in serie)
    prev_e = sum(m["entradas_previstas"] for m in serie)
    prev_s = sum(m["saidas_previstas"] for m in serie)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Realizado", theme.moeda(real_e - real_s),
              help=f"Entradas {theme.moeda(real_e)} · Saídas {theme.moeda(real_s)}")
    m2.metric("Previsto", theme.moeda(prev_e - prev_s),
              help=f"Entradas {theme.moeda(prev_e)} · Saídas {theme.moeda(prev_s)}")
    m3.metric("Total do período", theme.moeda((real_e + prev_e) - (real_s + prev_s)))
    unidade = {"Mensal": "mês", "Semanal": "semana", "Diário": "dia"}[periodo]
    m4.metric(f"Média por {unidade}",
              theme.moeda(((real_e + prev_e) - (real_s + prev_s)) / len(serie)),
              help=f"{len(serie)} {unidade}(s) com movimento no período.")


def _grafico_pr(serie, modo, series):
    rotulos = [m["rotulo"] for m in serie]

    def barras(fig, chave_e, chave_s, sufixo, opacidade):
        if "Entradas" in series:
            fig.add_trace(go.Bar(x=rotulos, y=[m[chave_e] for m in serie],
                                 name=f"Entradas{sufixo}", marker_color=theme.GREEN,
                                 opacity=opacidade))
        if "Saídas" in series:
            fig.add_trace(go.Bar(x=rotulos, y=[m[chave_s] for m in serie],
                                 name=f"Saídas{sufixo}", marker_color=theme.RED,
                                 opacity=opacidade))

    def linha(fig, chave, nome):
        if "Resultado" in series:
            fig.add_trace(go.Scatter(x=rotulos, y=[m[chave] for m in serie], name=nome,
                                     mode="lines+markers", line=dict(color=theme.BLUE, width=3),
                                     marker=dict(size=8, color=theme.BLUE)))

    def fechar(fig, altura=340):
        fig.add_hline(y=0, line_dash="dot", line_color=theme.TEXT_SUAVE, opacity=0.5)
        theme.apply_layout(fig)
        fig.update_layout(barmode="stack" if modo == "Unificado" else "group",
                          bargap=0.3, height=altura, yaxis_title="R$",
                          margin=dict(l=8, r=8, t=44, b=8))
        st.plotly_chart(fig, use_container_width=True)

    if modo == "Unificado":
        # Empilhado: a parte cheia é o que já aconteceu, a clara é o que falta.
        # Assim a barra do mês corrente mostra as duas coisas sem somar tudo.
        fig = go.Figure()
        barras(fig, "entradas_reais", "saidas_reais", " realizadas", 1.0)
        barras(fig, "entradas_previstas", "saidas_previstas", " previstas", 0.45)
        linha(fig, "resultado_total", "Resultado total")
        fechar(fig, 380)
        st.caption("Barra cheia é o que já aconteceu; a mais clara, o que ainda está marcado.")
        return

    esq, dir_ = st.columns(2)
    with esq:
        st.markdown("###### Realizado")
        fig = go.Figure()
        barras(fig, "entradas_reais", "saidas_reais", "", 1.0)
        linha(fig, "resultado_real", "Resultado")
        fechar(fig)
    with dir_:
        st.markdown("###### Previsto")
        fig = go.Figure()
        barras(fig, "entradas_previstas", "saidas_previstas", "", 1.0)
        linha(fig, "resultado_previsto", "Resultado")
        fechar(fig)


def _categorias_pr(conn, grupo_id, conta_id, inicio, fim, hoje, qtd_meses):
    st.divider()
    fatia = st.radio("Categorias de", ["Realizado", "Previsto"], horizontal=True,
                     key="fc_pr_cat_fatia")

    if fatia == "Realizado":
        # O realizado só existe até hoje; pedir além disso devolveria vazio.
        ini, fi = inicio.isoformat(), min(fim, hoje).isoformat()
        buscar = db.realizado_por_categoria
        titulos = ("📤 Para onde foi", "📥 De onde veio")
    else:
        ini, fi = max(inicio, hoje).isoformat(), fim.isoformat()
        buscar = db.previsto_por_categoria_periodo
        titulos = ("📤 O que vai sair", "📥 O que vai entrar")

    esq, dir_ = st.columns(2)
    for coluna, tipo, titulo, cor in (
        (esq, "saida", titulos[0], theme.RED),
        (dir_, "entrada", titulos[1], theme.GREEN),
    ):
        with coluna:
            st.markdown(f"##### {titulo}")
            linhas = buscar(conn, ini, fi, tipo, grupo_id=grupo_id, conta_id=conta_id)
            if not linhas:
                st.caption("Nada neste recorte.")
                continue
            st.markdown(_lista_categorias(linhas, cor, qtd_meses), unsafe_allow_html=True)


def _tabela_pr(serie):
    st.divider()
    st.markdown("##### Período a período")
    tabela = pd.DataFrame([{
        "Período": m["rotulo"],
        "Entradas realizadas": m["entradas_reais"],
        "Saídas realizadas": m["saidas_reais"],
        "Resultado realizado": m["resultado_real"],
        "Entradas previstas": m["entradas_previstas"],
        "Saídas previstas": m["saidas_previstas"],
        "Resultado previsto": m["resultado_previsto"],
    } for m in serie])
    st.dataframe(tabela, use_container_width=True, hide_index=True)


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


# ── Projeção ─────────────────────────────────────────────────────────────

def _projecao(conn, grupo_id, contas):
    c1, c2, c3 = st.columns([1.6, 1.2, 1.6], vertical_alignment="bottom")
    with c1:
        dias = st.select_slider(
            "Horizonte", options=[30, 60, 90, 180, 365], value=90,
            format_func=lambda d: f"{d} dias", key="fc_proj_dias",
        )
    with c2:
        rotulo = st.selectbox("Agrupar por", list(GRANULARIDADES), key="fc_proj_gran")
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

    faturas = db.faturas_previstas(conn, dias, grupo_id=grupo_id, conta_id=conta_id)
    if faturas:
        st.markdown("##### 💳 Faturas de cartão no período")
        st.caption(
            "A compra vira despesa no dia em que foi feita, mas o dinheiro só sai "
            "quando a fatura vence — é nesta data que ela entra na projeção."
        )
        linhas = "".join(
            f"<div style='display:flex;align-items:center;gap:8px;padding:7px 10px;"
            f"border-bottom:1px solid {theme.BORDER};'>"
            f"<span style='flex:1;font-weight:600;'>💳 {theme.esc(f['cartao'])}"
            f"<span style='color:{theme.TEXT_MUTED};font-weight:400;font-size:0.75rem;'>"
            f" · vence {theme.data_br(f['vencimento'].isoformat())}"
            f" · {f['quantidade']} compra(s)</span></span>"
            f"<span style='font-weight:700;color:{theme.RED};'>"
            f"{theme.moeda_md(f['total'])}</span></div>"
            for f in faturas
        )
        st.markdown(
            f"<div style='background:{theme.CARD};border:1px solid {theme.BORDER};"
            f"border-radius:12px;overflow:hidden;margin-bottom:10px;'>{linhas}</div>",
            unsafe_allow_html=True,
        )

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
