import os
import secrets
import uuid
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

import conexao

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "financeiro.db")

FORMAS_PAGAMENTO = [
    "Pix", "Cartão de crédito", "Cartão de débito", "Transferência / TED",
    "Boleto", "Débito automático", "Dinheiro", "Cheque", "Outro",
]


def get_connection():
    """Conexão com o banco — SQLite local ou Turso, decidido por conexao.py."""
    return conexao.conectar()


def init_db(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS grupos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        criado_em TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS usuarios_grupo (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        grupo_id INTEGER NOT NULL REFERENCES grupos(id),
        user_email TEXT NOT NULL,
        papel TEXT NOT NULL DEFAULT 'membro'
    );

    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        login TEXT UNIQUE NOT NULL,
        senha_hash TEXT NOT NULL,
        salt TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS sessoes (
        token TEXT PRIMARY KEY,
        usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
        criado_em TEXT NOT NULL,
        expira_em TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS contas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        tipo TEXT NOT NULL CHECK (tipo IN ('banco', 'carteira', 'cartao')),
        saldo_inicial REAL NOT NULL DEFAULT 0,
        cor TEXT DEFAULT '#6366f1',
        ativo INTEGER NOT NULL DEFAULT 1,
        grupo_id INTEGER REFERENCES grupos(id)
    );

    CREATE TABLE IF NOT EXISTS cartoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conta_id INTEGER NOT NULL REFERENCES contas(id),
        dia_fechamento INTEGER NOT NULL,
        dia_vencimento INTEGER NOT NULL,
        limite REAL NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS categorias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        tipo TEXT NOT NULL CHECK (tipo IN ('receita', 'despesa')),
        categoria_pai_id INTEGER REFERENCES categorias(id),
        icone TEXT DEFAULT '💰'
    );

    CREATE TABLE IF NOT EXISTS lancamentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data TEXT NOT NULL,
        conta_id INTEGER NOT NULL REFERENCES contas(id),
        categoria_id INTEGER NOT NULL REFERENCES categorias(id),
        descricao TEXT NOT NULL,
        valor REAL NOT NULL,
        tipo TEXT NOT NULL CHECK (tipo IN ('entrada', 'saida')),
        status TEXT NOT NULL CHECK (status IN ('pago', 'pendente')) DEFAULT 'pendente',
        usuario_id INTEGER REFERENCES usuarios(id),
        grupo_id INTEGER REFERENCES grupos(id),
        cartao_id INTEGER REFERENCES cartoes(id),
        compra_id TEXT,
        parcela_atual INTEGER DEFAULT 1,
        parcela_total INTEGER DEFAULT 1,
        recorrencia_id TEXT,
        forma_pagamento TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS patrimonio_itens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        tipo TEXT NOT NULL CHECK (tipo IN ('ativo', 'passivo')),
        categoria TEXT NOT NULL,
        valor_atual REAL NOT NULL,
        data_atualizacao TEXT NOT NULL,
        usuario_id INTEGER REFERENCES usuarios(id),
        grupo_id INTEGER REFERENCES grupos(id)
    );

    CREATE TABLE IF NOT EXISTS investimentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        tipo TEXT NOT NULL,
        valor_aportado REAL NOT NULL,
        valor_atual REAL NOT NULL,
        data TEXT NOT NULL,
        usuario_id INTEGER REFERENCES usuarios(id),
        grupo_id INTEGER REFERENCES grupos(id)
    );

    -- Anexos: só a FICHA do arquivo. O binário fica no disco (ver storage.py),
    -- para o backup do banco não inchar e a migração p/ nuvem ser indolor.
    -- entidade/entidade_id é polimórfico: serve para lançamento, conta, patrimônio…
    CREATE TABLE IF NOT EXISTS anexos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entidade TEXT NOT NULL,
        entidade_id INTEGER NOT NULL,
        nome_original TEXT NOT NULL,
        chave TEXT NOT NULL,
        backend TEXT NOT NULL DEFAULT 'local',
        mime TEXT,
        tamanho INTEGER NOT NULL DEFAULT 0,
        hash_sha256 TEXT,
        usuario_id INTEGER REFERENCES usuarios(id),
        grupo_id INTEGER REFERENCES grupos(id),
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS metas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        valor_alvo REAL NOT NULL,
        data_alvo TEXT,
        valor_atual REAL NOT NULL DEFAULT 0,
        usuario_id INTEGER REFERENCES usuarios(id),
        grupo_id INTEGER REFERENCES grupos(id)
    );
    """)
    conn.commit()
    _migrar_schema(conn)
    _seed_categorias(conn)


def _migrar_schema(conn):
    """Acrescenta colunas/índices novos em bancos criados antes deles existirem."""
    colunas = [c["name"] for c in conn.execute("PRAGMA table_info(lancamentos)").fetchall()]
    if "forma_pagamento" not in colunas:
        conn.execute("ALTER TABLE lancamentos ADD COLUMN forma_pagamento TEXT")

    cols_usuarios = [c["name"] for c in conn.execute("PRAGMA table_info(usuarios)").fetchall()]
    if "email" not in cols_usuarios:
        conn.execute("ALTER TABLE usuarios ADD COLUMN email TEXT")

    # Multi-tenancy: adiciona grupo_id às tabelas de dados
    _add_column_if_missing(conn, "contas", "grupo_id", "INTEGER REFERENCES grupos(id)")
    _add_column_if_missing(conn, "lancamentos", "grupo_id", "INTEGER REFERENCES grupos(id)")
    _add_column_if_missing(conn, "patrimonio_itens", "grupo_id", "INTEGER REFERENCES grupos(id)")
    _add_column_if_missing(conn, "investimentos", "grupo_id", "INTEGER REFERENCES grupos(id)")
    _add_column_if_missing(conn, "metas", "grupo_id", "INTEGER REFERENCES grupos(id)")
    _add_column_if_missing(conn, "anexos", "grupo_id", "INTEGER REFERENCES grupos(id)")

    # Categorias e formas de pagamento aceitam grupo_id NULO de propósito:
    # NULO é item de fábrica, que todo grupo enxerga; preenchido é criação de
    # uma família, visível só para ela.
    _add_column_if_missing(conn, "categorias", "grupo_id", "INTEGER REFERENCES grupos(id)")

    # Identificador da transação no extrato do banco (FITID do OFX). É ele que
    # deixa subir o mesmo extrato de novo sem duplicar: o que já tem fitid
    # gravado é reconhecido e ignorado.
    _add_column_if_missing(conn, "lancamentos", "fitid", "TEXT")

    conn.executescript("""
    CREATE TABLE IF NOT EXISTS formas_pagamento (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        grupo_id INTEGER REFERENCES grupos(id)
    );

    -- Link do vídeo de ajuda de cada tela. Fica no banco, e não no código,
    -- para o dono colar um vídeo novo sem precisar publicar versão. Sem
    -- grupo_id de propósito: a ajuda é do sistema, igual para todas as
    -- famílias — por isso só o super admin edita.
    CREATE TABLE IF NOT EXISTS ajuda_videos (
        tela TEXT PRIMARY KEY,
        url TEXT NOT NULL,
        atualizado_em TEXT DEFAULT (datetime('now'))
    );
    """)
    _seed_formas_pagamento(conn)

    conn.executescript("""
    CREATE INDEX IF NOT EXISTS idx_lanc_data ON lancamentos(data);
    CREATE INDEX IF NOT EXISTS idx_lanc_status ON lancamentos(status);
    CREATE INDEX IF NOT EXISTS idx_lanc_conta ON lancamentos(conta_id);
    CREATE INDEX IF NOT EXISTS idx_lanc_grupo ON lancamentos(grupo_id);
    CREATE INDEX IF NOT EXISTS idx_contas_grupo ON contas(grupo_id);
    CREATE INDEX IF NOT EXISTS idx_anexos_entidade ON anexos(entidade, entidade_id);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_usuarios_grupo_unique ON usuarios_grupo(grupo_id, user_email);
    """)
    conn.commit()


def _add_column_if_missing(conn, tabela, coluna, definicao):
    """ALTER TABLE seguro — sem erro se a coluna já existir."""
    cols = [c["name"] for c in conn.execute(f"PRAGMA table_info({tabela})").fetchall()]
    if coluna not in cols:
        conn.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {definicao}")
        conn.commit()


def _seed_categorias(conn):
    existentes = conn.execute("SELECT COUNT(*) as total FROM categorias").fetchone()["total"]
    if existentes > 0:
        return
    padrao = [
        ("Salário", "receita", "💼"), ("Pró-labore", "receita", "💼"),
        ("Distribuição de Lucros", "receita", "📈"), ("Outras Receitas", "receita", "💰"),
        ("Moradia", "despesa", "🏠"), ("Alimentação", "despesa", "🍽️"),
        ("Transporte", "despesa", "🚗"), ("Saúde", "despesa", "💊"),
        ("Educação", "despesa", "📚"), ("Lazer", "despesa", "🎉"),
        ("Assinaturas", "despesa", "📺"), ("Cartão de Crédito", "despesa", "💳"),
        ("Impostos", "despesa", "🧾"), ("Outras Despesas", "despesa", "📦"),
    ]
    conn.executemany(
        "INSERT INTO categorias (nome, tipo, icone) VALUES (?, ?, ?)", padrao
    )
    conn.commit()


def _seed_formas_pagamento(conn):
    """Popula a lista de fábrica uma única vez (grupo_id nulo = vale para todos)."""
    existentes = conn.execute(
        "SELECT COUNT(*) as total FROM formas_pagamento WHERE grupo_id IS NULL"
    ).fetchone()["total"]
    if existentes > 0:
        return
    conn.executemany(
        "INSERT INTO formas_pagamento (nome, grupo_id) VALUES (?, NULL)",
        [(f,) for f in FORMAS_PAGAMENTO],
    )
    conn.commit()


# ── Grupos (multi-tenancy) ────────────────────────────────────────────────

def listar_grupos(conn):
    return conn.execute("SELECT * FROM grupos ORDER BY criado_em").fetchall()


def criar_grupo(conn, nome):
    cur = conn.execute("INSERT INTO grupos (nome) VALUES (?)", (nome,))
    conn.commit()
    return cur.lastrowid


def buscar_grupo(conn, grupo_id):
    return conn.execute("SELECT * FROM grupos WHERE id = ?", (grupo_id,)).fetchone()


def renomear_grupo(conn, grupo_id, novo_nome):
    conn.execute("UPDATE grupos SET nome = ? WHERE id = ?", (novo_nome, grupo_id))
    conn.commit()


def grupo_do_usuario(conn, email):
    """Retorna o primeiro registro de usuarios_grupo para o e-mail, ou None."""
    return conn.execute(
        "SELECT * FROM usuarios_grupo WHERE lower(user_email) = lower(?) LIMIT 1",
        (email,),
    ).fetchone()


def listar_membros_grupo(conn, grupo_id):
    return conn.execute(
        "SELECT * FROM usuarios_grupo WHERE grupo_id = ? ORDER BY papel DESC, user_email",
        (grupo_id,),
    ).fetchall()


def adicionar_membro_grupo(conn, grupo_id, email, papel="membro"):
    """Insere membro; ignora se o e-mail já pertencer ao grupo."""
    existente = conn.execute(
        "SELECT id FROM usuarios_grupo WHERE grupo_id = ? AND lower(user_email) = lower(?)",
        (grupo_id, email),
    ).fetchone()
    if existente:
        return False
    conn.execute(
        "INSERT INTO usuarios_grupo (grupo_id, user_email, papel) VALUES (?, ?, ?)",
        (grupo_id, email.lower(), papel),
    )
    conn.commit()
    return True


def remover_membro_grupo(conn, grupo_id, email):
    conn.execute(
        "DELETE FROM usuarios_grupo WHERE grupo_id = ? AND lower(user_email) = lower(?)",
        (grupo_id, email),
    )
    conn.commit()


# ── Usuários ─────────────────────────────────────────────────────────────

def listar_usuarios(conn):
    return conn.execute("SELECT * FROM usuarios ORDER BY nome").fetchall()


def criar_usuario(conn, nome, login, senha_hash, salt):
    conn.execute(
        "INSERT INTO usuarios (nome, login, senha_hash, salt) VALUES (?, ?, ?, ?)",
        (nome, login, senha_hash, salt),
    )
    conn.commit()


def buscar_usuario_por_login(conn, login):
    return conn.execute("SELECT * FROM usuarios WHERE login = ?", (login,)).fetchone()


def buscar_usuario_por_email(conn, email):
    return conn.execute(
        "SELECT * FROM usuarios WHERE lower(email) = lower(?)", (email,)
    ).fetchone()


def criar_usuario_google(conn, nome, email):
    """Usuário que entra pelo Google não tem senha própria."""
    cur = conn.execute(
        "INSERT INTO usuarios (nome, login, email, senha_hash, salt) VALUES (?, ?, ?, '', '')",
        (nome, email.lower(), email.lower()),
    )
    conn.commit()
    return cur.lastrowid


def vincular_email(conn, usuario_id, email):
    """Liga um e-mail Google a um usuário que já existia com login e senha."""
    conn.execute("UPDATE usuarios SET email = lower(?) WHERE id = ?", (email, usuario_id))
    conn.commit()


def atualizar_senha(conn, usuario_id, senha_hash, salt):
    conn.execute(
        "UPDATE usuarios SET senha_hash = ?, salt = ? WHERE id = ?",
        (senha_hash, salt, usuario_id),
    )
    conn.commit()


# ── Sessões persistentes (mantém login após recarregar a página) ─────────

def criar_sessao(conn, usuario_id, dias=30):
    from datetime import datetime, timedelta

    token = secrets.token_hex(32)
    agora = datetime.now()
    conn.execute(
        "INSERT INTO sessoes (token, usuario_id, criado_em, expira_em) VALUES (?, ?, ?, ?)",
        (token, usuario_id, agora.isoformat(), (agora + timedelta(days=dias)).isoformat()),
    )
    conn.commit()
    return token


def usuario_por_sessao(conn, token):
    """Retorna o usuário dono do token, se a sessão existir e não tiver expirado."""
    from datetime import datetime

    if not token:
        return None
    linha = conn.execute(
        """SELECT usuarios.*, sessoes.expira_em FROM sessoes
           JOIN usuarios ON usuarios.id = sessoes.usuario_id
           WHERE sessoes.token = ?""",
        (token,),
    ).fetchone()
    if not linha:
        return None
    if linha["expira_em"] < datetime.now().isoformat():
        encerrar_sessao(conn, token)
        return None
    return linha


def encerrar_sessao(conn, token):
    if token:
        conn.execute("DELETE FROM sessoes WHERE token = ?", (token,))
        conn.commit()


def limpar_sessoes_expiradas(conn):
    from datetime import datetime

    conn.execute("DELETE FROM sessoes WHERE expira_em < ?", (datetime.now().isoformat(),))
    conn.commit()


# ── Contas ───────────────────────────────────────────────────────────────

def listar_contas(conn, apenas_ativas=True, grupo_id=None):
    params = []
    filtros = []
    if apenas_ativas:
        filtros.append("ativo = 1")
    if grupo_id is not None:
        filtros.append("grupo_id = ?")
        params.append(grupo_id)
    q = "SELECT * FROM contas"
    if filtros:
        q += " WHERE " + " AND ".join(filtros)
    q += " ORDER BY nome"
    return conn.execute(q, params).fetchall()


def criar_conta(conn, nome, tipo, saldo_inicial, cor="#6366f1", grupo_id=None):
    cur = conn.execute(
        "INSERT INTO contas (nome, tipo, saldo_inicial, cor, grupo_id) VALUES (?, ?, ?, ?, ?)",
        (nome, tipo, saldo_inicial, cor, grupo_id),
    )
    conn.commit()
    return cur.lastrowid


def atualizar_conta(conn, conta_id, nome, tipo, saldo_inicial):
    """Atualiza uma conta. Ao deixar de ser cartão, remove o registro de cartão órfão;
    ao virar cartão, cria um registro de cartão com valores padrão."""
    era_cartao = conn.execute(
        "SELECT tipo FROM contas WHERE id = ?", (conta_id,)
    ).fetchone()["tipo"] == "cartao"

    conn.execute(
        "UPDATE contas SET nome = ?, tipo = ?, saldo_inicial = ? WHERE id = ?",
        (nome, tipo, saldo_inicial, conta_id),
    )

    if era_cartao and tipo != "cartao":
        # desvincula lançamentos que apontavam para o cartão antes de removê-lo
        cartao = conn.execute("SELECT id FROM cartoes WHERE conta_id = ?", (conta_id,)).fetchone()
        if cartao:
            conn.execute("UPDATE lancamentos SET cartao_id = NULL WHERE cartao_id = ?", (cartao["id"],))
            conn.execute("DELETE FROM cartoes WHERE id = ?", (cartao["id"],))
    elif not era_cartao and tipo == "cartao":
        conn.execute(
            "INSERT INTO cartoes (conta_id, dia_fechamento, dia_vencimento, limite) VALUES (?, ?, ?, ?)",
            (conta_id, 25, 5, 0),
        )
    conn.commit()


def contar_lancamentos_conta(conn, conta_id):
    return conn.execute(
        "SELECT COUNT(*) as total FROM lancamentos WHERE conta_id = ?", (conta_id,)
    ).fetchone()["total"]


def deletar_conta(conn, conta_id, apagar_lancamentos=False):
    """Exclui uma conta. Só remove lançamentos vinculados se explicitamente autorizado."""
    if apagar_lancamentos:
        conn.execute("DELETE FROM lancamentos WHERE conta_id = ?", (conta_id,))
    elif contar_lancamentos_conta(conn, conta_id) > 0:
        raise ValueError("Conta possui lançamentos vinculados.")

    cartao = conn.execute("SELECT id FROM cartoes WHERE conta_id = ?", (conta_id,)).fetchone()
    if cartao:
        conn.execute("UPDATE lancamentos SET cartao_id = NULL WHERE cartao_id = ?", (cartao["id"],))
        conn.execute("DELETE FROM cartoes WHERE id = ?", (cartao["id"],))
    conn.execute("DELETE FROM contas WHERE id = ?", (conta_id,))
    conn.commit()


def saldos_por_conta(conn, grupo_id=None):
    """Saldo atual de todas as contas ativas em UMA consulta (evita N+1)."""
    filtro_grupo = "AND contas.grupo_id = ?" if grupo_id is not None else ""
    params = [grupo_id] if grupo_id is not None else []
    linhas = conn.execute(
        f"""SELECT contas.id, contas.nome, contas.tipo, contas.saldo_inicial,
                  COALESCE(SUM(CASE WHEN l.status = 'pago'
                       THEN CASE WHEN l.tipo = 'entrada' THEN l.valor ELSE -l.valor END
                       ELSE 0 END), 0) AS movimentos
           FROM contas
           LEFT JOIN lancamentos l ON l.conta_id = contas.id
           WHERE contas.ativo = 1 {filtro_grupo}
           GROUP BY contas.id
           ORDER BY contas.nome""",
        params,
    ).fetchall()
    for linha in linhas:
        linha["saldo"] = linha["saldo_inicial"] + linha["movimentos"]
    return linhas


def saldo_atual_conta(conn, conta_id):
    conta = conn.execute("SELECT saldo_inicial FROM contas WHERE id = ?", (conta_id,)).fetchone()
    if not conta:
        return 0
    movimentos = conn.execute(
        """SELECT COALESCE(SUM(CASE WHEN tipo = 'entrada' THEN valor ELSE -valor END), 0) as total
           FROM lancamentos WHERE conta_id = ? AND status = 'pago'""",
        (conta_id,),
    ).fetchone()["total"]
    return conta["saldo_inicial"] + movimentos


def saldo_total(conn, grupo_id=None):
    return sum(c["saldo"] for c in saldos_por_conta(conn, grupo_id=grupo_id) if c["tipo"] != "cartao")


def saldo_por_natureza(conn, grupo_id=None):
    """Separa o dinheiro parado em Caixa, Bancos e Aplicações.

    Cartão fica de fora: ele é dívida, não é onde o dinheiro está. Aplicações
    vêm dos investimentos, que não são conta e por isso não entram no
    `saldo_total` — daí o total daqui ser maior que o de lá.
    """
    contas = saldos_por_conta(conn, grupo_id=grupo_id)
    caixa = sum(c["saldo"] for c in contas if c["tipo"] == "carteira")
    bancos = sum(c["saldo"] for c in contas if c["tipo"] == "banco")
    aplicacoes = sum(i["valor_atual"] for i in listar_investimentos(conn, grupo_id=grupo_id))
    return {
        "caixa": caixa,
        "bancos": bancos,
        "aplicacoes": aplicacoes,
        "disponivel": caixa + bancos,
        "total": caixa + bancos + aplicacoes,
        "contas": [c for c in contas if c["tipo"] != "cartao"],
    }


def _filtro_previsto(grupo_id, conta_id, categoria_id):
    """Condição comum das consultas de previsto: só pendente, dentro do grupo."""
    cond = ["lancamentos.status = 'pendente'"]
    params = []
    if grupo_id is not None:
        cond.append("lancamentos.grupo_id = ?")
        params.append(grupo_id)
    if conta_id:
        cond.append("lancamentos.conta_id = ?")
        params.append(conta_id)
    if categoria_id:
        cond.append("lancamentos.categoria_id = ?")
        params.append(categoria_id)
    return " AND ".join(cond), params


def pendentes_em_caixa(conn, grupo_id=None, conta_id=None, categoria_id=None):
    """Pendentes com a data em que o dinheiro sai de verdade.

    Compra no cartão vira a data de vencimento da fatura. Sem isso o fluxo de
    caixa antecipa a saída para o dia da compra, e todas as compras do ciclo
    aparecem espalhadas em vez de uma fatura só.
    """
    onde, params = _filtro_previsto(grupo_id, conta_id, categoria_id)
    linhas = conn.execute(
        f"""SELECT id, data, valor, tipo, cartao_id, descricao, conta_id, categoria_id
            FROM lancamentos WHERE {onde}""",
        tuple(params),
    ).fetchall()
    cartoes = _mapa_cartoes(conn, grupo_id)
    for linha in linhas:
        linha["data_caixa"] = data_de_caixa(linha, cartoes)
    return linhas


# ── Vídeos de ajuda ──────────────────────────────────────────────────────

def videos_ajuda(conn):
    """{tela: url} de todos os vídeos cadastrados."""
    return {l["tela"]: l["url"]
            for l in conn.execute("SELECT tela, url FROM ajuda_videos").fetchall()}


def video_ajuda(conn, tela):
    linha = conn.execute("SELECT url FROM ajuda_videos WHERE tela = ?", (tela,)).fetchone()
    return linha["url"] if linha else ""


def salvar_video_ajuda(conn, tela, url):
    """Grava ou apaga o vídeo de uma tela. URL vazia remove o registro."""
    url = (url or "").strip()
    if not url:
        conn.execute("DELETE FROM ajuda_videos WHERE tela = ?", (tela,))
    else:
        conn.execute(
            """INSERT INTO ajuda_videos (tela, url, atualizado_em)
               VALUES (?, ?, datetime('now'))
               ON CONFLICT(tela) DO UPDATE SET url = excluded.url,
                                               atualizado_em = datetime('now')""",
            (tela, url),
        )
    conn.commit()


# ── Importação de extrato e conciliação ──────────────────────────────────

# Quanto o valor e a data podem divergir para o sistema propor que duas linhas
# são a mesma coisa. Data folgada porque a conta é paga uns dias antes ou
# depois do que foi cadastrado; valor apertado porque R$ 400 e R$ 450 são
# despesas diferentes, não a mesma com arredondamento.
TOLERANCIA_DIAS = 5
TOLERANCIA_VALOR = 0.02


def fitids_ja_importados(conn, fitids, grupo_id=None):
    """Quais desses identificadores já entraram — evita duplicar reimportando."""
    fitids = [f for f in fitids if f]
    if not fitids:
        return set()
    marcadores = ",".join("?" for _ in fitids)
    filtro = " AND grupo_id = ?" if grupo_id is not None else ""
    params = list(fitids) + ([grupo_id] if grupo_id is not None else [])
    linhas = conn.execute(
        f"SELECT fitid FROM lancamentos WHERE fitid IN ({marcadores}){filtro}",
        tuple(params),
    ).fetchall()
    return {l["fitid"] for l in linhas}


def candidatos_conciliacao(conn, transacao, grupo_id=None, conta_id=None):
    """Lançamentos pendentes que podem ser esta linha do extrato.

    Casa por valor quase exato e data próxima. Devolve ordenado pela distância
    de data, para o mais provável ficar em primeiro.
    """
    inicio = (transacao["data"] - timedelta(days=TOLERANCIA_DIAS)).isoformat()
    fim = (transacao["data"] + timedelta(days=TOLERANCIA_DIAS)).isoformat()

    cond = ["lancamentos.status = 'pendente'", "lancamentos.tipo = ?",
            "ABS(lancamentos.valor - ?) <= ?", "lancamentos.data BETWEEN ? AND ?"]
    params = [transacao["tipo"], transacao["valor"], TOLERANCIA_VALOR, inicio, fim]
    if grupo_id is not None:
        cond.append("lancamentos.grupo_id = ?")
        params.append(grupo_id)
    if conta_id:
        cond.append("lancamentos.conta_id = ?")
        params.append(conta_id)

    linhas = conn.execute(
        f"""SELECT lancamentos.*, categorias.nome AS nome_categoria,
                   categorias.icone AS icone_categoria
            FROM lancamentos
            JOIN categorias ON categorias.id = lancamentos.categoria_id
            WHERE {' AND '.join(cond)}""",
        tuple(params),
    ).fetchall()

    for linha in linhas:
        linha["distancia"] = abs((date.fromisoformat(linha["data"]) - transacao["data"]).days)
    return sorted(linhas, key=lambda l: l["distancia"])


def faturas_para_conciliar(conn, transacao, grupo_id=None, tolerancia=0.02):
    """Faturas em aberto cujo total bate com esta linha do extrato.

    O pagamento da fatura aparece no extrato como um valor só. Criar um
    lançamento novo com ele duplicaria as compras já registradas — o certo é
    dar as compras daquela fatura por pagas.
    """
    if transacao["tipo"] != "saida":
        return []
    cartoes = _mapa_cartoes(conn, grupo_id)
    if not cartoes:
        return []
    nomes = {c["id"]: c["nome_conta"] for c in listar_cartoes(conn, grupo_id=grupo_id)}

    agrupado = {}
    for linha in pendentes_em_caixa(conn, grupo_id, None, None):
        if not linha["cartao_id"]:
            continue
        chave = (linha["cartao_id"], linha["data_caixa"])
        total, ids = agrupado.get(chave, (0.0, []))
        agrupado[chave] = (total + linha["valor"], ids + [linha["id"]])

    achados = []
    for (cartao_id, vencimento), (total, ids) in agrupado.items():
        if abs(total - transacao["valor"]) > tolerancia:
            continue
        if abs((vencimento - transacao["data"]).days) > TOLERANCIA_DIAS:
            continue
        achados.append({
            "cartao": nomes.get(cartao_id, "Cartão"),
            "vencimento": vencimento,
            "total": total,
            "lancamento_ids": ids,
        })
    return sorted(achados, key=lambda f: abs((f["vencimento"] - transacao["data"]).days))


def conciliar_lancamento(conn, lancamento_id, fitid, data_extrato=None):
    """Marca como pago e guarda o identificador do extrato.

    A data também é atualizada: a conta foi paga quando o banco diz, não
    quando foi cadastrada, e é essa data que o fluxo de caixa precisa.
    """
    if data_extrato:
        conn.execute(
            "UPDATE lancamentos SET status = 'pago', fitid = ?, data = ? WHERE id = ?",
            (fitid, data_extrato, lancamento_id),
        )
    else:
        conn.execute(
            "UPDATE lancamentos SET status = 'pago', fitid = ? WHERE id = ?",
            (fitid, lancamento_id),
        )
    conn.commit()


def conciliar_fatura(conn, lancamento_ids, fitid):
    """Dá por pagas todas as compras de uma fatura.

    O fitid vai só na primeira: ele identifica a linha do extrato, e a linha é
    uma só. Repetir em todas faria o extrato parecer já importado por inteiro
    quando só o pagamento da fatura entrou.
    """
    if not lancamento_ids:
        return
    marcadores = ",".join("?" for _ in lancamento_ids)
    conn.execute(
        f"UPDATE lancamentos SET status = 'pago' WHERE id IN ({marcadores})",
        tuple(lancamento_ids),
    )
    conn.execute("UPDATE lancamentos SET fitid = ? WHERE id = ?",
                 (fitid, lancamento_ids[0]))
    conn.commit()


def criar_do_extrato(conn, transacao, conta_id, categoria_id, usuario_id, grupo_id=None):
    """Lançamento novo, já como pago — o extrato só mostra o que aconteceu."""
    cur = conn.execute(
        """INSERT INTO lancamentos
             (data, conta_id, categoria_id, descricao, valor, tipo, status,
              usuario_id, grupo_id, fitid)
           VALUES (?, ?, ?, ?, ?, ?, 'pago', ?, ?, ?)""",
        (transacao["data"].isoformat(), conta_id, categoria_id,
         transacao["descricao"][:200], transacao["valor"], transacao["tipo"],
         usuario_id, grupo_id, transacao["fitid"]),
    )
    conn.commit()
    return cur.lastrowid


def faturas_previstas(conn, dias, grupo_id=None, conta_id=None):
    """As faturas em aberto até hoje + `dias`, uma linha por cartão/vencimento.

    É a tradução do que o usuário vê no aplicativo do banco: não dezoito
    compras soltas, e sim 'Nubank, vence dia 05, R$ 3.000'.
    """
    limite = date.today() + timedelta(days=dias)
    cartoes = _mapa_cartoes(conn, grupo_id)
    if not cartoes:
        return []
    nomes = {c["id"]: c["nome_conta"] for c in listar_cartoes(conn, grupo_id=grupo_id)}

    agrupado = {}
    for linha in pendentes_em_caixa(conn, grupo_id, conta_id, None):
        if not linha["cartao_id"] or linha["data_caixa"] > limite:
            continue
        chave = (linha["cartao_id"], linha["data_caixa"])
        total, quantidade = agrupado.get(chave, (0.0, 0))
        agrupado[chave] = (total + linha["valor"], quantidade + 1)

    return sorted(
        ({"cartao": nomes.get(cid, "Cartão"), "vencimento": venc,
          "total": total, "quantidade": qtd}
         for (cid, venc), (total, qtd) in agrupado.items()),
        key=lambda f: f["vencimento"],
    )


def previsto_ate(conn, dias, grupo_id=None, conta_id=None, categoria_id=None):
    """(entradas, saidas) pendentes de hoje até hoje + `dias`, pela data em que
    o dinheiro sai.

    O passado pendente entra de propósito: conta vencida e não paga continua
    sendo dinheiro que vai sair, e some da previsão se filtrar só o futuro.
    """
    limite = date.today() + timedelta(days=dias)
    entradas = saidas = 0.0
    for linha in pendentes_em_caixa(conn, grupo_id, conta_id, categoria_id):
        if linha["data_caixa"] > limite:
            continue
        if linha["tipo"] == "entrada":
            entradas += linha["valor"]
        else:
            saidas += linha["valor"]
    return entradas, saidas


def previsto_por_categoria(conn, dias, tipo, grupo_id=None, conta_id=None):
    """Quebra o previsto por categoria — é o que responde 'sai tanto, com o quê'."""
    limite = (date.today() + timedelta(days=dias)).isoformat()
    onde, params = _filtro_previsto(grupo_id, conta_id, None)
    return conn.execute(
        f"""SELECT categorias.nome, categorias.icone,
                   COALESCE(SUM(lancamentos.valor), 0) AS total,
                   COUNT(*) AS quantidade
            FROM lancamentos
            JOIN categorias ON categorias.id = lancamentos.categoria_id
            WHERE {onde} AND lancamentos.tipo = ? AND lancamentos.data <= ?
            GROUP BY categorias.id ORDER BY total DESC""",
        tuple(params + [tipo, limite]),
    ).fetchall()


def _dia_valido(ano, mes, dia):
    """Encaixa o dia no mês: fechamento 31 em fevereiro vira 28 (ou 29)."""
    if mes > 12:
        ano, mes = ano + 1, mes - 12
    ultimo = (date(ano + (mes == 12), (mes % 12) + 1, 1) - timedelta(days=1)).day
    return date(ano, mes, min(dia, ultimo))


def ciclo_fatura(data_compra, dia_fechamento, dia_vencimento):
    """(fechamento, vencimento) da fatura em que a compra cai.

    Compra ANTES do fechamento entra na fatura que fecha neste mês; no dia do
    fechamento ou depois, já é a do mês seguinte — é assim que o cartão
    funciona, e errar isso joga a despesa um mês inteiro fora do lugar.

    O vencimento costuma cair no mês seguinte ao fechamento (fecha 25, vence
    05). Quando o dia do vencimento é maior que o do fechamento, os dois caem
    no mesmo mês (fecha 05, vence 15).
    """
    if isinstance(data_compra, str):
        data_compra = date.fromisoformat(data_compra)

    fechamento = _dia_valido(data_compra.year, data_compra.month, dia_fechamento)
    if data_compra >= fechamento:
        fechamento = _dia_valido(data_compra.year, data_compra.month + 1, dia_fechamento)

    mes_venc = fechamento.month + (0 if dia_vencimento > dia_fechamento else 1)
    vencimento = _dia_valido(fechamento.year, mes_venc, dia_vencimento)
    return fechamento, vencimento


def _mapa_cartoes(conn, grupo_id=None):
    """{cartao_id: (dia_fechamento, dia_vencimento)} para converter data de
    compra em data de pagamento sem ir ao banco a cada linha."""
    return {
        c["id"]: (c["dia_fechamento"], c["dia_vencimento"])
        for c in listar_cartoes(conn, grupo_id=grupo_id)
    }


def data_de_caixa(lancamento, cartoes):
    """Quando o dinheiro realmente sai da conta.

    Para compra no cartão é o vencimento da fatura, não o dia da compra: a
    despesa nasce na compra (competência), mas o dinheiro só sai quando a
    fatura é paga. Usar a data da compra no fluxo de caixa antecipa a saída e
    engana a projeção.
    """
    cartao_id = lancamento.get("cartao_id")
    if not cartao_id or cartao_id not in cartoes:
        return date.fromisoformat(lancamento["data"])
    fechamento, vencimento = cartoes[cartao_id]
    return ciclo_fatura(lancamento["data"], fechamento, vencimento)[1]


def previsto_por_categoria_periodo(conn, inicio, fim, tipo, grupo_id=None, conta_id=None):
    """Igual a `previsto_por_categoria`, mas entre duas datas em vez de N dias.

    Existe porque a tela Previsto × Realizado tem período livre e precisa
    comparar as duas metades com o mesmo recorte.
    """
    onde, params = _filtro_previsto(grupo_id, conta_id, None)
    return conn.execute(
        f"""SELECT categorias.nome, categorias.icone,
                   COALESCE(SUM(lancamentos.valor), 0) AS total,
                   COUNT(*) AS quantidade
            FROM lancamentos
            JOIN categorias ON categorias.id = lancamentos.categoria_id
            WHERE {onde} AND lancamentos.tipo = ?
              AND lancamentos.data BETWEEN ? AND ?
            GROUP BY categorias.id ORDER BY total DESC""",
        tuple(params + [tipo, inicio, fim]),
    ).fetchall()


def projecao_saldo(conn, dias, grupo_id=None, conta_id=None, categoria_id=None):
    """Saldo dia a dia daqui até `dias` à frente.

    Parte do saldo de hoje (só o que está pago) e vai somando os pendentes na
    data de cada um. Devolve [(data, saldo, entradas_do_dia, saidas_do_dia)].
    """
    hoje = date.today()
    saldo = saldo_total(conn, grupo_id=grupo_id)
    limite = hoje + timedelta(days=dias)

    # Pendente com data passada pesa no primeiro dia: já era para ter saído.
    por_dia = {}
    for linha in pendentes_em_caixa(conn, grupo_id, conta_id, categoria_id):
        if linha["data_caixa"] > limite:
            continue
        dia = max(linha["data_caixa"], hoje)
        entradas, saidas = por_dia.get(dia, (0.0, 0.0))
        if linha["tipo"] == "entrada":
            por_dia[dia] = (entradas + linha["valor"], saidas)
        else:
            por_dia[dia] = (entradas, saidas + linha["valor"])

    pontos = []
    for passo in range(dias + 1):
        dia = hoje + timedelta(days=passo)
        entradas, saidas = por_dia.get(dia, (0.0, 0.0))
        saldo += entradas - saidas
        pontos.append((dia, saldo, entradas, saidas))
    return pontos


def _filtro_realizado(grupo_id, conta_id, categoria_id):
    """Só o que foi efetivamente pago/recebido — o previsto tem visão própria."""
    cond = ["lancamentos.status = 'pago'"]
    params = []
    if grupo_id is not None:
        cond.append("lancamentos.grupo_id = ?")
        params.append(grupo_id)
    if conta_id:
        cond.append("lancamentos.conta_id = ?")
        params.append(conta_id)
    if categoria_id:
        cond.append("lancamentos.categoria_id = ?")
        params.append(categoria_id)
    return " AND ".join(cond), params


def realizado_resumo(conn, inicio, fim, grupo_id=None, conta_id=None, categoria_id=None):
    """(entradas, saidas) que de fato aconteceram no período."""
    onde, params = _filtro_realizado(grupo_id, conta_id, categoria_id)
    linha = conn.execute(
        f"""SELECT
              COALESCE(SUM(CASE WHEN tipo = 'entrada' THEN valor ELSE 0 END), 0) AS entradas,
              COALESCE(SUM(CASE WHEN tipo = 'saida'   THEN valor ELSE 0 END), 0) AS saidas
            FROM lancamentos WHERE {onde} AND data BETWEEN ? AND ?""",
        tuple(params + [inicio, fim]),
    ).fetchone()
    return linha["entradas"], linha["saidas"]


def realizado_por_mes(conn, inicio, fim, grupo_id=None, conta_id=None, categoria_id=None):
    """Mês a mês: quanto entrou, quanto saiu, quanto sobrou."""
    onde, params = _filtro_realizado(grupo_id, conta_id, categoria_id)
    linhas = conn.execute(
        f"""SELECT substr(data, 1, 7) AS mes,
              COALESCE(SUM(CASE WHEN tipo = 'entrada' THEN valor ELSE 0 END), 0) AS entradas,
              COALESCE(SUM(CASE WHEN tipo = 'saida'   THEN valor ELSE 0 END), 0) AS saidas
            FROM lancamentos WHERE {onde} AND data BETWEEN ? AND ?
            GROUP BY mes ORDER BY mes""",
        tuple(params + [inicio, fim]),
    ).fetchall()
    for linha in linhas:
        linha["resultado"] = linha["entradas"] - linha["saidas"]
    return linhas


# Como agrupar a série no SQL. A semana começa na segunda: recua o número de
# dias desde ela ((%w + 6) % 7 transforma domingo=0 em domingo=6).
_AGRUPAMENTO = {
    "diario": "data",
    "semanal": "date(data, '-' || ((CAST(strftime('%w', data) AS INTEGER) + 6) % 7) || ' days')",
    "mensal": "substr(data, 1, 7)",
}


def serie_periodo(conn, inicio, fim, granularidade="mensal",
                  grupo_id=None, conta_id=None, categoria_id=None):
    """Série no tempo separando o que já aconteceu do que ainda está marcado.

    Uma consulta só, com as quatro colunas, para dar o gráfico contínuo: o
    passado vem de `pago`, o futuro de `pendente`, e o período corrente costuma
    ter os dois. Somar tudo numa coluna esconderia justamente essa diferença.

    `granularidade` aceita diario, semanal ou mensal — mensal enxerga a
    tendência, diário serve para investigar um mês que destoou.
    """
    coluna = _AGRUPAMENTO.get(granularidade, _AGRUPAMENTO["mensal"])
    cond = []
    params = []
    if grupo_id is not None:
        cond.append("grupo_id = ?")
        params.append(grupo_id)
    if conta_id:
        cond.append("conta_id = ?")
        params.append(conta_id)
    if categoria_id:
        cond.append("categoria_id = ?")
        params.append(categoria_id)
    onde = (" AND " + " AND ".join(cond)) if cond else ""

    linhas = conn.execute(
        f"""SELECT {coluna} AS periodo,
              COALESCE(SUM(CASE WHEN status='pago' AND tipo='entrada' THEN valor ELSE 0 END), 0) AS entradas_reais,
              COALESCE(SUM(CASE WHEN status='pago' AND tipo='saida'   THEN valor ELSE 0 END), 0) AS saidas_reais,
              COALESCE(SUM(CASE WHEN status='pendente' AND tipo='entrada' THEN valor ELSE 0 END), 0) AS entradas_previstas,
              COALESCE(SUM(CASE WHEN status='pendente' AND tipo='saida'   THEN valor ELSE 0 END), 0) AS saidas_previstas
            FROM lancamentos WHERE data BETWEEN ? AND ?{onde}
            GROUP BY periodo ORDER BY periodo""",
        tuple([inicio, fim] + params),
    ).fetchall()

    for linha in linhas:
        linha["rotulo"] = _rotulo_periodo(linha["periodo"], granularidade)
        linha["resultado_real"] = linha["entradas_reais"] - linha["saidas_reais"]
        linha["resultado_previsto"] = linha["entradas_previstas"] - linha["saidas_previstas"]
        linha["entradas_total"] = linha["entradas_reais"] + linha["entradas_previstas"]
        linha["saidas_total"] = linha["saidas_reais"] + linha["saidas_previstas"]
        linha["resultado_total"] = linha["entradas_total"] - linha["saidas_total"]
    return linhas


def _rotulo_periodo(valor, granularidade):
    """Rótulo curto para o eixo do gráfico: 05/08 · 05/08 (semana) · ago/26."""
    if granularidade == "mensal":
        ano, mes = valor.split("-")
        nomes = ["jan", "fev", "mar", "abr", "mai", "jun",
                 "jul", "ago", "set", "out", "nov", "dez"]
        return f"{nomes[int(mes) - 1]}/{ano[2:]}"
    dia = date.fromisoformat(valor)
    return dia.strftime("%d/%m")


def serie_mensal(conn, inicio, fim, grupo_id=None, conta_id=None, categoria_id=None):
    """Atalho para a série mensal — o padrão da tela."""
    return serie_periodo(conn, inicio, fim, "mensal", grupo_id=grupo_id,
                         conta_id=conta_id, categoria_id=categoria_id)


def realizado_por_categoria(conn, inicio, fim, tipo, grupo_id=None, conta_id=None):
    onde, params = _filtro_realizado(grupo_id, conta_id, None)
    return conn.execute(
        f"""SELECT categorias.nome, categorias.icone,
                   COALESCE(SUM(lancamentos.valor), 0) AS total,
                   COUNT(*) AS quantidade
            FROM lancamentos
            JOIN categorias ON categorias.id = lancamentos.categoria_id
            WHERE {onde} AND lancamentos.tipo = ? AND lancamentos.data BETWEEN ? AND ?
            GROUP BY categorias.id ORDER BY total DESC""",
        tuple(params + [tipo, inicio, fim]),
    ).fetchall()


def agrupar_projecao(pontos, granularidade):
    """Reduz a projeção diária para semanas ou meses, guardando o saldo do
    último dia de cada balde — que é o que interessa: como termino o período."""
    if granularidade == "diario":
        return pontos

    baldes = {}
    for dia, saldo, entradas, saidas in pontos:
        if granularidade == "semanal":
            chave = dia - timedelta(days=dia.weekday())  # segunda-feira
        else:
            chave = dia.replace(day=1)
        anterior = baldes.get(chave)
        acumulado_e = (anterior[2] if anterior else 0) + entradas
        acumulado_s = (anterior[3] if anterior else 0) + saidas
        baldes[chave] = (chave, saldo, acumulado_e, acumulado_s)
    return [baldes[c] for c in sorted(baldes)]


# ── Cartões ──────────────────────────────────────────────────────────────

def listar_cartoes(conn, grupo_id=None):
    if grupo_id is not None:
        return conn.execute(
            """SELECT cartoes.*, contas.nome as nome_conta FROM cartoes
               JOIN contas ON contas.id = cartoes.conta_id
               WHERE contas.grupo_id = ? ORDER BY contas.nome""",
            (grupo_id,),
        ).fetchall()
    return conn.execute(
        """SELECT cartoes.*, contas.nome as nome_conta FROM cartoes
           JOIN contas ON contas.id = cartoes.conta_id ORDER BY contas.nome"""
    ).fetchall()


def criar_cartao(conn, nome, dia_fechamento, dia_vencimento, limite, grupo_id=None):
    conta_id = criar_conta(conn, nome, "cartao", 0, grupo_id=grupo_id)
    cur = conn.execute(
        "INSERT INTO cartoes (conta_id, dia_fechamento, dia_vencimento, limite) VALUES (?, ?, ?, ?)",
        (conta_id, dia_fechamento, dia_vencimento, limite),
    )
    conn.commit()
    return cur.lastrowid


def atualizar_cartao(conn, cartao_id, nome, dia_fechamento, dia_vencimento, limite, grupo_id):
    """O cartão vive em duas tabelas: o nome em `contas`, o resto em `cartoes`.

    O grupo entra na condição para ninguém editar cartão de outra família por
    id adivinhado.
    """
    linha = conn.execute(
        """SELECT cartoes.id, cartoes.conta_id FROM cartoes
           JOIN contas ON contas.id = cartoes.conta_id
           WHERE cartoes.id = ? AND contas.grupo_id = ?""",
        (cartao_id, grupo_id),
    ).fetchone()
    if not linha:
        return False
    conn.execute("UPDATE contas SET nome = ? WHERE id = ?", (nome, linha["conta_id"]))
    conn.execute(
        "UPDATE cartoes SET dia_fechamento = ?, dia_vencimento = ?, limite = ? WHERE id = ?",
        (dia_fechamento, dia_vencimento, limite, cartao_id),
    )
    conn.commit()
    return True


def contar_lancamentos_cartao(conn, cartao_id):
    return conn.execute(
        "SELECT COUNT(*) as total FROM lancamentos WHERE cartao_id = ?", (cartao_id,)
    ).fetchone()["total"]


def deletar_cartao(conn, cartao_id, grupo_id, apagar_lancamentos=False):
    """(apagou, motivo). Apaga a ficha do cartão e a conta que o representa.

    Sem `apagar_lancamentos`, recusa quando há compras lançadas — some com o
    cartão levaria junto o histórico de fatura sem o usuário perceber.
    """
    linha = conn.execute(
        """SELECT cartoes.id, cartoes.conta_id FROM cartoes
           JOIN contas ON contas.id = cartoes.conta_id
           WHERE cartoes.id = ? AND contas.grupo_id = ?""",
        (cartao_id, grupo_id),
    ).fetchone()
    if not linha:
        return False, "Cartão não encontrado neste grupo."

    compras = contar_lancamentos_cartao(conn, cartao_id)
    if compras and not apagar_lancamentos:
        return False, f"{compras} compra(s) lançada(s) neste cartão."

    deletar_conta(conn, linha["conta_id"], apagar_lancamentos=True)
    return True, ""


def fatura_cartao(conn, cartao_id, mes, ano):
    inicio = date(ano, mes, 1)
    fim = inicio + relativedelta(months=1)
    return conn.execute(
        """SELECT * FROM lancamentos WHERE cartao_id = ?
           AND data >= ? AND data < ? ORDER BY data""",
        (cartao_id, inicio.isoformat(), fim.isoformat()),
    ).fetchall()


# ── Categorias ───────────────────────────────────────────────────────────

def listar_categorias(conn, tipo=None, grupo_id=None):
    """As de fábrica (grupo_id nulo) mais as criadas pelo próprio grupo."""
    q = "SELECT * FROM categorias WHERE (grupo_id IS NULL OR grupo_id = ?)"
    params = [grupo_id]
    if tipo:
        q += " AND tipo = ?"
        params.append(tipo)
    q += " ORDER BY tipo, nome"
    return conn.execute(q, tuple(params)).fetchall()


def criar_categoria(conn, nome, tipo, icone="💰", grupo_id=None):
    cur = conn.execute(
        "INSERT INTO categorias (nome, tipo, icone, grupo_id) VALUES (?, ?, ?, ?)",
        (nome, tipo, icone, grupo_id),
    )
    conn.commit()
    return cur.lastrowid


def atualizar_categoria(conn, categoria_id, nome, icone, grupo_id):
    """Só mexe no que pertence ao grupo — item de fábrica ninguém renomeia."""
    conn.execute(
        "UPDATE categorias SET nome = ?, icone = ? WHERE id = ? AND grupo_id = ?",
        (nome, icone, categoria_id, grupo_id),
    )
    conn.commit()


def contar_lancamentos_categoria(conn, categoria_id):
    return conn.execute(
        "SELECT COUNT(*) as total FROM lancamentos WHERE categoria_id = ?", (categoria_id,)
    ).fetchone()["total"]


def deletar_categoria(conn, categoria_id, grupo_id):
    """(apagou, motivo). Recusa se estiver em uso ou se for item de fábrica.

    Apagar uma categoria usada deixaria lançamentos apontando para o vazio, e o
    DRE pararia de somar aquele gasto sem avisar ninguém.
    """
    em_uso = contar_lancamentos_categoria(conn, categoria_id)
    if em_uso:
        return False, f"{em_uso} lançamento(s) usam esta categoria."
    dona = conn.execute(
        "SELECT grupo_id FROM categorias WHERE id = ?", (categoria_id,)
    ).fetchone()
    if not dona or dona["grupo_id"] != grupo_id:
        return False, "Categoria de fábrica não pode ser excluída."
    conn.execute("DELETE FROM categorias WHERE id = ?", (categoria_id,))
    conn.commit()
    return True, ""


# ── Formas de pagamento ──────────────────────────────────────────────────

def listar_formas_pagamento(conn, grupo_id=None):
    linhas = conn.execute(
        "SELECT * FROM formas_pagamento WHERE (grupo_id IS NULL OR grupo_id = ?) "
        "ORDER BY grupo_id IS NOT NULL, nome",
        (grupo_id,),
    ).fetchall()
    return linhas


def nomes_formas_pagamento(conn, grupo_id=None):
    """Só os nomes, para alimentar os selectbox de lançamento."""
    return [f["nome"] for f in listar_formas_pagamento(conn, grupo_id=grupo_id)]


def criar_forma_pagamento(conn, nome, grupo_id):
    cur = conn.execute(
        "INSERT INTO formas_pagamento (nome, grupo_id) VALUES (?, ?)", (nome, grupo_id)
    )
    conn.commit()
    return cur.lastrowid


def atualizar_forma_pagamento(conn, forma_id, nome, grupo_id):
    """Só renomeia o que é do grupo — item de fábrica fica como está."""
    conn.execute(
        "UPDATE formas_pagamento SET nome = ? WHERE id = ? AND grupo_id = ?",
        (nome, forma_id, grupo_id),
    )
    conn.commit()


def deletar_forma_pagamento(conn, forma_id, grupo_id):
    """(apagou, motivo). Item de fábrica fica; o do grupo sai."""
    dona = conn.execute(
        "SELECT grupo_id FROM formas_pagamento WHERE id = ?", (forma_id,)
    ).fetchone()
    if not dona or dona["grupo_id"] != grupo_id:
        return False, "Forma de pagamento de fábrica não pode ser excluída."
    conn.execute("DELETE FROM formas_pagamento WHERE id = ?", (forma_id,))
    conn.commit()
    return True, ""


# ── Lançamentos ──────────────────────────────────────────────────────────

def criar_lancamento(
    conn, data_lanc, conta_id, categoria_id, descricao, valor, tipo, status,
    usuario_id, cartao_id=None, parcelas=1, recorrente=False, repeticoes=1,
    forma_pagamento=None, grupo_id=None,
):
    """Cria um lançamento simples, parcelado (cartão) ou recorrente (mensal).
    Parcelamento e recorrência são mutuamente exclusivos por lançamento."""
    d = date.fromisoformat(data_lanc)

    if parcelas > 1:
        compra_id = str(uuid.uuid4())
        for i in range(parcelas):
            data_parcela = d + relativedelta(months=i)
            conn.execute(
                """INSERT INTO lancamentos
                   (data, conta_id, categoria_id, descricao, valor, tipo, status,
                    usuario_id, grupo_id, cartao_id, compra_id, parcela_atual, parcela_total, forma_pagamento)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    data_parcela.isoformat(), conta_id, categoria_id,
                    f"{descricao} ({i + 1}/{parcelas})", valor, tipo,
                    "pago" if i == 0 and status == "pago" else "pendente",
                    usuario_id, grupo_id, cartao_id, compra_id, i + 1, parcelas, forma_pagamento,
                ),
            )
    elif recorrente and repeticoes > 1:
        recorrencia_id = str(uuid.uuid4())
        for i in range(repeticoes):
            data_ocorrencia = d + relativedelta(months=i)
            conn.execute(
                """INSERT INTO lancamentos
                   (data, conta_id, categoria_id, descricao, valor, tipo, status,
                    usuario_id, grupo_id, recorrencia_id, forma_pagamento)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    data_ocorrencia.isoformat(), conta_id, categoria_id, descricao,
                    valor, tipo, status if i == 0 else "pendente",
                    usuario_id, grupo_id, recorrencia_id, forma_pagamento,
                ),
            )
    else:
        conn.execute(
            """INSERT INTO lancamentos
               (data, conta_id, categoria_id, descricao, valor, tipo, status,
                usuario_id, grupo_id, cartao_id, forma_pagamento)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data_lanc, conta_id, categoria_id, descricao, valor, tipo, status,
             usuario_id, grupo_id, cartao_id, forma_pagamento),
        )
    conn.commit()


