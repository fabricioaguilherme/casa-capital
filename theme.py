"""Design system — base neutra com verde usado apenas como acento semântico.

Princípio (padrão SaaS atual): cor carrega significado, não decoração.
Cinza estrutura a interface; verde marca ação/positivo; vermelho marca negativo.
"""

import base64
import html
import os
from functools import lru_cache

_ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


@lru_cache(maxsize=8)
def imagem_base64(nome):
    """Devolve a imagem de assets/ como data URI (embutida no HTML, sem servir arquivo)."""
    caminho = os.path.join(_ASSETS, nome)
    if not os.path.exists(caminho):
        return ""
    with open(caminho, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()

# Superfícies e estrutura
BG = "#F4F6F8"
CARD = "#FFFFFF"
BORDER = "#E4E9EE"
BORDER_FORTE = "#D3DBE3"

# Texto
TEXT = "#1F2A37"
TEXT_MUTED = "#6B7A8D"
TEXT_SUAVE = "#93A1B0"

# Acento (verde Bling)
GREEN = "#2FA84F"
GREEN_DARK = "#248A40"
GREEN_SOFT = "#E9F7EE"

# Semânticos
RED = "#E05252"
AMBER = "#E8A33D"
BLUE = "#3B82F6"

# Compatibilidade com código existente
DEEP_GREEN = TEXT

# Paleta de gráficos: verdes graduados + neutros (legível e sóbria)
CHART_SEQUENCE = [GREEN, "#7FC99A", "#B9E3C8", "#8AA0B4", "#C6D0DA", AMBER]

PLOTLY_LAYOUT = dict(
    template="plotly_white",
    font=dict(family="Inter, sans-serif", color=TEXT, size=12),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    colorway=CHART_SEQUENCE,
    margin=dict(l=8, r=8, t=32, b=8),
    legend=dict(bgcolor="rgba(0,0,0,0)", orientation="h", y=-0.15, x=0),
    hoverlabel=dict(bgcolor=CARD, bordercolor=BORDER, font=dict(color=TEXT)),
)


def apply_layout(fig):
    fig.update_layout(**PLOTLY_LAYOUT)
    fig.update_xaxes(gridcolor=BORDER, zerolinecolor=BORDER, linecolor=BORDER)
    fig.update_yaxes(gridcolor=BORDER, zerolinecolor=BORDER, linecolor=BORDER)
    return fig


def moeda(valor):
    """Formata em Real no padrão brasileiro: R$ 1.234,56"""
    return "R$ " + f"{valor:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")


def moeda_md(valor):
    """Use SEMPRE esta em `st.markdown`, `st.caption` e afins.

    O markdown do Streamlit lê `$...$` como fórmula matemática. Dois valores em
    R$ na mesma string fecham um par de cifrões, e tudo entre eles — inclusive
    HTML — é engolido e reaparece como texto cru na tela. Escapar a cifra
    resolve. Em `st.metric` e `st.dataframe` não há markdown, então lá vale a
    `moeda()` normal.
    """
    return moeda(valor).replace("$", r"\$")


def moeda_curta(valor):
    """Versão compacta para rótulos de gráfico: R$ 3,2 mil · R$ 1,4 mi."""
    magnitude = abs(valor)
    if magnitude >= 1_000_000:
        return "R$ " + f"{valor / 1_000_000:.1f}".replace(".", ",") + " mi"
    if magnitude >= 1_000:
        return "R$ " + f"{valor / 1_000:.1f}".replace(".", ",") + " mil"
    return moeda(valor)


def data_br(iso):
    """'2026-08-31' → '31/08/2026' (aceita também só exibir dia/mês via [:5])."""
    try:
        a, m, d = iso[:10].split("-")
        return f"{d}/{m}/{a}"
    except (ValueError, AttributeError):
        return str(iso)


def esc(texto):
    """Escapa texto vindo do usuário antes de interpolar em HTML (unsafe_allow_html)."""
    return html.escape(str(texto), quote=True)
