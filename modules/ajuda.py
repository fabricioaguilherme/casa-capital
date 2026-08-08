"""Ajuda das telas — o "❔ Como funciona" e a tela completa em Configurações.

Isolado porque é transversal: toda tela usa, nenhuma tela é dona.

O **texto** mora em `conteudo_ajuda.py` (é conteúdo escrito, versionado junto
com o código). O **link do vídeo** mora no banco, porque o dono grava vídeo
quando quer e não deve depender de publicar versão nova para colar um link.

Por que uma janela (`st.dialog`) e não o balão nativo (`help=`): o balão aceita
só texto curto, não abre vídeo e some quando o mouse sai. Para explicar um
campo ele continua bom; para explicar uma tela, a janela cabe mais, abre por
cima com a largura toda e fica aberta enquanto a pessoa lê.
"""

import streamlit as st

import auth
import conteudo_ajuda
import database as db
import theme


def _url_video(conn, chave, padrao=""):
    """Link do banco; se não houver, o que estiver no catálogo em código."""
    if conn is not None:
        do_banco = db.video_ajuda(conn, chave)
        if do_banco:
            return do_banco
    return padrao or ""


@st.dialog("Como funciona", width="large")
def _painel(titulo, conn):
    """O conteúdo da ajuda, numa janela por cima da tela.

    Antes isto era um quadro desenhado ali mesmo, dentro da coluna estreita do
    cabeçalho — o texto saía espremido numa faixa de quatro palavras por linha
    e o vídeo ficava do tamanho de um selo. A janela usa a largura toda.
    """
    conteudo = conteudo_ajuda.para(titulo)
    st.markdown(conteudo["texto"])

    url = _url_video(conn, conteudo_ajuda.chave_video(titulo), conteudo.get("video"))
    if url:
        st.video(url)

    # Cada assunto tem vídeo próprio: é o que liga o vídeo à dica, e não à
    # tela inteira. O balão nativo (help=) não aceitaria vídeo nenhum.
    assuntos = conteudo_ajuda.topicos(titulo)
    if assuntos:
        st.divider()
        rotulos = [a["titulo"] for a in assuntos]
        escolhido = st.radio("Assunto", rotulos, key=f"assunto_{titulo}", horizontal=True)
        assunto = next(a for a in assuntos if a["titulo"] == escolhido)
        st.markdown(assunto["texto"])
        url_assunto = _url_video(
            conn, conteudo_ajuda.chave_video(titulo, escolhido), assunto.get("video"))
        if url_assunto:
            st.video(url_assunto)

    st.divider()
    if st.button("Fechar", key=f"fechar_ajuda_{titulo}", use_container_width=True):
        st.rerun()  # dentro de janela, é isto que fecha


def botao(titulo, conn=None):
    """Desenha o "❔ Como funciona" ao lado do título da tela."""
    if not conteudo_ajuda.para(titulo):
        return False

    # Sem estado guardado de propósito: a janela é um fragmento do Streamlit,
    # então ela se mantém aberta sozinha e o "X" fecha de verdade. Com um
    # sinalizador em session_state, fechar pelo "X" reabriria no rerun seguinte.
    # Ícone do Material em vez do emoji "❔": o emoji sai pálido e fininho na
    # fonte do tema, e era o que deixava o botão com cara de defeito.
    if st.button("Como funciona", icon=":material/help:", key=f"btn_ajuda_{titulo}",
                 help="Explicação desta tela", use_container_width=True):
        _painel(titulo, conn)
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
        format_func=lambda x: (
            "🎬 " if any(videos.get(k) for _, k in conteudo_ajuda.tudo_que_aceita_video(x))
            else ""
        ) + x,
    )

    itens = conteudo_ajuda.tudo_que_aceita_video(escolha)
    rotulos = [f"{'🎬 ' if videos.get(k) else ''}{r}" for r, k in itens]
    indice = rotulos.index(st.radio("Assunto", rotulos, key=f"ajuda_assunto_{escolha}"))
    rotulo, chave = itens[indice]

    conteudo = conteudo_ajuda.para(escolha)
    if indice == 0:
        texto, padrao = conteudo["texto"], conteudo.get("video")
    else:
        assunto = conteudo_ajuda.topicos(escolha)[indice - 1]
        texto, padrao = assunto["texto"], assunto.get("video")

    url = _url_video(conn, chave, padrao)
    with st.container(border=True):
        st.markdown(f"##### {rotulo}")
        st.markdown(texto)
        if url:
            st.video(url)
        else:
            st.caption("Sem vídeo ainda.")

    if dono:
        _editar_video(conn, chave, url, rotulo)

    total = sum(len(conteudo_ajuda.tudo_que_aceita_video(x)) for x in telas)
    com = sum(1 for x in telas
              for _, k in conteudo_ajuda.tudo_que_aceita_video(x) if videos.get(k))
    st.caption(
        f"{total} assunto(s) em {len(telas)} tela(s) · {com} com vídeo."
        + ("" if dono else " Só o dono do sistema cadastra vídeos.")
    )


def _editar_video(conn, chave, url_atual, rotulo):
    st.markdown(f"##### 🎬 Vídeo de « {rotulo} »")
    with st.form(f"ajuda_video_{chave}"):
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
            db.salvar_video_ajuda(conn, chave, limpa)
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
