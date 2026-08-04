import hashlib
import hmac
import secrets

import streamlit as st

import conexao
import database as db
import theme

# Token de sessão trafega como parâmetro da URL: é 100% servidor, sem depender
# de JavaScript, então sobrevive ao recarregamento da página de forma confiável.
PARAM_SESSAO = "sessao"
DIAS_SESSAO = 30

# PBKDF2-HMAC-SHA256: derivação lenta de propósito, dificulta força bruta.
PBKDF2_ITERACOES = 240_000
SENHA_MIN = 6


def hash_senha(senha, salt=None):
    """Hash forte (PBKDF2). O salt é armazenado em hex na coluna existente."""
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac(
        "sha256", senha.encode(), bytes.fromhex(salt), PBKDF2_ITERACOES
    ).hex()
    return h, salt


def _hash_legado(senha, salt):
    """Formato antigo (SHA-256 simples) — mantido só para migrar contas existentes."""
    return hashlib.sha256((salt + senha).encode()).hexdigest()


def verificar_senha(senha, senha_hash, salt):
    """True se a senha confere no formato novo OU no legado (comparação em tempo constante)."""
    novo, _ = hash_senha(senha, salt)
    if hmac.compare_digest(novo, senha_hash):
        return True
    return hmac.compare_digest(_hash_legado(senha, salt), senha_hash)


def _verificar_e_migrar(conn, user, senha):
    """Valida o login; se o hash ainda for do formato antigo, regrava no formato novo."""
    novo, _ = hash_senha(senha, user["salt"])
    if hmac.compare_digest(novo, user["senha_hash"]):
        return True
    if hmac.compare_digest(_hash_legado(senha, user["salt"]), user["senha_hash"]):
        h, s = hash_senha(senha)  # salt novo junto
        db.atualizar_senha(conn, user["id"], h, s)
        return True
    return False


def _sessao_publica(registro):
    """Só o necessário vai para a sessão — hash e salt nunca ficam em memória de UI."""
    return {"id": registro["id"], "nome": registro["nome"], "login": registro["login"]}


def _enriquecer_com_grupo(conn, usuario):
    """Adiciona grupo_id e papel ao dict do usuário.
    Retorna o próprio dict (modificado) se encontrado, ou None se sem grupo."""
    email = usuario.get("login") or ""
    membro = db.grupo_do_usuario(conn, email)
    if not membro:
        return None
    usuario["grupo_id"] = membro["grupo_id"]
    usuario["papel"] = membro["papel"]
    return usuario


# ── Login com Google (OIDC nativo do Streamlit) ──────────────────────────

def google_configurado():
    """True se as credenciais do Google estiverem no secrets.toml."""
    try:
        return bool(st.secrets.get("auth", {}).get("google", {}).get("client_id"))
    except Exception:
        return False


def _emails_autorizados():
    try:
        return [e.strip().lower() for e in st.secrets["acesso"]["emails_autorizados"]]
    except Exception:
        return []


def e_super_admin(email):
    """Dono do sistema: pode criar grupos e ver a lista de todos eles.

    Ser 'admin' apenas dá poder dentro do próprio grupo. Sem essa separação,
    o admin de uma família enxergaria o nome e os e-mails das outras famílias.
    Lista vazia = ninguém é super admin (falha fechada, de propósito).
    """
    if not email:
        return False
    try:
        donos = [e.strip().lower() for e in st.secrets["acesso"]["emails_super_admin"]]
    except Exception:
        return False
    return email.strip().lower() in donos


def _usuario_do_google(conn, info):
    """Casa a conta Google com um usuário do banco. Cria no primeiro acesso.

    Só e-mails da lista de autorizados passam — sem isso, qualquer conta
    Google do mundo entraria no app. Além disso, o e-mail precisa estar em
    usuarios_grupo para receber um grupo_id.
    """
    email = (info.get("email") or "").lower()
    if not email or email not in _emails_autorizados():
        return None

    # Garante que o registro de usuário existe
    registro = db.buscar_usuario_por_email(conn, email)
    if not registro:
        nome = info.get("name") or email.split("@")[0]
        existente = db.buscar_usuario_por_login(conn, email)
        if existente:
            db.vincular_email(conn, existente["id"], email)
            registro = db.buscar_usuario_por_email(conn, email)
        else:
            db.criar_usuario_google(conn, nome, email)
            registro = db.buscar_usuario_por_email(conn, email)

    usuario = _sessao_publica(registro)

    # Verifica pertencimento a um grupo
    enriquecido = _enriquecer_com_grupo(conn, usuario)
    if enriquecido is None:
        st.session_state["sem_grupo"] = email
        return None
    return enriquecido


