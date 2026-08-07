import os
import secrets
import uuid
from datetime import date
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

    conn.executescript("""
    CREATE TABLE IF NOT EXISTS formas_pagamento (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        grupo_id INTEGER REFERENCES grupos(id)
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
