"""teste_importar.py — o extrato confirma, não duplica.

    python3 teste_importar.py

O risco desta funcionalidade não é falhar: é funcionar parecendo certo e
dobrar os valores. Três formas de duplicar, todas cobertas aqui:

  1. subir o mesmo extrato duas vezes
  2. criar lançamento novo para uma conta que já estava cadastrada em A Pagar
  3. criar lançamento para o pagamento da fatura, sendo que as compras
     daquela fatura já estão no sistema

Também confere que o leitor de OFX aguenta o formato SGML sem fechamento de
etiqueta, que é o que os bancos brasileiros exportam.
"""

import os
import sqlite3
import sys
import tempfile
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import database as db  # noqa: E402
import ofx  # noqa: E402


def _extrato(linhas):
    """Monta um OFX no estilo SGML, sem fechar etiquetas — como os bancos."""
    blocos = "".join(
        f"""<STMTTRN>
<TRNTYPE>{'CREDIT' if valor >= 0 else 'DEBIT'}
<DTPOSTED>{data.strftime('%Y%m%d')}120000[-3:BRT]
<TRNAMT>{valor:.2f}
<FITID>{fitid}
<MEMO>{memo}
</STMTTRN>"""
        for data, valor, memo, fitid in linhas
    )
    return f"""OFXHEADER:100
DATA:OFXSGML
<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKTRANLIST>
{blocos}
</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>""".encode("utf-8")


def _conexao_descartavel():
    caminho = os.path.join(tempfile.mkdtemp(prefix="casacapital-imp-"), "teste.db")
    conn = sqlite3.connect(caminho)
    conn.row_factory = lambda cur, row: {c[0]: row[i] for i, c in enumerate(cur.description)}
    return conn