def _token_da_url():
    try:
        return st.query_params.get(PARAM_SESSAO)
    except Exception:
        return None


def usuario_logado(conn=None):
    """Usuário da sessão atual.

    Ordem: sessão em memória → conta Google já autenticada → token da URL.
    """
    usuario = st.session_state.get("usuario")
    if usuario:
        return usuario

    if conn is None:
        return None

    # Google: o próprio Streamlit mantém a sessão, não precisamos de token
    if google_configurado():
        try:
            if getattr(st.user, "is_logged_in", False):
                achado = _usuario_do_google(conn, dict(st.user))
                if achado:
                    st.session_state["usuario"] = achado
                    return achado
                st.session_state["email_nao_autorizado"] = st.user.get("email", "")
                return None
        except Exception:
            pass

    token = _token_da_url()
    if not token:
        return None

    registro = db.usuario_por_sessao(conn, token)
    if not registro:
        # token inválido ou expirado — limpa a URL para não ficar preso
        st.query_params.clear()
        return None

    usuario = _sessao_publica(registro)
    # Enriquece com grupo (o login para usuários Google é o próprio e-mail)
    _enriquecer_com_grupo(conn, usuario)

    st.session_state["usuario"] = usuario
    st.session_state["sessao_token"] = token
    return usuario


def _iniciar_sessao(conn, registro):
    """Registra a sessão no banco e guarda o token na URL."""
    token = db.criar_sessao(conn, registro["id"], dias=DIAS_SESSAO)
    st.session_state["usuario"] = _sessao_publica(registro)
    st.session_state["sessao_token"] = token
    st.query_params[PARAM_SESSAO] = token


def logout(conn=None):
    token = st.session_state.get("sessao_token") or _token_da_url()
    if conn is not None:
        db.encerrar_sessao(conn, token)
    st.session_state.pop("usuario", None)
    st.session_state.pop("sessao_token", None)
    st.query_params.clear()

    if google_configurado():
        try:
            if getattr(st.user, "is_logged_in", False):
                st.logout()   # já provoca o recarregamento
                return
        except Exception:
            pass
    st.rerun()


def _validar_novo_usuario(conn, nome, login, senha, exigir_login_livre=True):
    """Devolve mensagem de erro, ou None se estiver tudo certo."""
    if not nome.strip() or not login.strip() or not senha:
        return "Preencha todos os campos."
    if len(senha) < SENHA_MIN:
        return f"A senha precisa de pelo menos {SENHA_MIN} caracteres."
    if " " in login.strip():
        return "O login não pode conter espaços."
    if exigir_login_livre and db.buscar_usuario_por_login(conn, login.strip().lower()):
        return "Esse login já existe."
    return None