def listar_lancamentos(conn, data_inicio=None, data_fim=None, status=None, conta_id=None,
                        categoria_id=None, tipo=None, apenas_sem_cartao=False, grupo_id=None):
    q = """SELECT lancamentos.*, contas.nome as nome_conta, categorias.nome as nome_categoria,
                  categorias.icone as icone_categoria
           FROM lancamentos
           JOIN contas ON contas.id = lancamentos.conta_id
           JOIN categorias ON categorias.id = lancamentos.categoria_id
           WHERE 1=1"""
    params = []
    if grupo_id is not None:
        q += " AND lancamentos.grupo_id = ?"
        params.append(grupo_id)
    if data_inicio:
        q += " AND data >= ?"
        params.append(data_inicio)
    if data_fim:
        q += " AND data <= ?"
        params.append(data_fim)
    if status:
        q += " AND lancamentos.status = ?"
        params.append(status)
    if conta_id:
        q += " AND lancamentos.conta_id = ?"
        params.append(conta_id)
    if categoria_id:
        q += " AND lancamentos.categoria_id = ?"
        params.append(categoria_id)
    if tipo:
        q += " AND lancamentos.tipo = ?"
        params.append(tipo)
    if apenas_sem_cartao:
        q += " AND cartao_id IS NULL"
    q += " ORDER BY data DESC"
    return conn.execute(q, params).fetchall()


