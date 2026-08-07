"""teste_projecao.py — a conta do saldo futuro tem que fechar.

    python3 teste_projecao.py

Projeção errada não dá erro na tela: mostra um número plausível e o usuário
toma decisão em cima dele. Por isso os valores aqui são escolhidos a mão, com
o resultado conferível de cabeça.

Cenário: saldo pago de 1.000, uma entrada de 500 em 5 dias, uma saída de 2.000
em 10 dias, e uma conta de 300 VENCIDA há 3 dias e ainda não paga.
"""

import os
import sqlite3
import sys
import tempfile
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import database as db  # noqa: E402


def _conexao_descartavel():
    caminho = os.path.join(tempfile.mkdtemp(prefix="casacapital-proj-"), "teste.db")
    conn = sqlite3.connect(caminho)
    conn.row_factory = lambda cur, row: {c[0]: row[i] for i, c in enumerate(cur.description)}
    return conn


def executar():
    conn = _conexao_descartavel()
    db.init_db(conn)
    falhas = []
    hoje = date.today()

    grupo = db.criar_grupo(conn, "Família Teste")
    conta = db.criar_conta(conn, "Banco", "banco", 1000.0, grupo_id=grupo)
    db.criar_conta(conn, "Carteira", "carteira", 200.0, grupo_id=grupo)
    db.criar_investimento(conn, "Tesouro", "Renda Fixa", 5000.0, 5500.0, 1, grupo_id=grupo)

    receita = [c for c in db.listar_categorias(conn, tipo="receita", grupo_id=grupo)][0]["id"]
    despesa = [c for c in db.listar_categorias(conn, tipo="despesa", grupo_id=grupo)][0]["id"]

    def lancar(dias, desc, valor, tipo, status, cat):
        db.criar_lancamento(conn, (hoje + timedelta(days=dias)).isoformat(), conta, cat,
                            desc, valor, tipo, status, 1, grupo_id=grupo)

    lancar(+5, "Salário", 500.0, "entrada", "pendente", receita)
    lancar(+10, "Aluguel", 2000.0, "saida", "pendente", despesa)
    lancar(-3, "Luz atrasada", 300.0, "saida", "pendente", despesa)

    # ── Saldo por natureza ───────────────────────────────────────────────
    natureza = db.saldo_por_natureza(conn, grupo_id=grupo)
    print("Saldo atual:")
    print(f"  caixa={natureza['caixa']:.2f} (esperado 200)  "
          f"bancos={natureza['bancos']:.2f} (esperado 1000)  "
          f"aplicações={natureza['aplicacoes']:.2f} (esperado 5500)")
    for chave, esperado in (("caixa", 200), ("bancos", 1000), ("aplicacoes", 5500),
                            ("disponivel", 1200), ("total", 6700)):
        if abs(natureza[chave] - esperado) > 0.01:
            falhas.append(f"{chave}={natureza[chave]}, esperado {esperado}")

    # ── Previsto ─────────────────────────────────────────────────────────
    print("\nPrevisto (o vencido entra desde o primeiro dia):")
    for dias, esp_ent, esp_sai in ((7, 500, 300), (30, 500, 2300), (90, 500, 2300)):
        entradas, saidas = db.previsto_ate(conn, dias, grupo_id=grupo)
        ok = abs(entradas - esp_ent) < 0.01 and abs(saidas - esp_sai) < 0.01
        print(f"  {dias:>2} dias: entradas={entradas:>7.2f} (esp {esp_ent})  "
              f"saídas={saidas:>7.2f} (esp {esp_sai})   {'ok' if ok else 'ERRADO'}")
        if not ok:
            falhas.append(f"previsto {dias} dias")

    # ── Projeção diária ──────────────────────────────────────────────────
    # 1200 hoje, -300 do vencido = 900 · +500 no dia 5 = 1400 · -2000 no dia 10 = -600
    pontos = db.projecao_saldo(conn, 15, grupo_id=grupo)
    por_dia = {d: s for d, s, _, _ in pontos}
    print("\nProjeção diária:")
    for dias, esperado, rotulo in ((0, 900, "hoje, já com a conta vencida"),
                                   (4, 900, "véspera do salário"),
                                   (5, 1400, "salário cai"),
                                   (9, 1400, "véspera do aluguel"),
                                   (10, -600, "aluguel sai — fura o zero"),
                                   (15, -600, "fim do período")):
        obtido = por_dia[hoje + timedelta(days=dias)]
        ok = abs(obtido - esperado) < 0.01
        print(f"  dia +{dias:<3} {obtido:>9.2f}  (esperado {esperado:>7})  "
              f"{rotulo:32} {'ok' if ok else 'ERRADO'}")
        if not ok:
            falhas.append(f"projeção dia +{dias}: {obtido} != {esperado}")

    negativos = [d for d, s, _, _ in pontos if s < 0]
    esperado_negativo = hoje + timedelta(days=10)
    print(f"\n  primeiro dia negativo: {negativos[0] if negativos else 'nenhum'} "
          f"(esperado {esperado_negativo})   "
          f"{'ok' if negativos and negativos[0] == esperado_negativo else 'ERRADO'}")
    if not negativos or negativos[0] != esperado_negativo:
        falhas.append("não detectou o dia em que o saldo fura o zero")

    # ── Agrupamento ──────────────────────────────────────────────────────
    print("\nAgrupamento (o saldo de cada balde é o do ÚLTIMO dia dele):")
    for granularidade in ("semanal", "mensal"):
        baldes = db.agrupar_projecao(pontos, granularidade)
        soma_e = sum(b[2] for b in baldes)
        soma_s = sum(b[3] for b in baldes)
        ok = abs(soma_e - 500) < 0.01 and abs(soma_s - 2300) < 0.01 and baldes[-1][1] == pontos[-1][1]
        print(f"  {granularidade:<8} {len(baldes)} balde(s)  entradas={soma_e:.2f}  "
              f"saídas={soma_s:.2f}  saldo final={baldes[-1][1]:.2f}   {'ok' if ok else 'ERRADO'}")
        if not ok:
            falhas.append(f"agrupamento {granularidade} não bate com o diário")

    conn.close()
    return falhas


if __name__ == "__main__":
    problemas = executar()
    if problemas:
        print("\nFALHOU: " + "; ".join(problemas))
    else:
        print("\nOK — a projeção fecha, o vencido pesa desde hoje e o furo é detectado.")
    sys.stdout.flush()
    os._exit(1 if problemas else 0)
