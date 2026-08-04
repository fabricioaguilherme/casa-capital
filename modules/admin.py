"""Tela de administração de grupos e membros (acesso restrito a admins)."""

import streamlit as st

import auth
import database as db
import theme


def render(conn, usuario):
    grupo_id = usuario["grupo_id"]
    grupo = db.buscar_grupo(conn, grupo_id)
    membros = db.listar_membros_grupo(conn, grupo_id)

    # ── Info do grupo atual ───────────────────────────────────────────────
    # Tudo numa linha só: o nome do grupo muda uma vez por ano, não merece
    # meia tela de altura.
    with st.container(border=True):
        with st.form("renomear_grupo"):
            c_nome, c_botao = st.columns([4, 1], vertical_alignment="bottom")
            novo_nome = c_nome.text_input(
                f"👨‍👩‍👧‍👦 Grupo (ID {grupo_id} · criado em {theme.data_br(grupo['criado_em'][:10])})",
                value=grupo["nome"],
            )
            salvar_nome = c_botao.form_submit_button("Salvar", use_container_width=True)
        if salvar_nome and novo_nome.strip():
            db.renomear_grupo(conn, grupo_id, novo_nome.strip())
            st.success("Nome atualizado.")
            st.rerun()

    st.divider()

    # ── Membros do grupo ─────────────────────────────────────────────────
    st.markdown("#### 👥 Membros do grupo")
    if not membros:
        st.info("Nenhum membro cadastrado.")
    else:
        # Sem caixa e sem separador por membro: cada elemento a mais na vertical
        # soma o espaçamento padrão do Streamlit, e com três ou quatro pessoas
        # a lista virava rolagem à toa.
        for m in membros:
            eh_admin = m["papel"] == "admin"
            eh_eu = m["user_email"].lower() == usuario["login"].lower()
            c1, c2, c3 = st.columns([3, 1.5, 1.2], vertical_alignment="center")
            c1.markdown(
                f"**{theme.esc(m['user_email'])}**" + (" *(você)*" if eh_eu else ""),
            )
            c2.markdown(
                f"<span style='color:{theme.GREEN_DARK if eh_admin else theme.TEXT_MUTED};"
                f"font-weight:600;'>{'🔑 Admin' if eh_admin else '👤 Membro'}</span>",
                unsafe_allow_html=True,
            )
            with c3:
                if not eh_eu:
                    if st.button(
                        "Remover",
                        key=f"rem_{m['user_email']}",
                        use_container_width=True,
                    ):
                        db.remover_membro_grupo(conn, grupo_id, m["user_email"])
                        st.success(f"{m['user_email']} removido.")
                        st.rerun()

    st.divider()

    # ── Adicionar membro ─────────────────────────────────────────────────
    st.markdown("#### ➕ Adicionar membro")
    st.caption(
        "O e-mail também precisa estar na lista `emails_autorizados` do `secrets.toml` "
        "para o login via Google funcionar."
    )
    with st.container(border=True):
        with st.form("add_membro", clear_on_submit=True):
            c_email, c_papel, c_botao = st.columns([3, 1.4, 1.4], vertical_alignment="bottom")
            novo_email = c_email.text_input("E-mail", placeholder="pessoa@gmail.com")
            novo_papel = c_papel.selectbox("Papel", ["membro", "admin"])
            adicionar = c_botao.form_submit_button("Adicionar", use_container_width=True)

        if adicionar:
            if not novo_email.strip():
                st.error("Informe o e-mail.")
            elif "@" not in novo_email:
                st.error("E-mail inválido.")
            else:
                adicionado = db.adicionar_membro_grupo(
                    conn, grupo_id, novo_email.strip().lower(), novo_papel
                )
                if adicionado:
                    st.success(f"{novo_email.strip().lower()} adicionado como {novo_papel}.")
                    st.rerun()
                else:
                    st.warning("Este e-mail já é membro do grupo.")

    st.divider()

    # ── Daqui para baixo: só o dono do sistema ────────────────────────────
    # Criar grupos e enxergar os outros grupos é poder sobre o sistema inteiro,
    # não sobre a própria família. Um admin comum para por aqui.
    if not auth.e_super_admin(usuario.get("login")):
        return

    # ── Criar novo grupo ──────────────────────────────────────────────────
    st.markdown("#### 🏠 Criar novo grupo")
    st.caption(
        "Use para famílias ou casais independentes. Cada grupo tem seus próprios dados."
    )
    with st.container(border=True):
        with st.form("criar_grupo", clear_on_submit=True):
            c_nome, c_admin, c_botao = st.columns([2.2, 2.4, 1.4], vertical_alignment="bottom")
            nome_grupo = c_nome.text_input("Nome do grupo", placeholder="Ex: Família João e Maria")
            email_admin = c_admin.text_input(
                "E-mail do administrador", placeholder="admin@gmail.com"
            )
            criar = c_botao.form_submit_button("Criar grupo", use_container_width=True)

        if criar:
            if not nome_grupo.strip():
                st.error("Informe o nome do grupo.")
            elif not email_admin.strip() or "@" not in email_admin:
                st.error("Informe um e-mail válido para o administrador.")
            else:
                novo_grupo_id = db.criar_grupo(conn, nome_grupo.strip())
                db.adicionar_membro_grupo(
                    conn, novo_grupo_id, email_admin.strip().lower(), "admin"
                )
                st.success(
                    f"Grupo **{nome_grupo.strip()}** criado (ID {novo_grupo_id}). "
                    f"Admin: {email_admin.strip().lower()} — ele também precisa estar "
                    "em `emails_autorizados` para conseguir entrar."
                )

    # ── Todos os grupos (visão global) ────────────────────────────────────
    st.divider()
    st.markdown("#### 📋 Todos os grupos")
    grupos = db.listar_grupos(conn)
    for g in grupos:
        membros_g = db.listar_membros_grupo(conn, g["id"])
        ativo = "← **seu grupo**" if g["id"] == grupo_id else ""
        st.markdown(
            f"**{theme.esc(g['nome'])}** (ID {g['id']}) {ativo}  \n"
            f"<span style='color:{theme.TEXT_MUTED};font-size:0.82rem;'>"
            f"{len(membros_g)} membro(s): "
            f"{', '.join(m['user_email'] for m in membros_g)}</span>",
            unsafe_allow_html=True,
        )