def marcar_status(conn, lancamento_id, status):
    conn.execute("UPDATE lancamentos SET status = ? WHERE id = ?", (status, lancamento_id))
    conn.commit()


def deletar_lancamento(conn, lancamento_id, apenas_futuras=False):
    lanc = conn.execute("SELECT * FROM lancamentos WHERE id = ?", (lancamento_id,)).fetchone()
    if not lanc:
        return
    if apenas_futuras and (lanc["recorrencia_id"] or lanc["compra_id"]):
        chave = "recorrencia_id" if lanc["recorrencia_id"] else "compra_id"
        valor_chave = lanc[chave]
        alvos = [
            r["id"] for r in conn.execute(
                f"SELECT id FROM lancamentos WHERE {chave} = ? AND data >= ?",
                (valor_chave, lanc["data"]),
            ).fetchall()
        ]
        conn.execute(
            f"DELETE FROM lancamentos WHERE {chave} = ? AND data >= ?",
            (valor_chave, lanc["data"]),
        )
    else:
        alvos = [lancamento_id]
        conn.execute("DELETE FROM lancamentos WHERE id = ?", (lancamento_id,))
    conn.commit()
    # anexos ficariam órfãos (o vínculo é polimórfico, sem FK) — limpa junto
    for alvo in alvos:
        excluir_anexos_da_entidade(conn, "lancamento", alvo)


