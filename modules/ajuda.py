"""Ajuda das telas — o "❔ Como funciona" e a tela completa em Configurações.

Isolado porque é transversal: toda tela usa, nenhuma tela é dona.

O **texto** mora em `conteudo_ajuda.py` (é conteúdo escrito, versionado junto
com o código). O **link do vídeo** mora no banco, porque o dono grava vídeo
quando quer e não deve depender de publicar versão nova para colar um link.

Por que um painel e não o balão nativo (`help=`): o balão aceita só texto
curto, não abre vídeo e some quando o mouse sai. Para explicar um campo ele
continua bom; para explicar uma tela, o painel cabe mais e fica aberto
enquanto a pessoa lê.
"""

import streamlit as st

import auth
import conteudo_ajuda
import database as db
import theme


def _url_video(conn, titulo):
    """Link do banco; se não houver, o que estiver no catálogo em código."""
    if conn is not None:
        do_banco = db.video_ajuda(conn, titulo)
        if do_banco:
            return do_banco
    conteudo = conteudo_ajuda.para(titulo) or {}
    return conteudo.get("video") or ""


def botao(titulo, conn=None):
    """Desenha o "❔" ao lado do título e, se aberto, o painel de ajuda."""
    conteudo = conteudo_ajuda.para(titulo)
    if not conteudo:
        return False

    chave = f"ajuda_aberta_{titulo}"
    if st.button("❔ Como funciona", key=f"btn_{chave}", help="Explicação desta tela"):
        st.session_state[chave] = not st.session_state.get(chave, False)
        st.rerun()

    if not st.session_state.get(chave):
        return False

    with st.container(border=True):
        st.markdown(conteudo["texto"])
        url = _url_video(conn, titulo)
        if url:
            st.video(url)
        if st.button("Fechar", key=f"fechar_{chave}"):
            st.session_state[chave] = False
            st.rerun()
    return True


def render(conn, usuario):
    """Tela completa, dentro de Configurações."""
    dono = auth.e_super_admin(usuario.get("login"))

    st.markdown(
        "Explicação de cada tela. O mesmo texto aparece no **❔ Como funciona** "
        "no alto de cada uma."
    )

    telas = list(conteudo_ajuda.AJUDA)
    videos = db.videos_ajuda(conn)
    escolha = st.selectbox(
        "Tela", telas, key="ajuda_tela_escolhida",
        format_func=lambda t: f"{'🎬 ' if videos.get(t) else ''}{t}",
    )

    conteudo = conteudo_ajuda.para(escolha)
    url = _url_video(conn, escolha)

    with st.container(border=True):
        st.markdown(f"##### {escolha}")
        st.markdown(conteudo["texto"])
        if url:
            st.video(url)
        else:
            st.caption("Sem vídeo ainda.")

    if dono:
        _editar_video(conn, escolha, url)

    with_video = sum(1 for t in telas if _url_video(conn, t))
    st.caption(
        f"{len(telas)} telas documentadas · {with_video} com vídeo."
        + ("" if dono else " Só o dono do sistema cadastra vídeos.")
    )


def _editar_video(conn, tela, url_atual):
    st.markdown("##### 🎬 Vídeo desta tela")
    with st.form(f"ajuda_video_{tela}"):
        c1, c2 = st.columns([4, 1], vertical_alignment="bottom")
        nova = c1.text_input(
            "Link do YouTube", value=url_atual,
            placeholder="https://youtu.be/xxxxxxxxxxx",
            help="Deixe vazio para remover o vídeo desta tela.",
        )
        salvar = c2.form_submit_button("Salvar", use_container_width=True)

    if salvar:
        limpa = nova.strip()
        if limpa and not limpa.lower().startswith(("http://", "https://")):
            st.error("O endereço precisa começar com https://")
        else:
            db.salvar_video_ajuda(conn, tela, limpa)
            st.success("Vídeo removido." if not limpa else "Vídeo salvo.")
            st.rerun()

    st.caption(
        "Grave como **não listado** no YouTube e com dados de teste: quem tiver o "
        "link assiste, e você não quer o patrimônio real da família num tutorial."
    )


def dica(texto):
    """Texto curto de apoio, para explicar um detalhe sem abrir o painel."""
    st.markdown(
        f"<div style='color:{theme.TEXT_MUTED};font-size:0.82rem;margin:-4px 0 10px;'>"
        f"{texto}</div>",
        unsafe_allow_html=True,
    )
