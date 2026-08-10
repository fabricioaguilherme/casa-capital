import hashlib
import hmac
import secrets

import streamlit as st

import conexao
import database as db
import theme

# Token de sessÃ£o trafega como parÃ¢metro da URL: Ã© 100% servidor, sem depender
# de JavaScript, entÃ£o sobrevive ao recarregamento da pÃ¡gina de forma confiÃ¡vel.
PARAM_SESSAO = "sessao"
DIAS_SESSAO = 30

# PBKDF2-HMAC-SHA256: derivaÃ§Ã£o lenta de propÃ³sito, dificulta forÃ§a bruta.
PBKDF2_ITERACOES = 240_000
SENHA_MIN = 6


def hash_senha(senha, salt=None):
    """Hash forte (PBKDF2). O salt Ã© armazenado em hex na coluna existente."""
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac(
        "sha256", senha.encode(), bytes.fromhex(salt), PBKDF2_ITERACOES
    ).hex()
    return h, salt


def _hash_legado(senha, salt):
    """Formato antigo (SHA-256 simples) â mantido sÃ³ para migrar contas existentes."""
    return hashlib.sha256((salt + senha).encode()).hexdigest()


def verificar_senha(senha, senha_hash, salt):
    """True se a senha confere no formato novo OU no legado (comparaÃ§Ã£o em tempo constante)."""
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
    """SÃ³ o necessÃ¡rio vai para a sessÃ£o â hash e salt nunca ficam em memÃ³ria de UI."""
    return {"id": registro["id"], "nome": registro["nome"], "login": registro["login"]}


def _enriquecer_com_grupo(conn, usuario):
    """Adiciona grupo_id e papel ao dict do usuÃ¡rio.
    Retorna o prÃ³prio dict (modificado) se encontrado, ou None se sem grupo."""
    email = usuario.get("login") or ""
    membro = db.grupo_do_usuario(conn, email)
    if not membro:
        return None
    usuario["grupo_id"] = membro["grupo_id"]
    usuario["papel"] = membro["papel"]
    grupo = db.buscar_grupo(conn, membro["grupo_id"])
    usuario["grupo_nome"] = grupo["nome"] if grupo else None
    return usuario


