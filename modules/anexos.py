"""Componente reutilizável de anexos.

Use em qualquer módulo:
    anexos.painel(conn, usuario, "lancamento", lancamento_id)

O vínculo é polimórfico, então serve igual para conta, patrimônio, meta etc.
Basta escolher um nome de entidade e ser consistente.
"""

import mimetypes

import streamlit as st

import database as db
import storage
import theme


def _cabecalho_conta(quantidade):
    return f"📎 Anexos ({quantidade})" if quantidade else "📎 Anexos"


def painel(conn, usuario, entidade, entidade_id, chave_ui=None, titulo=None):
    """Renderiza upload + lista de anexos de um registro."""
    chave_ui = chave_ui or f"{entidade}_{entidade_id}"
    itens = db.listar_anexos(conn, entidade, entidade_id)

    if titulo:
        st.markdown(f"**{titulo}**")

    enviados = st.file_uploader(
        "Adicionar arquivo",
        type=[e.lstrip(".") for e in sorted(storage.EXTENSOES_PERMITIDAS)],
        accept_multiple_files=True,
        key=f"upload_{chave_ui}",
        help=(
            f"Até {storage.TAMANHO_MAX_MB} MB por arquivo. "
            "No celular, o botão abre a câmera para fotografar recibos."
        ),
    )

    if enviados:
        novos, ignorados, erros = 0, 0, []
        backend = storage.obter()
        for arquivo in enviados:
            dados = arquivo.getvalue()
            try:
                storage.validar(arquivo.name, dados)
            except storage.ArquivoRecusado as e:
                erros.append(f"{arquivo.name}: {e}")
                continue

            digest = storage.hash_conteudo(dados)
            if db.anexo_duplicado(conn, entidade, entidade_id, digest):
                ignorados += 1
                continue

            chave = backend.salvar(dados, arquivo.name)
            mime = arquivo.type or mimetypes.guess_type(arquivo.name)[0]
            db.criar_anexo(
                conn, entidade, entidade_id, arquivo.name, chave, backend.nome,
                mime, len(dados), digest, usuario["id"],
            )
            novos += 1

        for e in erros:
            st.error(e)
        if ignorados:
            st.info(f"{ignorados} arquivo(s) já estavam anexados aqui — ignorados.")
        if novos:
            st.success(f"{novos} arquivo(s) anexado(s).")
            st.rerun()

    if not itens:
        st.caption("Nenhum arquivo anexado ainda.")
        return

    backend_cache = {}
    for a in itens:
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 1.2, 1])
            c1.markdown(
                f"**{theme.esc(a['nome_original'])}**  \n"
                f"<span style='color:{theme.TEXT_MUTED};font-size:0.78rem;'>"
                f"{storage.tamanho_legivel(a['tamanho'])} · "
                f"{theme.data_br(a['created_at'])}</span>",
                unsafe_allow_html=True,
            )

            bk = backend_cache.setdefault(a["backend"], storage.obter(a["backend"]))
            conteudo = bk.ler(a["chave"])

            if conteudo is None:
                c2.warning("Arquivo ausente")
            else:
                c2.download_button(
                    "Baixar", data=conteudo, file_name=a["nome_original"],
                    mime=a["mime"] or "application/octet-stream",
                    key=f"dl_{a['id']}", use_container_width=True,
                )

            if c3.button("Excluir", key=f"delanx_{a['id']}", use_container_width=True):
                db.excluir_anexo(conn, a["id"])
                st.rerun()

            if conteudo is not None and storage.e_imagem(a["nome_original"]):
                if st.checkbox("Ver imagem", key=f"ver_{a['id']}"):
                    st.image(conteudo, use_container_width=True)


def alternar(conn, usuario, entidade, entidade_id, quantidade=0, chave_ui=None):
    """Versão compacta: um checkbox que revela o painel. Ideal dentro de listas."""
    chave_ui = chave_ui or f"{entidade}_{entidade_id}"
    if st.checkbox(_cabecalho_conta(quantidade), key=f"anx_toggle_{chave_ui}"):
        painel(conn, usuario, entidade, entidade_id, chave_ui=chave_ui)
