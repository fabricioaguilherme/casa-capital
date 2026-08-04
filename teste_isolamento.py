"""teste_isolamento.py — verifica que um grupo nunca enxerga dados de outro.

Rode sempre que mexer em consultas do database.py:

    python3 teste_isolamento.py

O teste cria um banco SQLite descartável numa pasta temporária. Ele NUNCA usa
o Turso nem o financeiro.db — a conexão é montada aqui, à mão, justamente para
não depender de `conexao.conectar()`, que escolhe a nuvem quando encontra
credenciais e escreveria dados de teste no banco de produção.
"""

import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import database as db  # noqa: E402


def _conexao_descartavel():
    caminho = os.path.join(tempfile.mkdtemp(prefix="casacapital-teste-"), "teste.db")
    conn = sqlite3.connect(caminho)
    conn.row_factory = lambda cur, row: {c[0]: row[i] for i, c in enumerate(cur.description)}
    return conn


def executar():
    conn = _conexao_descartavel()
    db.init_db(conn)

    grupo_a = db.criar_grupo(conn, "Família A")
    grupo_b = db.criar_grupo(conn, "Família B")
    db.adicionar_membro_grupo(conn, grupo_a, "a@teste.com", "admin")
    db.adicionar_membro_grupo(conn, grupo_b, "b@teste.com", "admin")

    categoria = [c for c in db.listar_categorias(conn) if c["tipo"] in ("saida", "despesa")][0]["id"]

    for grupo, marca in ((grupo_a, "A"), (grupo_b, "B")):
        e_a = grupo == grupo_a
        conta = db.criar_conta(conn, f"Conta {marca}", "banco", 1000.0 if e_a else 9999.0, grupo_id=grupo)
        db.criar_lancamento(conn, "2026-08-01", conta, categoria, f"Lanc {marca}",
                            100.0 if e_a else 777.0, "saida", "pago", 1, grupo_id=grupo)
        db.criar_patrimonio_item(conn, f"Bem {marca}", "ativo", "Imóvel",
                                 50000.0 if e_a else 88888.0, 1, grupo_id=grupo)
        db.criar_investimento(conn, f"Inv {marca}", "Renda Fixa", 10.0,
                              20.0 if e_a else 555.0, 1, grupo_id=grupo)
        db.criar_meta(conn, f"Meta {marca}", 100.0, "2026-12-31", 1, grupo_id=grupo)

    falhas = []
    marcas_b = ("Conta B", "Lanc B", "Bem B", "Inv B", "Meta B")

    def conferir(rotulo, itens):
        vazou = [i for i in itens if any(m in str(dict(i)) for m in marcas_b)]
        print(f"  {rotulo:22} {len(itens)} item(ns)   {'VAZOU' if vazou else 'isolado'}")
        if vazou:
            falhas.append(rotulo)

    print("Consultando como Família A — nada da Família B pode aparecer:")
    conferir("listar_contas", db.listar_contas(conn, apenas_ativas=False, grupo_id=grupo_a))
    conferir("listar_lancamentos", db.listar_lancamentos(conn, grupo_id=grupo_a))
    conferir("listar_patrimonio", db.listar_patrimonio(conn, grupo_id=grupo_a))
    conferir("listar_investimentos", db.listar_investimentos(conn, grupo_id=grupo_a))
    conferir("listar_metas", db.listar_metas(conn, grupo_id=grupo_a))
    conferir("saldos_por_conta", db.saldos_por_conta(conn, grupo_id=grupo_a))

    saldo_a, saldo_b = db.saldo_total(conn, grupo_id=grupo_a), db.saldo_total(conn, grupo_id=grupo_b)
    patr_a, patr_b = db.patrimonio_liquido(conn, grupo_id=grupo_a), db.patrimonio_liquido(conn, grupo_id=grupo_b)
    print(f"\n  saldo_total         A={saldo_a:>12,.2f}   B={saldo_b:>12,.2f}")
    print(f"  patrimonio_liquido  A={patr_a:>12,.2f}   B={patr_b:>12,.2f}")
    if saldo_a != 900.0 or saldo_b != 9222.0:
        falhas.append("saldo_total somou entre grupos")
    if patr_a == patr_b:
        falhas.append("patrimonio_liquido igual entre grupos")

    # Quem não está em usuarios_grupo não pode receber grupo nenhum.
    membro_a = db.grupo_do_usuario(conn, "a@teste.com")
    membro_b = db.grupo_do_usuario(conn, "b@teste.com")
    estranho = db.grupo_do_usuario(conn, "invasor@teste.com")
    print(f"\n  a@teste.com  -> grupo {membro_a['grupo_id'] if membro_a else None} (esperado {grupo_a})")
    print(f"  b@teste.com  -> grupo {membro_b['grupo_id'] if membro_b else None} (esperado {grupo_b})")
    print(f"  invasor      -> {estranho} (esperado None)")
    if not membro_a or membro_a["grupo_id"] != grupo_a:
        falhas.append("grupo_do_usuario A")
    if not membro_b or membro_b["grupo_id"] != grupo_b:
        falhas.append("grupo_do_usuario B")
    if estranho is not None:
        falhas.append("e-mail de fora recebeu grupo")

    conn.close()
    return falhas


if __name__ == "__main__":
    problemas = executar()
    if problemas:
        print("\nFALHOU: " + ", ".join(problemas))
    else:
        print("\nOK — nenhum dado atravessa de um grupo para o outro.")
    sys.stdout.flush()
    # os._exit evita travar caso algum driver deixe thread viva.
    os._exit(1 if problemas else 0)
