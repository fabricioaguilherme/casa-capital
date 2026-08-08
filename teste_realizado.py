"""teste_realizado.py — a análise do passado só conta o que aconteceu.

    python3 teste_realizado.py

O erro fácil aqui é misturar pendente com pago. Se o previsto entrar no
realizado, o mês aparece com um resultado que nunca existiu — e a pessoa acha
que fechou no azul quando na verdade a conta ainda vai cair.

Também confere o escape do cifrão: o markdown do Streamlit lê `$...$` como
fórmula, e dois valores em R$ na mesma string engolem o HTML entre eles.
"""

import os
import sqlite3
import sys
import tempfile
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import database as db  # noqa: E402
import theme  # noqa: E402


def _conexao_descartavel():
    caminho = os.path.join(tempfile.mkdtemp(prefix="casacapital-real-"), "teste.db")
    conn = sqlite3.connect(caminho)
    conn.row_factory = lambda cur, row: {c[0]: row[i] for i, c in enumerate(cur.description)}
    return conn


def executar():
    conn = _conexao_descartavel()
    db.init_db(conn)
    falhas = []
    hoje = date.today()

    grupo = db.criar_grupo(conn, "Família Teste")
    conta = db.criar_conta(conn, "Banco", "banco", 0.0, grupo_id=grupo)
    receita = db.listar_categorias(conn, tipo="receita", grupo_id=grupo)[0]["id"]
    despesa = db.listar_categorias(conn, tipo="despesa", grupo_id=grupo)[0]["id"]

    def lancar(dias, desc, valor, tipo, status, cat):
        db.criar_lancamento(conn, (hoje + timedelta(days=dias)).isoformat(), conta, cat,
                            desc, valor, tipo, status, 1, grupo_id=grupo)

    # Passado, pago — deve contar
    lancar(-40, "Salário mês passado", 5000.0, "entrada", "pago", receita)
    lancar(-35, "Aluguel mês passado", 2000.0, "saida", "pago", despesa)
    lancar(-10, "Mercado", 800.0, "saida", "pago", despesa)
    # Passado, PENDENTE — não pode contar no realizado
    lancar(-5, "Luz atrasada", 300.0, "saida", "pendente", despesa)
    # Futuro, pendente — também não
    lancar(+10, "Salário deste mês", 5000.0, "entrada", "pendente", receita)

    inicio = (hoje - timedelta(days=90)).isoformat()
    fim = hoje.isoformat()

    entradas, saidas = db.realizado_resumo(conn, inicio, fim, grupo_id=grupo)
    print("Resumo do realizado:")
    print(f"  entradas={entradas:.2f} (esperado 5000 — o salário pendente NÃO entra)")
    print(f"  saídas  ={saidas:.2f} (esperado 2800 — a luz pendente NÃO entra)")
    if abs(entradas - 5000) > 0.01:
        falhas.append(f"entradas={entradas}, esperado 5000")
    if abs(saidas - 2800) > 0.01:
        falhas.append(f"saidas={saidas}, esperado 2800")

    meses = db.realizado_por_mes(conn, inicio, fim, grupo_id=grupo)
    soma_e = sum(m["entradas"] for m in meses)
    soma_s = sum(m["saidas"] for m in meses)
    bate = abs(soma_e - entradas) < 0.01 and abs(soma_s - saidas) < 0.01
    print(f"\n  quebra mensal: {len(meses)} mês(es), soma bate com o resumo={bate}"
          f"   {'ok' if bate else 'ERRADO'}")
    if not bate:
        falhas.append("soma dos meses não bate com o resumo")

    por_cat = db.realizado_por_categoria(conn, inicio, fim, "saida", grupo_id=grupo)
    soma_cat = sum(c["total"] for c in por_cat)
    print(f"  quebra por categoria: soma={soma_cat:.2f} (esperado {saidas:.2f})"
          f"   {'ok' if abs(soma_cat - saidas) < 0.01 else 'ERRADO'}")
    if abs(soma_cat - saidas) > 0.01:
        falhas.append("soma por categoria não bate com as saídas")

    # Previsto e realizado não podem se sobrepor
    prev_e, prev_s = db.previsto_ate(conn, 30, grupo_id=grupo)
    print(f"\n  previsto (só pendente): entradas={prev_e:.2f} saídas={prev_s:.2f}"
          f"   (esperado 5000 e 300)")
    if abs(prev_e - 5000) > 0.01 or abs(prev_s - 300) > 0.01:
        falhas.append("previsto contaminado por lançamento pago")


    # ── Série mensal: passado e futuro na mesma consulta ─────────────────
    serie = db.serie_mensal(conn, (hoje - timedelta(days=90)).isoformat(),
                            (hoje + timedelta(days=90)).isoformat(), grupo_id=grupo)
    tot_er = sum(m["entradas_reais"] for m in serie)
    tot_sr = sum(m["saidas_reais"] for m in serie)
    tot_ep = sum(m["entradas_previstas"] for m in serie)
    tot_sp = sum(m["saidas_previstas"] for m in serie)
    print("\n  série mensal:")
    print(f"    realizado: +{tot_er:.2f} / -{tot_sr:.2f}   (esperado +5000 / -2800)")
    print(f"    previsto : +{tot_ep:.2f} / -{tot_sp:.2f}   (esperado +5000 / -300)")
    if abs(tot_er - 5000) > 0.01 or abs(tot_sr - 2800) > 0.01:
        falhas.append("série: parte realizada não bate")
    if abs(tot_ep - 5000) > 0.01 or abs(tot_sp - 300) > 0.01:
        falhas.append("série: parte prevista não bate")

    # As duas metades não podem se sobrepor: somadas dão o total do período
    for m in serie:
        if abs(m["entradas_total"] - (m["entradas_reais"] + m["entradas_previstas"])) > 0.01:
            falhas.append(f"série: total do mês {m['mes']} não fecha")

    # ── Cifrão escapado ──────────────────────────────────────────────────
    md = theme.moeda_md(1234.56)
    esperado_md = "R" + chr(92) + "$ 1.234,56"
    marca = "ok" if md == esperado_md else "ERRADO"
    print("\n  moeda_md(1234.56) = %r   %s" % (md, marca))
    if md != esperado_md:
        falhas.append(f"moeda_md devolveu {md!r}")
    if theme.moeda(1234.56) != "R$ 1.234,56":
        falhas.append("moeda() normal foi alterada por engano")

    conn.close()
    return falhas


if __name__ == "__main__":
    problemas = executar()
    if problemas:
        print("\nFALHOU: " + "; ".join(problemas))
    else:
        print("\nOK — realizado só conta o pago, previsto só o pendente, e o cifrão sai escapado.")
    sys.stdout.flush()
    os._exit(1 if problemas else 0)