def tela_login(conn):
    usuarios = db.listar_usuarios(conn)

    # Coluna central estreita — caixa de login não ocupa a largura toda
    _, centro, _ = st.columns([1, 1.15, 1])

    with centro:
        logo = theme.imagem_base64("logo.png")
        st.markdown(
            f"""<div class="login-topo">
            <img class="login-logo" src="{logo}" alt="Casa Capital">
            <p class="login-sub">Controle, organize e faça crescer<br>o patrimônio da sua família.</p>
            </div>""",
            unsafe_allow_html=True,
        )

        # ── Caminho Google: preferido quando configurado ──────────────
        if google_configurado():
            barrado = st.session_state.pop("email_nao_autorizado", None)
            if barrado:
                st.error(
                    f"A conta **{theme.esc(barrado)}** não tem permissão de acesso. "
                    "Peça para o administrador incluir esse e-mail."
                )
                if st.button("Sair e tentar outra conta", use_container_width=True):
                    st.logout()

            with st.container(border=True):
                st.markdown("**Entrar com sua conta Google**")
                st.caption("Só e-mails autorizados conseguem acessar.")
                if st.button("🔐  Entrar com Google", use_container_width=True, type="primary"):
                    st.login("google")

            st.markdown(
                '<div class="login-rodape">Acesso restrito aos membros da família.</div>',
                unsafe_allow_html=True,
            )
            return None

        # ── Modo nuvem sem Google configurado: bloqueio de segurança ──
        # Nunca exibir formulário manual quando o app está rodando na nuvem
        # (Turso presente = implantação remota). Qualquer pessoa com o link
        # poderia criar um admin — risco crítico de segurança.
        if conexao.modo() == "nuvem":
            with st.container(border=True):
                st.error(
                    "⚠️ **Acesso bloqueado.** Esta versão online só aceita "
                    "login via Google. Configure as credenciais OAuth nas "
                    "Secrets do Streamlit Cloud para liberar o acesso."
                )
            st.markdown(
                '<div class="login-rodape">Acesso restrito aos membros da família.</div>',
                unsafe_allow_html=True,
            )
            return None

        if not usuarios:
            with st.container(border=True):
                st.markdown("**Criar o primeiro acesso**")
                st.caption("Este será o administrador da família.")
                with st.form("primeiro_usuario"):
                    nome = st.text_input("Seu nome", placeholder="Ex: Fabricio")
                    login = st.text_input("Login", placeholder="sem espaços")
                    senha = st.text_input("Senha", type="password")
                    senha2 = st.text_input("Confirmar senha", type="password")
                    enviar = st.form_submit_button("Criar acesso", use_container_width=True)
                if enviar:
                    erro = _validar_novo_usuario(conn, nome, login, senha, exigir_login_livre=False)
                    if erro:
                        st.error(erro)
                    elif senha != senha2:
                        st.error("As senhas não conferem.")
                    else:
                        senha_hash, salt = hash_senha(senha)
                        db.criar_usuario(conn, nome.strip(), login.strip().lower(), senha_hash, salt)
                        st.success("Acesso criado! Faça login abaixo.")
                        st.rerun()
            st.markdown(
                '<div class="login-rodape">Seus dados ficam salvos apenas neste computador.</div>',
                unsafe_allow_html=True,
            )
            return None

        tab_login, tab_novo = st.tabs(["Entrar", "Novo membro"])

        with tab_login:
            with st.container(border=True):
                with st.form("login"):
                    login = st.text_input("Login")
                    senha = st.text_input("Senha", type="password")
                    entrar = st.form_submit_button("Entrar", use_container_width=True)
                if entrar:
                    user = db.buscar_usuario_por_login(conn, login.strip().lower())
                    if user and _verificar_e_migrar(conn, user, senha):
                        _iniciar_sessao(conn, user)
                        st.rerun()
                    else:
                        st.error("Login ou senha inválidos.")
                st.caption("Você permanece conectado por 30 dias neste navegador.")

        with tab_novo:
            with st.container(border=True):
                st.caption("Qualquer pessoa da família com acesso pode cadastrar um novo membro.")
                with st.form("novo_membro"):
                    nome = st.text_input("Nome do novo membro")
                    login = st.text_input("Login", key="novo_login", placeholder="sem espaços")
                    senha = st.text_input("Senha", type="password", key="novo_senha")
                    criar = st.form_submit_button("Cadastrar membro", use_container_width=True)
                if criar:
                    erro = _validar_novo_usuario(conn, nome, login, senha)
                    if erro:
                        st.error(erro)
                    else:
                        senha_hash, salt = hash_senha(senha)
                        db.criar_usuario(conn, nome.strip(), login.strip().lower(), senha_hash, salt)
                        st.success(f"Membro {nome.strip()} cadastrado! Já pode fazer login.")

        st.markdown(
            '<div class="login-rodape">Seus dados ficam salvos apenas neste computador.</div>',
            unsafe_allow_html=True,
        )

    return None