def executar():
    conn = _conexao_descartavel()
    db.init_db(conn)
    falhas = []
    hoje = date.today()

    grupo = db.criar_grupo(conn, "Família Teste")
    conta = db.criar_conta(conn, "Banco", "banco", 10000.0, grupo_id=grupo)
    despesa = db.listar_categorias(conn, tipo="despesa", grupo_id=grupo)[0]["id"]
    receita = db.listar_categorias(conn, tipo="receita", grupo_id=grupo)[0]["id"]

    # Já cadastrado em A Pagar — o extrato vai trazer de novo
    db.criar_lancamento(conn, (hoje - timedelta(days=2)).isoformat(), conta, despesa,
                        "Aluguel", 2000.0, "saida", "pendente", 1, grupo_id=grupo)

    # Compras no cartão — o extrato vai trazer só o pagamento da fatura
    fecha, vence = (hoje + timedelta(days=3)).day, (hoje + timedelta(days=13)).day
    cartao = db.criar_cartao(conn, "Nubank", fecha, vence, 8000.0, grupo_id=grupo)
    for desc, valor in (("Mercado", 400.0), ("Farmácia", 150.0), ("Posto", 250.0)):
        db.criar_lancamento(conn, hoje.isoformat(), conta, despesa, desc, valor,
                            "saida", "pendente", 1, cartao_id=cartao, grupo_id=grupo)
    _, vencimento = db.ciclo_fatura(hoje.isoformat(), fecha, vence)

    conteudo = _extrato([
        (hoje - timedelta(days=2), -2000.00, "ALUGUEL IMOBILIARIA", "F001"),
        (vencimento, -800.00, "PAGAMENTO CARTAO NUBANK", "F002"),
        (hoje - timedelta(days=1), 5000.00, "CREDITO SALARIO", "F003"),
    ])

    # ── Leitura ──────────────────────────────────────────────────────────
    transacoes = ofx.ler(conteudo)
    print(f"Leitura do OFX: {len(transacoes)} transação(ões)")
    if len(transacoes) != 3:
        falhas.append(f"leu {len(transacoes)} transações, esperado 3")
    salario = [t for t in transacoes if t["fitid"] == "F003"][0]
    ok = salario["tipo"] == "entrada" and abs(salario["valor"] - 5000) < 0.01
    print(f"  sinal vira tipo: +5000 → {salario['tipo']} {salario['valor']:.2f}   "
          f"{'ok' if ok else 'ERRADO'}")
    if not ok:
        falhas.append("sinal do valor não virou tipo corretamente")

    # ── 1. Conta já cadastrada: propõe casar, não criar ──────────────────
    aluguel = [t for t in transacoes if t["fitid"] == "F001"][0]
    candidatos = db.candidatos_conciliacao(conn, aluguel, grupo_id=grupo, conta_id=conta)
    print(f"\n  aluguel do extrato → {len(candidatos)} candidato(s) para casar"
          f"   {'ok' if len(candidatos) == 1 else 'ERRADO'}")
    if len(candidatos) != 1:
        falhas.append("não achou o lançamento já cadastrado para casar")
    else:
        db.conciliar_lancamento(conn, candidatos[0]["id"], aluguel["fitid"],
                                aluguel["data"].isoformat())

    # ── 2. Pagamento da fatura: propõe baixar as compras ─────────────────
    pagamento = [t for t in transacoes if t["fitid"] == "F002"][0]
    faturas = db.faturas_para_conciliar(conn, pagamento, grupo_id=grupo)
    print(f"  pagamento de R$ 800 → {len(faturas)} fatura(s) correspondente(s)"
          f"   {'ok' if len(faturas) == 1 else 'ERRADO'}")
    if len(faturas) != 1:
        falhas.append("não casou o pagamento com a fatura de 3 compras")
    else:
        if len(faturas[0]["lancamento_ids"]) != 3:
            falhas.append("a fatura não agrupou as 3 compras")
        db.conciliar_fatura(conn, faturas[0]["lancamento_ids"], pagamento["fitid"])

    # ── 3. Linha sem correspondência: cria ───────────────────────────────
    candidatos_salario = db.candidatos_conciliacao(conn, salario, grupo_id=grupo, conta_id=conta)
    print(f"  salário → {len(candidatos_salario)} candidato(s) (esperado 0, é novo)"
          f"   {'ok' if not candidatos_salario else 'ERRADO'}")
    if candidatos_salario:
        falhas.append("propôs casar algo que não existia")
    db.criar_do_extrato(conn, salario, conta, receita, 1, grupo_id=grupo)

    # ── O total não pode ter dobrado ─────────────────────────────────────
    total = conn.execute("SELECT COUNT(*) n FROM lancamentos").fetchone()["n"]
    pagos = conn.execute("SELECT COUNT(*) n FROM lancamentos WHERE status='pago'").fetchone()["n"]
    saidas = conn.execute(
        "SELECT COALESCE(SUM(valor),0) s FROM lancamentos WHERE tipo='saida'").fetchone()["s"]
    print(f"\n  lançamentos no banco: {total} (esperado 5: aluguel + 3 compras + salário)")
    print(f"  pagos: {pagos} (esperado 5)")
    print(f"  soma das saídas: {saidas:.2f} (esperado 2800 — NÃO 3600)")
    if total != 5:
        falhas.append(f"{total} lançamentos, esperado 5 — algo duplicou")
    if pagos != 5:
        falhas.append(f"{pagos} pagos, esperado 5")
    if abs(saidas - 2800) > 0.01:
        falhas.append(f"saídas somam {saidas}, esperado 2800 (o pagamento da fatura duplicou)")

    # ── 4. Subir o MESMO extrato de novo não traz nada ───────────────────
    de_novo = ofx.ler(conteudo)
    ja = db.fitids_ja_importados(conn, [t["fitid"] for t in de_novo], grupo_id=grupo)
    restantes = [t for t in de_novo if t["fitid"] not in ja]
    print(f"\n  reimportando o mesmo arquivo: {len(restantes)} transação(ões) nova(s)"
          f"   {'ok' if not restantes else 'ERRADO'}")
    if restantes:
        falhas.append(f"reimportação traria {len(restantes)} duplicata(s)")

    conn.close()
    return falhas


