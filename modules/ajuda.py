"""Botão de ajuda das telas — o "?" que abre a explicação e o vídeo.

Isolado porque é transversal: toda tela usa, nenhuma tela é dona. O texto de
cada uma mora em `conteudo_ajuda.py`, para acrescentar vídeo sem abrir código
de interface.

Por que um painel e não o balão de ajuda do Streamlit: o balão (`help=`) aceita
só texto curto, não abre vídeo e some quando o mouse sai. Ele continua bom para
explicar um campo — para explicar uma tela inteira, o painel cabe mais e fica
aberto enquanto a pessoa lê.
"""

import streamlit as st

import conteudo_ajuda
import theme


def botao(titulo):
    """Desenha o "?" ao lado do título e, se aberto, o painel de ajuda.

    Devolve True quando o painel está aberto — útil se a tela quiser encolher
    algo enquanto a ajuda ocupa espaço.
    """
    ajuda = conteudo_ajuda.para(titulo)
    if not ajuda:
        return False

    chave = f"ajuda_aberta_{titulo}"
    aberto = st.session_state.get(chave, False)

    if st.button("❔ Como funciona", key=f"btn_{chave}",
                 help="Explicação desta tela"):
        st.session_state[chave] = not aberto
        st.rerun()

    if not st.session_state.get(chave):
        return False

    with st.container(border=True):
        st.markdown(ajuda["texto"])

        if ajuda.get("video"):
            st.video(ajuda["video"])
        else:
            st.caption("Vídeo explicativo em breve.")

        if st.button("Fechar", key=f"fechar_{chave}"):
            st.session_state[chave] = False
            st.rerun()

    return True


def render(conn=None, usuario=None):
    """Tela de ajuda inteira, dentro de Configurações.

    Mesmo conteúdo do "?" de cada tela, lido do mesmo catálogo — quem prefere
    ler tudo de uma vez, ou procurar algo que não sabe onde fica, acha aqui.
    """
    st.markdown(
        "Explicação de cada tela do sistema. O mesmo texto aparece no **❔ Como "
        "funciona** no alto de cada uma."
    )

    titulos = list(conteudo_ajuda.AJUDA)
    escolha = st.selectbox("Tela", titulos, key="ajuda_tela_escolhida")

    conteudo = conteudo_ajuda.para(escolha)
    with st.container(border=True):
        st.markdown(f"##### {escolha}")
        st.markdown(conteudo["texto"])
        if conteudo.get("video"):
            st.video(conteudo["video"])
        else:
            st.caption("Vídeo explicativo em breve.")

    com_video = sum(1 for a in conteudo_ajuda.AJUDA.values() if a.get("video"))
    st.caption(
        f"{len(titulos)} telas documentadas · {com_video} com vídeo. "
        "Para acrescentar um vídeo, cole o link do YouTube em `conteudo_ajuda.py`."
    )


def dica(texto):
    """Texto curto de apoio, no tom das telas. Para explicar um detalhe sem
    abrir o painel inteiro."""
    st.markdown(
        f"<div style='color:{theme.TEXT_MUTED};font-size:0.82rem;margin:-4px 0 10px;'>"
        f"{texto}</div>",
        unsafe_allow_html=True,
    )
