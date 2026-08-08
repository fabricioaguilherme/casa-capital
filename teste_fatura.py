"""teste_fatura.py — em que fatura cada compra cai.

    python3 teste_fatura.py

Esta é a conta que decide se a despesa aparece no mês certo e se o dinheiro
sai na data certa. Errar por um dia joga a compra para a fatura seguinte —
um mês inteiro de diferença — e ninguém percebe olhando a tela.

Os casos vêm de cartões reais: fecha 25 vence 05 (vencimento no mês seguinte),
fecha 05 vence 15 (mesmo mês), e fechamento 31 caindo em fevereiro.
"""

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import database as db  # noqa: E402


def executar():
    falhas = []

    casos = [
        # (compra, fecha, vence, fechamento esperado, vencimento esperado, por quê)
        ("2026-08-10", 25, 5, "2026-08-25", "2026-09-05", "compra antes do fechamento"),
        ("2026-08-24", 25, 5, "2026-08-25", "2026-09-05", "véspera do fechamento"),
        ("2026-08-25", 25, 5, "2026-09-25", "2026-10-05", "NO dia do fechamento: já é a próxima"),
        ("2026-08-28", 25, 5, "2026-09-25", "2026-10-05", "depois do fechamento"),
        ("2026-12-28", 25, 5, "2027-01-25", "2027-02-05", "vira o ano"),
        ("2026-08-01", 5, 15, "2026-08-05", "2026-08-15", "vence no mesmo mês do fechamento"),
        ("2026-08-06", 5, 15, "2026-09-05", "2026-09-15", "idem, depois do fechamento"),
        ("2026-01-30", 31, 10, "2026-01-31", "2026-02-10", "fechamento 31 em mês de 31"),
        ("2026-02-05", 31, 10, "2026-02-28", "2026-03-10", "fechamento 31 em fevereiro → dia 28"),
        ("2024-02-05", 31, 10, "2024-02-29", "2024-03-10", "ano bissexto → dia 29"),
    ]

    for compra, fecha, vence, esp_f, esp_v, motivo in casos:
        f, v = db.ciclo_fatura(compra, fecha, vence)
        ok = f.isoformat() == esp_f and v.isoformat() == esp_v
        if not ok:
            falhas.append(f"{compra} (fecha {fecha}/vence {vence}): "
                          f"deu {f}/{v}, esperado {esp_f}/{esp_v}")
        print(f"  {compra}  fecha {fecha:>2} vence {vence:>2}  →  "
              f"fatura {f} paga em {v}   {'ok' if ok else 'ERRADO'}   {motivo}")

    # Todas as compras de um mesmo ciclo têm de cair no MESMO vencimento —
    # é isso que faz a fatura virar um valor só no fluxo de caixa.
    print("\n  compras do mesmo ciclo caem no mesmo vencimento:")
    vencimentos = {db.ciclo_fatura(f"2026-08-{d:02d}", 25, 5)[1]
                   for d in (1, 10, 20, 24)}
    ok = len(vencimentos) == 1
    print(f"    dias 1, 10, 20 e 24 → {len(vencimentos)} vencimento(s)   {'ok' if ok else 'ERRADO'}")
    if not ok:
        falhas.append("compras do mesmo ciclo caíram em vencimentos diferentes")

    # E a compra logo após o fechamento tem de cair no vencimento seguinte
    v_antes = db.ciclo_fatura("2026-08-24", 25, 5)[1]
    v_depois = db.ciclo_fatura("2026-08-25", 25, 5)[1]
    ok = v_depois > v_antes
    print(f"    24/08 vence {v_antes} · 25/08 vence {v_depois}   {'ok' if ok else 'ERRADO'}")
    if not ok:
        falhas.append("o fechamento não separou os ciclos")

    return falhas


def caixa_vs_competencia():
    """A compra é despesa no dia da compra; o dinheiro sai no vencimento."""
    import sqlite3, tempfile
    from datetime import timedelta
    caminho = os.path.join(tempfile.mkdtemp(prefix="casacapital-fat-"), "teste.db")
    conn = sqlite3.connect(caminho)
    conn.row_factory = lambda cur, row: {c[0]: row[i] for i, c in enumerate(cur.description)}
    db.init_db(conn)
    falhas = []
    hoje = date.today()

    grupo = db.criar_grupo(conn, "Família Teste")
    conta = db.criar_conta(conn, "Banco", "banco", 10000.0, grupo_id=grupo)
    # Fecha daqui a 5 dias, vence 20 dias depois da compra
    fecha = (hoje + timedelta(days=5)).day
    vence = (hoje + timedelta(days=20)).day
    cartao = db.criar_cartao(conn, "Cartão", fecha, vence, 5000.0, grupo_id=grupo)
    despesa = db.listar_categorias(conn, tipo="despesa", grupo_id=grupo)[0]["id"]

    db.criar_lancamento(conn, hoje.isoformat(), conta, despesa, "Notebook",
                        3000.0, "saida", "pendente", 1,
                        cartao_id=cartao, grupo_id=grupo)

    pendentes = db.pendentes_em_caixa(conn, grupo_id=grupo)
    compra = pendentes[0]
    _, vencimento = db.ciclo_fatura(hoje.isoformat(), fecha, vence)

    print("\n  compra no cartão:")
    print(f"    data da compra   : {hoje}")
    print(f"    data de caixa    : {compra['data_caixa']}  (esperado {vencimento})")
    ok = compra["data_caixa"] == vencimento and compra["data_caixa"] != hoje
    print(f"    o dinheiro sai na fatura, não na compra   {'ok' if ok else 'ERRADO'}")
    if not ok:
        falhas.append("data de caixa da compra no cartão não é o vencimento")

    # A projeção não pode debitar no dia da compra
    pontos = db.projecao_saldo(conn, 60, grupo_id=grupo)
    saldo_por_dia = {d: s for d, s, _, _ in pontos}
    antes = saldo_por_dia[hoje]
    depois = saldo_por_dia.get(vencimento)
    print(f"\n    saldo hoje       : {antes:.2f}  (esperado 10000 — nada saiu ainda)")
    print(f"    saldo no venc.   : {depois:.2f}  (esperado 7000)")
    if abs(antes - 10000) > 0.01:
        falhas.append("a projeção debitou a compra antes da fatura")
    if depois is None or abs(depois - 7000) > 0.01:
        falhas.append("a projeção não debitou a fatura no vencimento")

    conn.close()
    return falhas


if __name__ == "__main__":
    print("Ciclo de fatura:")
    problemas = executar() + caixa_vs_competencia()
    if problemas:
        print("\nFALHOU:\n  " + "\n  ".join(problemas))
    else:
        print("\nOK — cada compra cai na fatura certa, inclusive virando mês, ano e fevereiro.")
    sys.stdout.flush()
    os._exit(1 if problemas else 0)
