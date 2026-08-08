import streamlit as st

import database as db
import auth
import theme
from modules import (
    dashboard, fluxo_caixa, contas_pagar_receber, cartao_credito,
    patrimonio, investimentos, metas, admin, configuracoes, ajuda,
)

st.set_page_config(
    page_title="Financeiro Familiar",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {{
  --bg: {theme.BG};
  --card: {theme.CARD};
  --border: {theme.BORDER};
  --border-forte: {theme.BORDER_FORTE};
  --text: {theme.TEXT};
  --text-muted: {theme.TEXT_MUTED};
  --text-suave: {theme.TEXT_SUAVE};
  --green: {theme.GREEN};
  --green-dark: {theme.GREEN_DARK};
  --green-soft: {theme.GREEN_SOFT};
  --red: {theme.RED};
}}

/* ── Base ─────────────────────────────────────────────────────── */
html, body, input, button, select, textarea,
p, span, div, label, h1, h2, h3, h4, h5, h6 {{
  font-family: 'Inter', -apple-system, sans-serif;
}}
[data-testid="stIconMaterial"],
span[class*="material-symbols"], .material-symbols-rounded {{
  font-family: 'Material Symbols Rounded', 'Material Symbols Outlined' !important;
}}

[data-testid="stAppViewContainer"] {{ background: var(--bg); }}
[data-testid="stHeader"] {{ background: transparent !important; height: 0; }}
body, p, span, label, div {{ color: var(--text); }}

/* Conteúdo principal: topo (72px) alinha com o logo da lateral (69px).
   Alinhado à esquerda — centralizar abre um vão grande entre a lateral e o conteúdo
   em telas largas. Assim a distância da lateral é sempre a mesma. */
[data-testid="stMainBlockContainer"] {{
  padding: 72px 2.75rem 4rem !important;
  max-width: 1500px !important;
  margin-left: 0 !important;
  margin-right: auto !important;
}}

h1, h2, h3 {{ letter-spacing: -0.02em; }}

/* ── Sidebar (navegação principal) ────────────────────────────── */
[data-testid="stSidebar"] {{
  background: var(--card) !important;
  border-right: 1px solid var(--border) !important;
  width: 264px !important;
  position: relative;
}}
/* barra verde de marca no topo da lateral */
[data-testid="stSidebar"]::before {{
  content: "";
  position: absolute; top: 0; left: 0; right: 0;
  height: 12px; z-index: 5;
  background: linear-gradient(90deg, #1B7A38 0%, {theme.GREEN} 55%, #8BDC63 100%);
}}
/* 12px da barra + ~11px de respiro (era ~18px, reduzido 40%) */
[data-testid="stSidebar"] > div:first-child {{ padding-top: 1.44rem; }}
/* o cabeçalho da lateral vem com 60px + 16px de margem só para abrigar o botão «;
   compactamos para o logo subir, mantendo o botão utilizável */
[data-testid="stSidebarHeader"] {{
  height: 34px !important; min-height: 34px !important;
  margin-bottom: 12px !important; padding: 0 !important;
}}
[data-testid="stSidebar"] * {{ color: var(--text); }}

.marca {{
  display: flex; align-items: center; gap: 0.6rem;
  padding: 0 0.35rem 0.9rem;
}}
.marca-icone {{
  width: 36px; height: 36px; border-radius: 9px;
  background: var(--green); color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.1rem; flex-shrink: 0;
}}
.marca-nome {{ font-weight: 700; font-size: 1rem; line-height: 1.15; }}
.marca-sub {{ font-size: 0.7rem; color: var(--text-suave); }}

.nav-secao {{
  font-size: 0.68rem; font-weight: 700; letter-spacing: 0.09em;
  text-transform: uppercase; color: var(--text-suave);
  margin: 1rem 0 0.35rem 0.5rem;
}}

/* Radio da sidebar vira lista de navegação */
[data-testid="stSidebar"] [role="radiogroup"] {{ gap: 2px !important; }}
[data-testid="stSidebar"] [role="radiogroup"] label {{
  display: flex !important; align-items: center;
  width: 100%; padding: 0.5rem 0.7rem; margin: 0;
  border-radius: 9px; cursor: pointer;
  transition: background 0.12s ease, color 0.12s ease;
}}
/* esconde a bolinha do radio */
[data-testid="stSidebar"] [role="radiogroup"] label > div:first-child {{
  display: none !important;
}}
[data-testid="stSidebar"] [role="radiogroup"] label p {{
  font-size: 0.88rem !important; font-weight: 500 !important; margin: 0 !important;
}}
[data-testid="stSidebar"] [role="radiogroup"] label:hover {{ background: #F1F4F7; }}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {{
  background: var(--green);
}}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p {{
  color: #FFFFFF !important; font-weight: 600 !important;
}}

.usuario-box {{
  display: flex; align-items: center; gap: 0.55rem;
  padding: 0.6rem 0.7rem; border-radius: 10px;
  background: #F5F7F9; border: 1px solid var(--border);
  margin-bottom: 0.5rem;
}}
.usuario-avatar {{
  width: 30px; height: 30px; border-radius: 50%;
  background: var(--green-soft); color: var(--green-dark);
  display: flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 0.8rem; flex-shrink: 0;
}}
.usuario-nome {{ font-size: 0.84rem; font-weight: 600; line-height: 1.2; }}
.usuario-papel {{ font-size: 0.7rem; color: var(--text-suave); }}

/* ── Cabeçalho de página ──────────────────────────────────────── */
.pagina-topo {{ margin-bottom: 1.1rem; }}
.pagina-titulo {{
  font-size: 1.45rem; font-weight: 700; letter-spacing: -0.02em;
  margin: 0 0 0.15rem 0;
}}
.pagina-desc {{ font-size: 0.88rem; color: var(--text-muted); margin: 0; }}

/* ── Cards e containers ───────────────────────────────────────── */
[data-testid="stVerticalBlockBorderWrapper"] {{
  background: var(--card);
  border: 1px solid var(--border) !important;
  border-radius: 12px !important;
  box-shadow: 0 1px 2px rgba(16,24,40,0.04);
}}

[data-testid="stMetric"] {{
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1rem 1.15rem;
  box-shadow: 0 1px 2px rgba(16,24,40,0.04);
}}
[data-testid="stMetricLabel"] p {{
  color: var(--text-muted) !important;
  font-size: 0.8rem !important; font-weight: 500 !important;
}}
[data-testid="stMetricValue"] {{
  color: var(--text) !important; font-weight: 700 !important;
  font-size: 1.5rem !important; letter-spacing: -0.02em;
}}

/* KPI custom */
.kpi {{
  background: var(--card); border: 1px solid var(--border);
  border-radius: 12px; padding: 1rem 1.15rem;
  box-shadow: 0 1px 2px rgba(16,24,40,0.04);
  transition: box-shadow 0.15s ease, transform 0.15s ease;
  height: 100%;
}}
.kpi:hover {{ box-shadow: 0 4px 12px rgba(16,24,40,0.07); transform: translateY(-1px); }}
.kpi-topo {{ display: flex; align-items: center; gap: 0.45rem; margin-bottom: 0.5rem; }}
.kpi-icone {{
  width: 28px; height: 28px; border-radius: 8px;
  background: var(--green-soft);
  display: flex; align-items: center; justify-content: center; font-size: 0.9rem;
}}
.kpi-label {{ font-size: 0.78rem; color: var(--text-muted); font-weight: 600; }}
.kpi-valor {{
  font-size: clamp(1.05rem, 1.6vw, 1.45rem); font-weight: 700;
  letter-spacing: -0.03em; white-space: nowrap;
}}
.kpi-nota {{ font-size: 0.74rem; color: var(--text-suave); margin-top: 0.15rem; }}

/* ── Botões ───────────────────────────────────────────────────── */
.stButton button, .stFormSubmitButton button {{
  border-radius: 9px !important;
  font-weight: 600 !important; font-size: 0.87rem !important;
  border: 1px solid var(--border-forte) !important;
  background: var(--card) !important; color: var(--text) !important;
  box-shadow: 0 1px 2px rgba(16,24,40,0.04) !important;
  transition: all 0.12s ease !important;
}}
.stButton button:hover, .stFormSubmitButton button:hover {{
  background: #F5F7F9 !important; border-color: var(--text-suave) !important;
}}
/* primário */
.stButton button[kind="primary"], .stFormSubmitButton button[kind="primaryFormSubmit"] {{
  background: var(--green) !important; color: #fff !important;
  border-color: var(--green) !important;
}}
.stButton button[kind="primary"]:hover, .stFormSubmitButton button[kind="primaryFormSubmit"]:hover {{
  background: var(--green-dark) !important; border-color: var(--green-dark) !important;
}}
.stFormSubmitButton button {{
  background: var(--green) !important; color: #fff !important;
  border-color: var(--green) !important;
}}
.stFormSubmitButton button:hover {{
  background: var(--green-dark) !important; border-color: var(--green-dark) !important;
}}

/* ── Inputs ───────────────────────────────────────────────────── */
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input,
[data-testid="stDateInput"] input, [data-testid="stTextArea"] textarea {{
  background: var(--card) !important; color: var(--text) !important;
  border-radius: 9px !important; font-size: 0.9rem !important;
}}
[data-baseweb="input"], [data-baseweb="select"] > div {{
  border-radius: 9px !important; border-color: var(--border-forte) !important;
  background: var(--card) !important;
}}
[data-baseweb="input"]:focus-within, [data-baseweb="select"] > div:focus-within {{
  border-color: var(--green) !important;
  box-shadow: 0 0 0 3px rgba(47,168,79,0.12) !important;
}}
[data-testid="stWidgetLabel"] p {{
  font-size: 0.82rem !important; font-weight: 600 !important;
  color: var(--text-muted) !important;
}}

/* ── Alertas mais discretos ───────────────────────────────────── */
[data-testid="stAlert"] {{
  border-radius: 10px; border: 1px solid var(--border); font-size: 0.88rem;
}}

/* ── Tabela ───────────────────────────────────────────────────── */
[data-testid="stDataFrame"] {{ border: 1px solid var(--border); border-radius: 10px; }}

/* ── Divisor ──────────────────────────────────────────────────── */
hr {{ border-color: var(--border) !important; margin: 1.1rem 0 !important; }}

/* ── Abas internas ────────────────────────────────────────────── */
[data-testid="stTabs"] button[role="tab"] {{
  color: var(--text-muted) !important; font-weight: 600 !important;
  font-size: 0.88rem !important;
}}
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {{ color: var(--green-dark) !important; }}
[data-testid="stTabs"] [data-baseweb="tab-highlight"] {{ background-color: var(--green) !important; }}
[data-testid="stTabs"] [data-baseweb="tab-border"] {{ background-color: var(--border) !important; }}

/* ── Barra de progresso ───────────────────────────────────────── */
[data-testid="stProgress"] div[role="progressbar"] > div {{ background: var(--green) !important; }}

/* ── Login ────────────────────────────────────────────────────── */
.login-topo {{ text-align: center; margin: 2rem 0 1.25rem; }}
.login-logo {{ width: 210px; max-width: 70%; height: auto; margin: 0 auto 0.6rem; display: block; }}
.login-sub {{ font-size: 0.88rem; color: var(--text-muted); margin: 0; }}

/* Logo na sidebar */
.sidebar-logo-box {{
  width: 178px; margin: 0 auto 0.5rem; padding: 16px 17px;
  border: 1px solid #CFEBDA;
  border-radius: 14px;
  background: #FFFFFF;
  box-shadow: 0 1px 2px rgba(47,168,79,0.05);
  display: flex; align-items: center; justify-content: center;
}}
.sidebar-logo {{
  width: 144px; max-width: 144px; height: auto; display: block;
}}
.sidebar-subtitulo {{
  text-align: center; font-size: 0.72rem; color: var(--text-suave);
  font-weight: 600; letter-spacing: 0.02em; margin-bottom: 0.9rem;
}}
.login-rodape {{
  text-align: center; font-size: 0.76rem; color: var(--text-suave); margin-top: 1.1rem;
}}
</style>
""", unsafe_allow_html=True)

conn = db.get_connection()
db.init_db(conn)
db.limpar_sessoes_expiradas(conn)

usuario = auth.usuario_logado(conn)

def _tela_de_aviso(mensagem):
    """Mesma moldura da tela de login, com um aviso no lugar do formulário."""
    _, centro, _ = st.columns([1, 1.5, 1])
    with centro:
        logo = theme.imagem_base64("logo.png")
        st.markdown(
            f"""<div class="login-topo">
            <img class="login-logo" src="{logo}" alt="Casa Capital">
            </div>""",
            unsafe_allow_html=True,
        )
        with st.container(border=True):
            st.warning(mensagem)
            if st.button("Sair e tentar outra conta", use_container_width=True):
                st.logout()


if not usuario:
    # Três motivos diferentes para não entrar — cada um com seu recado.
    sem_grupo = st.session_state.pop("sem_grupo", None)
    bloqueio_rede = st.session_state.pop("rede_bloqueada", None)

    if bloqueio_rede:
        visto = bloqueio_rede.get("ip") or "não identificado"
        _tela_de_aviso(
            f"**Esta conta só pode entrar pela rede de casa.**  \n"
            f"O e-mail **{theme.esc(bloqueio_rede.get('email', ''))}** está autorizado, "
            "mas o acesso está vindo de uma rede que não está liberada.  \n\n"
            f"Rede detectada: `{theme.esc(visto)}`  \n"
            "Conecte-se ao Wi-Fi de casa e tente de novo."
        )
    elif sem_grupo:
        _tela_de_aviso(
            f"**Você não tem acesso a nenhum grupo.**  \n"
            f"O e-mail **{theme.esc(sem_grupo)}** não está vinculado a nenhuma família.  \n"
            "Peça ao administrador para adicioná-lo na tela de Administração."
        )
    else:
        auth.tela_login(conn)
    st.stop()

# Garante que o grupo_id está na sessão (pode faltar em sessões antigas)
if not usuario.get("grupo_id"):
    st.session_state.pop("usuario", None)
    st.rerun()

# ── Navegação lateral ────────────────────────────────────────────
PAGINAS = {
    "📊  Dashboard": ("Dashboard", "Visão geral das finanças da família.", dashboard.render),
    "💰  Fluxo de Caixa": ("Fluxo de Caixa", "Tudo que entrou e saiu.", fluxo_caixa.render),
    "📤  A Pagar": ("Contas a Pagar", "Despesas em aberto e futuras.", contas_pagar_receber.render_a_pagar),
    "📥  A Receber": ("Contas a Receber", "Receitas previstas ainda não recebidas.", contas_pagar_receber.render_a_receber),
    "💳  Cartão": ("Cartão de Crédito", "Faturas e compras parceladas.", cartao_credito.render),
    "🏠  Patrimônio": ("Patrimônio", "Bens, dívidas e patrimônio líquido.", patrimonio.render),
    "💹  Investimentos": ("Investimentos", "Carteira, aportes e rentabilidade.", investimentos.render),
    "🎯  Metas": ("Metas", "Objetivos financeiros e progresso.", metas.render),
    "⚙️  Configurações": ("Configurações", "Cadastros, backup e ajuda.", configuracoes.render),
}

# Administração: visível somente para admins
if usuario.get("papel") == "admin":
    PAGINAS["⚙️  Administração"] = ("Administração", "Gerenciar grupos e membros.", admin.render)

with st.sidebar:
    st.markdown(
        f"""<div class="sidebar-logo-box">
          <img class="sidebar-logo" src="{theme.imagem_base64('logo.png')}" alt="Casa Capital">
        </div>
        <div class="sidebar-subtitulo">Financeiro Familiar · Pessoa Física</div>""",
        unsafe_allow_html=True,
    )

    iniciais = "".join(p[0] for p in usuario["nome"].split()[:2]).upper()
    st.markdown(
        f"""<div class="usuario-box">
        <div class="usuario-avatar">{theme.esc(iniciais)}</div>
        <div>
          <div class="usuario-nome">{theme.esc(usuario['nome'])}</div>
          <div class="usuario-papel">Conectado</div>
        </div>
        </div>""",
        unsafe_allow_html=True,
    )

    st.markdown('<div class="nav-secao">Navegação</div>', unsafe_allow_html=True)
    escolha = st.radio(
        "Navegação", list(PAGINAS.keys()),
        label_visibility="collapsed", key="nav_principal",
    )

    st.markdown("<div style='height:0.6rem'></div>", unsafe_allow_html=True)
    if st.button("Sair", use_container_width=True):
        auth.logout(conn)

titulo, descricao, render = PAGINAS[escolha]
cab_esq, cab_dir = st.columns([4, 1], vertical_alignment="center")
with cab_esq:
    st.markdown(
        f"""<div class="pagina-topo">
        <div class="pagina-titulo">{titulo}</div>
        <p class="pagina-desc">{descricao}</p>
        </div>""",
        unsafe_allow_html=True,
    )
with cab_dir:
    # O "?" vive aqui, e não dentro de cada módulo, para toda tela ganhar de
    # graça: basta a tela existir em conteudo_ajuda.py.
    ajuda.botao(titulo, conn)

render(conn, usuario)
