"""teste_cartao_crud.py — editar e excluir cartão sem estragar nada.

    python3 teste_cartao_crud.py

O cartão vive em duas tabelas ao mesmo tempo: o nome em `contas`, o resto
(fechamento, vencimento, limite) em `cartoes`. É fácil atualizar uma e esquecer
a outra, ou apagar a ficha e deixar a conta órfã aparecendo no Fluxo de Caixa.

Também confere que um grupo não mexe no cartão do outro por id adivinhado, e
que excluir cartão com compras exige confirmação — senão o histórico de fatura
sumiria junto sem ninguém perceber.
"""

import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import database as db  # noqa: E402


def _conexao_descartavel():
    caminho = os.path.join(tempfile.mkdtemp(prefix="casacapital-cartao-"), "teste.db")
    conn = sqlite3.connect(caminho)
    conn.row_factory = lambda cur, row: {c[0]: row[i] for i, c in enumerate(cur.description)}
    return conn


def executar():
    conn = _conexao_descartavel()
    db.init_db(conn)
    falhas = []

    grupo_a = db.criar_grupo(conn, "Família A")
    grupo_b = db.criar_grupo(conn, "Família B")
    cartao = db.criar_cartao(conn, "Nubank", 25, 5, 3000.0, grupo_id=grupo_a)

    # ── Editar ───────────────────────────────────────────────────────────
    db.atualizar_cartao(conn, cartao, "Nubank Ultravioleta", 20, 10, 9000.0, grupo_a)
    depois = [c for c in db.listar_cartoes(conn, grupo_id=grupo_a) if c["id"] == cartao][0]
    nome_ok = depois["nome_conta"] == "Nubank Ultravioleta"
    dados_ok = (depois["dia_fechamento"], depois["dia_vencimento"], depois["limite"]) == (20, 10, 9000.0)
    print(f"  editar: nome em `contas`={nome_ok}  resto em `cartoes`={dados_ok}"
          f"   {'ok' if nome_ok and dados_ok else 'ERRADO'}")
    if not nome_ok:
        falhas.append("nome não atualizou na tabela contas")
    if not dados_ok:
        falhas.append("fechamento/vencimento/limite não atualizaram")

    # ── Grupo alheio não edita ───────────────────────────────────────────
    mexeu = db.atualizar_cartao(conn, cartao, "Invadido", 1, 1, 0.0, grupo_b)
    nome_atual = [c for c in db.listar_cartoes(conn, grupo_id=grupo_a) if c["id"] == cartao][0]["nome_conta"]
    print(f"  grupo B editar cartão do A -> {'MEXEU' if mexeu else 'recusou'}"
          f"   {'ERRADO' if mexeu or nome_atual == 'Invadido' else 'ok'}")
    if mexeu or nome_atual == "Invadido":
        falhas.append("grupo B editou cartão do grupo A")

    # ── Excluir com compras: recusa sem confirmação ──────────────────────
    conta = db.criar_conta(conn, "Banco A", "banco", 0.0, grupo_id=grupo_a)
    categoria = [c for c in db.listar_categorias(conn, tipo="despesa", grupo_id=grupo_a)][0]["id"]
    db.criar_lancamento(conn, "2026-08-01", conta, categoria, "Notebook",
                        3000.0, "saida", "pendente", 1, cartao_id=cartao, grupo_id=grupo_a)

    apagou, motivo = db.deletar_cartao(conn, cartao, grupo_a)
    print(f"  excluir com compras, sem confirmar -> {'APAGOU' if apagou else 'recusou'}"
          f"   ({motivo})   {'ERRADO' if apagou else 'ok'}")
    if apagou:
        falhas.append("apagou cartão com compras sem confirmação")

    # ── Grupo alheio não exclui ──────────────────────────────────────────
    apagou, _ = db.deletar_cartao(conn, cartao, grupo_b, apagar_lancamentos=True)
    print(f"  grupo B excluir cartão do A        -> {'APAGOU' if apagou else 'recusou'}"
          f"   {'ERRADO' if apagou else 'ok'}")
    if apagou:
        falhas.append("grupo B apagou cartão do grupo A")

    # ── Excluir confirmado: some das DUAS tabelas ────────────────────────
    apagou, _ = db.deletar_cartao(conn, cartao, grupo_a, apagar_lancamentos=True)
    sobrou_ficha = conn.execute("SELECT COUNT(*) n FROM cartoes WHERE id = ?", (cartao,)).fetchone()["n"]
    sobrou_conta = len([c for c in db.listar_contas(conn, apenas_ativas=False, grupo_id=grupo_a)
                        if c["tipo"] == "cartao"])
    print(f"  excluir confirmado -> apagou={apagou}  ficha restante={sobrou_ficha}  "
          f"conta órfã={sobrou_conta}   {'ok' if apagou and not sobrou_ficha and not sobrou_conta else 'ERRADO'}")
    if not apagou:
        falhas.append("não apagou com confirmação")
    if sobrou_ficha:
        falhas.append("ficha em `cartoes` sobrou")
    if sobrou_conta:
        falhas.append("conta órfã sobrou em `contas`")

    conn.close()
    return falhas


if __name__ == "__main__":
    print("Cartão — editar e excluir:")
    problemas = executar()
    if problemas:
        print("\nFALHOU: " + "; ".join(problemas))
    else:
        print("\nOK — as duas tabelas andam juntas e nenhum grupo mexe no cartão do outro.")
    sys.stdout.flush()
    os._exit(1 if problemas else 0)