# ââ Login com Google (OIDC nativo do Streamlit) ââââââââââââââââââââââââââ

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

    Ser 'admin' apenas dÃ¡ poder dentro do prÃ³prio grupo. Sem essa separaÃ§Ã£o,
    o admin de uma famÃ­lia enxergaria o nome e os e-mails das outras famÃ­lias.
    Lista vazia = ninguÃ©m Ã© super admin (falha fechada, de propÃ³sito).
    """
    if not email:
        return False
    try:
        donos = [e.strip().lower() for e in st.secrets["acesso"]["emails_super_admin"]]
    except Exception:
        return False
    return email.strip().lower() in donos


# ââ RestriÃ§Ã£o por rede âââââââââââââââââââââââââââââââââââââââââââââââââââ
# Alguns usuÃ¡rios sÃ³ podem entrar de casa. Quem manda o IP verdadeiro Ã© o
# Cloudflare, no cabeÃ§alho CF-Connecting-IP; os outros nomes sÃ£o para quando o
# app Ã© acessado direto pelo endereÃ§o do Streamlit, sem passar pelo proxy.
CABECALHOS_DE_IP = ("Cf-Connecting-Ip", "X-Real-Ip", "X-Forwarded-For")


def ip_do_cliente():
    """IP de quem estÃ¡ acessando, ou None se nÃ£o der para descobrir."""
    try:
        cabecalhos = st.context.headers or {}
    except Exception:
        return None
    for nome in CABECALHOS_DE_IP:
        valor = cabecalhos.get(nome) or cabecalhos.get(nome.lower())
        if valor:
            # X-Forwarded-For vem como "cliente, proxy1, proxy2"
            return valor.split(",")[0].strip()
    return None


def ip_e_utilizavel(ip):
    """False quando o endereÃ§o nÃ£o Ã© o de quem acessa, e sim o de um servidor
    no meio do caminho.

    O Streamlit Community Cloud entrega o IP interno dele (10.x.x.x) para
    qualquer visitante. Tratar isso como 'a rede do usuÃ¡rio' Ã© pior que nÃ£o ter
    informaÃ§Ã£o: liberar essa faixa liberaria o mundo inteiro de uma vez, porque
    todo mundo chega por ela.
    """
    if not ip:
        return False
    try:
        import ipaddress
        endereco = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not (endereco.is_private or endereco.is_loopback or endereco.is_link_local)


def _redes_liberadas():
    """Faixas de IP consideradas 'de casa'. Vazio = nenhuma."""
    try:
        return [str(r).strip() for r in st.secrets["acesso"]["redes_liberadas"] if str(r).strip()]
    except Exception:
        return []


def _emails_de_qualquer_rede():
    """Quem pode entrar de qualquer lugar (vocÃ  e sua esposa)."""
    try:
        return [e.strip().lower() for e in st.secrets["acesso"]["emails_qualquer_rede"]]
    except Exception:
        return []


def rede_permitida(email):
    """(permitido, ip_visto). Quem nÃ£o estÃ¡ na lista livre sÃ³ entra de casa.

    Falha fechada de propÃ³sito: sem conseguir ler o IP, ou sem nenhuma rede
    configurada, o usuÃ¡rio restrito nÃ£o entra. PreferÃ­vel a liberar por engano
    justamente quem se quis limitar.
    """
    ip = ip_do_cliente()
    if (email or "").strip().lower() in _emails_de_qualquer_rede():
        return True, ip

    redes = _redes_liberadas()
    if not redes or not ip:
        return False, ip

    try:
        import ipaddress
        endereco = ipaddress.ip_address(ip)
    except ValueError:
        return False, ip

    for rede in redes:
        try:
            # aceita tanto "189.4.5.6" quanto "189.4.5.0/24"
            if endereco in ipaddress.ip_network(rede, strict=False):
                return True, ip
        except ValueError:
            continue
    return False, ip


def _usuario_do_google(conn, info):
    """Casa a conta Google com um usuÃ¡rio do banco. Cria no primeiro acesso.

    Quem manda Ã© o vÃ­nculo em `usuarios_grupo`, gerenciado na tela de
    AdministraÃ§Ã£o: sem grupo, ninguÃ©m passa. `emails_autorizados` virou uma
    tranca extra opcional â se a lista existir nos secrets ela Ã© respeitada,
    se nÃ£o existir o grupo decide sozinho. Assim liberar alguÃ©m Ã© um cadastro
    na tela, sem editar secrets nem reiniciar o app para todo mundo.
    """
    email = (info.get("email") or "").lower()
    if not email:
        return None

    autorizados = _emails_autorizados()
    if autorizados and email not in autorizados:
        return None

    # O grupo Ã© conferido ANTES de tocar no banco. Do contrÃ¡rio cada curioso
    # com conta Google deixaria uma linha em `usuarios` sÃ³ por ter tentado.
    membro = db.grupo_do_usuario(conn, email)
    if not membro:
        st.session_state["sem_grupo"] = email
        return None

    liberado, ip = rede_permitida(email)
    if not liberado:
        st.session_state["rede_bloqueada"] = {"email": email, "ip": ip}
        return None

    # Garante que o registro de usuÃ¡rio existe
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
    return _enriquecer_com_grupo(conn, usuario)


def _token_da_url():
    try:
        return st.query_params.get(PARAM_SESSAO)
    except Exception:
        return None


def usuario_logado(conn=None):
    """UsuÃ¡rio da sessÃ£o atual.

    Ordem: sessÃ£o em memÃ³ria â conta Google jÃ¡ autenticada â token da URL.
    """
    usuario = st.session_state.get("usuario")
    if usuario:
        return usuario

    if conn is None:
        return None

    # Google: o prÃ³prio Streamlit mantÃ©m a sessÃ£o, nÃ£o precisamos de token
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
        # token invÃ¡lido ou expirado â limpa a URL para nÃ£o ficar preso
        st.query_params.clear()
        return None

    # A restriÃ§Ã£o de rede vale aqui tambÃ©m. Sem isto, um link salvo com
    # ?sessao=... entra de qualquer lugar e passa por cima da regra: era a
    # segunda porta da casa, destrancada.
    liberado, ip = rede_permitida(registro.get("email") or registro.get("login"))
    if not liberado:
        st.session_state["rede_bloqueada"] = {
            "email": registro.get("email") or registro.get("login") or "",
            "ip": ip,
        }
        return None

    usuario = _sessao_publica(registro)
    # Enriquece com grupo (o login para usuÃ¡rios Google Ã© o prÃ³prio e-mail)
    _enriquecer_com_grupo(conn, usuario)

    st.session_state["usuario"] = usuario
    st.session_state["sessao_token"] = token
    return usuario


def _iniciar_sessao(conn, registro):
    """Registra a sessÃ£o no banco e guarda o token na URL."""
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
                st.logout()   # jÃ¡ provoca o recarregamento
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
        return "O login nÃ£o pode conter espaÃ§os."
    if exigir_login_livre and db.buscar_usuario_por_login(conn, login.strip().lower()):
        return "Esse login jÃ¡ existe."
    return None


def tela_login(conn):
    usuarios = db.listar_usuarios(conn)

    # Coluna central estreita â caixa de login nÃ£o ocupa a largura toda
    _, centro, _ = st.columns([1, 1.15, 1])

    with centro:
        logo = theme.imagem_base64("logo.png")
        st.markdown(
            f"""<div class="login-topo">
            <img class="login-logo" src="{logo}" alt="Casa Capital">
            <p class="login-sub">Controle, organize e faÃ§a crescer<br>o patrimÃ´nio da sua famÃ­lia.</p>
            </div>""",
            unsafe_allow_html=True,
        )

        # ââ Caminho Google: preferido quando configurado ââââââââââââââ
        if google_configurado():
            barrado = st.session_state.pop("email_nao_autorizado", None)
            if barrado:
                st.error(
                    f"A conta **{theme.esc(barrado)}** nÃ£o tem permissÃ£o de acesso. "
                    "PeÃ§a para o administrador incluir esse e-mail."
                )
                if st.button("Sair e tentar outra conta", use_container_width=True):
                    st.logout()

            with st.container(border=True):
                st.markdown("**Entrar com sua conta Google**")
                st.caption("SÃ³ e-mails autorizados conseguem acessar.")
                if st.button("ð  Entrar com Google", use_container_width=True, type="primary"):
                    st.login("google")

            st.markdown(
                '<div class="login-rodape">Acesso restrito aos membros da famÃ­lia.</div>',
                unsafe_allow_html=True,
            )
            return None

        # ââ Modo nuvem sem Google configurado: bloqueio de seguranÃ§a ââ
        # Nunca exibir formulÃ¡rio manual quando o app estÃ¡ rodando na nuvem
        # (Turso presente = implantaÃ§Ã£o remota). Qualquer pessoa com o link
        # poderia criar um admin â risco crÃ­tico de seguranÃ§a.
        if conexao.modo() == "nuvem":
            with st.container(border=True):
                st.error(
                    "â ï¸ **Acesso bloqueado.** Esta versÃ£o online sÃ³ aceita "
                    "login via Google. Configure as credenciais OAuth nas "
                    "Secrets do Streamlit Cloud para liberar o acesso."
                )
            st.markdown(
                '<div class="login-rodape">Acesso restrito aos membros da famÃ­lia.</div>',
                unsafe_allow_html=True,
            )
            return None

        if not usuarios:
            with st.container(border=True):
                st.markdown("**Criar o primeiro acesso**")
                st.caption("Este serÃ¡ o administrador da famÃ­lia.")
                with st.form("primeiro_usuario"):
                    nome = st.text_input("Seu nome", placeholder="Ex: Fabricio")
                    login = st.text_input("Login", placeholder="sem espaÃ§os")
                    senha = st.text_input("Senha", type="password")
                    senha2 = st.text_input("Confirmar senha", type="password")
                    enviar = st.form_submit_button("Criar acesso", use_container_width=True)
                if enviar:
                    erro = _validar_novo_usuario(conn, nome, login, senha, exigir_login_livre=False)
                    if erro:
                        st.error(erro)
                    elif senha != senha2:
                        st.error("As senhas nÃ£o conferem.")
                    else:
                        senha_hash, salt = hash_senha(senha)
                        db.criar_usuario(conn, nome.strip(), login.strip().lower(), senha_hash, salt)
                        st.success("Acesso criado! FaÃ§a login abaixo.")
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
                        st.error("Login ou senha invÃ¡lidos.")
                st.caption("VocÃª permanece conectado por 30 dias neste navegador.")

        with tab_novo:
            with st.container(border=True):
                st.caption("Qualquer pessoa da famÃ­lia com acesso pode cadastrar um novo membro.")
                with st.form("novo_membro"):
                    nome = st.text_input("Nome do novo membro")
                    login = st.text_input("Login", key="novo_login", placeholder="sem espaÃ§os")
                    senha = st.text_input("Senha", type="password", key="novo_senha")
                    criar = st.form_submit_button("Cadastrar membro", use_container_width=True)
                if criar:
                    erro = _validar_novo_usuario(conn, nome, login, senha)
                    if erro:
                        st.error(erro)
                    else:
                        senha_hash, salt = hash_senha(senha)
                        db.criar_usuario(conn, nome.strip(), login.strip().lower(), senha_hash, salt)
                        st.success(f"Membro {nome.strip()} cadastrado! JÃ¡ pode fazer login.")

        st.markdown(
            '<div class="login-rodape">Seus dados ficam salvos apenas neste computador.</div>',
            unsafe_allow_html=True,
        )

    return None
