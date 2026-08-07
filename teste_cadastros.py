"""teste_cadastros.py — categorias e formas de pagamento por grupo.

    python3 teste_cadastros.py

As duas listas misturam item de fábrica (grupo_id nulo, todo mundo vê) com
item criado por uma família (só ela vê). É fácil errar isso e vazar o nome de
uma categoria de um grupo para outro, ou deixar alguém apagar item de fábrica
e sumir com a opção para todas as famílias de uma vez.

Também cobre a recusa em apagar categoria em uso: sem isso, lançamentos
ficariam apontando para o vazio e o DRE pararia de somar aquele gasto sem
avisar ninguém.
"""

import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import database as db  # noqa: E402


def _conexao_descartavel():
    caminho = os.path.join(tempfile.mkdtemp(prefix="casacapital-cad-"), "teste.db")
    conn = sqlite3.connect(caminho)
    conn.row_factory = lambda cur, row: {c[0]: row[i] for i, c in enumerate(cur.description)}
    return conn


def executar():
    conn = _conexao_descartavel()
    db.init_db(conn)
    falhas = []

    grupo_a = db.criar_grupo(conn, "Família A")
    grupo_b = db.criar_grupo(conn, "Família B")

    de_fabrica = len(db.listar_categorias(conn, grupo_id=grupo_a))
    print(f"Categorias de fábrica visíveis para qualquer grupo: {de_fabrica}")
    if de_fabrica == 0:
        falhas.append("nenhuma categoria de fábrica")

    # ── Categorias ───────────────────────────────────────────────────────
    db.criar_categoria(conn, "Cavalo do Leo", "despesa", "🐴", grupo_id=grupo_a)
    db.criar_categoria(conn, "Barco", "despesa", "⛵", grupo_id=grupo_b)

    nomes_a = [c["nome"] for c in db.listar_categorias(conn, grupo_id=grupo_a)]
    nomes_b = [c["nome"] for c in db.listar_categorias(conn, grupo_id=grupo_b)]

    print("\nCategorias:")
    for rotulo, nomes, minha, alheia in (
        ("grupo A", nomes_a, "Cavalo do Leo", "Barco"),
        ("grupo B", nomes_b, "Barco", "Cavalo do Leo"),
    ):
        ve_a_sua = minha in nomes
        ve_a_outra = alheia in nomes
        print(f"  {rotulo}: vê a própria={ve_a_sua}  vê a do vizinho={ve_a_outra}"
              f"   {'ok' if ve_a_sua and not ve_a_outra else 'ERRADO'}")
        if not ve_a_sua:
            falhas.append(f"{rotulo} não vê a própria categoria")
        if ve_a_outra:
            falhas.append(f"{rotulo} VÊ a categoria do outro grupo")

    # Categoria de fábrica ninguém apaga
    fabrica = [c for c in db.listar_categorias(conn, grupo_id=grupo_a) if c["grupo_id"] is None][0]
    apagou, motivo = db.deletar_categoria(conn, fabrica["id"], grupo_a)
    print(f"\n  apagar categoria de fábrica -> {'APAGOU' if apagou else 'recusou'}"
          f"   {'ERRADO' if apagou else 'ok'}")
    if apagou:
        falhas.append("apagou categoria de fábrica")

    # Categoria de outro grupo também não
    minha_b = [c for c in db.listar_categorias(conn, grupo_id=grupo_b)
               if c["nome"] == "Barco"][0]
    apagou, _ = db.deletar_categoria(conn, minha_b["id"], grupo_a)
    print(f"  grupo A apagar categoria do B  -> {'APAGOU' if apagou else 'recusou'}"
          f"   {'ERRADO' if apagou else 'ok'}")
    if apagou:
        falhas.append("grupo A apagou categoria do grupo B")

    # Categoria em uso não sai
    minha_a = [c for c in db.listar_categorias(conn, grupo_id=grupo_a)
               if c["nome"] == "Cavalo do Leo"][0]
    conta = db.criar_conta(conn, "Banco A", "banco", 0.0, grupo_id=grupo_a)
    db.criar_lancamento(conn, "2026-08-01", conta, minha_a["id"], "Ração",
                        200.0, "saida", "pago", 1, grupo_id=grupo_a)
    apagou, motivo = db.deletar_categoria(conn, minha_a["id"], grupo_a)
    print(f"  apagar categoria em uso        -> {'APAGOU' if apagou else 'recusou'}"
          f"   ({motivo})   {'ERRADO' if apagou else 'ok'}")
    if apagou:
        falhas.append("apagou categoria em uso")

    # ── Formas de pagamento ──────────────────────────────────────────────
    print("\nFormas de pagamento:")
    padrao = db.nomes_formas_pagamento(conn, grupo_id=grupo_a)
    print(f"  de fábrica: {len(padrao)}")
    if "Pix" not in padrao:
        falhas.append("lista de fábrica sem Pix")

    db.criar_forma_pagamento(conn, "Vale-refeição", grupo_a)
    a = db.nomes_formas_pagamento(conn, grupo_id=grupo_a)
    b = db.nomes_formas_pagamento(conn, grupo_id=grupo_b)
    print(f"  grupo A vê a própria={'Vale-refeição' in a}  "
          f"grupo B vê a do A={'Vale-refeição' in b}"
          f"   {'ok' if 'Vale-refeição' in a and 'Vale-refeição' not in b else 'ERRADO'}")
    if "Vale-refeição" not in a:
        falhas.append("grupo A não vê a própria forma")
    if "Vale-refeição" in b:
        falhas.append("grupo B VÊ a forma do grupo A")

    fabrica_forma = [f for f in db.listar_formas_pagamento(conn, grupo_id=grupo_a)
                     if f["grupo_id"] is None][0]
    apagou, _ = db.deletar_forma_pagamento(conn, fabrica_forma["id"], grupo_a)
    print(f"  apagar forma de fábrica        -> {'APAGOU' if apagou else 'recusou'}"
          f"   {'ERRADO' if apagou else 'ok'}")
    if apagou:
        falhas.append("apagou forma de pagamento de fábrica")

    conn.close()
    return falhas


if __name__ == "__main__":
    problemas = executar()
    if problemas:
        print("\nFALHOU: " + "; ".join(problemas))
    else:
        print("\nOK — cada grupo só vê o que é seu, e nada de fábrica ou em uso é apagado.")
    sys.stdout.flush()
    os._exit(1 if problemas else 0)