# ── Patrimônio ───────────────────────────────────────────────────────────

def listar_patrimonio(conn, grupo_id=None):
    if grupo_id is not None:
        return conn.execute(
            "SELECT * FROM patrimonio_itens WHERE grupo_id = ? ORDER BY tipo, categoria",
            (grupo_id,),
        ).fetchall()
    return conn.execute("SELECT * FROM patrimonio_itens ORDER BY tipo, categoria").fetchall()


def criar_patrimonio_item(conn, nome, tipo, categoria, valor_atual, usuario_id, grupo_id=None):
    conn.execute(
        """INSERT INTO patrimonio_itens (nome, tipo, categoria, valor_atual, data_atualizacao, usuario_id, grupo_id)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (nome, tipo, categoria, valor_atual, date.today().isoformat(), usuario_id, grupo_id),
    )
    conn.commit()


def atualizar_patrimonio_item(conn, item_id, valor_atual):
    conn.execute(
        "UPDATE patrimonio_itens SET valor_atual = ?, data_atualizacao = ? WHERE id = ?",
        (valor_atual, date.today().isoformat(), item_id),
    )
    conn.commit()


def deletar_patrimonio_item(conn, item_id):
    conn.execute("DELETE FROM patrimonio_itens WHERE id = ?", (item_id,))
    conn.commit()


def patrimonio_liquido(conn, saldo_contas=None, investido=None, grupo_id=None):
    """Aceita valores pré-calculados para evitar repetir consultas na mesma tela."""
    itens = listar_patrimonio(conn, grupo_id=grupo_id)
    ativos = sum(i["valor_atual"] for i in itens if i["tipo"] == "ativo")
    passivos = sum(i["valor_atual"] for i in itens if i["tipo"] == "passivo")
    if investido is None:
        investido = sum(i["valor_atual"] for i in listar_investimentos(conn, grupo_id=grupo_id))
    if saldo_contas is None:
        saldo_contas = saldo_total(conn, grupo_id=grupo_id)
    return ativos + investido - passivos + saldo_contas


# ── Investimentos ────────────────────────────────────────────────────────

def listar_investimentos(conn, grupo_id=None):
    if grupo_id is not None:
        return conn.execute(
            "SELECT * FROM investimentos WHERE grupo_id = ? ORDER BY tipo, nome",
            (grupo_id,),
        ).fetchall()
    return conn.execute("SELECT * FROM investimentos ORDER BY tipo, nome").fetchall()


def criar_investimento(conn, nome, tipo, valor_aportado, valor_atual, usuario_id, grupo_id=None):
    conn.execute(
        """INSERT INTO investimentos (nome, tipo, valor_aportado, valor_atual, data, usuario_id, grupo_id)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (nome, tipo, valor_aportado, valor_atual, date.today().isoformat(), usuario_id, grupo_id),
    )
    conn.commit()


