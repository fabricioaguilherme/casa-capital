"""Camada de conexão com o banco: SQLite local ou Turso na nuvem.

O aplicativo inteiro fala com UMA interface (`execute`, `executescript`,
`executemany`, `commit`), e as linhas sempre voltam como dicionário.
Assim `database.py` e os módulos não sabem — nem precisam saber — onde
o banco está rodando.

Modo é decidido pela presença das credenciais do Turso em st.secrets
(ou variáveis de ambiente). Sem elas, roda local, como sempre foi.
"""

import os
import sqlite3

CAMINHO_LOCAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "financeiro.db")


def _credenciais_turso():
    """Lê url/token de st.secrets ou de variáveis de ambiente. None se não houver."""
    url = token = None
    try:
        import streamlit as st

        if "turso" in st.secrets:
            url = st.secrets["turso"].get("url")
            token = st.secrets["turso"].get("auth_token")
    except Exception:
        pass

    url = url or os.environ.get("TURSO_URL")
    token = token or os.environ.get("TURSO_AUTH_TOKEN")
    return (url, token) if url and token else (None, None)


def modo():
    """'nuvem' se houver credenciais do Turso, senão 'local'."""
    url, _ = _credenciais_turso()
    return "nuvem" if url else "local"


def _linha_para_dict(cursor, row):
    return {col[0]: row[i] for i, col in enumerate(cursor.description)}


# ── Adaptador do Turso ───────────────────────────────────────────────────

class _ResultadoTurso:
    """Imita o cursor do sqlite3 para o resto do código não perceber diferença."""

    def __init__(self, resultset):
        self._linhas = [dict(zip(resultset.columns, linha)) for linha in resultset.rows]
        self.lastrowid = getattr(resultset, "last_insert_rowid", None)
        self.rowcount = getattr(resultset, "rows_affected", -1)

    def fetchone(self):
        return self._linhas[0] if self._linhas else None

    def fetchall(self):
        return self._linhas

    def __iter__(self):
        return iter(self._linhas)


class ConexaoTurso:
    """Conexão com o Turso expondo a mesma interface do sqlite3 usada no app."""

    def __init__(self, url, auth_token):
        import libsql_client

        # o cliente HTTP fala https://; o painel do Turso mostra libsql://
        if url.startswith("libsql://"):
            url = url.replace("libsql://", "https://", 1)
        self._cliente = libsql_client.create_client_sync(url=url, auth_token=auth_token)
        self.modo = "nuvem"

    def execute(self, sql, params=()):
        # o cliente HTTP espera lista; None vira NULL normalmente
        return _ResultadoTurso(self._cliente.execute(sql, list(params)))

    def executemany(self, sql, sequencia):
        comandos = [(sql, list(p)) for p in sequencia]
        if comandos:
            self._cliente.batch(comandos)
        return self

    def executescript(self, script):
        """Executa vários comandos separados por ';'.

        As linhas de comentário são removidas ANTES da divisão: se um comando
        vier precedido de comentário, dividir primeiro faria o trecho inteiro
        parecer comentário e o comando seria perdido silenciosamente.
        """
        sem_comentarios = "\n".join(
            linha for linha in script.splitlines()
            if not linha.strip().startswith("--")
        )
        comandos = [c.strip() for c in sem_comentarios.split(";")]
        comandos = [c for c in comandos if c]
        if comandos:
            self._cliente.batch(comandos)
        return self

    def commit(self):
        # o Turso via HTTP confirma cada comando na hora
        pass

    def close(self):
        self._cliente.close()


# ── Fábrica ──────────────────────────────────────────────────────────────

def conectar():
    """Devolve a conexão certa conforme o ambiente."""
    url, token = _credenciais_turso()
    if url:
        return ConexaoTurso(url, token)

    conn = sqlite3.connect(CAMINHO_LOCAL, check_same_thread=False)
    conn.row_factory = _linha_para_dict
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