def fatura_de_cartao():
    """Importar a FATURA: as compras entram no cartão, não como saída da conta."""
    import sqlite3, tempfile
    caminho = os.path.join(tempfile.mkdtemp(prefix="casacapital-fat-"), "teste.db")
    conn = sqlite3.connect(caminho)
    conn.row_factory = lambda cur, row: {c[0]: row[i] for i, c in enumerate(cur.description)}
    db.init_db(conn)
    falhas = []
    hoje = date.today()

    grupo = db.criar_grupo(conn, "Família Teste")
    conta = db.criar_conta(conn, "Banco", "banco", 10000.0, grupo_id=grupo)
    despesa = db.listar_categorias(conn, tipo="despesa", grupo_id=grupo)[0]["id"]
    fecha, vence = (hoje + timedelta(days=5)).day, (hoje + timedelta(days=20)).day
    cartao = db.criar_cartao(conn, "Nubank", fecha, vence, 8000.0, grupo_id=grupo)

    # Uma compra JÁ lançada na mão — a fatura vai trazer a mesma
    db.criar_lancamento(conn, hoje.isoformat(), conta, despesa, "Supermercado",
                        400.0, "saida", "pendente", 1, cartao_id=cartao, grupo_id=grupo)

    fatura = _extrato([
        (hoje, -400.00, "SUPERMERCADO EXTRA", "C1"),
        (hoje, -150.00, "DROGARIA SP", "C2"),
    ]).replace(b"BANKMSGSRSV1", b"CREDITCARDMSGSRSV1")

    print("\nFatura de cartão:")
    print(f"  reconhecida como cartão? {ofx.e_de_cartao(fatura)}   "
          f"{'ok' if ofx.e_de_cartao(fatura) else 'ERRADO'}")
    if not ofx.e_de_cartao(fatura):
        falhas.append("não reconheceu o arquivo como fatura de cartão")

    transacoes = ofx.ler(fatura)
    mercado = [t for t in transacoes if t["fitid"] == "C1"][0]
    drogaria = [t for t in transacoes if t["fitid"] == "C2"][0]

    # A compra já lançada tem de aparecer como candidata
    cand = db.candidatos_conciliacao(conn, mercado, grupo_id=grupo,
                                     conta_id=conta, cartao_id=cartao)
    print(f"  compra já lançada na mão → {len(cand)} candidato(s)   "
          f"{'ok' if len(cand) == 1 else 'ERRADO'}")
    if len(cand) != 1:
        falhas.append("não achou a compra lançada na mão — duplicaria")

    # A que não existia entra como compra do cartão, pendente
    novo_id = db.criar_do_extrato(conn, drogaria, conta, despesa, 1,
                                  grupo_id=grupo, cartao_id=cartao)
    linha = conn.execute("SELECT * FROM lancamentos WHERE id = ?", (novo_id,)).fetchone()
    ok = linha["cartao_id"] == cartao and linha["status"] == "pendente"
    print(f"  compra nova: cartao_id={linha['cartao_id']} status={linha['status']}   "
          f"{'ok' if ok else 'ERRADO'}")
    if not ok:
        falhas.append("compra da fatura não entrou vinculada ao cartão como pendente")

    # E sai do caixa no vencimento, não na data da compra
    pendentes = db.pendentes_em_caixa(conn, grupo_id=grupo)
    datas = {p["id"]: p["data_caixa"] for p in pendentes}
    _, vencimento = db.ciclo_fatura(hoje.isoformat(), fecha, vence)
    ok = datas.get(novo_id) == vencimento
    print(f"  sai do caixa em {datas.get(novo_id)} (esperado {vencimento})   "
          f"{'ok' if ok else 'ERRADO'}")
    if not ok:
        falhas.append("compra da fatura não usou a data de vencimento")

    conn.close()
    return falhas


if __name__ == "__main__":
    problemas = executar() + fatura_de_cartao()
    if problemas:
        print("\nFALHOU:\n  " + "\n  ".join(problemas))
    else:
        print("\nOK — o extrato confirmou o que existia, criou só o que faltava,")
        print("     e reimportar não duplica nada.")
    sys.stdout.flush()
    os._exit(1 if problemas else 0)