def atualizar_investimento(conn, inv_id, valor_atual):
    conn.execute("UPDATE investimentos SET valor_atual = ? WHERE id = ?", (valor_atual, inv_id))
    conn.commit()


def deletar_investimento(conn, inv_id):
    conn.execute("DELETE FROM investimentos WHERE id = ?", (inv_id,))
    conn.commit()


# ── Metas ────────────────────────────────────────────────────────────────

def listar_metas(conn, grupo_id=None):
    if grupo_id is not None:
        return conn.execute(
            "SELECT * FROM metas WHERE grupo_id = ? ORDER BY data_alvo",
            (grupo_id,),
        ).fetchall()
    return conn.execute("SELECT * FROM metas ORDER BY data_alvo").fetchall()


def criar_meta(conn, nome, valor_alvo, data_alvo, usuario_id, grupo_id=None):
    conn.execute(
        "INSERT INTO metas (nome, valor_alvo, data_alvo, usuario_id, grupo_id) VALUES (?, ?, ?, ?, ?)",
        (nome, valor_alvo, data_alvo, usuario_id, grupo_id),
    )
    conn.commit()


def atualizar_meta_progresso(conn, meta_id, valor_atual):
    conn.execute("UPDATE metas SET valor_atual = ? WHERE id = ?", (valor_atual, meta_id))
    conn.commit()


