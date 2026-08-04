"""migrar_multiusuario.py
Migração para suporte multi-tenant com grupos.

Execute ANTES de subir o novo código para produção:

    python migrar_multiusuario.py

O script:
1. Cria as tabelas `grupos` e `usuarios_grupo` (se não existirem).
2. Adiciona a coluna `grupo_id` às tabelas de dados (se não existir).
3. Cria o grupo 'Família Fabricio' (ID 1) — se ainda não existir.
4. Adiciona fabricioaguilherme@gmail.com (admin) e danielacvalente@gmail.com (membro).
5. Atualiza todas as linhas com grupo_id NULL para grupo_id = 1.
6. Repete tudo no banco Turso (nuvem), se as credenciais estiverem disponíveis.

Você pode rodar novamente sem problemas — todas as operações são idempotentes.
"""

import os
import sqlite3
import sys

# ── Configuração ─────────────────────────────────────────────────────────

GRUPO_NOME = "Família Fabricio"
ADMIN_EMAIL = "fabricioaguilherme@gmail.com"
MEMBRO_EMAIL = "danielacvalente@gmail.com"

# Altere aqui para adicionar mais membros iniciais:
MEMBROS = [
    (ADMIN_EMAIL, "admin"),
    (MEMBRO_EMAIL, "membro"),
]

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "financeiro.db")

TABELAS_COM_GRUPO_ID = [
    "contas",
    "lancamentos",
    "patrimonio_itens",
    "investimentos",
    "metas",
    "anexos",
]


# ── Helpers ───────────────────────────────────────────────────────────────

def _linha_para_dict(cursor, row):
    return {col[0]: row[i] for i, col in enumerate(cursor.description)}


def _col_exists(conn, tabela, coluna):
    """Verifica se uma coluna existe na tabela (SQLite ou interface Turso)."""
    try:
        rows = conn.execute(f"PRAGMA table_info({tabela})").fetchall()
        # rows pode ser lista de dicts ou de tuples dependendo do driver
        for r in rows:
            nome = r["name"] if isinstance(r, dict) else r[1]
            if nome == coluna:
                return True
    except Exception:
        pass
    return False


def _table_exists(conn, tabela):
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (tabela,),
        ).fetchall()
        return len(rows) > 0
    except Exception:
        return False


# ── Migração principal ────────────────────────────────────────────────────

def migrar(conn, label="local"):
    print(f"\n{'='*55}")
    print(f"  Migrando banco: {label}")
    print(f"{'='*55}")

    # 1. Cria tabelas novas
    print("1. Criando tabelas grupos e usuarios_grupo…")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS grupos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            criado_em TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usuarios_grupo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grupo_id INTEGER NOT NULL,
            user_email TEXT NOT NULL,
            papel TEXT NOT NULL DEFAULT 'membro'
        )
    """)
    try:
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_usuarios_grupo_unique
            ON usuarios_grupo(grupo_id, user_email)
        """)
    except Exception as e:
        print(f"   (índice único já existe ou não suportado: {e})")
    conn.commit()

    # 2. Adiciona grupo_id às tabelas de dados
    print("2. Adicionando coluna grupo_id às tabelas de dados…")
    for tabela in TABELAS_COM_GRUPO_ID:
        if not _table_exists(conn, tabela):
            print(f"   ⚠  Tabela '{tabela}' não existe — pulando.")
            continue
        if _col_exists(conn, tabela, "grupo_id"):
            print(f"   ✓  {tabela}.grupo_id já existe.")
        else:
            conn.execute(f"ALTER TABLE {tabela} ADD COLUMN grupo_id INTEGER")
            conn.commit()
            print(f"   +  {tabela}.grupo_id adicionado.")

    # 3. Cria o grupo inicial (se ainda não existir)
    print("3. Verificando grupo inicial…")
    rows = conn.execute("SELECT id FROM grupos LIMIT 1").fetchall()
    if rows:
        grupo_id = rows[0]["id"] if isinstance(rows[0], dict) else rows[0][0]
        print(f"   ✓  Grupo existente encontrado (ID {grupo_id}) — usando-o.")
    else:
        cur = conn.execute("INSERT INTO grupos (nome) VALUES (?)", (GRUPO_NOME,))
        conn.commit()
        grupo_id = cur.lastrowid
        print(f"   +  Grupo '{GRUPO_NOME}' criado (ID {grupo_id}).")

    # 4. Adiciona membros ao grupo
    print("4. Adicionando membros ao grupo…")
    for email, papel in MEMBROS:
        existe = conn.execute(
            "SELECT id FROM usuarios_grupo WHERE grupo_id=? AND lower(user_email)=lower(?)",
            (grupo_id, email),
        ).fetchall()
        if existe:
            print(f"   ✓  {email} já é membro.")
        else:
            conn.execute(
                "INSERT INTO usuarios_grupo (grupo_id, user_email, papel) VALUES (?, ?, ?)",
                (grupo_id, email.lower(), papel),
            )
            conn.commit()
            print(f"   +  {email} adicionado como {papel}.")

    # 5. Migra linhas existentes sem grupo_id
    print("5. Atualizando linhas sem grupo_id para grupo_id =", grupo_id, "…")
    for tabela in TABELAS_COM_GRUPO_ID:
        if not _table_exists(conn, tabela):
            continue
        if not _col_exists(conn, tabela, "grupo_id"):
            continue
        try:
            cur = conn.execute(
                f"UPDATE {tabela} SET grupo_id = ? WHERE grupo_id IS NULL",
                (grupo_id,),
            )
            conn.commit()
            try:
                n = cur.rowcount
            except Exception:
                n = "?"
            print(f"   ✓  {tabela}: {n} linha(s) atualizada(s).")
        except Exception as e:
            print(f"   ✗  {tabela}: erro ao atualizar — {e}")

    print(f"\n✅  Migração concluída para {label}!\n")


