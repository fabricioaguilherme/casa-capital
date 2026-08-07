"""teste_porta_entrada.py — quem entra é quem tem grupo.

    python3 teste_porta_entrada.py

O vínculo em `usuarios_grupo` é a porta. `emails_autorizados` virou tranca
extra opcional: se a lista existir nos secrets, vale; se não existir, o grupo
decide sozinho. Assim liberar alguém é um cadastro na tela de Administração,
sem editar secrets nem reiniciar o app.

Duas garantias são verificadas aqui:
  1. sem grupo ninguém entra, com ou sem lista de autorizados;
  2. quem não entra NÃO deixa linha em `usuarios` — senão qualquer curioso com
     conta Google engordaria o banco só por ter tentado.
"""

import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import auth  # noqa: E402
import database as db  # noqa: E402


def _conexao_descartavel():
    caminho = os.path.join(tempfile.mkdtemp(prefix="casacapital-porta-"), "teste.db")
    conn = sqlite3.connect(caminho)
    conn.row_factory = lambda cur, row: {c[0]: row[i] for i, c in enumerate(cur.description)}
    return conn


class SessaoFalsa(dict):
    """Substitui st.session_state, que não existe fora do Streamlit."""


def executar():
    conn = _conexao_descartavel()
    db.init_db(conn)
    grupo = db.criar_grupo(conn, "Família Teste")
    db.adicionar_membro_grupo(conn, grupo, "membro@teste.com", "admin")

    # Sem Streamlit rodando, st.session_state e st.secrets não existem.
    auth.st.session_state = SessaoFalsa()
    auth.rede_permitida = lambda email: (True, "179.193.98.99")

    falhas = []

    def tentar(rotulo, email, autorizados, deve_entrar):
        auth._emails_autorizados = lambda: autorizados
        auth.st.session_state.clear()
        antes = len(conn.execute("SELECT id FROM usuarios").fetchall())
        resultado = auth._usuario_do_google(conn, {"email": email, "name": "Fulano"})
        depois = len(conn.execute("SELECT id FROM usuarios").fetchall())
        entrou = resultado is not None
        sujou = depois > antes

        marca = "ok" if entrou == deve_entrar else "ERRADO"
        if entrou != deve_entrar:
            falhas.append(rotulo)
        # Quem não entra não pode criar registro
        if not deve_entrar and sujou:
            marca = "ERRADO (criou linha no banco)"
            falhas.append(rotulo + " / sujou o banco")

        print(f"  {rotulo:44} {'entrou' if entrou else 'barrado':8} {marca}")

    print("Com lista de autorizados vazia (o grupo decide sozinho):")
    tentar("membro do grupo", "membro@teste.com", [], True)
    tentar("estranho sem grupo", "invasor@teste.com", [], False)

    print("\nCom lista de autorizados preenchida (tranca extra ligada):")
    tentar("membro do grupo, na lista", "membro@teste.com", ["membro@teste.com"], True)
    tentar("membro do grupo, fora da lista", "membro@teste.com", ["outro@teste.com"], False)
    tentar("estranho, mesmo estando na lista", "invasor@teste.com", ["invasor@teste.com"], False)

    total = len(conn.execute("SELECT id FROM usuarios").fetchall())
    print(f"\n  linhas em `usuarios` ao final: {total} (só o membro legítimo)")
    if total != 1:
        falhas.append(f"banco com {total} usuários, esperado 1")

    conn.close()
    return falhas


if __name__ == "__main__":
    problemas = executar()
    if problemas:
        print("\nFALHOU: " + "; ".join(problemas))
    else:
        print("\nOK — o grupo é a porta, e quem é barrado não deixa rastro.")
    sys.stdout.flush()
    os._exit(1 if problemas else 0)