def deletar_meta(conn, meta_id):
    conn.execute("DELETE FROM metas WHERE id = ?", (meta_id,))
    conn.commit()


# ── Anexos ───────────────────────────────────────────────────────────────
# O binário fica no disco (storage.py); aqui guardamos só a ficha.
# Isso mantém o backup do banco leve e permite migrar para nuvem sem tocar
# no restante do aplicativo.

def criar_anexo(conn, entidade, entidade_id, nome_original, chave, backend,
                mime, tamanho, hash_sha256, usuario_id, grupo_id=None):
    cur = conn.execute(
        """INSERT INTO anexos
           (entidade, entidade_id, nome_original, chave, backend, mime,
            tamanho, hash_sha256, usuario_id, grupo_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (entidade, entidade_id, nome_original, chave, backend, mime,
         tamanho, hash_sha256, usuario_id, grupo_id),
    )
    conn.commit()
    return cur.lastrowid


def listar_anexos(conn, entidade, entidade_id):
    return conn.execute(
        """SELECT * FROM anexos
           WHERE entidade = ? AND entidade_id = ?
           ORDER BY created_at DESC, id DESC""",
        (entidade, entidade_id),
    ).fetchall()


def buscar_anexo(conn, anexo_id):
    return conn.execute("SELECT * FROM anexos WHERE id = ?", (anexo_id,)).fetchone()


def anexo_duplicado(conn, entidade, entidade_id, hash_sha256):
    """Evita subir duas vezes o mesmo arquivo no mesmo registro."""
    return conn.execute(
        """SELECT * FROM anexos
           WHERE entidade = ? AND entidade_id = ? AND hash_sha256 = ?""",
        (entidade, entidade_id, hash_sha256),
    ).fetchone()


def contar_anexos(conn, entidade, ids):
    """{entidade_id: quantidade} em UMA consulta (evita N+1 em listagens)."""
    ids = [int(i) for i in ids]
    if not ids:
        return {}
    marcadores = ",".join("?" for _ in ids)
    linhas = conn.execute(
        f"""SELECT entidade_id, COUNT(*) AS total FROM anexos
            WHERE entidade = ? AND entidade_id IN ({marcadores})
            GROUP BY entidade_id""",
        [entidade, *ids],
    ).fetchall()
    return {l["entidade_id"]: l["total"] for l in linhas}


def excluir_anexo(conn, anexo_id):
    """Apaga a ficha e o arquivo correspondente."""
    import storage

    anexo = buscar_anexo(conn, anexo_id)
    if not anexo:
        return False
    try:
        storage.obter(anexo["backend"]).excluir(anexo["chave"])
    except Exception:
        pass  # arquivo já sumiu do disco — segue e limpa a ficha
    conn.execute("DELETE FROM anexos WHERE id = ?", (anexo_id,))
    conn.commit()
    return True


def excluir_anexos_da_entidade(conn, entidade, entidade_id):
    """Remove todos os anexos de um registro (usado quando ele é excluído)."""
    for anexo in listar_anexos(conn, entidade, entidade_id):
        excluir_anexo(conn, anexo["id"])