# ── SQLite local ──────────────────────────────────────────────────────────

def migrar_local():
    if not os.path.exists(DB_PATH):
        print(f"⚠  Banco local não encontrado em {DB_PATH}")
        print("   Se for uma instalação nova, o banco será criado ao iniciar o app.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = _linha_para_dict
    conn.execute("PRAGMA foreign_keys = OFF")  # permite ALTER TABLE
    try:
        migrar(conn, label=f"SQLite local ({DB_PATH})")
    finally:
        conn.close()


# ── Turso (nuvem) ─────────────────────────────────────────────────────────

def migrar_turso():
    """Lê credenciais do ambiente ou de .streamlit/secrets.toml e migra o Turso."""
    url = os.environ.get("TURSO_URL")
    token = os.environ.get("TURSO_AUTH_TOKEN")

    if not url or not token:
        # Tenta ler do secrets.toml
        secrets_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), ".streamlit", "secrets.toml"
        )
        if os.path.exists(secrets_path):
            try:
                import tomllib  # Python 3.11+
            except ImportError:
                try:
                    import tomli as tomllib  # pip install tomli
                except ImportError:
                    tomllib = None

            if tomllib:
                with open(secrets_path, "rb") as f:
                    secrets = tomllib.load(f)
                url = secrets.get("turso", {}).get("url")
                token = secrets.get("turso", {}).get("auth_token")

    if not url or not token:
        print("\n⚠  Credenciais do Turso não encontradas.")
        print("   Defina TURSO_URL e TURSO_AUTH_TOKEN no ambiente, ou adicione-as ao secrets.toml.")
        print("   Pulando migração do banco em nuvem.")
        return

    try:
        import libsql_client
    except ImportError:
        print("\n⚠  libsql_client não instalado. Execute: pip install libsql-client")
        return

    # Adapta URL
    if url.startswith("libsql://"):
        url = url.replace("libsql://", "https://", 1)

    # Wrapper compatível com a interface SQLite usada por migrar()
    class TursoConn:
        def __init__(self):
            self._c = libsql_client.create_client_sync(url=url, auth_token=token)

        class _Res:
            def __init__(self, rs):
                if rs.columns:
                    self._rows = [dict(zip(rs.columns, r)) for r in rs.rows]
                else:
                    self._rows = []
                try:
                    self.lastrowid = rs.last_insert_rowid
                    self.rowcount = rs.rows_affected
                except Exception:
                    self.lastrowid = None
                    self.rowcount = -1

            def fetchall(self):
                return self._rows

            def fetchone(self):
                return self._rows[0] if self._rows else None

        def execute(self, sql, params=()):
            return self._Res(self._c.execute(sql, list(params)))

        def commit(self):
            pass  # Turso auto-confirma

    conn = TursoConn()
    migrar(conn, label="Turso (nuvem)")


# ── Ponto de entrada ──────────────────────────────────────────────────────

if __name__ == "__main__":
    migrar_local()
    migrar_turso()
    print("Tudo pronto! Pode subir o novo código.")
